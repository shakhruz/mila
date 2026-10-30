#!/usr/bin/env bash
# All core tests in one command (plan 17.10, item 5): every test_* in the repo + frontmatter. Sandboxed tests only, nothing outside temp dirs.
# Exit 0 — all green; otherwise the list of failed tests. Usage: bash tests/run_all.sh
cd "$(dirname "$0")/.." || exit 1
unset TELEGRAM_STATE_DIR MILA_OUTBOX MILA_OWNER_CHAT   # tests never write into a real send queue
bad=(); n=0
RUN_TMP="$(mktemp -d)"; trap 'chmod -R u+w "$RUN_TMP" 2>/dev/null; rm -rf "$RUN_TMP"' EXIT   # every test gets its own TMPDIR, removed after it: repeated runs leave nothing in /tmp
run() { n=$((n+1)); local out td; td="$(mktemp -d "$RUN_TMP/t.XXXXXX")"; out=$(TMPDIR="$td" "$@" 2>&1 </dev/null); local rc=$?; chmod -R u+w "$td" 2>/dev/null; rm -rf "$td"   # stdin closed: a test must not eat the file list of the while-read loop
  local last; last=$(printf '%s\n' "$out" | grep -v '^\s*$' | tail -1)
  if printf '%s' "$last" | grep -Eq 'итог 0/0'; then   # test skipped itself (no font, no tool): visible, and a failure in CI
    if [ -n "$CI" ]; then printf '❌ %-55s %s (skipped in CI)\n' "$*" "$last"; bad+=("$*"); else printf '⚠️  %-55s %s\n' "$*" "$last"; fi; return; fi
  if [ $rc -eq 0 ] && ! printf '%s' "$last" | grep -Eq '❌|FAIL|итог ([0-9]+)/([0-9]+)' || printf '%s' "$last" | grep -Eq 'итог ([0-9]+)/\1$|итого: ([0-9]+) из \2$'; then
    printf '✅ %-55s %s\n' "$*" "$last"
  else printf '❌ %-55s %s\n' "$*" "$last"; bad+=("$*"); fi; }
while IFS= read -r t; do
  case "$t" in *.sh) run bash "$t" ;; *.py) run python3 "$t" ;; esac
done < <(git ls-files | grep -E '(^|/)test_[^/]*\.(sh|py)$' | sort)
run python3 tools/check_frontmatter.py skills templates
echo; [ ${#bad[@]} -eq 0 ] && { echo "ALL GREEN · $n"; exit 0; } || { echo "FAILED ${#bad[@]}/$n: ${bad[*]}"; exit 1; }
