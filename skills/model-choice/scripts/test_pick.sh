#!/bin/bash
# pick.py: два варианта с ценой за работу и рекомендацией; --x масштабирует цену; --best меняет рекомендацию и порядок кнопок;
# каждая задача каталога считается; нет задачи — справка. Без сети (без --live). bash skills/model-choice/scripts/test_pick.sh
set -u; H="$(cd "$(dirname "$0")" && pwd)"; R="python3 -I $H/pick.py"
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
J=$($R image --x 10)
chk "картинки ×10: недорого \$0.03, лучшее \$1.50" "echo '$J' | python3 -c \"import json,sys;d=json.load(sys.stdin);o={x['key']:x['usd'] for x in d['options']};assert abs(o['cheap']-0.03)<1e-6 and abs(o['best']-1.5)<1e-6,o\""
chk "рекомендация по умолчанию — недорого, первая кнопка зелёная" "echo '$J' | python3 -c \"import json,sys;d=json.load(sys.stdin);b=d['buttons'][0];assert d['recommend']=='cheap' and b[0]['label'].startswith('Недорого') and b[0]['style']=='success'\""
chk "--best: рекомендация — лучшее качество, первой кнопкой" "$R video --best | python3 -c \"import json,sys;d=json.load(sys.stdin);assert d['recommend']=='best' and d['buttons'][0][0]['label'].startswith('Лучшее')\""
chk "все задачи каталога считаются" "for t in text analysis translate image video voice transcribe; do $R \$t >/dev/null || exit 1; done"
chk "в карточке названия моделей и дата цен" "$R voice | python3 -c \"import json,sys;d=json.load(sys.stdin);c=d['card_text'];assert 'ElevenLabs' in c and 'Цены: на' in c\""
chk "нет такой задачи — справка, не ошибка расчёта" "! $R pizza"
echo "итог $ok/$n"; [ $ok -eq $n ]
