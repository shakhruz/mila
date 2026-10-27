#!/usr/bin/env python3
"""test_limit_probe по часам (CI 27.10, Качество): тот же тест при «сейчас» = 10:00, 14:10, 14:30, 15:00, 23:50, 00:10 по Ташкенту.
Зашитое «resets 2pm» падало с 14:00 до ≈14:35 — тест не должен зависеть от того, когда его запускают."""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
RUN = r'''
import sys, time, datetime as dt, zoneinfo, runpy
h, m = map(int, sys.argv[1].split(":"))
want = dt.datetime.now(zoneinfo.ZoneInfo("Asia/Tashkent")).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()
off = want - time.time(); real = time.time; time.time = lambda: real() + off
sys.argv = [sys.argv[2]]; runpy.run_path(sys.argv[0], run_name="__main__")
'''
for hm in ("10:00", "14:10", "14:30", "15:00", "23:50", "00:10"):
    p = subprocess.run([sys.executable, "-c", RUN, hm, os.path.join(HERE, "test_limit_probe.py")], capture_output=True, text=True, timeout=120)
    last = ([l for l in p.stdout.splitlines() if l.strip()] or ["(пусто) " + p.stderr[-200:]])[-1]
    n += 1; good = last == "итог 8/8"; ok += good; print(("✅ " if good else "❌ ") + "«сейчас» %s по Ташкенту → %s" % (hm, last))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
