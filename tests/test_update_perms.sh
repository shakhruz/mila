#!/usr/bin/env bash
# PERMS-1022: apply оставляет записанное читаемым (файлы go+r, каталоги go+rx) — иначе суточная копия дома падает
# (Permission denied на ~/.claude/mila-update/new/<тег>/было-*). Журнал и бэкапы не открывает. Песочница, без сети.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"
export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
U="python3 $REPO/skills/mila-update/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git"
umask 077   # строгий umask, как у Мил в контейнерах
$U apply --src "$T/rel" --yes "тест: база" >/dev/null 2>&1
# правка хозяина в навыке ядра + новая версия навыка в релизе → копия релиза ляжет в new/<тег>/
echo "моя правка" >> "$CLAUDE_CONFIG_DIR/skills/visual/SKILL.md"; chmod 600 "$CLAUDE_CONFIG_DIR/skills/visual/SKILL.md"
echo "# v2" >> "$T/rel/skills/visual/SKILL.md"; chmod -R go-rwx "$T/rel/skills/visual"
python3 - "$T/rel/release.json" <<'PY'
import json, sys; p = sys.argv[1]; d = json.load(open(p)); d["version"], d["tag"] = "9.9.9", "v9.9.9"; json.dump(d, open(p, "w"), ensure_ascii=False, indent=2)
PY
$U apply --src "$T/rel" --yes "тест: v9.9.9" > "$T/a.json" 2>&1
NEW="$CLAUDE_CONFIG_DIR/mila-update/new/v9.9.9"
chk "копия релиза рядом с правкой хозяина лежит в new/<тег>/" "[ -f $NEW/visual/SKILL.md ]"
bad_f=$(find "$NEW" -type f ! -perm -044 | wc -l); bad_d=$(find "$NEW" "$CLAUDE_CONFIG_DIR/mila-update/new" -type d ! -perm -055 | wc -l)
chk "new/<тег>: все файлы go+r, все каталоги go+rx (было 600/700 при umask 077)" "[ $bad_f -eq 0 ] && [ $bad_d -eq 0 ]"
chk "каталог mila-update проходим для копии (go+rx)" "[ -n \"\$(find $CLAUDE_CONFIG_DIR/mila-update -maxdepth 0 -perm -055)\" ]"
chk "журнал и бэкапы не открыты (go без чтения)" "[ -z \"\$(find $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl $CLAUDE_CONFIG_DIR/mila-update/backups -maxdepth 1 -type f -perm /044)\" ]"
chk "правка хозяина в самом навыке — на месте" "grep -q 'моя правка' $CLAUDE_CONFIG_DIR/skills/visual/SKILL.md"
echo "итог $ok/$n"; rm -rf "$T"; [ $ok -eq $n ]
