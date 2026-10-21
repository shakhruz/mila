#!/bin/bash
# get.sh: из локальной копии репо в пустой HOME — клонирует, ставит (install.sh), повторный запуск обновляет; без git — честная
# подсказка и выход 1. Без сети. bash install/test_get.sh
set -u; H="$(cd "$(dirname "$0")/.." && pwd)"; T=$(mktemp -d)
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
B=$(git -C "$H" rev-parse --abbrev-ref HEAD)
run(){ HOME=$T MILA_SKIP_CHECKS=1 MILA_REPO="$H" MILA_REF="$B" MILA_DIR="$T/mila-companion" bash "$H/install/get.sh"; }
run > $T/o1.txt 2>&1
chk "клон в ~/mila-companion и установка навыков в ~/.claude/skills" "[ -d $T/mila-companion/.git ] && [ -d $T/.claude/skills ] && ls $T/.claude/skills | grep -q mila-update"
chk "в конце — шаги «дальше» и mila doctor" "grep -q 'mila doctor' $T/o1.txt"
run > $T/o2.txt 2>&1
chk "повторный запуск — обновление, не ошибка" "grep -q 'updating' $T/o2.txt"
chk "без git — подсказка и выход 1" "! env -i HOME=$T PATH=/nonexistent /bin/bash $H/install/get.sh > $T/o3.txt 2>&1 && grep -q 'git' $T/o3.txt"
echo "итог $ok/$n"; rm -rf $T; [ $ok -eq $n ]
