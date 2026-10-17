#!/usr/bin/env bash
# INSTALL-HOOKS-1017: каждый хук, который install.sh прописал в settings.json, лежит файлом (иначе Stop-хук без файла = код 2 = сессия не останавливается).
set -u; unset TELEGRAM_STATE_DIR
REPO="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; mkdir -p "$T/home/.claude"
HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" PATH=/usr/bin:/bin:/usr/local/bin bash "$REPO/install/install.sh" >/dev/null 2>&1
ok=0; n=0; chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
miss=$(python3 - "$T/home/.claude/settings.json" <<'PY'
import json, os, sys, shlex
d = json.load(open(sys.argv[1])); miss = []
for ev, lst in d.get("hooks", {}).items():
    for e in lst:
        for h in e.get("hooks", []):
            parts = shlex.split(h.get("command", "")); f = next((p for p in parts if p.endswith((".py", ".sh", ".ts"))), None)
            if f and not os.path.isfile(f): miss.append(ev + ":" + f)
print(" ".join(miss))
PY
)
chk "все хуки из settings.json лежат файлами" "[ -z \"$miss\" ]"
chk "Stop: reply-required.py установлен" "[ -x $T/home/.claude/hooks/reply-required.py ]"
chk "PostToolUse: pd-mask.py установлен" "[ -x $T/home/.claude/hooks/pd-mask.py ]"
chk "ключ хранилища ПДн создан, 600" "[ \"\$(stat -c %a $T/home/.config/mila/pd.key 2>/dev/null)\" = 600 ]"
[ -n "$miss" ] && echo "нет файлов: $miss"
echo "итог $ok/$n"; rm -rf "$T"
