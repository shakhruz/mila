#!/usr/bin/env bash
# Alias (v1.4.0): skills/naglyadno/scripts/shot.sh → skills/visual/scripts/shot.sh. Removed in v1.6.0.
exec bash "$(cd "$(dirname "$0")" && pwd)/../../visual/scripts/shot.sh" "$@"
