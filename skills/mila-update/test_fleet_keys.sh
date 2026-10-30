#!/usr/bin/env bash
# version.json, записанный с хоста (пути хоста), изнутри дома узнаётся: стоящие файлы прошлого релиза — «обновится», не «отличается».
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
$U apply --src "$T/rel" --yes "тест: база" >/dev/null 2>&1
# как будто ставили с хоста: ключи version.json — пути хоста
python3 - "$CLAUDE_CONFIG_DIR/mila-update/version.json" "$HOME" <<'PY'
import json, sys
p, home = sys.argv[1], sys.argv[2]; v = json.load(open(p))
v["files"] = {k.replace(home, "/opt/host/companion/test/home"): s for k, s in v["files"].items()}
json.dump(v, open(p, "w"))
PY
chk "ключи version.json — пути хоста (подготовка)" "grep -q '/opt/host/companion/test/home/.claude/skills' $CLAUDE_CONFIG_DIR/mila-update/version.json"
echo "# новое в релизе" >> "$T/rel/skills/visual/SKILL.md"
$U diff --src "$T/rel" --json > "$T/d.json"
chk "изнутри дома: навык прошлого релиза с новым в релизе — «обновится», не «отличается»" "python3 -c \"import json,sys;r=[x for x in json.load(open('$T/d.json'))['rows'] if x['name']=='visual'][0];sys.exit(0 if r['state']=='обновится' else 1)\""
chk "остальные стоящие — «как есть», «отличается» нет" "python3 -c \"import json,sys;rs=json.load(open('$T/d.json'))['rows'];sys.exit(0 if not any(x['state']=='отличается' for x in rs) else 1)\""
echo "моя правка" >> "$CLAUDE_CONFIG_DIR/skills/screen/SKILL.md"; echo "# и в релизе" >> "$T/rel/skills/screen/SKILL.md"
$U diff --src "$T/rel" --json > "$T/d2.json"
chk "правка хозяина поверх записанной версии — «ваша правка», не затираю" "python3 -c \"import json,sys;r=[x for x in json.load(open('$T/d2.json'))['rows'] if x['name']=='screen'][0];sys.exit(0 if r['state']=='ваша правка' else 1)\""
$U apply --src "$T/rel" --yes "тест: обновление" >/dev/null 2>&1
chk "apply обновил visual, а screen с правкой хозяина — нет" "grep -q 'новое в релизе' $CLAUDE_CONFIG_DIR/skills/visual/SKILL.md && grep -q 'моя правка' $CLAUDE_CONFIG_DIR/skills/screen/SKILL.md"
chk "после apply ключи — пути нынешнего дома (хвоста хоста нет)" "! grep -q '/opt/host/companion/test/home' $CLAUDE_CONFIG_DIR/mila-update/version.json"
echo "итог $ok/$n"; [ $ok -eq $n ]
