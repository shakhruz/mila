#!/usr/bin/env bash
# All core tests in one command (plan 17.10, item 5): every test_* in the repo + frontmatter. Sandboxed tests only, nothing outside temp dirs.
# Exit 0 — all green; otherwise the list of failed tests. Usage: bash tests/run_all.sh
cd "$(dirname "$0")/.." || exit 1
unset TELEGRAM_STATE_DIR MILA_OUTBOX MILA_OWNER_CHAT   # tests never write into a real send queue
bad=(); n=0
run() { n=$((n+1)); local out; out=$("$@" 2>&1); local rc=$?
  local last; last=$(printf '%s\n' "$out" | grep -v '^\s*$' | tail -1)
  if [ $rc -eq 0 ] && ! printf '%s' "$last" | grep -Eq '❌|FAIL|итог ([0-9]+)/([0-9]+)' || printf '%s' "$last" | grep -Eq 'итог ([0-9]+)/\1$|итого: ([0-9]+) из \2$'; then
    printf '✅ %-55s %s\n' "$*" "$last"
  else printf '❌ %-55s %s\n' "$*" "$last"; bad+=("$*"); fi; }
while IFS= read -r t; do
  case "$t" in *.sh) run bash "$t" ;; *.py) run python3 "$t" ;; esac
done < <(git ls-files | grep -E '(^|/)test_[^/]*\.(sh|py)$' | sort)
run python3 tools/check_frontmatter.py skills templates
echo; [ ${#bad[@]} -eq 0 ] && { echo "ALL GREEN · $n"; exit 0; } || { echo "FAILED ${#bad[@]}/$n: ${bad[*]}"; exit 1; }
