#!/usr/bin/env bash
# mila-update на чистом доме (аудит 21.10): пустой HOME, только знакомство пройдено → apply из локальной копии релиза → версия =
# release.json, навыки и хуки на месте → rollback возвращает «до». Ничего вне временной папки. bash skills/mila-update/test_clean_home.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git"
V=$(python3 -c "import json;print(json.load(open('$REPO/release.json'))['version'])")
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
chk "чистый дом: status без версии" "! $U status | grep -q '$V'"
$U apply --src "$T/rel" --yes "тест чистого дома" > "$T/a.json" 2>&1
chk "apply на чистом доме — версия $V" "$U status | grep -q '$V'"
chk "навыки ядра и хуки поставлены (mila-update, send-guard)" "[ -f $CLAUDE_CONFIG_DIR/skills/mila-update/SKILL.md ] && [ -f $CLAUDE_CONFIG_DIR/hooks/send-guard.py ]"
chk "конституция в work" "[ -f $MILA_WORK/CONSTITUTION.md ]"
$U rollback > "$T/r.json" 2>&1
chk "rollback — навыка из релиза больше нет, версия снова не записана" "[ ! -f $CLAUDE_CONFIG_DIR/skills/mila-update/SKILL.md ] && $U status | python3 -c \"import json,sys;assert json.load(sys.stdin)['version']!='$V'\""
echo "итог $ok/$n"; rm -rf "$T"; [ $ok -eq $n ]
