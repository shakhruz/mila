#!/usr/bin/env bash
# SHELF-CHECK-1018: install-skill не ставит навык, у которого SKILL.md называет scripts/… (и др.), а файлов в папке нет;
# --allow-missing — ставит осознанно и показывает missing; файлы чужого навыка и примеры-заглушки не мешают; все навыки ядра и пакетов — полные.
set -u; unset TELEGRAM_STATE_DIR MILA_OUTBOX MILA_OWNER_CHAT
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"; mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
S="$T/shelf/urok"; mkdir -p "$S"
cat > "$S/SKILL.md" <<'M'
---
name: urok
description: test
---
Запуск: `python3 ~/.claude/skills/urok/scripts/render.py examples/t2.json`, голос — scripts/tts_ru.py.
Шрифт — fonts/Nunito.ttf. Чужое: ~/.claude/skills/genimage/scripts/gen.py. Пример пути: scripts/<имя>.py.
M
$U install-skill "$S" --from test > "$T/o.json" 2>&1
chk "только SKILL.md → отказ, «навык неполный»" "grep -q 'навык неполный' $T/o.json && [ ! -e $CLAUDE_CONFIG_DIR/skills/urok ]"
chk "список missing: render.py, tts_ru.py, t2.json, Nunito; без чужого gen.py и заглушки <имя>" "python3 -c \"import json;m=json.load(open('$T/o.json'))['missing'];assert set(m)=={'scripts/render.py','scripts/tts_ru.py','examples/t2.json','fonts/Nunito.ttf'},m\""
$U install-skill "$S" --from test --allow-missing > "$T/o2.json"
chk "--allow-missing: поставлен, в ответе missing" "[ -f $CLAUDE_CONFIG_DIR/skills/urok/SKILL.md ] && grep -q '\"missing\"' $T/o2.json"
mkdir -p "$S/scripts" "$S/examples" "$S/fonts"; touch "$S/scripts/render.py" "$S/scripts/tts_ru.py" "$S/examples/t2.json" "$S/fonts/Nunito.ttf"
$U install-skill "$S" --from test > "$T/o3.json"
chk "папка целая → поставлен без missing" "grep -q '\"ok\": true' $T/o3.json && ! grep -q missing $T/o3.json"
bad=""; for d in "$REPO"/skills/*/ "$REPO"/packs/*/*/; do [ -f "$d/SKILL.md" ] || continue
  m=$(python3 -c "import sys;sys.path.insert(0,'$HERE');import importlib.util as u;s=u.spec_from_file_location('up','$HERE/update.py');x=u.module_from_spec(s);s.loader.exec_module(x);print(','.join(x.missing_refs('$d')))" 2>/dev/null)
  [ -n "$m" ] && bad="$bad $(basename "$d"):$m"; done
chk "все навыки ядра и пакетов — полные${bad:+ (нет:$bad)}" "[ -z \"$bad\" ]"
echo "итог $ok/$n"; rm -rf "$T"
