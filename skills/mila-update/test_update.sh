#!/usr/bin/env bash
# тест mila-update в песочнице: ничего вне временной папки не трогает
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR/skills/moy-lichny" "$MILA_WORK/memory" "$HOME/secrets"
echo "мой навык" > "$CLAUDE_CONFIG_DIR/skills/moy-lichny/SKILL.md"; echo "NOW хозяина" > "$MILA_WORK/NOW.md"; echo "память" > "$MILA_WORK/memory/a.md"
echo '{"x":1}' > "$CLAUDE_CONFIG_DIR/settings.json"; echo KEY > "$HOME/secrets/k.key"
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git"
# базовая версия песочницы — 1.0.0, что бы ни стояло в release.json репо
python3 - "$T/rel/release.json" <<'PY'
import json, sys; p = sys.argv[1]; d = json.load(open(p))
d["version"], d["tag"] = "1.0.0", "v1.0"; open(p, "w").write(json.dumps(d, ensure_ascii=False, indent=2))
PY
mkdir -p "$CLAUDE_CONFIG_DIR/hooks"; echo "# мой хук новее релиза" > "$CLAUDE_CONFIG_DIR/hooks/chat_note.py"
mkdir -p "$MILA_WORK/rituals"; echo "мой ритуал" > "$MILA_WORK/rituals/WAKE.md"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
echo "знакомство: идёт" > "$MILA_WORK/USER.md"
chk "новорождённая до знакомства — не обновляется" "! $U apply --src $T/rel --yes x >/dev/null 2>&1 && [ ! -e $CLAUDE_CONFIG_DIR/skills/visual ]"
chk "nightly у новорождённой — skip" "$U nightly --dry-run 2>/dev/null | grep -q 'знакомство ещё не пройдено'"
chk "Мила команды (MILA_INTERNAL=1): гейт не срабатывает" "MILA_INTERNAL=1 python3 -c \"import sys; sys.argv=['u']; sys.path.insert(0,'$HERE'); import update; sys.exit(0 if update.newborn_block()=='' else 1)\""
$U config --set internal=true >/dev/null
chk "internal=true в mila-update.json: гейт не срабатывает, nightly не skip по знакомству" "python3 -c \"import sys; sys.argv=['u']; sys.path.insert(0,'$HERE'); import update; sys.exit(0 if update.newborn_block()=='' else 1)\" && ! $U nightly --dry-run 2>/dev/null | grep -q 'знакомство ещё не пройдено'"
chk "обход гейта в журнале: internal, источник config, где nightly" "grep -q '\"newborn_gate_skipped\".*\"source\": \"config\".*\"where\": \"nightly\"' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
$U config --set internal=false >/dev/null
chk "internal=false — гейт снова на месте" "! $U apply --src $T/rel --yes x >/dev/null 2>&1 && [ ! -e $CLAUDE_CONFIG_DIR/skills/visual ]"
chk "internal только true/false" "! $U config --set internal=yes >/dev/null 2>&1"
echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
chk "без «да» не обновляется" "! $U apply --src $T/rel >/dev/null 2>&1 && [ ! -e $CLAUDE_CONFIG_DIR/skills/visual ]"
$U diff --src "$T/rel" > "$T/d1.json"
chk "diff: навыки ядра — новое" "grep -q visual $T/d1.json"
$U apply --src "$T/rel" --yes "тест: хозяин нажал ✅ 12.10" > "$T/a1.json"
chk "первая сверка: чужой хук — «отличается», не затёрт; ритуалы не тронуты" "grep -q 'мой хук новее' $CLAUDE_CONFIG_DIR/hooks/chat_note.py && grep -A3 otlichaetsya $T/d1.json | grep -q chat_note && grep -q 'мой ритуал' $MILA_WORK/rituals/WAKE.md"
chk "apply: навык ядра поставлен" "[ -f $CLAUDE_CONFIG_DIR/skills/visual/SKILL.md ]"
chk "apply: хук поставлен, тесты — нет" "[ -f $CLAUDE_CONFIG_DIR/hooks/telegram-inbox-feed.py ] && [ ! -e $CLAUDE_CONFIG_DIR/hooks/test_records.py ]"
chk "NOW, memory, settings, ключ, личный навык — как были" "[ \"\$(cat $MILA_WORK/NOW.md)\" = 'NOW хозяина' ] && [ -f $MILA_WORK/memory/a.md ] && grep -q x $CLAUDE_CONFIG_DIR/settings.json && [ -f $HOME/secrets/k.key ] && [ -f $CLAUDE_CONFIG_DIR/skills/moy-lichny/SKILL.md ]"
chk "версия и журнал записаны" "$U status | grep -q 1.0.0 && grep -q 'хозяин нажал' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
$U apply --src "$T/rel" --yes "тест: взять хук" --take chat_note.py >/dev/null
chk "--take: хук из релиза взят" "! grep -q 'мой хук новее' $CLAUDE_CONFIG_DIR/hooks/chat_note.py"
$U diff --src "$T/rel" > "$T/d2.json"
chk "повторный diff: всё как есть" "python3 -c \"import json,sys; d=json.load(open('$T/d2.json')); sys.exit(0 if list(d['itog'])==['как есть'] else 1)\""
# хозяин поправил навык ядра, а релиз v1.1 изменил его и хук
echo "моя правка" >> "$CLAUDE_CONFIG_DIR/skills/visual/SKILL.md"
echo "# v1.1" >> "$T/rel/skills/visual/SKILL.md"; echo "# v1.1" >> "$T/rel/install/doctor.py"
python3 - "$T/rel/release.json" <<'PY'   # портативно: sed -i у GNU и BSD разный
import sys; p = sys.argv[1]; s = open(p).read()
import json; d = json.loads(s); d["version"], d["tag"] = "1.1.0", "v1.1"; open(p, "w").write(json.dumps(d, ensure_ascii=False, indent=2))
PY
$U diff --src "$T/rel" > "$T/d3.json"
chk "diff: правка хозяина видна, хук обновится" "grep -A3 vasha_pravka $T/d3.json | grep -q visual && grep -A3 obnovitsya $T/d3.json | grep -q doctor.py"
$U apply --src "$T/rel" --yes "тест v1.1" > /dev/null
chk "правка хозяина цела, новая версия отдельно" "grep -q 'моя правка' $CLAUDE_CONFIG_DIR/skills/visual/SKILL.md && grep -q v1.1 $CLAUDE_CONFIG_DIR/mila-update/new/v1.1/visual/SKILL.md && [ ! -e $CLAUDE_CONFIG_DIR/skills/naglyadno.new-v1.1 ]"
chk "хук обновлён до v1.1" "grep -q '# v1.1' $CLAUDE_CONFIG_DIR/hooks/doctor.py"
$U rollback > /dev/null
chk "откат: хук как в v1.0, версия 1.0.0" "! grep -q '# v1.1' $CLAUDE_CONFIG_DIR/hooks/doctor.py && $U status | grep -q '\"1.0.0\"'"
mkdir -p "$T/pkg/novaya-sila"; echo "---
name: novaya-sila
---" > "$T/pkg/novaya-sila/SKILL.md"
chk "навык от администратора без --from — отказ" "! $U install-skill $T/pkg/novaya-sila >/dev/null 2>&1"
$U install-skill "$T/pkg/novaya-sila" --from "Мила-администратор, пакет 12.10" > /dev/null
chk "навык от администратора поставлен и в журнале" "[ -f $CLAUDE_CONFIG_DIR/skills/novaya-sila/SKILL.md ] && grep -q 'Мила-администратор' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
echo "token=1" > "$T/pkg/novaya-sila/.env"
chk "навык с секретом — отказ" "! $U install-skill $T/pkg/novaya-sila --from x >/dev/null 2>&1"
rm "$T/pkg/novaya-sila/.env"; $U rollback >/dev/null
chk "откат установки навыка" "[ ! -e $CLAUDE_CONFIG_DIR/skills/novaya-sila ]"
$U installed > "$T/i.json"
chk "installed: ядро и личные раздельно" "grep -q moy-lichny $T/i.json && python3 -c \"import json,sys; d=json.load(open('$T/i.json')); sys.exit(0 if 'visual' in d['yadro'] and 'moy-lichny' in d['lichnye'] else 1)\""
cp "$CLAUDE_CONFIG_DIR/mila-update/version.json" "$T/v.bak"; echo "{битый" > "$CLAUDE_CONFIG_DIR/mila-update/version.json"
$U status >/dev/null 2>&1
chk "битый version.json — не молча: строка error в журнале" "grep -q '\"event\": \"error\", \"where\": \"load_version\"' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
cp "$T/v.bak" "$CLAUDE_CONFIG_DIR/mila-update/version.json"
chk "заголовки всех SKILL.md репо разбираются YAML (нужен pyyaml)" "python3 $REPO/tools/check_frontmatter.py $REPO/skills $REPO/templates >/dev/null"
# миграция настроек — только onFailure: block хукам send-guard; остальное как было; бэкап; симлинк не трогаем
S="$CLAUDE_CONFIG_DIR/settings.json"; cp "$S" "$T/s.bak"
python3 - "$S" <<'PY'
import json, sys; json.dump({"x": 1, "env": {"OWNER_ID": "1"}, "hooks": {"PreToolUse": [{"matcher": "m", "hooks": [{"type": "command", "command": "python3 /h/send-guard.py"}]},
    {"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 /h/other.py"}]}]}}, open(sys.argv[1], "w"))
