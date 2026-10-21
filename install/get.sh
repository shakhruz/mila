#!/usr/bin/env bash
# Mila Companion — one-command install / установка одной командой:
#   curl -fsSL https://raw.githubusercontent.com/shakhruz/mila-companion/main/install/get.sh | bash
# Checks what is needed (Claude Code, Bun, git), clones the kit to ~/mila-companion (or updates it), runs install/install.sh.
# Env: MILA_DIR (where to clone), MILA_REF (branch/tag, default main), MILA_REPO, MILA_INSTALL_ARGS (e.g. --dry-run).
set -euo pipefail
REPO="${MILA_REPO:-https://github.com/shakhruz/mila-companion}"
DIR="${MILA_DIR:-$HOME/mila-companion}"
REF="${MILA_REF:-main}"
miss=0
need() { command -v "$1" >/dev/null 2>&1 || { printf '  ✗ %s — %s\n' "$1" "$2"; miss=1; }; }
echo "Mila Companion · install"
if [[ "${MILA_SKIP_CHECKS:-0}" != "1" ]]; then
  need claude "Claude Code: https://docs.claude.com/en/docs/claude-code"
  need bun    "Bun: curl -fsSL https://bun.sh/install | bash"
fi
need git "git: https://git-scm.com/downloads"
[[ $miss -eq 0 ]] || { echo "Install the missing tools above and run the same command again."; exit 1; }
if [[ -d "$DIR/.git" ]]; then
  echo "  updating $DIR"; git -C "$DIR" fetch -q --depth 1 origin "$REF" && git -C "$DIR" checkout -q FETCH_HEAD
else
  echo "  cloning into $DIR"; git clone -q --depth 1 --branch "$REF" "$REPO" "$DIR"
fi
bash "$DIR/install/install.sh" ${MILA_INSTALL_ARGS:-}
cat <<'NEXT'

Next / дальше:
  1. Create a bot at @BotFather and keep its token.
  2. In Claude Code: /plugin install the Telegram plugin, then /telegram:configure <token> (see README → Install).
  3. Check everything:  mila doctor   — all lines 🟢 or 🟡 with a hint.
NEXT
