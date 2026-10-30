#!/usr/bin/env bash
# Прогон «как GitHub Actions» одной командой (CI-TZ-2810: у нас зелено, в CI красно — пояс и пустой HOME):
# чистый HOME, CI=true, пояс UTC и ещё один с летним временем, пакеты Python — из workflow (CI-PIP-3010).
# Usage: bash tests/run_ci_local.sh [пояс …]   (по умолчанию UTC America/Los_Angeles)
cd "$(dirname "$0")/.." || exit 1
# CI-PIP-3010 (Качество 30.10: test_folders зелёный тут, красный в GitHub — telethon стоял у пользователя, в CI его нет):
# Python-пакеты — ровно из строки «pip install» в .github/workflows/tests.yml, в своём venv (кэш по строке). Нет сети — громко
# предупреждаю и беру пакеты пользователя, как раньше.
PIPLINE="$(grep -m1 -oE 'pip install [^#]*' .github/workflows/tests.yml | sed 's/^pip install //; s/ *$//')"
VENV="${TMPDIR:-/tmp}/mila-ci-venv-$(printf '%s' "$PIPLINE" | sha256sum | cut -c1-12)"
PYPATH_EXTRA=""
if [ -x "$VENV/bin/python3" ] || { python3 -m venv "$VENV" >/dev/null 2>&1 && "$VENV/bin/pip" install -q $PIPLINE >/dev/null 2>&1; }; then
  export PATH="$VENV/bin:$PATH"; echo "пакеты Python — как в CI: $PIPLINE"
else
  rm -rf "$VENV"; PYPATH_EXTRA="$(python3 -m site --user-site 2>/dev/null)"
  echo "⚠️  venv с пакетами CI не собрался (нет сети?) — беру пакеты пользователя: зелёное здесь может быть красным в GitHub"
fi
zones=("$@"); [ ${#zones[@]} -eq 0 ] && zones=(UTC America/Los_Angeles)
rc=0
for z in "${zones[@]}"; do
  h="$(mktemp -d)"
  out="$(HOME="$h" TZ="$z" CI=true PYTHONPATH="${PYPATH_EXTRA}${PYTHONPATH:+:$PYTHONPATH}" bash tests/run_all.sh 2>&1)"; r=$?
  printf '%-22s %s\n' "$z" "$(printf '%s\n' "$out" | tail -1)"
  [ $r -ne 0 ] && { printf '%s\n' "$out" | grep '^❌'; rc=1; }
  rm -rf "$h"
done
exit $rc
