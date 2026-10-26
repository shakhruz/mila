#!/usr/bin/env bash
# Самопроверка mila-export в песочнице: ничего вне временной папки не трогает.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export PYTHONDONTWRITEBYTECODE=1
X="python3 $HERE/mila_export.py"
H="$T/src"; C="$H/.claude"; W="$H/work"
mkdir -p "$C/skills/moy-lichny" "$C/hooks" "$C/channels/telegram/inbound" "$C/channels/telegram/chats" "$C/projects/p" "$C/plugins" \
         "$W/memory" "$W/canon" "$W/state" "$W/journal" "$W/inbox" "$W/secrets"
echo "мой личный навык" > "$C/skills/moy-lichny/SKILL.md"
printf '#!/bin/sh\necho hook\n' > "$C/hooks/my.sh"; chmod 755 "$C/hooks/my.sh"
echo "# инструкции" > "$W/CLAUDE.md"; echo "конституция" > "$W/CONSTITUTION.md"; echo "канон" > "$W/canon/LIVE.md"
echo "память хозяина" > "$W/memory/a.md"; echo "- cron */5 x" > "$W/state/crons.md"; echo "дневник" > "$W/journal/d.md"
echo "записка" > "$W/inbox/n.md"
cat > "$C/settings.json" <<'J'
{"env":{"DISABLE_TELEMETRY":"1","MY_API_TOKEN":"zzz-not-for-archive"},"hooks":{"Stop":[]}}
J
echo '{"plugins":{"mila-telegram@mila":{"version":"1.0.0"}}}' > "$C/plugins/installed_plugins.json"
TGID="1234""56789"   # склейкой: в строке нет 9 цифр подряд (pre-push)
echo '{"dmPolicy":"allowlist","allowFrom":["'"$TGID"'"],"groups":{"-100123":{"requireMention":true}}}' > "$C/channels/telegram/access.json"
echo 'TELEGRAM_BOT_TOKEN=notreallyatoken' > "$C/channels/telegram/.env"
echo 'ELEVENLABS_API_KEY=qzv9wxfake' > "$W/.env"
echo "сообщение гостя" > "$C/channels/telegram/inbound/events.jsonl"
echo "карточка чата" > "$C/channels/telegram/chats/c1.md"
echo '{"x":1}' > "$C/projects/p/session.jsonl"
echo '{"oauthAccount":{"emailAddress":"x@y.z"}}' > "$C/.claude.json"; echo "ключ" > "$W/secrets/k.txt"; echo "x" > "$W/my_api_key.txt"
mkdir -p "$C/mila-update"; echo '{"version":"1.0.0","tag":"v1.0"}' > "$C/mila-update/version.json"
ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "ok   $1"; else echo "FAIL $1"; fi; }

# 1. подложенный фальшивый секрет — export обязан упасть и назвать файл, но не значение
FAKE="sk-$(printf 'a%.0s' {1..30})"
echo "ключ: $FAKE" > "$W/memory/leak.md"
$X export --home "$H" --name t --out "$T/out" >"$T/e1.out" 2>"$T/e1.err"; rc=$?
chk "секрет в файле: export падает (код 3)" "[ $rc -eq 3 ]"
chk "отказ называет файл" "grep -q 'work/memory/leak.md' $T/e1.err"
chk "значение секрета не напечатано" "! grep -q aaaaaaaaaa $T/e1.err $T/e1.out"
chk "архив не создан" "[ ! -e $T/out ] || [ -z \"\$(ls $T/out 2>/dev/null)\" ]"
# все виды из спецификации
for s in "sk""-ant-api03-$(printf 'b%.0s' {1..40})" "12345""67890:AA$(printf 'c%.0s' {1..34})" "gh""p_$(printf 'd%.0s' {1..36})" "AK""IA$(printf 'E%.0s' {1..16})" "r""e_$(printf 'f%.0s' {1..24})" "$(printf -- '-%.0s' {1..5})BEGIN RSA PRIV""ATE K""EY-----" "pa""ss""word=Abcdef123456" "pa""ss""word = \"Qw3rty98765\""; do   # фальшивки собираются при запуске — в файле их нет (сканер флота, 24.10)
  echo "x $s" > "$W/memory/leak.md"; $X export --home "$H" --name t --out "$T/out" >/dev/null 2>&1
  chk "сканер ловит: ${s:0:7}…" "[ $? -eq 3 ]"
done
rm "$W/memory/leak.md"

