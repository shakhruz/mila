#!/usr/bin/env bash
# UPDATE-BOOTSTRAP-2810 (часть Г): Мила клиента без навыка обновлений — текст хозяину, установка только с его «да», потом status и план работают.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR/skills/klient-svoy" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"; echo "свой навык" > "$CLAUDE_CONFIG_DIR/skills/klient-svoy/SKILL.md"
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git"
U="python3 $HERE/update.py"; I="python3 $T/rel/skills/mila-update/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
$U bootstrap-note --name "Анвар" > "$T/note.json"
chk "текст хозяину: обращение, что даст, что не тронет, кнопки «Поставить / Не сейчас», без жаргона" "grep -q 'Анвар, предлагаю поставить' $T/note.json && grep -q 'Что не тронет' $T/note.json && grep -q 'Поставить' $T/note.json && ! grep -Eqi 'nightly|apply|journal|токен' $T/note.json"
chk "первая установка навыка обновлений без «да» хозяина — отказ, навыка нет" "! $U install-skill $T/rel/skills/mila-update --from старшая >/dev/null 2>&1 && [ ! -e $CLAUDE_CONFIG_DIR/skills/mila-update ]"
$U install-skill "$T/rel/skills/mila-update" --from "старшая" --yes "Анвар · личка · 28.10 12:40 · ✅ Поставить" > "$T/i.json" 2>&1
chk "с «да» хозяина — поставлен, в журнале install-skill с его «да»" "[ -f $CLAUDE_CONFIG_DIR/skills/mila-update/update.py ] && grep -q 'Поставить' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
chk "после установки status работает из её дома (версия ещё не записана)" "$I status 2>/dev/null | grep -q 'не записана'"
$I plan --src "$T/rel" > "$T/p.txt" 2>&1
chk "и план обновления строится; её свой навык — не тронется" "grep -q 'Риск:' $T/p.txt && [ -f $CLAUDE_CONFIG_DIR/skills/klient-svoy/SKILL.md ]"
chk "переустановка уже стоящего навыка — без нового «да» (обычный путь «навык от администратора»)" "$U install-skill $T/rel/skills/mila-update --from старшая >/dev/null 2>&1"
echo "итог $ok/$n"; [ $ok -eq $n ]
