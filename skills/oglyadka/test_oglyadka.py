#!/usr/bin/env python3
"""Сценарий: за утро хозяин дал три поручения и сказал «спасибо». Для одного задача заведена (общие слова), для второго —
по якорю сообщения, третье потеряно. Оглядка находит только потерянное; «спасибо» и старое — не поручения; чужой — не хозяин."""
import datetime as dt, json, os, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(os.path.dirname(H)); sys.path.insert(0, H); sys.path.insert(0, os.path.join(R, "tests", "fixtures"))
from oglyadka import lost
from fake_people import OWNER_ID, USER_ID, PHONES
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(); P = os.path.join(T, "projects", "-w"); os.makedirs(P); L = os.path.join(T, "ledger.jsonl")
now = dt.datetime.now().astimezone()
iso = lambda m: (now - dt.timedelta(minutes=m)).isoformat(timespec="seconds")
def inbound(mins_ago, text, uid=OWNER_ID, msg="1"):
    body = '<channel source="telegram" chat_id="%s" message_id="%s" user_id="%s" ts="%s">%s</channel>' % (uid, msg, uid, iso(mins_ago), text)
    with open(os.path.join(P, "s.jsonl"), "a") as f:
        f.write(json.dumps({"type": "user", "timestamp": iso(mins_ago), "message": {"role": "user", "content": body}}, ensure_ascii=False) + "\n")
inbound(120, "Подготовь прайс для клиента X на следующую неделю", msg="11")
inbound(100, "Напомни мне про встречу с Иваном", msg="12")
inbound(90, "Найди три кафе для ужина, мой номер " + PHONES[0], msg="13")
inbound(80, "Спасибо!", msg="14")
inbound(70, "Сделай отчёт по рекламе", uid=USER_ID, msg="15")
inbound(60 * 20, "Проверь сайт", msg="16")
with open(L, "w") as f:
    f.write(json.dumps({"ev": "new", "id": "M-0001", "title": "Прайс клиенту X на неделю", "check": "файл прайса", "ts": iso(118)}, ensure_ascii=False) + "\n")
    f.write(json.dumps({"ev": "new", "id": "M-0002", "title": "встреча", "check": "напоминание", "anchor": "msg:%s/12" % OWNER_ID, "ts": iso(99)}, ensure_ascii=False) + "\n")
r = lost(os.path.join(T, "projects"), L, OWNER_ID, 12)
chk("потеряно одно поручение — «найди три кафе»", [x["msg"] for x in r] == ["13"], r)
chk("задача по общим словам (прайс клиенту X) — не потеряно", "11" not in [x["msg"] for x in r])
chk("задача по якорю сообщения (напомни) — не потеряно", "12" not in [x["msg"] for x in r])
chk("«спасибо» — не поручение; чужой человек — не хозяин; 20 ч назад — вне окна", not {"14", "15", "16"} & {x["msg"] for x in r}, r)
out = subprocess.run([sys.executable, os.path.join(H, "oglyadka.py"), "--projects", os.path.join(T, "projects"), "--ledger", L, "--owner", str(OWNER_ID)],
                     capture_output=True, text=True).stdout
chk("командная строка: итог числом, телефон маской", "поручений без задачи: 1" in out and "⟦тел⟧" in out and PHONES[0] not in out, out)
from fake_people import CHAT_ID
with open(os.path.join(P, "s.jsonl"), "a") as f:
    f.write(json.dumps({"type": "user", "timestamp": iso(30), "message": {"role": "user", "content": '<channel source="telegram" chat_id="%s" message_id="21" user_id="%s" ts="%s">@mila собери отзывы за месяц</channel>' % (CHAT_ID, OWNER_ID, iso(30))}}, ensure_ascii=False) + "\n")
    f.write(json.dumps({"type": "user", "timestamp": iso(29), "message": {"role": "user", "content": '<channel source="telegram" chat_id="%s" message_id="22" ts="%s">Сделай скидку</channel>' % (USER_ID, iso(29))}}, ensure_ascii=False) + "\n")
ids = [x["msg"] for x in lost(os.path.join(T, "projects"), L, OWNER_ID, 12)]
chk("поручение хозяина в группе — в счёт; без отправителя в чужой личке — нет", "21" in ids and "22" not in ids, ids)
os.remove(L)
chk("журнала задач нет — все поручения окна потеряны (4), не падаю", len(lost(os.path.join(T, "projects"), L, OWNER_ID, 12)) == 4)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
