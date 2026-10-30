#!/usr/bin/env bash
# install-skill → remove-skill (нужны --from и --yes, бэкап, журнал); навык ядра не снимается; путь с ../ — отказ.
set -u; unset TELEGRAM_STATE_DIR MILA_OUTBOX MILA_OWNER_CHAT
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"; mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
$U install-skill "$REPO/packs/clinic/clinic-booking" --from test >/dev/null
chk "навык пакета поставлен" "[ -f $CLAUDE_CONFIG_DIR/skills/clinic-booking/SKILL.md ]"
chk "без --yes не снимает" "! $U remove-skill clinic-booking --from test >/dev/null 2>&1 && [ -d $CLAUDE_CONFIG_DIR/skills/clinic-booking ]"
$U remove-skill clinic-booking --from test --yes "хозяин: сними" > "$T/r.json"
chk "с --yes снят, бэкап есть" "[ ! -e $CLAUDE_CONFIG_DIR/skills/clinic-booking ] && f=\$(python3 -c \"import json;print(json.load(open('$T/r.json'))['backup'])\") && [ -s \"\$f\" ]"
chk "в журнале remove-skill" "grep -q '\"remove-skill\"' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
chk "путь с ../ — отказ" "! $U remove-skill ../../etc --from t --yes y >/dev/null 2>&1"
mkdir -p "$CLAUDE_CONFIG_DIR/mila-update"; mkdir -p "$CLAUDE_CONFIG_DIR/skills/cards"; echo x > "$CLAUDE_CONFIG_DIR/skills/cards/SKILL.md"
python3 -c "import json;json.dump({'files':{'$CLAUDE_CONFIG_DIR/skills/cards':'x'}},open('$CLAUDE_CONFIG_DIR/mila-update/version.json','w'))"
chk "навык ядра не снимается" "! $U remove-skill cards --from t --yes y >/dev/null 2>&1 && [ -d $CLAUDE_CONFIG_DIR/skills/cards ]"
echo "итог $ok/$n"; rm -rf "$T"
