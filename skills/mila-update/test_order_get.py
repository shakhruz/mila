#!/usr/bin/env python3
"""order_get (Качество 17:13): «Что получите» — по строке с каждой версии, сначала выпуск x.y.0, потом патчи от свежего; вторые строки — после."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); os.environ.setdefault("MILA_HOME", "/nonexistent-home")
import update as U
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
get = [("v1.6.2", "a1"), ("v1.6.1", "b1"), ("v1.6.1", "b2"), ("v1.6.0", "c1"), ("v1.6.0", "c2"), ("v1.6.0", "c3"), ("v1.5.3", "d1")]
o = [l for v, l in U.order_get(get)]
chk("первая строка — из v1.6.0 (выпуск x.y.0), не из свежего патча", o[0] == "c1", o)
chk("сначала по одной с каждой версии: c1, a1, b1, d1", o[:4] == ["c1", "a1", "b1", "d1"], o)
chk("потом вторые строки: c2, b2; потом c3", o[4:] == ["c2", "b2", "c3"], o)
chk("ничего не потеряно и не задвоено", sorted(o) == sorted(l for v, l in get), o)
chk("пусто — пусто", U.order_get([]) == [])
o2 = [v for v, l in U.order_get([("v2.0.0", "x"), ("v1.9.0", "y"), ("v1.9.1", "z")])]
chk("два выпуска x.y.0 — свежий первым, патч после", o2 == ["v2.0.0", "v1.9.0", "v1.9.1"], o2)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
