#!/usr/bin/env bash
# Alias (v1.4.0): skills/znakomstvo/fuel.sh → skills/onboarding/fuel.sh. Removed in v1.7.0.
exec bash "$(cd "$(dirname "$0")" && pwd)/../onboarding/fuel.sh" "$@"
