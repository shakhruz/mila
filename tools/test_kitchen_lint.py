#!/usr/bin/env python3
"""kitchen_lint: в публичном ядре нет следов кухни (коды задач, номера чужих сообщений, время приёмок, номера раскаток);
--fix убирает только метку и пустые от неё скобки/знаки — чужие «()» в коде не трогает."""
import os, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import kitchen_lint as K
ok = n = 0
def chk(m, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + repr(x)[:200]))
R = os.path.dirname(H)
r = subprocess.run([sys.executable, os.path.join(H, "kitchen_lint.py")], capture_output=True, text=True, cwd=R)
chk("репозиторий: следов кухни 0", r.returncode == 0 and "следов кухни: 0" in r.stdout, r.stdout[-400:])
code = "AB" + "C-1234"; when = "Качество" + " 12:34"; who = "владелец" + " 12345"
for src, want in [
    ('x = text.strip()[:120]   # %s\n' % code, 'x = text.strip()[:120]\n'),
    ('# %s: сторож падает — сообщение не уходит\n' % code, '# сторож падает — сообщение не уходит\n'),
    ('"""%s (%s): три числа"""\n' % (code, who), '"""три числа"""\n'),
    ('f()   # слабое место (%s: {} — не улика)\n' % when, 'f()   # слабое место ({} — не улика)\n'),
    ('если пусто (%s)\n' % when, 'если пусто\n'),
    ('ROLL' + 'OUT №41, правило\n', 'правило\n'),
    ('print("ok")\n', 'print("ok")\n'),
    ('call(a, b)  # обычный\n', 'call(a, b)  # обычный\n'),
]:
    got = K.clean(src)
    chk("clean: %s" % want.strip()[:50], got == want, got)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
