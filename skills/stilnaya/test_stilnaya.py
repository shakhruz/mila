#!/usr/bin/env python3
"""Сценарий: дека для инвесторов. Три задания независимы (никто не видит чужих мнений). Два взгляда сказали «любитель»,
главную правку двое назвали одинаково — она главная; после правки все «профи» — готово. Двух взглядов мало."""
import json, os, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from stilnaya import prompts, svod
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
p = prompts("инвесторы ранней стадии", "назначить вторую встречу")
chk("три задания: бренд, тренды, доверие", [x["role"] for x in p] == ["бренд", "тренды", "доверие"], p)
chk("в каждом — аудитория и цель", all("инвесторы ранней стадии" in x["prompt"] and "вторую встречу" in x["prompt"] for x in p))
chk("каждый не видит чужих мнений, и в задании нет текста других ролей", all("не видишь" in x["prompt"] and sum(r in x["prompt"] for r in ("арт-директор", "визуальные тренды", "представитель аудитории")) == 1 for x in p))
A = [{"role": "бренд", "verdict": "любитель", "main_fix": "один шрифт и сетка 12 колонок", "minor": ["цвета бренда"]},
     {"role": "тренды", "verdict": "профи", "main_fix": "убрать стоковые 3D-фигуры", "minor": []},
     {"role": "доверие", "verdict": "любитель", "main_fix": "один шрифт и сетка 12 колонок", "minor": ["цифры с источником", "команда на слайде 2"]}]
r = svod(A)
chk("двое «любитель» — не готово, названы", r["ready"] is False and r["amateur_by"] == ["бренд", "доверие"], r)
chk("главная правка — та, что назвали двое", r["main_fix"] == "один шрифт и сетка 12 колонок" and r["agree"] == ["один шрифт и сетка 12 колонок"], r)
chk("второстепенных — не больше двух, без главной", len(r["minor"]) == 2 and r["main_fix"] not in r["minor"], r)
B = [dict(a, verdict="профи") for a in A]
chk("после правки все «профи» — готово", svod(B)["ready"] is True)
chk("двух взглядов мало — не готово", svod(B[:2])["ready"] is False)
C = [{"role": "бренд", "verdict": "профи", "main_fix": "x"}, {"role": "тренды", "verdict": "профи", "main_fix": "y"}, {"role": "доверие", "verdict": "профи", "main_fix": "z"}]
chk("все правки разные — главная от «доверия» (аудитория важнее вкуса)", svod(C)["main_fix"] == "z", svod(C))
d = tempfile.mkdtemp(); fs = []
for i, a in enumerate(A):
    f = os.path.join(d, "%d.json" % i); json.dump(a, open(f, "w"), ensure_ascii=False); fs.append(f)
rc = subprocess.run([sys.executable, os.path.join(H, "stilnaya.py"), "svod", *fs], capture_output=True, text=True).returncode
chk("командная строка: «любитель» — код 1", rc == 1, rc)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
