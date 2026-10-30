#!/usr/bin/env bash
# тест nightly / dry-run / yanked / rollback на фальшивом репо с тегами во временной папке (сети нет)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$(mktemp -d)"; trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
unset TELEGRAM_STATE_DIR MILA_OUTBOX MILA_OWNER_CHAT   # тест не трогает настоящую очередь отправки (17.10: карточки ушли в outbox сессии)
export GIT_CONFIG_GLOBAL="$T/gitconfig" GIT_CONFIG_SYSTEM=/dev/null
git config --global user.email t@t; git config --global user.name t; git config --global init.defaultBranch main
mkdir -p "$CLAUDE_CONFIG_DIR/skills/moy-lichny" "$MILA_WORK/state" "$MILA_WORK/memory"
echo "мой" > "$CLAUDE_CONFIG_DIR/skills/moy-lichny/SKILL.md"; echo "NOW" > "$MILA_WORK/NOW.md"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
echo '[{"cron":"x"}]' > "$MILA_WORK/state/crons.json"
R="$T/core"; mkdir -p "$R/skills/demo"; cd "$R"
manifest() { # $1 версия, $2 health-команда JSON или пусто
  printf '{"version":"%s","tag":"v%s","zones":[{"what":"навыки","src":"skills/*","dst":"{claude}/skills/*","kind":"dir"}]%s}\n' "$1" "$1" "${2:+,\"health\":$2}" > release.json; }
