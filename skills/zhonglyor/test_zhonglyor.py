#!/usr/bin/env python3
"""Сценарий: делаю деку, осталось 2 шага. Хозяин пишет подряд: «сделай пост к пятнице», «оплата клиента X не проходит»,
«разбери 30 чатов за неделю», «попроси видео-Милу ролик», «оплати домен»."""
import json, os, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from zhonglyor import when, HOW
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
chk("пост к пятнице, дека почти готова (2 шага) — доделываю деку", when(False, 2) == "finish-first")
chk("оплата клиента не проходит — срочно, беру сейчас, хоть дека и почти готова", when(True, 2) == "now")
chk("текущее далеко от конца (8 шагов), новое на сегодня — в очередь сегодня", when(False, 8, "today") == "queue-today")
chk("ничего не в работе, несрочное — в очередь недели", when(False, None) == "queue-week")
chk("30 чатов — параллельно, и только если хозяин разрешил", "параллельно" in HOW["bulk"] and "разрешил" in HOW["bulk"])
chk("ролик — записка видео-Миле, не делаю сама", HOW["other-mila"].startswith("записка"))
chk("оплатить домен — сама не плачу, спрашиваю «да»", "сама не делаю" in HOW["money"])
chk("текст наружу — не лёгкой моделью", "не лёгкой" in HOW["text-out"])
r = subprocess.run([sys.executable, os.path.join(H, "zhonglyor.py"), "when", "--urgent", "--current-left", "1"], capture_output=True, text=True)
chk("командная строка: срочное → now", json.loads(r.stdout)["when"] == "now", r.stdout)
r = subprocess.run([sys.executable, os.path.join(H, "zhonglyor.py"), "how", "--kind", "магия"], capture_output=True, text=True)
chk("неизвестный вид — отказ со списком", r.returncode != 0 and "short" in r.stderr, r.stderr)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
