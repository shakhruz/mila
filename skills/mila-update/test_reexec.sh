#!/usr/bin/env bash
# apply запускает update.py из РЕЛИЗА, если он новее моего (старый updater не узнаёт свои файлы — 30.10).
# Один раз, только вперёд по версии, только обычный файл внутри релиза; тот же файл — свой.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$(mktemp -d)"; trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
unset TELEGRAM_STATE_DIR MILA_OUTBOX MILA_OWNER_CHAT MILA_UPDATE_REEXEC
mkdir -p "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
J="$CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
rel() {   # rel <папка> <версия> [метка в update.py релиза]
  mkdir -p "$1/skills/mila-update" "$1/skills/demo"
  printf '{"version":"%s","tag":"v%s","zones":[{"what":"навыки","src":"skills/*","dst":"{claude}/skills/*","kind":"dir"}]}\n' "$2" "$2" > "$1/release.json"
  printf -- '---\nname: demo\ndescription: "демо %s"\n---\n# demo\n' "$2" > "$1/skills/demo/SKILL.md"
  cp "$HERE/update.py" "$1/skills/mila-update/update.py"; cp "$HERE/SKILL.md" "$1/skills/mila-update/SKILL.md"
  if [ -n "${3:-}" ]; then python3 - "$1/skills/mila-update/update.py" "$3" <<'PY'
import sys; p, m = sys.argv[1], sys.argv[2]; t = open(p).read()
t = t.replace("def cmd_apply(a):\n", "def cmd_apply(a):\n    print('%s', flush=True)\n" % m, 1); open(p, "w").write(t)
PY
  fi
}
rel "$T/r1" 1.0.0
python3 "$HERE/update.py" apply --src "$T/r1" --yes "тест: старт" >/dev/null
chk "старт: стоит 1.0.0" "grep -q '\"version\": \"1.0.0\"' $CLAUDE_CONFIG_DIR/mila-update/version.json"
rel "$T/r2" 1.1.0 NEW-UPDATER-110
out=$(python3 "$HERE/update.py" apply --src "$T/r2" --yes "тест: 1.1.0" 2>&1)
chk "релиз 1.1.0 с другим update.py → apply выполняет ЕГО (метка NEW-UPDATER-110), журнал «reexec 1.0.0→1.1.0»" "printf '%s' \"\$out\" | grep -q NEW-UPDATER-110 && grep -q '\"event\": \"reexec\", \"from\": \"1.0.0\", \"to\": \"1.1.0\"' $J"
chk "…и обновление прошло: стоит 1.1.0" "grep -q '\"version\": \"1.1.0\"' $CLAUDE_CONFIG_DIR/mila-update/version.json"
chk "перезапуск ровно один (в журнале один reexec)" "[ \$(grep -c '\"event\": \"reexec\"' $J) -eq 1 ]"
rel "$T/r0" 1.0.5 OLD-UPDATER-105
out=$(python3 "$HERE/update.py" apply --src "$T/r0" --yes "тест: откат" 2>&1)
chk "релиз СТАРШЕ моей версии (откат) → старый updater не запускаю" "! printf '%s' \"\$out\" | grep -q OLD-UPDATER-105"
rel "$T/r3" 1.2.0
out=$(python3 "$HERE/update.py" apply --src "$T/r3" --yes "тест: тот же файл" 2>&1)
chk "update.py в релизе тот же, что мой → перезапуска нет" "[ \$(grep -c '\"event\": \"reexec\"' $J) -eq 1 ]"
rel "$T/r4" 1.3.0 NEW-UPDATER-130
out=$(MILA_UPDATE_REEXEC=1 python3 "$HERE/update.py" apply --src "$T/r4" --yes "тест: уже перезапущен" 2>&1)
chk "MILA_UPDATE_REEXEC уже стоит → второй раз не перезапускаю" "! printf '%s' \"\$out\" | grep -q NEW-UPDATER-130"
rel "$T/r5" 1.4.0; mv "$T/r5/skills/mila-update/update.py" "$T/evil.py"; printf "print('EVIL', flush=True)\n" >> "$T/evil.py"; ln -s "$T/evil.py" "$T/r5/skills/mila-update/update.py"
out=$(python3 "$HERE/update.py" apply --src "$T/r5" --yes "тест: ссылка" 2>&1)
chk "update.py релиза — ссылка наружу → не запускаю" "! printf '%s' \"\$out\" | grep -q EVIL && [ \$(grep -c '\"event\": \"reexec\"' $J) -eq 1 ]"
# манифест с зоной вне дома + меченый update.py → отказ ДО запуска чужого кода, метки нет
rel "$T/r6" 1.5.0 PWNED-150; python3 - "$T/r6/release.json" <<'PY'
import json, sys; p = sys.argv[1]; m = json.load(open(p)); m["zones"].append({"what": "чужое", "src": "skills/*", "dst": "/etc/*", "kind": "dir"}); json.dump(m, open(p, "w"))
PY
out=$(python3 "$HERE/update.py" apply --src "$T/r6" --yes "тест: плохой манифест" 2>&1)
chk "манифест с зоной вне дома → «отклонён целиком», код релиза НЕ запущен (метки нет)" "printf '%s' \"\$out\" | grep -q 'отклонён целиком' && ! printf '%s' \"\$out\" | grep -q PWNED-150"
rel "$T/r7" 1.6.0 IN-MANIFEST-160; python3 - "$T/r7/release.json" <<'PY'
import json, sys; p = sys.argv[1]; m = json.load(open(p)); m["zones"] = [{"what": "только demo", "src": "skills/demo", "dst": "{claude}/skills/demo", "kind": "dir"}]; json.dump(m, open(p, "w"))
PY
out=$(python3 "$HERE/update.py" apply --src "$T/r7" --yes "тест: update.py не в манифесте" 2>&1)
chk "update.py релиза не в строках манифеста → не запускаю его" "! printf '%s' \"\$out\" | grep -q IN-MANIFEST-160"
rel "$T/r8" 1.7.0 HARDLINK-170; ln -f "$T/r8/skills/mila-update/update.py" "$T/hl-update.py"
out=$(python3 "$HERE/update.py" apply --src "$T/r8" --yes "тест: жёсткая ссылка" 2>&1)
chk "update.py релиза — жёсткая ссылка → не запускаю (_bad_src)" "! printf '%s' \"\$out\" | grep -q HARDLINK-170"
# защита внутри reexec (если манифест когда-то пропустит): ссылка и жёсткая ссылка на update.py — функция возвращается, не запускает
rel "$T/r9" 1.8.0 DIRECT-180
res=$(cd "$HERE" && MILA_UPDATE_REEXEC= python3 - "$T" <<'PY'
import os, sys, importlib.util
T = sys.argv[1]; spec = importlib.util.spec_from_file_location("u", "update.py"); u = importlib.util.module_from_spec(spec); spec.loader.exec_module(u)
calls = []; u.os.execve = lambda *a: calls.append(a)
src = T + "/r9"; up = src + "/skills/mila-update/update.py"; rows = [{"src": src + "/skills/mila-update"}]
os.link(up, T + "/hl2.py"); u.reexec_release_updater(src, rows, ["apply"]); hl = len(calls); os.remove(T + "/hl2.py")
os.rename(up, T + "/real.py"); os.symlink(T + "/real.py", up); u.reexec_release_updater(src, rows, ["apply"]); sl = len(calls) - hl
os.remove(up); os.rename(T + "/real.py", up); u.reexec_release_updater(src, rows, ["apply"]); ok = len(calls) - hl - sl
print(hl, sl, ok)
PY
)
chk "внутри reexec: жёсткая ссылка — нет, ссылка — нет, обычный файл в манифесте — да (0 0 1)" "[ \"\$res\" = '0 0 1' ]"
rm -rf "$T"; echo "итог $ok/$n"; [ $ok -eq $n ]