skill() { printf -- '---\nname: demo\ndescription: "демо %s"\n---\n# demo %s\n' "$1" "$1" > skills/demo/SKILL.md; }
rel() { git add -A; git commit -qm "$1"; git tag "$2"; }
printf '# CHANGELOG\n\n## v1.0.0\n- старое\n\n' > CHANGELOG.md
manifest 1.0.0; skill 1.0.0; git init -q; rel r1 v1.0.0
printf '# CHANGELOG\n\n## v1.1.0 · свежее\n**Для хозяина**\n- Я быстрее разбираю входящие\n- Карточки понятнее\n**Для Мил**\n- технически: hook\n\n## v1.0.0\n- старое\n' > CHANGELOG.md
manifest 1.1.0; skill 1.1.0; rel r2 v1.1.0
manifest 1.2.0; skill 1.2.0; echo '["v1.2.0"]' > yanked.json; rel r3 v1.2.0       # отозван
manifest 1.3.0; skill 1.3.0; rel r4 v1.3.0-rc1                                      # rc в stable не идёт
export MILA_CORE_REPO="$R"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
J="$CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"; V="$CLAUDE_CONFIG_DIR/mila-update/version.json"
# ставим v1.0.0 как стартовую версию (git-тег + apply с «да»)
git checkout -q v1.0.0 2>/dev/null; $U apply --src "$R" --yes "тест: старт" >/dev/null; git checkout -q main
chk "старт: demo 1.0.0, версия 1.0.0" "grep -q 'demo 1.0.0' $CLAUDE_CONFIG_DIR/skills/demo/SKILL.md && grep -q '\"1.0.0\"' $V"
chk "конфиг по умолчанию: stable, auto=false, публичный репо" "$U config | grep -q '\"auto\": false' && $U config | grep -q github.com/shakhruz/mila-agent"
chk "config --set: неверное значение — отказ" "! $U config --set channel=zzz >/dev/null 2>&1"
$U check > "$T/c.json"
chk "check: yanked и -rc не предлагаются, newer = v1.1.0" "python3 -c \"import json,sys; d=json.load(open('$T/c.json')); sys.exit(0 if d['newer']==['v1.1.0'] and 'v1.2.0' in d['yanked'] else 1)\""
# dry-run
$U nightly --dry-run > "$T/n1.json"
chk "dry-run: показывает v1.1.0, ничего не записано" "grep -q 'dry-run' $T/n1.json && grep -q v1.1.0 $T/n1.json && grep -q 'demo 1.0.0' $CLAUDE_CONFIG_DIR/skills/demo/SKILL.md && ! grep -q nightly $J && [ ! -e $CLAUDE_CONFIG_DIR/mila-update/cards ]"
# auto=false: только предложение
$U nightly > "$T/n2.json"
chk "auto=false: карточка «есть обновление», навык не тронут" "grep -q 'offered' $T/n2.json && grep -q 'demo 1.0.0' $CLAUDE_CONFIG_DIR/skills/demo/SKILL.md && grep -q 'Обновиться' $CLAUDE_CONFIG_DIR/mila-update/cards/offer-v1_1_0.json && grep -q 'быстрее разбираю' $CLAUDE_CONFIG_DIR/mila-update/cards/offer-v1_1_0.json"
$U nightly > "$T/n3.json"
chk "повторная ночь: то же предложение не дублируется" "grep -q offered-already $T/n3.json"
python3 - <<PY
import json; p="$V"; v=json.load(open(p)); v["offered"]="v0.9.0"; json.dump(v,open(p,"w"))
PY
$U nightly > "$T/n3b.json"
chk "ONE-CARD: прошлая карточка (v0.9.0) без ответа — новая говорит «заменяет прошлую — про v0.9.0»" "grep -q 'заменяет прошлую — про v0.9.0' $CLAUDE_CONFIG_DIR/mila-update/cards/offer-v1_1_0.json"
$U apply --tag v1.0.0 --yes "тест: кнопка старой карточки" > "$T/stale.json" 2>&1; rc=$?
chk "ONE-CARD: apply с тегом старой карточки (v1.0.0 старее предложенной v1.1.0) — отказ «карточка устарела», ничего не поставлено" "[ $rc != 0 ] && grep -q 'карточка устарела' $T/stale.json && grep -q 'demo 1.0.0' $CLAUDE_CONFIG_DIR/skills/demo/SKILL.md"
# outbox
mkdir -p "$CLAUDE_CONFIG_DIR/channels/telegram"; $U config --set owner_chat=12345 >/dev/null
rm "$CLAUDE_CONFIG_DIR/mila-update/version.json.tmp" 2>/dev/null; python3 - <<PY
import json; p="$V"; v=json.load(open(p)); v.pop("offered",None); json.dump(v,open(p,"w"))
PY
$U nightly >/dev/null
chk "owner_chat: карточка с кнопками в outbox" "ls $CLAUDE_CONFIG_DIR/channels/telegram/outbox/update-*.json >/dev/null 2>&1 && grep -q buttons $CLAUDE_CONFIG_DIR/channels/telegram/outbox/update-*.json"
# auto=true
$U config --set auto=true >/dev/null
$U nightly > "$T/n4.json"; rc=$?
chk "auto=true: v1.1.0 поставлен, health ок, версия и журнал" "[ $rc = 0 ] && grep -q updated $T/n4.json && grep -q 'demo 1.1.0' $CLAUDE_CONFIG_DIR/skills/demo/SKILL.md && grep -q '\"1.1.0\"' $V && grep -q '\"result\": \"ok\"' $J"
chk "кроны сохранены копией, state не тронут" "ls $CLAUDE_CONFIG_DIR/mila-update/crons-*/crons.json >/dev/null && grep -q cron $MILA_WORK/state/crons.json"
chk "карточка «что нового» из CHANGELOG, без «Для Мил»" "grep -q 'быстрее разбираю' $CLAUDE_CONFIG_DIR/mila-update/cards/done-v1_1_0.json && ! grep -q 'технически' $CLAUDE_CONFIG_DIR/mila-update/cards/done-v1_1_0.json"
chk "личное цело: NOW, личный навык, память" "[ \"\$(cat $MILA_WORK/NOW.md)\" = NOW ] && [ -f $CLAUDE_CONFIG_DIR/skills/moy-lichny/SKILL.md ] && [ -d $MILA_WORK/memory ]"
$U nightly > "$T/n5.json"
chk "после v1.1.0 обновлять нечего (v1.2.0 отозван)" "grep -q up-to-date $T/n5.json"
# провал health → автооткат
git checkout -q main; manifest 1.4.0 '["false"]'; skill 1.4.0; rel r5 v1.4.0
$U nightly > "$T/n6.json"; rc=$?
chk "health провален: авто-откат, навык как в 1.1.0, версия 1.1.0" "[ $rc = 1 ] && grep -q rolled-back $T/n6.json && grep -q 'demo 1.1.0' $CLAUDE_CONFIG_DIR/skills/demo/SKILL.md && grep -q '\"1.1.0\"' $V"
chk "журнал: health-failed-rolled-back и rollback" "grep -q health-failed-rolled-back $J && grep -q '\"event\": \"rollback\"' $J"
chk "хозяину карточка «не прошло, вернула»" "grep -q 'вернула' $CLAUDE_CONFIG_DIR/mila-update/cards/failed-v1_4_0.json"
# битый навык: отклонён сухой проверкой, до записи
git checkout -q main; manifest 1.5.0; printf -- '---\nname: demo\ndescription: плохо: двоеточие\n---\n' > skills/demo/SKILL.md; rel r6 v1.5.0
$U nightly > "$T/n7.json"
chk "битый заголовок навыка: rejected до записи" "grep -q rejected $T/n7.json && grep -q 'demo 1.1.0' $CLAUDE_CONFIG_DIR/skills/demo/SKILL.md"
# отзыв: v1.4.0 и v1.5.0 в yanked → ничего не ставится
echo '{"yanked":[{"tag":"v1.4.0","reason":"x"},{"tag":"v1.5.0","reason":"y"},"v1.2.0"]}' > yanked.json; git add -A; git commit -qm yank
$U nightly > "$T/n8.json"
chk "yanked: все новее отозваны — up-to-date" "grep -q up-to-date $T/n8.json"
# стоящая версия отозвана
echo '["v1.1.0"]' > yanked.json; git add -A; git commit -qm yank2
$U nightly > "$T/n9.json"
chk "стоящая версия отозвана: предупреждение и карточка" "grep -q installed_yanked $T/n9.json && grep -q 'отозвана' $CLAUDE_CONFIG_DIR/mila-update/cards/yanked-v1_1_0.json"
# canary: main
echo '[]' > yanked.json; manifest 1.6.0; skill 1.6.0; git add -A; git commit -qm c1
$U config --set channel=canary >/dev/null
$U nightly > "$T/n10.json"
chk "canary: ставит main, версия main@sha" "grep -q updated $T/n10.json && grep -q 'demo 1.6.0' $CLAUDE_CONFIG_DIR/skills/demo/SKILL.md && grep -q 'main@' $V"
$U nightly > "$T/n11.json"
chk "canary: тот же коммит — обновлять нечего" "grep -q up-to-date $T/n11.json"
$U config --set channel=manual >/dev/null
chk "manual: сама не проверяю" "$U nightly | grep -q manual"
$U slot > "$T/s"; chk "slot: число 0–119" "python3 -c \"import sys; v=int(open('$T/s').read()); sys.exit(0 if 0<=v<120 else 1)\""
$U plan --tag v1.1.0 --offer > "$T/plan-offer.txt"
chk "ONE-CARD c: plan --offer — ручная карточка пишет offered = v1.1.0" "grep -q '\"offered\": \"v1.1.0\"' $V"
$U apply --tag v1.0.0 --yes "тест: кнопка карточки старее ручной" > "$T/stale2.json" 2>&1
chk "ONE-CARD c: после ручной карточки v1.1.0 кнопка v1.0.0 — «устарела»" "grep -q 'карточка устарела' $T/stale2.json"
python3 - <<PY
import json; p="$V"; v=json.load(open(p)); v["offered"]="v0.1.0"; json.dump(v,open(p,"w"))
PY
$U apply --tag v1.1.0 --yes "тест: ручная карточка новее ночной" > "$T/newer.json" 2>&1
chk "ONE-CARD: apply с тегом НОВЕЕ предложенного (ручная карточка раскатки) — не «устарела»" "! grep -q 'устарела' $T/newer.json"
echo "итог $ok/$n"; rm -rf "$T"; [ "$ok" = "$n" ]
