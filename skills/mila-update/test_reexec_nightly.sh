#!/usr/bin/env bash
# Ночью auto-патч ставит и проверяет update.py релиза — после compare, тем же порядком, что apply.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$(mktemp -d)"; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
unset TELEGRAM_STATE_DIR MILA_OUTBOX MILA_OWNER_CHAT MILA_UPDATE_REEXEC
export GIT_CONFIG_GLOBAL="$T/gitconfig" GIT_CONFIG_SYSTEM=/dev/null
git config --global user.email t@t; git config --global user.name t; git config --global init.defaultBranch main
mkdir -p "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
R="$T/core"; mkdir -p "$R/skills/demo" "$R/skills/mila-update"; cd "$R"
manifest() { printf '{"version":"%s","tag":"v%s","zones":[{"what":"навыки","src":"skills/*","dst":"{claude}/skills/*","kind":"dir"}%s]}\n' "$1" "$1" "${2:-}" > release.json; }
skill() { printf -- '---\nname: demo\ndescription: "демо %s"\n---\n# demo %s\n' "$1" "$1" > skills/demo/SKILL.md; }
upd() { cp "$HERE/update.py" skills/mila-update/update.py; cp "$HERE/SKILL.md" skills/mila-update/SKILL.md
  [ -n "${1:-}" ] && python3 - skills/mila-update/update.py "$1" <<'PY'
import sys; p, m = sys.argv[1], sys.argv[2]; t = open(p).read()
t = t.replace("def cmd_apply(a):\n", "def cmd_apply(a):\n    open(__import__('os').path.expanduser('~/%s'), 'w').write('x')\n" % m, 1); open(p, "w").write(t)
PY
}
rel() { git add -A; git commit -qm "$1"; git tag "$2"; }
printf '# CHANGELOG\n' > CHANGELOG.md
manifest 1.0.0; skill 1.0.0; upd; git init -q; rel r1 v1.0.0
export MILA_CORE_REPO="$R"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
J="$CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
$U apply --src "$R" --yes "тест: старт" >/dev/null; $U config --set auto=patch >/dev/null
manifest 1.0.1 ',{"what":"чужое","src":"skills/*","dst":"/etc/*","kind":"dir"}'; skill 1.0.1; upd PWNED; rel r2 v1.0.1
$U nightly > "$T/n1.json" 2>&1
chk "ночью: манифест с /etc/* → отклонён, код релиза не запущен (метки нет), стоит 1.0.0" "grep -q 'rejected' $T/n1.json && [ ! -e $HOME/PWNED ] && grep -q '\"version\": \"1.0.0\"' $CLAUDE_CONFIG_DIR/mila-update/version.json"
git tag -d v1.0.1 >/dev/null; manifest 1.0.2; skill 1.0.2; upd NIGHT-102; rel r3 v1.0.2
$U nightly > "$T/n2.json" 2>&1
chk "ночью: патч 1.0.2 с другим update.py → ставит updater релиза (метка), журнал reexec via nightly" "[ -e $HOME/NIGHT-102 ] && grep -q '\"via\": \"nightly\"' $J"
chk "…стоит 1.0.2, health ok, статус updated" "grep -q '\"version\": \"1.0.2\"' $CLAUDE_CONFIG_DIR/mila-update/version.json && grep -q '\"status\": \"updated\"' $T/n2.json"
manifest 1.0.3; skill 1.0.3; cp "$HERE/update.py" skills/mila-update/update.py; python3 - skills/mila-update/update.py <<'PY'
import sys; p = sys.argv[1]; t = open(p).read(); t = t.replace("def cmd_apply(a):\n", "def cmd_apply(a):\n    sys.exit(3)\n", 1); open(p, "w").write(t)
PY
rel r4 v1.0.3
$U nightly > "$T/n3.json" 2>&1
chk "ночью: updater релиза упал (код 3) → «rejected», версия прежняя 1.0.2, не «updated»" "grep -q 'rejected' $T/n3.json && ! grep -q '\"status\": \"updated\"' $T/n3.json && grep -q '\"version\": \"1.0.2\"' $CLAUDE_CONFIG_DIR/mila-update/version.json"
git tag -d v1.0.3 >/dev/null; manifest 1.0.4; skill 1.0.4; cp "$HERE/update.py" skills/mila-update/update.py; python3 - skills/mila-update/update.py <<'PY'
import sys; p = sys.argv[1]; t = open(p).read(); t = t.replace("def cmd_apply(a):\n", "def cmd_apply(a):\n    print('{\"obnovleno\": []}'); return\n", 1); open(p, "w").write(t)
PY
rel r5 v1.0.4
$U nightly > "$T/n4.json" 2>&1
chk "ночью: updater релиза ответил код 0, но без \"ok\": true → «rejected», версия прежняя 1.0.2" "grep -q 'rejected' $T/n4.json && ! grep -q '\"status\": \"updated\"' $T/n4.json && grep -q '\"version\": \"1.0.2\"' $CLAUDE_CONFIG_DIR/mila-update/version.json"
cd /; rm -rf "$T"; echo "итог $ok/$n"; [ $ok -eq $n ]
