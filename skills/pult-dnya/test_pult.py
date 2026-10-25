#!/usr/bin/env python3
"""Пульт дня: правила навыка в скрипте — песочница. python3 test_pult.py"""
import json, os, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(); ok = n = 0
def chk(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + str(x)[:200]))
def b(*a, day="2026-10-22", lang="ru", now="1792641600"):
    r = subprocess.run([sys.executable, os.path.join(H, "scripts", "day_board.py"), *a, "--lang", lang], capture_output=True, text=True,
                       env=dict(os.environ, MILA_WORK=T, DAY_BOARD_DATE=day, DAY_BOARD_NOW=now))
    return r.returncode, json.loads(r.stdout)
rc, o = b("add", "--text", "Discord-мост", "--who", "хозяин")
chk("первое дело — сразу в работу", o["state"] == "now" and o["line"].startswith("№1 беру сразу"), o)
rc, o = b("add", "--text", "Пульт дня", "--who", "Админ", "--why", "Discord к PH раньше")
chk("новое при занятой работе — строка «№N в очередь, беру после №X, потому что …»", o["line"] == "№2 в очередь, беру после №1, потому что Discord к PH раньше", o)
rc, o = b("add", "--text", "Касса упала", "--red")
chk("🔴 — сразу в работу, текущее не трогаем", o["state"] == "now" and "🔴" in o["line"], o)
b("add", "--text", "Третье"); rc, o = b("start", "2")
chk("второе обычное дело в работу — да (🔴 в счёт двух не идёт)", rc == 0, o)
rc, o = b("start", "4")
chk("ещё одно сверх двух — отказ", rc == 1 and "не больше 2" in o["error"], o)
rc, o = b("wait", "2", "--on", "хозяин")
chk("«ждёт» без заданного вопроса — отказ", rc == 1 and "--asked" in o["error"], o)
rc, o = b("wait", "2", "--on", "хозяин", "--asked", "x")
chk("--asked не ссылка и не номер сообщения («x») — отказ", rc == 1, o)
rc, o = b("wait", "2", "--on", "хозяин", "--asked", "2090")
chk("«ждёт» с уликой вопроса — да", rc == 0 and o["state"] == "wait", o)
rc, o = b("done", "1", "--result", "готово")
chk("закрыть без улики — отказ", rc == 1 and "улик" in o["error"], o)
rc, o = b("done", "1", "--evidence", "45bd59d", "--result", "мост на стенде\nлишняя строка")
chk("закрыть с уликой и выводом — да, вывод одной строкой, следующий из очереди назван", rc == 0 and o["next"] == 4, o)
rc, o = b("drop", "4")
chk("снять без причины — отказ", rc == 1, o)
rc, o = b("render")
t = o["text"]
chk("пульт: четыре раздела, улика и вывод у сделанного, вопрос у ждущего", all(k in t for k in ("▶️ В работе", "⏳ Очередь", "🤝 Ждёт ответа", "✅ Сделано"))
    and "№1 Discord-мост · хозяин → мост на стенде · 45bd59d" in t and "вопрос: 2090" in t and "лишняя строка" not in t, t)
rc, o = b("render", now=str(1792641600 + 61 * 60))
chk("«ждёт» дольше часа — 🔴 переспросить или решить сам", "🔴 №2" in o["text"] and "ждёт 61 мин" in o["text"] and "переспросить или решить сам" in o["text"], o["text"])
b("add", "--text", "Позвонить +998901234567 по карте 4111 1111 1111 1111, почта a.b@mail.uz")
rc, o = b("render")
import re as _re
chk("личные данные на пульте: карта ****1111, телефон ⟦тел⟧, почта ⟦почта⟧, ни одной цифры подряд длиннее 4",
    "****1111" in o["text"] and "⟦тел⟧" in o["text"] and "⟦почта⟧" in o["text"] and not _re.search(r"\d{5,}", o["text"].replace(" ", "")), o["text"])
st = open(os.path.join(T, "state", "day-2026-10-22.json"), encoding="utf-8").read()
chk("и в файле дня номера карты и телефона нет", "4111" not in st and "998901234567" not in st, st[:200])
rc, o = b("plan", "--pool", "а; б")
chk("авто-пул меньше 3 — отказ", rc == 1, o)
rc, o = b("plan", "--pool", "а; б; в")
chk("авто-пул 3 дела — в очередь, номера дальше", rc == 0 and o["pool"] == [6, 7, 8], o)
rc, o = b("pin", "--chat", "-100", "--message", "77"); rc, o = b("render")
chk("закреплённое сообщение помнится (для edit_message)", o["pin"] == {"chat_id": "-100", "message_id": "77"}, o)
rc, o = b("evening")
chk("вечер: итог, сделанное с выводом, кто ждёт, перенос", o["text"].startswith("Итог дня 22.10: сделано 1") and "✅ №1 Discord-мост → мост на стенде" in o["text"]
    and "🤝 №2" in o["text"] and "Переносится:" in o["text"], o["text"])
rc, o = b("render", day="2026-10-23")
chk("новый день: незакрытое перенесено «со вчера», нумерация продолжается, закрытого нет", "со вчера" in o["text"] and "Discord-мост" not in o["text"] and "№2 Пульт дня" in o["text"], o["text"])
rc, o = b("add", "--text", "x", day="2026-10-23")
chk("новый день: номер продолжается", o["no"] == 9, o)
rc, o = b("render", lang="en")
chk("en: заголовки по-английски", "📋 Day board" in o["text"] and "▶️ In progress" in o["text"], o["text"][:80])
from importlib import util as _u
_sp = _u.spec_from_file_location("db", os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "day_board.py")); _db = _u.module_from_spec(_sp); _sp.loader.exec_module(_db)
KEEP = ["Заявка №1234567890123456", "ждёт ответа в чате -100" "1234567890", "id 123456789 спросил", "Заявка № 4567"]
chk("маска телефона не ест номер заявки, id чата, id человека (Качество 22.10)", [_db.mask(x) for x in KEEP] == KEEP, [_db.mask(x) for x in KEEP])
PH = ["+998901234567", "+998 90 123 45 67", "90 123-45-67", "(90) 123 45 67", "998901234567", "89161234567", "+7 916 123-45-67"]
chk("телефоны в форме телефона — ⟦тел⟧", all(_db.mask("звонить " + x) == "звонить ⟦тел⟧" for x in PH), [_db.mask(x) for x in PH])
# /status: render отдаёт empty и «ждёт вас» и файл дня не меняет
_before = open(os.path.join(T, "state", "day-2026-10-22.json"), encoding="utf-8").read()
rc, o = b("render")
chk("render: empty=false, ждёт вас — №2 (ждём хозяина), файл дня не тронут", rc == 0 and o["empty"] is False and [w["no"] for w in o["waiting"]] == [2]
    and open(os.path.join(T, "state", "day-2026-10-22.json"), encoding="utf-8").read() == _before, o.get("waiting"))
_E = tempfile.mkdtemp()
_r = subprocess.run([sys.executable, os.path.join(H, "scripts", "day_board.py"), "render"], capture_output=True, text=True, env=dict(os.environ, MILA_WORK=_E, DAY_BOARD_DATE="2026-10-22"))
_o = json.loads(_r.stdout)
chk("пустой день: render empty=true, waiting пусто, файла дня не создал", _o["empty"] is True and _o["waiting"] == [] and not os.path.exists(os.path.join(_E, "state", "day-2026-10-22.json")), _o)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
