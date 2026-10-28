#!/usr/bin/env bash
# UPDATE-PLAN-2810 (владелец 37034): читаемый план обновления — что получит (все версии между), что изменится, что не тронется, риск.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; echo "   $(head -c 400 $T/p.txt 2>/dev/null)"; fi; }
$U plan --src "$T/rel" > "$T/p0.txt"
chk "план «с нуля» (все зоны новые) — в тексте ≥ 2 строк «Что получите», ≤ 900, риск на месте" "[ \$(sed -n '/^Что получите:/,/^Что изменится/p' $T/p0.txt | grep -c '^· ') -ge 2 ] && python3 -c \"import sys; sys.exit(len(open('$T/p0.txt').read().rstrip('\\\\n')) > 900)\" && grep -q '^Риск:' $T/p0.txt"
$U apply --src "$T/rel" --yes "тест: база" >/dev/null 2>&1
# стоящая версия — v1.5.1: «что получите» должно собрать строки v1.5.2 и v1.5.3, не только последней
python3 - "$CLAUDE_CONFIG_DIR/mila-update/version.json" <<'PY'
import json, sys; p = sys.argv[1]; d = json.load(open(p)); d["tag"] = "v1.5.1"; json.dump(d, open(p, "w"))
PY
$U plan --src "$T/rel" > "$T/p.txt"; $U plan --src "$T/rel" --json > "$T/p.json"
chk "ничего не меняется → «Что изменится: ничего», риск «нет»" "grep -q 'Что изменится: ничего' $T/p.txt && grep -q '\"risk\": \"нет\"' $T/p.json"
chk "«Что получите» — по-русски из «Для хозяина» нескольких версий новее v1.5.1 (≥ 4 строк из ≥ 2 версий), без v1.5.1" "python3 -c \"
import json,sys,re; d=json.load(open('$T/p.json')); g=' '.join(d['get'])
sys.exit(0 if len(d['get']) >= 4 and len(d['get_versions']) >= 2 and 'v1.5.1' not in d['get_versions'] and 'Сейф' not in g and not re.search(r'[A-Za-z]{4,}', g) else 1)\""
chk "первая строка «Что получите» в тексте — из «Для хозяина» выпуска x.y.0 (v1.6.0, суть строки), а не из свежего патча" "python3 -c \"
import re,sys; c=open('$T/rel/CHANGELOG.md').read(); sec=re.split(r'^## ', c, flags=re.M); v=[s for s in sec if re.match(r'v1\\.6\\.0 ', s)][0]
own=v.split('**Для хозяина**')[1].split('**')[0]; L=[l[2:].strip().replace('\\x60','') for l in own.splitlines() if l.startswith('- ')]
first=open('$T/p.txt').read().split('Что получите:')[1].strip().splitlines()[0][2:].strip()
f=first.rstrip('.…'); sys.exit(0 if L and any(x.startswith(f) for x in L) else 1)\""
chk "в 900 знаков — строки пользы не меньше чем 3 версий (Качество 19:10), каждая ≤ 90" "python3 -c \"
import json,sys; t=open('$T/p.txt').read(); d=json.load(open('$T/p.json')); g=t.split('Что получите:')[1].split('Что изменится')[0]
L=[l[2:] for l in g.strip().splitlines() if l.startswith('· ')]; vs={v for v,l in zip(d['get_order'], d['get']) if l in L}
sys.exit(0 if len(vs) >= 3 and all(len(l) <= 90 for l in L) else 1)\""
chk "текст ≤ 900 знаков, есть «Не тронется» и «Отменить можно»" "python3 -c \"import sys; sys.exit(len(open('$T/p.txt').read().rstrip('\\\\n')) > 900)\" && grep -q 'Не тронется' $T/p.txt && grep -q 'Отменить можно' $T/p.txt"
echo "новая строка текста" >> "$T/rel/skills/visual/SKILL.md"
$U plan --src "$T/rel" --json > "$T/p.json"; $U plan --src "$T/rel" > "$T/p.txt"
chk "поменялся только текст навыка → риск низкий, в «изменится» — visual" "grep -q '\"risk\": \"низкий\"' $T/p.json && grep -q 'visual' $T/p.txt"
f=$(ls $T/rel/skills/visual/scripts/*.py 2>/dev/null | head -1); [ -z "$f" ] && { mkdir -p $T/rel/skills/visual/scripts; f=$T/rel/skills/visual/scripts/x.py; }
echo "# правка кода" >> "$f"
$U plan --src "$T/rel" --json > "$T/p.json"
chk "поменялся код навыка → риск средний" "grep -q '\"risk\": \"средний\"' $T/p.json"
h=$(ls $T/rel/install/*.py | grep -v '/test_' | head -1); echo "# правка хука" >> "$h"
$U plan --src "$T/rel" --json > "$T/p.json"
chk "поменялся хук → риск высокий, имя хука в причине" "grep -q '\"risk\": \"высокий\"' $T/p.json && grep -q \"\$(basename $h)\" $T/p.json"
echo "моя правка" >> "$CLAUDE_CONFIG_DIR/skills/visual/SKILL.md"
$U plan --src "$T/rel" > "$T/p.txt"
chk "хозяин правил навык → «ваши правки в 1 месте сохранятся» числом, без имени латиницей; не в «изменится»" "grep 'Не тронется' $T/p.txt | grep -q 'ваши правки в 1 месте сохранятся' && ! grep 'Не тронется' $T/p.txt | grep -q visual && ! grep 'навыки ядра' $T/p.txt | grep -q '(visual'"
chk "plan ничего не пишет: дом не изменился" "grep -q 'моя правка' $CLAUDE_CONFIG_DIR/skills/visual/SKILL.md && ! grep -q 'правка хука' $CLAUDE_CONFIG_DIR/hooks/\$(basename $h)"
python3 - "$T/rel/CHANGELOG.md" <<'PY'
import sys; p = sys.argv[1]; t = open(p).read(); h = "## v1.5.3 "
i = t.index(h); j = t.index("\n", i) + 1
open(p, "w").write(t[:j] + "**For the owner**\n- English owner line goes first here\n\n" + t[j:])
PY
$U plan --src "$T/rel" --json > "$T/p3.json"
chk "в версии оба блока, английский первым — беру русский «Для хозяина» (по всем строкам, до обрезки до 6)" "! grep -q 'English owner line' $T/p3.json && python3 -c \"
import sys; sys.path.insert(0, '$HERE'); import update as U; g=[l for v, l in U.changelog_since('$T/rel', 'v1.5.1', None) if v == 'v1.5.3']
sys.exit(0 if any('Пульт дня' in l for l in g) and not any('English owner' in l for l in g) else 1)\""
sed -i 's/^\*\*Для хозяина\*\*$/**For the owner**/' "$T/rel/CHANGELOG.md"
$U plan --src "$T/rel" --json > "$T/p2.json"
chk "версия без русского блока «Для хозяина» — строка без английского текста" "grep -q 'описания для хозяина в этой версии нет' $T/p2.json && ! grep -q 'day board' $T/p2.json"
echo "новая статья" >> "$T/rel/CONSTITUTION.md"; rm -f "$f"; cp "$T/rel/install/$(basename $h)" /dev/null
git -C "$REPO" show HEAD:install/$(basename $h) > "$T/rel/install/$(basename $h)" 2>/dev/null || true
$U plan --src "$T/rel" > "$T/p.txt"; $U plan --src "$T/rel" --json > "$T/p.json"
chk "меняется конституция → отдельная строка «прочитайте» и риск не ниже среднего" "grep -q 'Меняется конституция' $T/p.txt && grep -q '\"risk\": \"средний\"' $T/p.json"
python3 -c "
import json;p='$T/rel/release.json';d=json.load(open(p));d['migrations']=['x'];json.dump(d,open(p,'w'))"
$U plan --src "$T/rel" --json > "$T/p.json"
chk "только migrations — высокий, причина без пустого хвоста" "grep -q 'миграция настроек' $T/p.json && ! grep -q 'настройки: \"' $T/p.json"
echo "итог $ok/$n"
