#!/usr/bin/env bash
# хук pd-mask.py — после записи в память/журналы ярлыки вместо ПДн; вне списка, код, Read, PD_MASK=0 — не трогает.
REPO="$(cd "$(dirname "$0")/.." && pwd)"
set -u; unset TELEGRAM_STATE_DIR; T=$(mktemp -d); trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; export HOME=$T/h MILA_WORK=$T/h/work CLAUDE_CONFIG_DIR=$T/h/.claude PD_KEY=$T/h/.config/mila/pd.key PD_VAULT=$T/h/work/state/pd/vault.enc
mkdir -p $MILA_WORK/memory $MILA_WORK/razvitie $CLAUDE_CONFIG_DIR/skills; cp -r $REPO/skills/pd-vault $CLAUDE_CONFIG_DIR/skills/
python3 $CLAUDE_CONFIG_DIR/skills/pd-vault/pd_vault.py init >/dev/null
H=$REPO/install/pd-mask.py; ok=0; n=0; chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
echo "Азиз: +998 90 123-45-67, почта aziz@mail.uz" > $MILA_WORK/memory/clients.md
out=$(echo "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MILA_WORK/memory/clients.md\"}}" | python3 $H)
chk "память: номер и почта → ярлыки" "! grep -q '123-45-67\|aziz@' $MILA_WORK/memory/clients.md && grep -q '⟦тел·1⟧' $MILA_WORK/memory/clients.md"
chk "Миле — заметка о ярлыках" "echo '$out' | grep -q 'заменены ярлыками'"
echo "test +998 90 111 22 33" > $MILA_WORK/razvitie/code.md
echo "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MILA_WORK/razvitie/code.md\"}}" | python3 $H >/dev/null
chk "вне списка папок — не трогаем" "grep -q '111 22 33' $MILA_WORK/razvitie/code.md"
echo 'PHONE = "+998 90 111 22 33"' > $MILA_WORK/memory/tool.py
echo "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$MILA_WORK/memory/tool.py\"}}" | python3 $H >/dev/null
chk "код (.py) — не трогаем" "grep -q '111 22 33' $MILA_WORK/memory/tool.py"
echo "+998 90 555 66 77" > $MILA_WORK/NOW.md
PD_MASK=0 bash -c "echo '{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MILA_WORK/NOW.md\"}}' | python3 $H" >/dev/null
chk "PD_MASK=0 — выключено" "grep -q '555 66 77' $MILA_WORK/NOW.md"
echo "{\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"$MILA_WORK/NOW.md\"}}" | python3 $H >/dev/null
chk "Read — не трогаем" "grep -q '555 66 77' $MILA_WORK/NOW.md"
echo "битый вход" | python3 $H; chk "битый вход — молча, код 0" "[ \$? -eq 0 ]"
echo "итог $ok/$n"; rm -rf $T
