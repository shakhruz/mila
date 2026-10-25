#!/usr/bin/env python3
"""Пробы Разработки к ENV_KV (mila-export c): переменные кода с *_key — не секрет; настоящие env — секрет. Usage: python3 proby_envkv.py <папка с mila_export.py>"""
import os, sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
import mila_export as M
ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)
hits = lambda t: [k for _, k in M.scan_bytes(t.encode(), "t.py")]
for t in ('idempotency_key="mila:-100500:7"', "sort_key=lambda1x2y3z", 'cache_key = "user:42:v2"', 'api_key = os.environ["X"]'):
    chk("не секрет: %s" % t, not hits(t))
for t in ("OPENROUTER_API_KEY=" + "sk-" + "or-v1-" + "abc123def456", "DB_PASS" + "WORD=Qwerty123!x", "TELEGRAM_BOT_TOKEN=" + "x9" * 8):
    chk("секрет: %s…" % t[:18], hits(t))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
