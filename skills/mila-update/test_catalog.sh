#!/usr/bin/env bash
# КАТАЛОГ-НАВЫКОВ-2810: update.py catalog — навыки каталога, которых у меня нет; «нет» хозяина — больше не предлагаю, «позже» — через 4 недели; карточка с ценой только из каталога.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$(mktemp -d)"; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"; unset MILA_CATALOG_URL
mkdir -p "$CLAUDE_CONFIG_DIR/skills/aaa" "$CLAUDE_CONFIG_DIR/skills/bbb" "$CLAUDE_CONFIG_DIR/skills/ccc.bak-1" "$MILA_WORK"
cat > "$T/catalog.json" <<'J'
{"version": "2026-10-28", "skills": [
 {"name": "aaa", "who": "хозяин", "price": "бесплатно", "gives": "Уже стоит"},
 {"name": "ccc", "who": "хозяин", "price": "бесплатно", "gives": "Письма от вашего имени."},
 {"name": "ddd", "who": "оператор", "price": "бесплатно", "gives": "Ведёт гостя"},
 {"name": "eee", "who": "хозяин", "price": "генерации платные", "gives": "Подкаст двумя голосами"},
 {"name": "fff", "who": "хозяин", "price": "120 000 сум", "gives": "Сайт под ключ"},
 {"name": "ggg", "who": "хозяин", "gives": "Без цены"},
 {"name": "hhh", "who": "наша Мила", "price": "бесплатно", "gives": "Служебное"}, "мусор"]}
J
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
names() { python3 -c "import json,sys;print(','.join(r['name'] for r in json.load(sys.stdin)['new']))"; }
chk "адрес по умолчанию — каталог milagpt.io/navyki (без сети не хожу: только строка в коде)" "grep -q '^DEFAULT_CATALOG = \"https://milagpt.io/navyki/catalog.json\"' $HERE/update.py"
$U config --set catalog_url= >/dev/null
chk "catalog_url пустой — каталог выключен, понятный отказ, не трасса" "$U catalog 2>&1 | grep -q 'адрес каталога не задан'"
$U config --set catalog_url="$T/catalog.json" >/dev/null
chk "без стоящих (aaa), без служебных и операторских, «ccc.bak-1» — не стоящий ccc" "[ \"\$($U catalog | names)\" = 'ccc,eee,fff,ggg' ]"
chk "--who оператор — только операторские" "[ \"\$($U catalog --who оператор | names)\" = 'ddd' ]"
$U catalog --offered ccc --answer later >/dev/null
chk "«позже» — ccc сейчас не предлагаю" "[ \"\$($U catalog | names)\" = 'eee,fff,ggg' ]"
$U catalog --offered fff >/dev/null
chk "карточка ушла, ответа нет — fff тоже не повторяю" "[ \"\$($U catalog | names)\" = 'eee,ggg' ]"
$U catalog --offered eee --answer no >/dev/null
python3 - "$CLAUDE_CONFIG_DIR/mila-update/journal.jsonl" <<'PY'
import json, sys
p = sys.argv[1]; rs = [json.loads(l) for l in open(p)]
for r in rs:
    if r.get("event") == "offered": r["t"] -= 29 * 86400
open(p, "w").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rs))
PY
chk "через 29 дней: «позже» и без ответа — снова в списке, «нет» — никогда" "[ \"\$($U catalog | names)\" = 'ccc,fff,ggg' ]"
chk "карточка: бесплатно" "$U catalog --card ccc | grep -q '^Могу научиться: ccc — Письма от вашего имени. Бесплатно.$'"
chk "карточка: платные генерации — «по вашему «да» на расход»" "$U catalog --card eee | grep -q 'по вашему «да» на расход'"
chk "карточка: цена — только из каталога; нет цены — «Цену уточню.»" "$U catalog --card fff | grep -q 'Цена: 120 000 сум.' && $U catalog --card ggg | grep -q 'Цену уточню.'"
chk "кнопки карточки" "$U catalog --card ccc | grep -q '^\[✅ Хочу\] \[Позже\]$'"
chk "ответ не из want/later/no — отказ" "! $U catalog --offered ccc --answer может >/dev/null 2>&1"
chk "каталог недоступен (нет файла / сеть) — строка, код ≠ 0" "! MILA_CATALOG_URL=$T/nope.json $U catalog >$T/e 2>&1 && grep -q 'каталог недоступен' $T/e && ! MILA_CATALOG_URL=http://127.0.0.1:9/c.json $U catalog >$T/e2 2>&1 && grep -q 'каталог недоступен' $T/e2"
echo '{"skills": "нет"}' > "$T/bad.json"
chk "битый каталог (skills не список) — «недоступен», не трасса" "MILA_CATALOG_URL=$T/bad.json $U catalog 2>&1 | grep -q 'каталог недоступен'"
echo "итог $ok/$n"; [ $ok -eq $n ]
