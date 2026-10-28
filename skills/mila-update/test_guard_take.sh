#!/usr/bin/env bash
# GUARD-TAKE-2810 (Качество 17:27): сторож отправки, поставленный не обновлением и отличный от ядра, mila-update сам не обновит —
# план говорит об этом отдельной строкой и советует заменить; apply без --take его не трогает, с --take — заменяет.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
$U apply --src "$T/rel" --yes "тест: база" >/dev/null 2>&1
G="$CLAUDE_CONFIG_DIR/hooks/send-guard.py"
python3 - "$CLAUDE_CONFIG_DIR/mila-update/version.json" "$G" <<'PY'
import json, sys
p, g = sys.argv[1], sys.argv[2]; v = json.load(open(p)); v["files"].pop(g, None); json.dump(v, open(p, "w"))
open(g, "a").write("# старый сторож, поставленный руками\n")
PY
chk "подготовка: сторож стоит и в version.json его нет" "[ -f $G ] && ! grep -q 'hooks/send-guard.py' $CLAUDE_CONFIG_DIR/mila-update/version.json"
$U plan --src "$T/rel" > "$T/p.txt"; $U plan --src "$T/rel" --json > "$T/p.json"
chk "план: отдельная строка «Сторож отправки … советую заменить»" "grep -q '^Сторож отправки у вас отличается от ядра и ставился не обновлением — советую заменить' $T/p.txt"
chk "план --json: recommend_take = [send-guard.py]" "python3 -c \"import json,sys; sys.exit(0 if json.load(open('$T/p.json'))['recommend_take'] == ['send-guard.py'] else 1)\""
chk "строка совета — до строки риска, текст ≤ 900" "python3 -c \"import sys; t=open('$T/p.txt').read(); sys.exit(0 if t.index('Сторож отправки') < t.index('Риск:') and len(t.rstrip()) <= 900 else 1)\""
$U apply --src "$T/rel" --yes "тест: без take" >/dev/null 2>&1
chk "apply без --take сторожа не трогает" "grep -q 'старый сторож' $G"
$U apply --src "$T/rel" --yes "тест: с take" --take send-guard.py >/dev/null 2>&1
chk "apply --take send-guard.py — сторож как в ядре, план совет больше не даёт" "cmp -s $G $T/rel/templates/home/.claude/hooks/send-guard.py && ! $U plan --src $T/rel | grep -q 'Сторож отправки'"
C="$MILA_WORK/CONSTITUTION.md"
python3 - "$CLAUDE_CONFIG_DIR/mila-update/version.json" "$C" <<'PY'
import json, sys
p, c = sys.argv[1], sys.argv[2]; v = json.load(open(p)); v["files"].pop(c, None); json.dump(v, open(p, "w"))
open(c, "a").write("\n4. Закон 4 в редакции владельца, новее ядра.\n")
PY
$U plan --src "$T/rel" --json > "$T/p4.json"
chk "конституция «отличается» (может быть новее ядра) — совета заменить нет, recommend_take её не содержит" "python3 -c \"import json,sys; d=json.load(open('$T/p4.json')); sys.exit(0 if 'CONSTITUTION.md' not in d['recommend_take'] and 'CONSTITUTION.md' in d['keep'].get('отличается', []) else 1)\" && ! $U plan --src $T/rel | grep -qi 'конституция у вас отличается'"
echo "итог $ok/$n"; [ $ok -eq $n ]
