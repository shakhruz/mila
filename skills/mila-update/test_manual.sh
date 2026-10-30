#!/usr/bin/env bash
# ручная вставка — только с записью (что, почему, кто); status видит; план говорит «заменит / сохранит».
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
$U apply --src "$T/rel" --yes "тест: база" >/dev/null 2>&1
chk "без причины или автора — понятный отказ «без причины и автора», в журнал не пишется" "$U manual --what $CLAUDE_CONFIG_DIR/skills/visual --by admin 2>&1 | grep -q 'без причины и автора' && $U manual --what $CLAUDE_CONFIG_DIR/skills/visual --why x 2>&1 | grep -q 'без причины и автора' && ! grep -q '\"manual\"' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
chk "путь вне дома — отказ" "! $U manual --what /etc/passwd --why x --by admin >/dev/null 2>&1"
echo "# аварийная правка" >> "$CLAUDE_CONFIG_DIR/skills/visual/SKILL.md"
echo "# аварийная правка 2" >> "$CLAUDE_CONFIG_DIR/skills/screen/SKILL.md"
$U manual --what "$CLAUDE_CONFIG_DIR/skills/visual/SKILL.md,$CLAUDE_CONFIG_DIR/skills/screen" --why "авария 28.10: мост падал" --by "администратор" > "$T/m.json"
chk "ручная вставка записана: событие manual, кто, почему, sha" "grep -q '\"event\": \"manual\"' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl && grep -q 'мост падал' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl && grep -q '\"sha\"' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
$U status > "$T/s.json"
chk "status: ручных вставок с последнего обновления — 1, видно кто и почему" "grep -q '\"manual_since_update\": 1' $T/s.json && grep -q 'администратор' $T/s.json"
echo "# новая строка релиза" >> "$T/rel/skills/screen/SKILL.md"
$U plan --src "$T/rel" > "$T/p.txt"; $U plan --src "$T/rel" --json > "$T/p.json"
chk "план: ручные правки — «сохранятся» (хозяин/админ правил навык — не затираю) по обоим путям" "grep -q 'Ручные правки администратора сохранятся' $T/p.txt && grep -q 'skills/visual' $T/p.json && grep -q 'skills/screen' $T/p.json"
# админ поставил ровно то, что потом придёт в релизе → для mila-update это «наша версия» → обновится и заменит
cp "$CLAUDE_CONFIG_DIR/skills/visual/SKILL.md" "$T/vis.md"; cp "$T/rel/skills/visual/SKILL.md" "$CLAUDE_CONFIG_DIR/skills/visual/SKILL.md"
python3 -c "
import json,sys; sys.path.insert(0,'$HERE'); import update as u
v=u.load_version(); v['files'][u.os.path.realpath('$CLAUDE_CONFIG_DIR/skills/visual')]=u.sha('$CLAUDE_CONFIG_DIR/skills/visual'); json.dump(v,open(u.VERSION,'w'))"
echo "# релиз меняет visual" >> "$T/rel/skills/visual/SKILL.md"
$U plan --src "$T/rel" --json > "$T/p2.json"
chk "ручная вставка в папку, которую обновление заменит → «заменит»" "python3 -c \"import json,sys;d=json.load(open('$T/p2.json'));sys.exit(0 if any('visual' in x for x in d['manual']['zatryot']) else 1)\""
$U apply --src "$T/rel" --yes "тест: обновление" >/dev/null 2>&1
$U status > "$T/s2.json"
chk "после обновления счёт ручных вставок — с нуля" "grep -q '\"manual_since_update\": 0' $T/s2.json"
echo "итог $ok/$n"; [ $ok -eq $n ]
