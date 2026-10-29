#!/usr/bin/env bash
# AUTO-PATCH-2910: auto=patch — ночью сама ставлю только патч той же x.y с риском не выше среднего; новая x.y или хуки — карточка хозяину.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$(mktemp -d)"; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
unset TELEGRAM_STATE_DIR MILA_OUTBOX MILA_OWNER_CHAT
export GIT_CONFIG_GLOBAL="$T/gitconfig" GIT_CONFIG_SYSTEM=/dev/null
git config --global user.email t@t; git config --global user.name t; git config --global init.defaultBranch main
mkdir -p "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
R="$T/core"; mkdir -p "$R/skills/demo" "$R/install"; cd "$R"
manifest() { printf '{"version":"%s","tag":"v%s","zones":[{"what":"навыки","src":"skills/*","dst":"{claude}/skills/*","kind":"dir"},{"what":"хуки","src":"install/*.py","dst":"{claude}/hooks/*","kind":"file"}]}\n' "$1" "$1" > release.json; }
skill() { printf -- '---\nname: demo\ndescription: "демо %s"\n---\n# demo %s\n' "$1" "$1" > skills/demo/SKILL.md; }
rel() { git add -A; git commit -qm "$1"; git tag "$2"; }
printf '# CHANGELOG\n' > CHANGELOG.md; echo "# hook 1" > install/h.py
manifest 1.0.0; skill 1.0.0; git init -q; rel r1 v1.0.0
manifest 1.0.1; skill 1.0.1; rel r2 v1.0.1
export MILA_CORE_REPO="$R"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
V="$CLAUDE_CONFIG_DIR/mila-update/version.json"
git checkout -q v1.0.0 2>/dev/null; $U apply --src "$R" --yes "тест: старт" >/dev/null; git checkout -q main
$U config --set auto=patch >/dev/null
chk "config: auto=patch сохраняется как «patch»" "$U config | grep -q '\"auto\": \"patch\"'"
$U nightly > "$T/n1.json"
chk "патч 1.0.0 → 1.0.1, меняется только текст навыка — ставлю сама, «да» записано как auto=patch" "grep -q '\"status\": \"updated\"' $T/n1.json && grep -q 'demo 1.0.1' $CLAUDE_CONFIG_DIR/skills/demo/SKILL.md && grep -q 'auto=patch' $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
manifest 1.1.0; skill 1.1.0; rel r3 v1.1.0
$U nightly > "$T/n2.json"
chk "новая x.y (1.1.0) — не ставлю, карточка хозяину" "grep -q 'offered' $T/n2.json && grep -q 'demo 1.0.1' $CLAUDE_CONFIG_DIR/skills/demo/SKILL.md"
git checkout -q v1.0.1 2>/dev/null; git checkout -q -b p102; manifest 1.0.2; skill 1.0.2; echo "# hook 2" > install/h.py; rel r4 v1.0.2; git checkout -q main; git tag -d v1.1.0 >/dev/null
python3 - <<PY
import json; p="$V"; v=json.load(open(p)); v.pop("offered", None); json.dump(v, open(p, "w"))
PY
$U nightly > "$T/n3.json"
chk "патч 1.0.2, но меняется хук (риск высокий) — не ставлю, карточка хозяину" "grep -q 'offered' $T/n3.json && grep -q 'demo 1.0.1' $CLAUDE_CONFIG_DIR/skills/demo/SKILL.md && grep -q 'риск высокий' $T/n3.json"
$U config --set auto=false >/dev/null
chk "auto=false — снова только по кнопке" "$U config | grep -q '\"auto\": false'"
echo "итог $ok/$n"; [ $ok -eq $n ]
