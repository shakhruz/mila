#!/usr/bin/env bash
# Прогон «как GitHub Actions» одной командой (CI-TZ-2810: у нас зелено, в CI красно — пояс и пустой HOME):
# чистый HOME, CI=true, пояс UTC и ещё один с летним временем. Пакеты Python пользователя видны через PYTHONPATH.
# Usage: bash tests/run_ci_local.sh [пояс …]   (по умолчанию UTC America/Los_Angeles)
cd "$(dirname "$0")/.." || exit 1
US="$(python3 -m site --user-site 2>/dev/null)"
zones=("$@"); [ ${#zones[@]} -eq 0 ] && zones=(UTC America/Los_Angeles)
rc=0
for z in "${zones[@]}"; do
  h="$(mktemp -d)"
  out="$(HOME="$h" TZ="$z" CI=true PYTHONPATH="${US}${PYTHONPATH:+:$PYTHONPATH}" bash tests/run_all.sh 2>&1)"; r=$?
  printf '%-22s %s\n' "$z" "$(printf '%s\n' "$out" | tail -1)"
  [ $r -ne 0 ] && { printf '%s\n' "$out" | grep '^❌'; rc=1; }
  rm -rf "$h"
done
exit $rc
