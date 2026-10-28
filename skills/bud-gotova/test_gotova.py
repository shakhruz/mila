#!/usr/bin/env python3
"""Сценарий: мастер-класс через 3 часа. Wi-Fi зала «вроде есть» — не готова; нехватка без «кто» — названа; карточка хозяину —
только его пункт; после живой пробы и закрытой нехватки — готова."""
import json, os, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from gotova import check
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
d = {"event": "мастер-класс клиента X", "at": "2026-11-01T18:00:00+05:00",
     "items": {"цель": "20 человек проходят QR-вход", "люди": "список гостей, файл guests.csv", "материалы": "дека v3, PDF, ссылка открыта 15:02",
               "инструменты": "интернет в зале вроде есть", "вопросы": "3 вопроса с ответами в deck-notes.md", "шаг": "кнопка «записаться» в боте"},
     "gaps": [{"what": "пароль от Wi-Fi зала", "who": "хозяин", "by": "2026-11-01T15:00:00+05:00"}, {"what": "запасной ноутбук", "who": "", "by": ""}]}
r = check(d, now=__import__("datetime").datetime.fromisoformat("2026-11-01T12:00:00+05:00"))
chk("нет пункта «запасной» — назван", r["missing"] == ["запасной"], r)
chk("«вроде есть» — не улика", r["weak"] == ["инструменты"], r)
chk("не готова, пока есть нехватки", r["ready"] is False)
chk("нехватка без «кто» и «к когда» — названа", r["gaps_without_owner_or_time"] == ["запасной ноутбук"], r)
chk("карточка хозяину — только его пункт (пароль Wi-Fi), без моего", "пароль от Wi-Fi зала" in r["owner_card"] and "ноутбук" not in r["owner_card"], r["owner_card"])
d["items"]["инструменты"] = "Wi-Fi зала: живая проба 12:40, QR открыл вход с телефона"; d["items"]["запасной"] = "раздача с телефона, проверена 12:45"; d["gaps"] = []
r = check(d)
chk("после живой пробы и без нехваток — готова", r["ready"] is True, r)
d["gaps"] = [{"what": "печать бейджей", "who": "я", "by": "2026-01-01T10:00:00+05:00"}]
chk("просроченная нехватка — названа", check(d)["gaps"][0]["problem"] == ["просрочено"], check(d))
p = os.path.join(tempfile.mkdtemp(), "i.json"); json.dump(d, open(p, "w"), ensure_ascii=False)
rc = subprocess.run([sys.executable, os.path.join(H, "gotova.py"), "check", p], capture_output=True, text=True).returncode
chk("командная строка: не готова — код 1", rc == 1, rc)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
