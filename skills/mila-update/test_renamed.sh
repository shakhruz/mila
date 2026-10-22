#!/usr/bin/env bash
# RENAMED-1017: обновление 1.3 → 1.4 с переименованием навыков. Ничего вне временной папки не трогает.
set -u
unset TELEGRAM_STATE_DIR MILA_OUTBOX MILA_OWNER_CHAT
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
export GIT_CONFIG_GLOBAL="$T/gitconfig" GIT_CONFIG_SYSTEM=/dev/null
mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
# «старый» релиз 1.3: навыки под старыми именами целиком, без renamed
cp -R "$REPO" "$T/old"; rm -rf "$T/old/.git"
python3 - "$T/old" <<'PY'
import json, os, shutil, sys
r = sys.argv[1]; m = json.load(open(f"{r}/release.json")); ren = m.pop("renamed"); m.pop("renamed_note", None)
for o, n in ren.items():
    if o.endswith(".md"):
        shutil.copy(f"{r}/canon/{n}", f"{r}/canon/{o}"); os.remove(f"{r}/canon/{n}"); continue
    shutil.rmtree(f"{r}/legacy/skills/{o}", ignore_errors=True); shutil.rmtree(f"{r}/skills/{o}", ignore_errors=True); shutil.move(f"{r}/skills/{n}", f"{r}/skills/{o}")
    p = f"{r}/skills/{o}/SKILL.md"; s = open(p).read().replace(f"name: {n}", f"name: {o}", 1); open(p, "w").write(s)
m["version"], m["tag"] = "1.3.0", "v1.3.0"; json.dump(m, open(f"{r}/release.json", "w"), ensure_ascii=False, indent=2)
PY
$U apply --src "$T/old" --yes "тест: база 1.3" >/dev/null
chk "база: навыки под старыми именами стоят" "[ -f $CLAUDE_CONFIG_DIR/skills/kartochki/SKILL.md ] && [ -f $CLAUDE_CONFIG_DIR/skills/rashod/SKILL.md ] && [ ! -e $CLAUDE_CONFIG_DIR/skills/cards ]"
echo "моя правка расхода" >> "$CLAUDE_CONFIG_DIR/skills/rashod/SKILL.md"
cp -R "$REPO" "$T/new"; rm -rf "$T/new/.git"
python3 - "$T/new/release.json" <<'PY'
import json, sys; p = sys.argv[1]; d = json.load(open(p)); d["version"], d["tag"] = "1.4.0", "v1.4.0"; json.dump(d, open(p, "w"), ensure_ascii=False, indent=2)
PY
$U apply --src "$T/new" --yes "тест: 1.4 с переименованием" > "$T/a.json"
chk "новые имена поставлены (cards, spend, onboarding)" "[ -f $CLAUDE_CONFIG_DIR/skills/cards/SKILL.md ] && [ -f $CLAUDE_CONFIG_DIR/skills/spend/SKILL.md ] && [ -f $CLAUDE_CONFIG_DIR/skills/onboarding/SKILL.md ]"
chk "старые папки — алиасы без SKILL.md (навык не задвоен)" "[ ! -e $CLAUDE_CONFIG_DIR/skills/kartochki/SKILL.md ] && [ -f $CLAUDE_CONFIG_DIR/skills/kartochki/MOVED.md ] && [ ! -e $CLAUDE_CONFIG_DIR/skills/rashod/SKILL.md ]"
chk "ни один навык не задвоен по name:" "[ -z \"\$(grep -h '^name:' $CLAUDE_CONFIG_DIR/skills/*/SKILL.md | sort | uniq -d)\" ]"
chk "старый путь скрипта работает: kartochki/kartochki.py → cards.py" "python3 $CLAUDE_CONFIG_DIR/skills/kartochki/kartochki.py 2>&1 | grep -q 'usage: cards.py'"
chk "правка хозяина под старым именем сохранена в new/v1.4.0/было-rashod" "grep -q 'моя правка расхода' $CLAUDE_CONFIG_DIR/mila-update/new/v1.4.0/было-rashod/SKILL.md"
chk "отчёт: переименовано и где правка" "python3 -c \"import json,sys; d=json.load(open('$T/a.json')); sys.exit(0 if d['pereimenovano'].get('kartochki')=='cards' and d['pereimenovano'].get('rashod')=='spend' and any('было-rashod' in x for x in d['pravka_starogo_imeni']) else 1)\""
chk "канон: OBDUMYVANIE → ссылка, THINKING-BUDGET — текст" "grep -q 'THINKING-BUDGET' $MILA_WORK/canon/OBDUMYVANIE.md && grep -q 'max_tokens' $MILA_WORK/canon/THINKING-BUDGET.md"
chk "журнал: renamed записан" "grep -q '\"renamed\"' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
$U diff --src "$T/new" > "$T/d.json"
chk "повторный diff после переименования — всё как есть" "python3 -c \"import json,sys; d=json.load(open('$T/d.json')); sys.exit(0 if list(d['itog'])==['как есть'] else 1)\""
echo "итог $ok/$n"; rm -rf "$T"
