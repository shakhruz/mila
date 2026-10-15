#!/bin/bash
# transcribe-voice.sh <audiofile> — расшифровка голосового в контейнере Компаньона (14.09.2026).
# Groq whisper-large-v3 с автоопределением языка и вторым проходом на узбекском —
# та же схема, что у администратора на Маке и у агентов. Ключ — GROQ_API_KEY из env контейнера.
# Никогда не печатает ключ. Пусто → "[empty]" (приёмник покажет «расшифровка пустая»).
set -euo pipefail
[ -n "${1:-}" ] || { echo "usage: transcribe-voice.sh <audiofile>" >&2; exit 1; }
KEY="${GROQ_API_KEY:-}"
[ -n "$KEY" ] || { echo "[нет ключа Groq в env]" >&2; exit 1; }
API="https://api.groq.com/openai/v1/audio/transcriptions"
SRC="$1"
case "$SRC" in
  *.oga) TMP="$(mktemp -t voiceXXXX).ogg"; cp "$SRC" "$TMP"; trap 'rm -f "$TMP"' EXIT; SRC="$TMP" ;;
esac
ask() {
  if [ -n "${2:-}" ]; then
    curl -s --max-time 90 -X POST "$API" -H "Authorization: Bearer $KEY" -F "file=@$1" -F "model=whisper-large-v3" -F "language=$2" -F "response_format=verbose_json"
  else
    curl -s --max-time 90 -X POST "$API" -H "Authorization: Bearer $KEY" -F "file=@$1" -F "model=whisper-large-v3" -F "response_format=verbose_json"
  fi
}
pick() { python3 -c '
import sys, json
try: d = json.load(sys.stdin)
except Exception: print("\t"); sys.exit()
print((d.get("language") or "") + "\t" + (d.get("text") or "").strip())'; }
OUT=$(ask "$SRC" "" | pick)
LANG="${OUT%%$'\t'*}"; TEXT="${OUT#*$'\t'}"
case "$LANG" in
  uzbek|uz|azerbaijani|az|kazakh|kk|kyrgyz|ky|turkmen|tk|tatar|tt|turkish|tr|bashkir|ba|tajik|tg|uighur|ug|chuvash|cv|"")
    OUT2=$(ask "$SRC" "uz" | pick); TEXT2="${OUT2#*$'\t'}"; [ -n "$TEXT2" ] && TEXT="$TEXT2" ;;
esac
# D-NNNN (10.10): whisper путает имена продукта («Милодипити.io», «Milo Companion», «хайку 55»).
# Подсказка prompt проверена и отвергнута: на голосовом 835 съела 30 % текста и вставила себя в ответ.
# Поэтому только точная замена известных искажений после расшифровки; смысл не трогаем.
TEXT=$(printf '%s' "$TEXT" | python3 -c '
import re, sys
t = sys.stdin.read()
for a, b in [
    (r"(?i)\bмилодипити\.?\s*io\b", "milagpt.io"), (r"(?i)\bмилодипити\b", "MilaGPT"),
    (r"(?i)\b(?:mewl|meal|milo|mela)\s?gpt\b", "MilaGPT"), (r"(?i)\bмила\s?(?:гпт|джипити|джи пи ти)\b", "MilaGPT"),
    (r"\bMilo (Companion|Telegram|Pay)\b", r"Mila \1"), (r"(?i)\bхайку\s*5[.,]?5\b", "Haiku 5.5"),
]:
    t = re.sub(a, b, t)
sys.stdout.write(t)')
[ -n "$TEXT" ] && printf '%s\n' "$TEXT" || echo "[empty]"
