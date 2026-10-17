#!/bin/sh
# fuel.sh — счётчик топлива: сколько осталось на ключе OpenRouter. Печатает только числа, ключ не печатает.
# Вывод: «FUEL left=3.91 limit=5.00 used=1.09 low=no src=or|est» (low=yes, когда осталось < $1).
# Счётчик OpenRouter отстаёт на десятки минут, поэтому used = max(OpenRouter, оценка по моим транскриптам
# по прайсу Sonnet 5.5: вход $2 · запись кэша $2,5 · чтение кэша $0,2 · выход $10 за 1М). Нет ключа/сети — «FUEL unknown».
CL="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
# вход по подписке хозяина (нет ANTHROPIC_BASE_URL, есть claudeAiOauth) — я не на запасе.
# OPENROUTER_API_KEY при этом остаётся ключом инструментов (картинки, голос) — его баланс не «моё топливо».
if [ -z "${ANTHROPIC_BASE_URL:-}" ] && grep -q claudeAiOauth "$CL/.credentials.json" 2>/dev/null; then
  echo "FUEL sub (подписка хозяина подключена: строку ⛽ не пишу, о запасе не говорю)"; exit 0
fi
[ -n "${OPENROUTER_API_KEY:-}" ] || { echo "FUEL unknown (нет ключа в окружении)"; exit 0; }
curl -s -m 15 https://openrouter.ai/api/v1/key -H "Authorization: Bearer $OPENROUTER_API_KEY" | python3 -c '
import sys, json, glob, os
cl = sys.argv[1]
try:
    d = json.load(sys.stdin)["data"]
    lim, use = d.get("limit"), float(d.get("usage") or 0)
except Exception:
    print("FUEL unknown (ответ не разобран)"); sys.exit(0)
if lim is None:
    print("FUEL unknown (у ключа нет лимита)"); sys.exit(0)
seen = {}
for f in glob.glob(os.path.join(cl, "projects", "*", "*.jsonl")):
    try:
        for l in open(f, encoding="utf-8", errors="ignore"):
            if "\"usage\"" not in l: continue
            try: r = json.loads(l)
            except Exception: continue
            m = r.get("message") or {}
            u = m.get("usage")
            if r.get("type") == "assistant" and u:
                seen[m.get("id") or r.get("uuid")] = u
    except Exception:
        pass
est = sum(u.get("input_tokens", 0) * 2e-6 + u.get("cache_creation_input_tokens", 0) * 2.5e-6 + u.get("cache_read_input_tokens", 0) * 0.2e-6 + u.get("output_tokens", 0) * 1e-5 for u in seen.values())
src = "est" if est > use else "or"
used = max(use, est); left = max(0.0, float(lim) - used)
print("FUEL left=%.2f limit=%.2f used=%.2f low=%s src=%s" % (left, float(lim), used, "yes" if left < 1 else "no", src))
' "$CL"
