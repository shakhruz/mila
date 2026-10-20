#!/bin/bash
# safe_read.py: --check показывает наличие полей и маску, значений нет; открытый сейф (644) — отказ; нет сейфа — подсказка. Номер карты
# собирается в тесте. bash skills/safe-link/scripts/test_safe_read.sh
set -u; H="$(cd "$(dirname "$0")" && pwd)"; T=$(mktemp -d); export SAFE_DIR=$T; R="python3 -I $H/safe_read.py"
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
P=$(python3 -c "
import random;d=[8,6,0,0]+[random.randint(0,9) for _ in range(11)]
t=sum((x*2-9 if x*2>9 else x*2) if i%2==0 else x for i,x in enumerate(reversed(d)));print(''.join(map(str,d))+str((10-t%10)%10))")
PW="pw$RANDOM$RANDOM"
umask 077; printf "SITE_LOGIN='998901112233'\nSITE_PASSWORD='%s'\nCARD_NUMBER='%s'\nCARD_EXPIRY='0828'\n" "$PW" "$P" > $T/login.env
out=$($R login --check SITE_LOGIN,SITE_PASSWORD,CARD_NUMBER,CARD_EXPIRY)
chk "все поля есть, ok" "echo '$out' | grep -q '\"ok\": true'"
chk "маска карты ****1234 и логина 998…, значений нет" "echo '$out' | grep -q '\\*\\*\\*\\*${P: -4}' && echo '$out' | grep -q '998…' && ! echo '$out' | grep -q '$PW' && ! echo '$out' | grep -q '$P'"
chk "нет поля — в «нет»" "$R login --check API_KEY | grep -q '\"нет\": \\[\"API_KEY\"\\]'"
chmod 644 $T/login.env
chk "сейф открыт для других — отказ" "! $R login --check CARD_NUMBER"
chk "нет сейфа — подсказка попросить ссылку" "$R nosuch --check X | grep -q 'попросить ссылку сейфа'"
chk "без --check — значений не печатает (справка)" "! $R login 2>&1 | grep -q '$PW'"
echo "итог $ok/$n"; rm -rf $T; [ $ok -eq $n ]
