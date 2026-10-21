#!/usr/bin/env python3
"""fit_text: перенос, кегль, высота, совет — на шрифте DejaVu из системы (нет шрифта — пропуск, не провал)."""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"]
F = next((f for f in FONTS if os.path.isfile(f)), None)
try:
    import PIL  # noqa
except ImportError:
    F = None
if not F:
    print("итог 0/0 (нет DejaVu или Pillow — пропуск)"); sys.exit(0)
from fit_text import fit, advise
ok = n = 0
def chk(name, c, got=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else f"  → {got!r}"))
r = fit("Короткая подпись", F, 64, 30, 900, 2); chk("короткое — 1 строка, крупный кегль", r and r[0] == 64 and len(r[1]) == 1, r)
r = fit("Bugun choy ichamizmi, oʻrtoq? Albatta ichamiz, choy tayyor", F, 64, 30, 900, 2); chk("длинное — перенос в 2 строки, кегль меньше", r and len(r[1]) == 2 and r[0] < 64, r)
chk("слишком длинное — None", fit(" ".join(["слово"] * 40), F, 64, 30, 460, 2) is None)
chk("«\\n» — жёсткий перенос", fit("Две\nстроки", F, 64, 30, 900, 2)[1] == ["Две", "строки"])
r6 = fit("один два три четыре пять шесть семь", F, 64, 30, 300, 6); r7 = fit("один два три четыре пять шесть семь", F, 64, 30, 300, 6, max_height=160)
chk("высота зоны: тот же текст при низкой зоне — мельче или None", r6 and (r7 is None or (r7[0] < r6[0] and len(r7[1]) * r7[0] * 1.18 <= 160)), (r6, r7))
a = advise(" ".join(["слово"] * 40), F, 64, 30, 460, 2); chk("совет — «сократите до K слов»", "сократите до" in a, a)
p = subprocess.run([sys.executable, os.path.join(HERE, "fit_text.py"), " ".join(["слово"] * 40), "--font", F, "--size", "64", "--min", "30", "--width", "460"], capture_output=True, text=True)
chk("CLI: не влезает — код 4 и совет", p.returncode == 4 and "сократите до" in p.stdout, (p.returncode, p.stdout))
print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
