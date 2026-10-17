#!/usr/bin/env bash
# пробы plain_words_check.py (проверка): запретные слова — целым словом с формами, не подстрокой
H="$(cd "$(dirname "$0")" && pwd)"; ok=0; n=0
pass() { n=$((n+1)); if python3 "$H/plain_words_check.py" "$1" >/dev/null; then ok=$((ok+1)); echo "✅ ясно: $1"; else echo "❌ ждали «ясно»: $1"; fi; }
fail() { n=$((n+1)); if ! python3 "$H/plain_words_check.py" "$1" >/dev/null; then ok=$((ok+1)); echo "✅ поймано: $1"; else echo "❌ ждали замечание: $1"; fi; }
pass "Продлить подписку?"
pass "Новый продукт?"
fail "Выложить квиз на прод?"
fail "Сколько лидов пришло?"
pass "Квиз зала: показать на экране сегодня?"
fail "Выложить квиз на прод сегодня? Решай сама"
echo "итог $ok/$n"; [ $ok = $n ]
