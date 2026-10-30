#!/usr/bin/env bash
# каждый хук, который install.sh прописал в settings.json, лежит файлом (иначе Stop-хук без файла = код 2 = сессия не останавливается).
set -u; unset TELEGRAM_STATE_DIR
REPO="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; mkdir -p "$T/home/.claude"
export MILA_CC_VERSION=2.1.310
OID="555""000111"   # вымышленный id владельца (tests/fixtures/fake_people.py), склейкой
HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_OWNER_ID=$OID PATH=/usr/bin:/bin:/usr/local/bin bash "$REPO/install/install.sh" >/dev/null 2>&1
ok=0; n=0; chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
miss=$(python3 - "$T/home/.claude/settings.json" <<'PY'
import json, os, sys, shlex
d = json.load(open(sys.argv[1])); miss = []
for ev, lst in d.get("hooks", {}).items():
    for e in lst:
        for h in e.get("hooks", []):
            parts = shlex.split(h.get("command", "")); f = next((p for p in parts if p.endswith((".py", ".sh", ".ts"))), None)
            if f and not os.path.isfile(f): miss.append(ev + ":" + f)
print(" ".join(miss))
PY
)
chk "все хуки из settings.json лежат файлами" "[ -z \"$miss\" ]"
chk "Stop: reply-required.py установлен" "[ -x $T/home/.claude/hooks/reply-required.py ]"
chk "PostToolUse: pd-mask.py установлен" "[ -x $T/home/.claude/hooks/pd-mask.py ]"
chk "ключ хранилища ПДн создан, 600" "python3 -c \"import os,sys; sys.exit(0 if os.stat(sys.argv[1]).st_mode & 0o777 == 0o600 else 1)\" $T/home/.config/mila/pd.key"
S="$T/home/.claude/settings.json"
chk "PreToolUse send-guard зарегистрирован и лежит файлом" "grep -q 'send-guard.py' $S && [ -x $T/home/.claude/hooks/send-guard.py ]"
chk "task-sent (PostToolUse reply) и task-open (SessionStart) зарегистрированы" "grep -q 'task-sent.py' $S && grep -q 'task-open.py' $S"
chk "OWNER_ID из MILA_OWNER_ID — в env settings.json" "python3 -c \"import json;assert json.load(open('$S'))['env']['OWNER_ID']=='$OID'\""
chk "повторная установка не дублирует хуки" "HOME=$T/home CLAUDE_CONFIG_DIR=$T/home/.claude MILA_OWNER_ID=$OID PATH=/usr/bin:/bin:/usr/local/bin bash $REPO/install/install.sh >/dev/null 2>&1; [ \$(grep -c 'send-guard.py' $S) -eq 1 ]"
# сторож отправки — с "onFailure": "block" и при установке, и у старой записи без ключа
sgok() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); h=[h for e in d['hooks']['PreToolUse'] for h in e['hooks'] if 'send-guard.py' in h['command']]; sys.exit(0 if h and all(x.get('onFailure')=='block' for x in h) else 1)" "$S"; }
chk "SG-ONFAIL: установка пишет send-guard с onFailure: block" "sgok"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); [h.pop('onFailure',None) for e in d['hooks']['PreToolUse'] for h in e['hooks']]; json.dump(d,open(sys.argv[1],'w'))" "$S"
HOME=$T/home CLAUDE_CONFIG_DIR=$T/home/.claude MILA_OWNER_ID=$OID PATH=/usr/bin:/bin:/usr/local/bin bash "$REPO/install/install.sh" >/dev/null 2>&1
chk "SG-ONFAIL: повторная установка дописывает ключ старой записи (без дубля хука)" "sgok && [ \$(grep -c 'send-guard.py' $S) -eq 1 ]"
T2="$(mktemp -d)"; mkdir -p "$T2/home/.claude"
MILA_CC_VERSION=2.1.200 HOME="$T2/home" CLAUDE_CONFIG_DIR="$T2/home/.claude" PATH=/usr/bin:/bin:/usr/local/bin bash "$REPO/install/install.sh" > "$T2/out" 2>&1
chk "SG-ONFAIL: старая CC (2.1.200) — хук сторожа есть, ключа нет, строка «пропущен»" "grep -q 'send-guard.py' $T2/home/.claude/settings.json && ! grep -q onFailure $T2/home/.claude/settings.json && grep -q 'onFailure пропущен' $T2/out"
rm -rf "$T2"
chk "шаблон settings.json без зашитого /home/companion" "! grep -q '/home/companion' $REPO/templates/home/.claude/settings.json"
[ -n "$miss" ] && echo "нет файлов: $miss"
echo "итог $ok/$n"; rm -rf "$T"
