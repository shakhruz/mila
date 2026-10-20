#!/bin/bash
# hooks_sync.py: живая Мила без хуков mila-tasks → добавлены PostToolUse(reply) task-sent и SessionStart task-open; повтор — без изменений;
# чужие хуки целы; бэкап есть; без навыка — честный отказ. bash tools/test_hooks_sync.sh
set -u; H="$(cd "$(dirname "$0")" && pwd)"; T=$(mktemp -d); S="python3 -I $H/hooks_sync.py --home $T"
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
mkdir -p $T/.claude
chk "без навыка mila-tasks — отказ с подсказкой" "! $S"
mkdir -p $T/.claude/skills/mila-tasks/hooks; touch $T/.claude/skills/mila-tasks/hooks/task-sent.py $T/.claude/skills/mila-tasks/hooks/task-open.py
cat > $T/.claude/settings.json <<'J'
{"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "python3 x/session-start.py"}]}], "PreToolUse": [{"matcher": "reply", "hooks": [{"type": "command", "command": "python3 x/send-guard.py"}]}], "Stop": [{"hooks": [{"type": "command", "command": "python3 x/reply-required.py"}]}]}, "env": {"OWNER_ID": "1"}}
J
$S > /dev/null
chk "добавлены оба хука" "grep -q 'task-sent' $T/.claude/settings.json && grep -q 'task-open' $T/.claude/settings.json"
chk "PostToolUse — на reply" "python3 -c \"import json;d=json.load(open('$T/.claude/settings.json'));assert any('telegram_telegram__reply' in x.get('matcher','') for x in d['hooks']['PostToolUse'])\""
chk "чужие хуки и env целы" "python3 -c \"import json;d=json.load(open('$T/.claude/settings.json'));assert 'send-guard' in json.dumps(d['hooks']['PreToolUse']) and 'reply-required' in json.dumps(d['hooks']['Stop']) and d['env']['OWNER_ID']=='1' and 'session-start' in json.dumps(d['hooks']['SessionStart'])\""
chk "бэкап settings.json есть" "ls $T/.claude/settings.json.bak-* "
chk "повтор — ничего не добавляет" "$S | grep -q '\"added\": \[\]'"
echo "итог $ok/$n"; rm -rf $T; [ $ok -eq $n ]
