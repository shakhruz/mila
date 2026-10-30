#!/usr/bin/env bash
# apply пишет «до»; effect раньше 3 дней — молчит; через 4 дня — карточка «до → после»; хуже — кнопка отката; второй раз — нет.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR/projects/-w" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git"
U="python3 $HERE/update.py"; ok=0; n=0; E="$CLAUDE_CONFIG_DIR/mila-update/effect.json"
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
# журнал сессий: 7 дней до «сейчас» — по 10 ответов в день
python3 - "$CLAUDE_CONFIG_DIR/projects/-w/a.jsonl" <<'PY'
import json, sys, time
now = time.time()
with open(sys.argv[1], "w") as f:
    for d in range(7):
        for k in range(10):
            t = now - (d + 1) * 86400 + k * 600 + 60
            f.write(json.dumps({"type": "assistant", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t)),
                "message": {"usage": {"output_tokens": 100}, "content": [{"type": "tool_use", "name": "mcp__x__reply", "input": {}}]}}) + "\n")
import os   # входящие: 12 в день и до, и после — доля отвеченных до 10/12, после 4/12
ev = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(sys.argv[1]))), "channels", "telegram", "inbound"); os.makedirs(ev, exist_ok=True)
with open(os.path.join(ev, "events.jsonl"), "w") as g:
    for d in range(-8, 8):
        for k in range(12): g.write(json.dumps({"ts": int((now + d * 86400 + k * 300 + 30) * 1000)}) + "\n")
PY
$U apply --src "$T/rel" --yes "тест: хозяин нажал ✅" >/dev/null 2>&1
chk "apply записал «до»: ~10 ответов в день за 7 дней, ошибки — нет данных" "python3 -c \"import json;e=json.load(open('$E'));b=e['before'];import sys;sys.exit(0 if 9<=b['replies']<=10.1 and b['errors'] is None and e['reported'] is False else 1)\""
chk "журнал: effect_before" "grep -q effect_before $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
chk "effect сразу после — «рано», карточки нет" "$U effect | grep -q рано && [ ! -e $CLAUDE_CONFIG_DIR/mila-update/cards/effect-.json ]"
# прошло 4 дня, после — по 4 ответа в день
python3 - "$E" "$CLAUDE_CONFIG_DIR/projects/-w/b.jsonl" <<'PY'
import json, sys, time
e = json.load(open(sys.argv[1])); e["applied"] -= 4 * 86400; json.dump(e, open(sys.argv[1], "w"))
import os, calendar
a = os.path.join(os.path.dirname(sys.argv[2]), "a.jsonl")   # «до» в журнале — только до нового момента обновления
keep = [l for l in open(a) if calendar.timegm(time.strptime(json.loads(l)["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")) < e["applied"]]
open(a, "w").write("".join(keep))
with open(sys.argv[2], "w") as f:
    for d in range(4):
        for k in range(4):
            t = e["applied"] + d * 86400 + k * 600 + 60
            f.write(json.dumps({"type": "assistant", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t)),
                "message": {"content": [{"type": "tool_use", "name": "mcp__x__reply", "input": {}}]}}) + "\n")
PY
$U effect > "$T/e.json"
chk "через 4 дня: карточка «до → после», ответов стало меньше → «хуже» и кнопка «↩ Вернуть прежнюю»" "grep -q 'ответов в день' $CLAUDE_CONFIG_DIR/mila-update/cards/effect-.json && grep -q 'label.: .↩ Вернуть прежнюю' $CLAUDE_CONFIG_DIR/mila-update/cards/effect-.json && grep -q '\"worse\": true' $T/e.json"
chk "откат сам не запускался (только кнопка хозяину)" "! grep -q '\"event\": \"rollback\"' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
chk "второй раз — не отчитываюсь" "$U effect | grep -q рано"
chk "журнал: effect_after" "grep -q effect_after $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
echo "итог $ok/$n"; [ $ok -eq $n ]