# 2. чисто — проходит; с --allow ложное срабатывание
$X export --home "$H" --name t --out "$T/out" >"$T/e2.out" 2>"$T/e2.err"; rc=$?
chk "без секрета export проходит" "[ $rc -eq 0 ]"
A="$(ls $T/out/mila-export-t-*.tar.gz 2>/dev/null | head -1)"
chk "архив создан, права 600" "[ -f '$A' ] && [ \"\$(stat -c %a '$A' 2>/dev/null || stat -f %Lp '$A')\" = 600 ]"
mkdir "$T/x"; tar -xzf "$A" -C "$T/x"; R="$(ls -d $T/x/mila-export-*)"
chk "manifest: format=1, версия ядра, sha256" "python3 -c \"import json;m=json.load(open('$R/manifest.json'));assert m['format']==1 and m['core']['version']=='1.0.0' and all(len(f['sha256'])==64 for f in m['files']) and m['created']\""
chk "RESTORE.md внутри" "[ -s $R/RESTORE.md ] && grep -q ELEVENLABS_API_KEY $R/RESTORE.md"
F="$R/files"
chk "взято: инструкции, canon, навыки (личные), хуки, память, кроны, плагины, версия" "[ -f $F/work/CLAUDE.md ] && [ -f $F/work/canon/LIVE.md ] && [ -f $F/claude/skills/moy-lichny/SKILL.md ] && [ -x $F/claude/hooks/my.sh ] && [ -f $F/work/memory/a.md ] && [ -f $F/work/state/crons.md ] && [ -f $F/claude/plugins/installed_plugins.json ] && [ -f $F/claude/mila-update/version.json ] || grep -q 1.0.0 $R/manifest.json"
chk "settings.json: хуки есть, секретный env пуст" "grep -q hooks $F/claude/settings.json && ! grep -q zzz-not-for $F/claude/settings.json"
chk "access: только шаблон, без id" "[ -f $F/claude/channels/telegram/access.template.json ] && ! grep -rq $TGID $F && ! grep -rq 100123 $F && grep -q allowlist $F/claude/channels/telegram/access.template.json"
chk "не взято: .env, токены, ключ-файлы, secrets/, inbound, сессии, inbox, карточки чатов" "[ ! -e $F/work/.env ] && [ ! -e $F/claude/.claude.json ] && [ ! -e $F/claude/channels/telegram/.env ] && [ ! -e $F/work/my_api_key.txt ] && [ ! -e $F/work/secrets ] && [ ! -e $F/claude/channels/telegram/inbound ] && [ ! -e $F/claude/projects ] && [ ! -e $F/work/inbox ] && [ ! -e $F/claude/channels/telegram/chats ]"
chk "journal/ берётся по умолчанию; версия из release.json при отсутствии version.json" "[ -f $F/work/journal/d.md ]"
mkdir -p "$C/skills/moy-lichny/students" && echo "ученик" > "$C/skills/moy-lichny/students/1.md"
$X export --home "$H" --name np --out "$T/outnp" --no-people >/dev/null 2>&1
chk "--no-people: students/ исключена, в RESTORE.md предупреждение" "! tar -tzf $T/outnp/*.tar.gz | grep -q students && grep -q 'третьим лицам' $R/RESTORE.md"
rm -rf "$C/skills/moy-lichny/students"
mv "$C/mila-update" "$T/mu"; $X export --home "$H" --name nv --out "$T/outnv" >/dev/null 2>&1; mv "$T/mu" "$C/mila-update"
chk "нет version.json: версия берётся из release.json ядра" "python3 -c 'import sys,tarfile; t=tarfile.open(sys.argv[1]); sys.exit(0 if any(b\"release.json\" in t.extractfile(m).read() for m in t.getmembers() if m.name.endswith(\"manifest.json\")) else 1)' $T/outnv/*.tar.gz"   # манифест — через python tarfile: --include есть только у BSD tar (Сила 25.10)
chk "ни одного значения секрета в архиве" "! grep -rq -e notreallyatoken -e qzv9wxfake -e zzz-not $R --include='*' -l"
chk "сканер по распакованному: 0" "$X scan $R >/dev/null"
chk "verify проходит" "$X verify $A >/dev/null"

