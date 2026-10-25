#!/usr/bin/env python3
"""Пробы Разработки к pd_vault (25.10): что ловить и что не трогать; + слово-подсказка не вплотную (b). Usage: python3 proby_pd_razrabotka.py <папка с pd_vault.py>"""
import os, sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
import pd_vault as P
ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)
kinds = lambda t: [x[2] for x in P.find(t)]
# ловить (сейчас пропускает)
chk("«звоните 901234567» — телефон", "phone" in kinds("звоните 901234567"))
chk("«позвоните 901234567» — телефон", "phone" in kinds("позвоните 901234567"))
chk("«whatsapp 901234567» — телефон", "phone" in kinds("whatsapp 901234567"))
chk("«aloqa uchun 901234567» — телефон", "phone" in kinds("aloqa uchun 901234567"))
# не трогать (сейчас трогает)
chk("«номер 335550101 в телеграме» — не телефон (это id Telegram)", "phone" not in kinds("номер 335550101 в телеграме"))
chk("«номер чата 335550101» — не телефон", "phone" not in kinds("номер чата 335550101"))
# уже верно — держать
for t in ("Telegram id 335550101, chat -100" + "1234567890", "номер заказа 901234567", "ИНН 301234567", "счёт 20208000900123456001", "время 10:30 – 12:45, комната 905"):
    chk("не трогать: %s" % t, not kinds(t))
for t, k in (("позвоните: 90 123 45 67", "phone"), ("8 (90) 123-45-67", "phone"), ("паспорт ав 1234567", "passport"), ("ПИНФЛ 31234567890123", "pinfl")):
    chk("ловить: %s" % t, k in kinds(t))
k = lambda t: [x[2] for x in P.find(t)]
for t in ("телефон для связи 901234567", "номер для связи 901234567", "мой рабочий номер 901234567", "aloqa uchun telefon raqami 901234567"):
    chk("ловить: %s" % t, "phone" in k(t))
for t in ("номер заказа 901234567", "номер чата 335550101", "id 901234567"):
    chk("не трогать: %s" % t, "phone" not in k(t))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
