#!/usr/bin/env bash
# Mila — one-command install / установка одной командой:
#   curl -fsSL https://raw.githubusercontent.com/shakhruz/mila/main/install/get.sh | bash
# Checks what is needed (Claude Code, Bun, git), clones the kit to ~/mila (or updates it; an older ~/mila-companion is updated in place), runs install/install.sh.
# Then installs the Telegram plugin: claude plugin marketplace add shakhruz/mila-telegram + claude plugin install mila-telegram@mila.
# Env: MILA_DIR (where to clone), MILA_REF (branch/tag; default — latest stable tag vX.Y.Z, canary: MILA_REF=main), MILA_REPO, MILA_INSTALL_ARGS,
#      MILA_PLUGIN_MARKET (default shakhruz/mila-telegram), MILA_SKIP_PLUGIN=1 — without the plugin step.
set -euo pipefail
REPO="${MILA_REPO:-https://github.com/shakhruz/mila}"
DIR="${MILA_DIR:-}"
if [ -z "$DIR" ]; then [ -d "$HOME/mila-companion/.git" ] && DIR="$HOME/mila-companion" || DIR="$HOME/mila"; fi   # старая установка обновляется на месте
REF="${MILA_REF:-}"   # пусто → последний стабильный тег vX.Y.Z (как в README: стабильная — Releases); main — только по MILA_REF=main
miss=0
need() { command -v "$1" >/dev/null 2>&1 || { printf '  ✗ %s — %s\n' "$1" "$2"; miss=1; }; }
echo "Mila · install"
if [[ "${MILA_SKIP_CHECKS:-0}" != "1" ]]; then
  need claude "Claude Code: https://docs.claude.com/en/docs/claude-code"
  need bun    "Bun: curl -fsSL https://bun.sh/install | bash"
fi
need git "git: https://git-scm.com/downloads"
[[ $miss -eq 0 ]] || { echo "Install the missing tools above and run the same command again."; exit 1; }
if [[ -z "$REF" ]]; then
  REF=$(git ls-remote --tags --sort=-v:refname "$REPO" 'v*' 2>/dev/null | grep -v '\^{}' | sed 's#.*refs/tags/##' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)
  REF="${REF:-main}"
  echo "  version: $REF"
fi
# Папка занята чужим: не наш набор (нет install/get.sh и skills/mila-update) — не трогаем, честный отказ (Качество 21.10)
ours(){ [[ -f "$1/install/get.sh" && -d "$1/skills/mila-update" ]]; }
if [[ -e "$DIR" ]] && ! ours "$DIR" && [[ -n "$(ls -A "$DIR" 2>/dev/null)" ]]; then
  echo "  $DIR is already used by something else (not the Mila kit) — I leave it untouched."
  echo "  Run again with another folder, e.g.: MILA_DIR=\$HOME/mila-kit bash <(curl -fsSL …/install/get.sh)"; exit 1
fi
if [[ -d "$DIR/.git" ]]; then
  echo "  updating $DIR"; git -C "$DIR" fetch -q --depth 1 origin "$REF" && git -C "$DIR" checkout -q FETCH_HEAD
else
  echo "  cloning into $DIR"; git clone -q --depth 1 --branch "$REF" "$REPO" "$DIR"
fi
bash "$DIR/install/install.sh" ${MILA_INSTALL_ARGS:-}
# Плагин Telegram — тем же запуском (комиссия 22.10): повторный запуск ничего не ломает, оба шага у claude идемпотентны
MARKET="${MILA_PLUGIN_MARKET:-shakhruz/mila-telegram}"
PLUGIN_OK=0
echo "Telegram plugin"
if [[ "${MILA_SKIP_PLUGIN:-0}" == "1" ]]; then echo "  skipped (MILA_SKIP_PLUGIN=1)"
elif [[ " ${MILA_INSTALL_ARGS:-} " == *" --dry-run "* ]]; then echo "  dry run: would run  claude plugin marketplace add $MARKET  and  claude plugin install mila-telegram@mila"
elif ! command -v claude >/dev/null 2>&1; then echo "  ✗ claude not found — install Claude Code, then run the same command again"
elif claude plugin marketplace add "$MARKET" >/dev/null 2>&1 && claude plugin install mila-telegram@mila --scope user >/dev/null 2>&1; then
  echo "  ✓ mila-telegram@mila installed"; PLUGIN_OK=1
else echo "  ✗ could not install it — in a Claude Code session: /plugin marketplace add $MARKET, then /plugin install mila-telegram@mila"
fi
cat <<'NEXT'

Next / дальше:
  1. Create a bot at @BotFather and keep its token.
  2. Start Claude Code with `mila` and save the token:
       /mila-telegram:configure <token>
  3. Restart with `mila`, message your bot, then in the session:
       /mila-telegram:access pair <code>
       /mila-telegram:access policy allowlist
  4. Check everything:  mila doctor   — all lines 🟢 or 🟡 with a hint.
  Details: README → Quick start.
NEXT