PY
chmod 600 "$S"
mig() { MILA_CC_VERSION=${CCV:-2.1.310} python3 -c "import sys; sys.argv=['u']; sys.path.insert(0,'$HERE'); import update; print(update.migrate_settings('vtest') or '')"; }
r0=$(CCV=2.1.200 mig)
chk "SG-ONFAIL: старая CC — не трогаем, в журнале migrate_skipped" "[ -z \"$r0\" ] && ! grep -q onFailure $S && grep -q '\"event\": \"migrate_skipped\"' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
r1=$(mig)
chk "SG-ONFAIL: send-guard получил onFailure: block, чужой хук и env — как были, права 600" "python3 -c \"import json,os;d=json.load(open('$S'));h=d['hooks']['PreToolUse'];assert h[0]['hooks'][0]['onFailure']=='block' and 'onFailure' not in h[1]['hooks'][0] and d['env']=={'OWNER_ID':'1'} and d['x']==1 and os.stat('$S').st_mode&0o777==0o600\" && [ -n \"$r1\" ]"
chk "SG-ONFAIL: бэкап настроек и строка migrate в журнале" "ls $CLAUDE_CONFIG_DIR/mila-update/backups/*vtest_settings*.tgz >/dev/null 2>&1 && grep -q '\"event\": \"migrate\"' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
r2=$(mig); chk "SG-ONFAIL: повтор — правок нет" "[ -z \"$r2\" ]"
mv "$S" "$T/real.json"; ln -s "$T/real.json" "$S"; python3 -c "import json;d=json.load(open('$T/real.json'));d['hooks']['PreToolUse'][0]['hooks'][0].pop('onFailure');json.dump(d,open('$T/real.json','w'))"
r3=$(mig); chk "SG-ONFAIL: settings.json — симлинк → не трогаем" "[ -z \"$r3\" ] && ! grep -q onFailure $T/real.json"
rm -f "$S"; cp "$T/s.bak" "$S"
echo "итог $ok/$n"; rm -rf "$T"
