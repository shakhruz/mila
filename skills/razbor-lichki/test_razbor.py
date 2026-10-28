#!/usr/bin/env python3
"""Сценарий: Иван (клиент X) пишет хозяину «помощник молчит». По журналу помощника: Иван писал в 12:23, помощник ответил
в 12:25 и 12:27 — не молчал. Второй случай: последнее входящее без ответа 40 минут — настоящее молчание. Тексты не выводятся."""
import datetime as dt, json, os, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(os.path.dirname(H)); sys.path.insert(0, H); sys.path.insert(0, os.path.join(R, "tests", "fixtures"))
from razbor import report
from fake_people import USER_ID, CHAT_ID
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(); P = os.path.join(T, "projects", "-w"); os.makedirs(P)
base = dt.datetime.now().astimezone().replace(second=0, microsecond=0) - dt.timedelta(hours=2)
iso = lambda m: (base + dt.timedelta(minutes=m)).isoformat()
def w(d):
    with open(os.path.join(P, "s.jsonl"), "a") as f: f.write(json.dumps(d, ensure_ascii=False) + "\n")
def inbound(m, chat, text="помогите с документом"):
    w({"type": "user", "timestamp": iso(m), "message": {"content": '<channel source="telegram" chat_id="%s" message_id="1" user_id="%s" ts="%s">%s</channel>' % (chat, chat, iso(m), text)}})
def reply(m, chat, text="Принял. Подпись задним числом поставить не могу — есть два законных пути: …"):
    w({"type": "assistant", "timestamp": iso(m), "message": {"content": [{"type": "tool_use", "name": "mcp__plugin_mila-telegram_telegram__reply", "input": {"chat_id": str(chat), "text": text}}]}})
inbound(0, USER_ID); reply(2, USER_ID); reply(4, USER_ID)
inbound(1, CHAT_ID, "в группе другое"); reply(3, CHAT_ID, "в группе: Иван (%s) уже получил ответ" % USER_ID)
r = report(os.path.join(T, "projects"), str(USER_ID), 24)
chk("Иван писал один раз, помощник ответил дважды", len(r["inbound"]) == 1 and len(r["replies"]) == 2, r)
chk("ответ на последнее входящее был, через 2 минуты — не молчал", r["answered_last"] is True and r["first_answer_min"] == 2 and r["silent_min"] is None, r)
chk("ответы в другой чат не считаются", all(x["len"] > 0 for x in r["replies"]) and len(r["replies"]) == 2)
chk("текстов в выводе нет — только время и длина", "подпись" not in json.dumps(r, ensure_ascii=False).lower() and "документ" not in json.dumps(r, ensure_ascii=False))
inbound(30, USER_ID, "ну где ответ?")
r2 = report(os.path.join(T, "projects"), str(USER_ID), 24, now=(base + dt.timedelta(minutes=70)).timestamp())
chk("последнее входящее 40 минут без ответа — настоящее молчание, минуты названы", r2["answered_last"] is False and r2["silent_min"] == 40, r2)
r3 = report(os.path.join(T, "projects"), "999", 24)
chk("чата нет в журнале — пусто, без выдумки", r3["inbound"] == [] and r3["replies"] == [] and r3["answered_last"] is None, r3)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
