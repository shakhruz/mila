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
chk("«звоните 9012" "34567» — телефон", "phone" in kinds("звоните 9012" "34567"))
chk("«позвоните 9012" "34567» — телефон", "phone" in kinds("позвоните 9012" "34567"))
chk("«whatsapp 9012" "34567» — телефон", "phone" in kinds("whatsapp 9012" "34567"))
chk("«aloqa uchun 9012" "34567» — телефон", "phone" in kinds("aloqa uchun 9012" "34567"))
# не трогать (сейчас трогает)
chk("«номер 3355" "50101 в телеграме» — не телефон (это id Telegram)", "phone" not in kinds("номер 3355" "50101 в телеграме"))
chk("«номер чата 3355" "50101» — не телефон", "phone" not in kinds("номер чата 3355" "50101"))
# уже верно — держать
for t in ("Telegram id 3355" "50101, chat -100" + "12345" "67890", "номер заказа 9012" "34567", "ИНН 3012" "34567", "счёт 20208" "00090" "01234" "56001", "время 10:30 – 12:45, комната 905"):
    chk("не трогать: %s" % t, not kinds(t))
for t, k in (("позвоните: 90 123 45 67", "phone"), ("8 (90) 123-45-67", "phone"), ("паспорт ав 1234567", "passport"), ("ПИНФЛ 3123456" "7890123", "pinfl")):
    chk("ловить: %s" % t, k in kinds(t))
k = lambda t: [x[2] for x in P.find(t)]
for t in ("телефон для связи 9012" "34567", "номер для связи 9012" "34567", "мой рабочий номер 9012" "34567", "aloqa uchun telefon raqami 9012" "34567"):
    chk("ловить: %s" % t, "phone" in k(t))
for t in ("номер заказа 9012" "34567", "номер чата 3355" "50101", "id 9012" "34567"):
    chk("не трогать: %s" % t, "phone" not in k(t))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
