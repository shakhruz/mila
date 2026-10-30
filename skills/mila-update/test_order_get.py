#!/usr/bin/env python3
"""order_get: «Что получите» — по строке с каждой версии, сначала выпуск x.y.0, потом патчи от свежего; вторые строки — после."""
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
import tempfile
d = tempfile.mkdtemp()
secs = "".join("## %s · 28.10 — x\n**Для хозяина**\n- Польза %s раз.\n- Польза %s два.\n\n" % (v, v, v) for v in ("v1.2.2", "v1.2.1", "v1.2.0", "v1.1.9"))
open(os.path.join(d, "CHANGELOG.md"), "w").write("# CHANGELOG\n\n" + secs)
got = U.changelog_since(d, "v1.1.8", "v1.2.2")
chk("changelog_since не режет до раскладки: все 8 строк четырёх версий", len(got) == 8, got)
o3 = [l for v, l in U.order_get(got)[:6]]
chk("после раскладки и обрезки до 6 — v1.2.0 первой и строка самой старой версии v1.1.9 на месте", o3[0].startswith("Польза v1.2.0") and any("v1.1.9" in l for l in o3), o3)
L = "Обновления теперь понятны: перед обновлением вижу и показываю вам план — что получите, что изменится, что не тронется, риск"
chk("длинная строка — суть до двоеточия, ≤ 90", U.short_line(L) == "Обновления теперь понятны." and len(U.short_line(L)) <= 90, U.short_line(L))
M = "Самопроверка находит то, что включено, но не работает, и подсказывает, что сделать, где и кому сказать, и сколько это займёт времени у вас"
chk("без двоеточия и тире — по слову с «…», ≤ 90", U.short_line(M).endswith("…") and len(U.short_line(M)) <= 90 and " " + U.short_line(M)[:-1].split()[-1] in " " + M, U.short_line(M))
chk("короткая — как есть", U.short_line("Новый сторож отправки.") == "Новый сторож отправки.")
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