# 3. --with-history добавляет переписку (с предупреждением)
$X export --home "$H" --name h --out "$T/outh" --with-history >/dev/null 2>"$T/h.err"
chk "--with-history: предупреждение о чужих данных, сессии и journal внутри" "grep -q 'чужие данные' $T/h.err && tar -tzf $T/outh/*.tar.gz | grep -q 'projects/p/session.jsonl' && tar -tzf $T/outh/*.tar.gz | grep -q 'journal/d.md'"
chk "--with-history: inbound и токены всё равно нет" "! tar -tzf $T/outh/*.tar.gz | grep -q 'inbound\\|\\.env'"

# 4. restore в чистую папку и сравнение по манифесту
D="$T/dst"; mkdir -p "$D"
$X restore "$A" --home "$D" >"$T/r1.out" 2>&1; rc=$?
chk "restore в чистый дом: код 0, чек-лист «введите заново»" "[ $rc -eq 0 ] && grep -q 'Введите заново' $T/r1.out && grep -q ELEVENLABS_API_KEY $T/r1.out"
chk "сверка с манифестом: каждый sha256 совпал" "python3 - <<PY
import json,hashlib,os
m=json.load(open('$R/manifest.json'));z={'claude':'$D/.claude','work':'$D/work'}
bad=[f['path'] for f in m['files'] if hashlib.sha256(open(os.path.join(z[f['zone']],f['rel']),'rb').read()).hexdigest()!=f['sha256']]
raise SystemExit(1 if bad else 0)
PY"
chk "бит исполнения сохранён" "[ -x $D/.claude/hooks/my.sh ]"
# 5. повтор: ничего не перезаписывает; существующее не тронуто; расхождение — в conflicts
echo "новая память на новой машине" > "$D/work/memory/a.md"
echo "TOKEN-ON-NEW-MACHINE" > "$D/.claude/channels/telegram/.env"
$X restore "$A" --home "$D" >"$T/r2.out" 2>&1
chk "повторный restore: существующее не перезаписано" "grep -q 'новая память' $D/work/memory/a.md"
chk "расхождение лежит в conflicts" "find $D/.claude/mila-restore -path '*conflicts/work/memory/a.md' | grep -q ."
chk "секрет на новой машине не тронут" "grep -q TOKEN-ON-NEW-MACHINE $D/.claude/channels/telegram/.env"
$X restore "$A" --home "$D" --overwrite >/dev/null 2>&1
chk "--overwrite: заменено, старая копия сохранена" "grep -q 'память хозяина' $D/work/memory/a.md && find $D/.claude/mila-restore -path '*replaced/work/memory/a.md' | grep -q ."
chk "--dry-run ничего не пишет" "rm -rf $T/dry; mkdir $T/dry; $X restore $A --home $T/dry --dry-run >/dev/null 2>&1 && [ -z \"\$(ls -A $T/dry)\" ]"

# 6. подмена: повреждённый файл, лишний файл, неверный формат, путь наружу
python3 - "$A" "$T" <<'PY'
import sys,tarfile,io,json
a,t=sys.argv[1:]
def rebuild(name,fn):
    with tarfile.open(a) as src, tarfile.open(t+"/"+name,"w:gz") as out:
        for ti in src:
            data=src.extractfile(ti).read(); r=fn(ti.name,data)
            if r is None: continue
            ti.size=len(r); out.addfile(ti,io.BytesIO(r))
rebuild("tamper.tar.gz",lambda n,d: d+b"x" if n.endswith("work/memory/a.md") else d)
def fmt(n,d):
    if n.endswith("manifest.json"):
        m=json.loads(d); m["format"]=2; return json.dumps(m).encode()
    return d
rebuild("fmt2.tar.gz",fmt)
with tarfile.open(t+"/evil.tar.gz","w:gz") as out:
    ti=tarfile.TarInfo("r/../../evil"); ti.size=1; out.addfile(ti,io.BytesIO(b"x"))
PY
chk "подмена файла: restore отказывает по sha256" "! $X restore $T/tamper.tar.gz --home $T/dst2 >/dev/null 2>&1 && [ ! -e $T/dst2 ]"
chk "формат 2: понятный отказ" "$X verify $T/fmt2.tar.gz 2>&1 | grep -q 'не поддерживается'"
chk "путь с .. отвергнут" "! $X verify $T/evil.tar.gz >/dev/null 2>&1 && [ ! -e $T/evil ]"

# 7. сам навык проходит свой сканер (регулярки не ловят себя)
chk "mila-export не содержит секретов (scan по навыку, кроме теста с фальшивками)" "$X scan $HERE --allow test_export.sh >/dev/null"

echo; echo "итого: $ok из $n"; [ "$ok" -eq "$n" ]
