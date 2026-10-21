#!/bin/bash
# get.sh: из локальной копии репо в пустой HOME — клонирует, ставит (install.sh), повторный запуск обновляет; без git — честная
# подсказка и выход 1. Без сети. bash install/test_get.sh
set -u; H="$(cd "$(dirname "$0")/.." && pwd)"; T=$(mktemp -d)
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
# Источник — копия репо с веткой на текущем коммите: так тест работает и в detached HEAD (CI, проверка Качества),
# где rev-parse --abbrev-ref даёт «HEAD» и git clone --branch HEAD падает.
SRC=$T/src; git clone -q "$H" "$SRC"; git -C "$SRC" checkout -q -B mila-test "$(git -C "$H" rev-parse HEAD)"; B=mila-test
run(){ HOME=$T MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" bash "$H/install/get.sh"; }   # без MILA_DIR — папка по умолчанию
run > $T/o1.txt 2>&1
chk "клон в ~/mila (по умолчанию) и установка навыков в ~/.claude/skills" "[ -d $T/mila/.git ] && [ -d $T/.claude/skills ] && ls $T/.claude/skills | grep -q mila-update"
chk "в конце — шаги «дальше» и mila doctor" "grep -q 'mila doctor' $T/o1.txt"
run > $T/o2.txt 2>&1
chk "повторный запуск — обновление, не ошибка" "grep -q 'updating' $T/o2.txt"
chk "без git — подсказка и выход 1" "! env -i HOME=$T PATH=/nonexistent /bin/bash $H/install/get.sh > $T/o3.txt 2>&1 && grep -q 'git' $T/o3.txt"
R2=$T/rel2; git clone -q "$H" $R2; git -C $R2 tag v9.9.9 >/dev/null 2>&1; git -C $R2 tag v10.0.0-rc1 >/dev/null 2>&1
HOME=$T MILA_SKIP_CHECKS=1 MILA_REPO="$R2" MILA_DIR="$T/m2" bash "$H/install/get.sh" > $T/o4.txt 2>&1
chk "без MILA_REF — последний стабильный тег (v9.9.9, не rc)" "grep -q 'version: v9.9.9' $T/o4.txt && [ -d $T/m2/.git ]"
T3=$(mktemp -d); git clone -q "$SRC" "$T3/mila-companion"   # старая установка до переименования
HOME=$T3 MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" bash "$H/install/get.sh" > $T/o5.txt 2>&1
chk "старая ~/mila-companion обновляется на месте, вторую папку ~/mila не заводит" "grep -q 'updating $T3/mila-companion' $T/o5.txt && [ ! -d $T3/mila ]"; rm -rf $T3
T4=$(mktemp -d); mkdir -p "$T4/mila"; git -C "$T4/mila" init -q; echo x > "$T4/mila/notes.txt"; git -C "$T4/mila" add -A; git -C "$T4/mila" -c user.email=a@b -c user.name=a commit -qm x
HOME=$T4 MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" bash "$H/install/get.sh" > $T/o6.txt 2>&1; rc=$?
chk "~/mila — чужой git-проект: честный отказ, выход 1, проект не тронут" "[ $rc -eq 1 ] && grep -q 'already used' $T/o6.txt && [ -f $T4/mila/notes.txt ] && [ ! -d $T4/mila/skills ] && [ \$(git -C $T4/mila log --oneline | wc -l) -eq 1 ]"; rm -rf $T4
echo "итог $ok/$n"; rm -rf $T; [ $ok -eq $n ]
