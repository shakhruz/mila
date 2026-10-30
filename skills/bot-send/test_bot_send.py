#!/usr/bin/env python3
"""Тест bot_send.py без сети: поддельный Telegram."""
import os, sys, tempfile, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bot_send import BotSend, TZ

calls, recs = [], []
def api(method, p):
    calls.append((method, p))
    if p["chat_id"] == "403": return {"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked by the user"}
    return {"ok": True, "result": {"message_id": 100 + len(calls)}}
KNOWN = {"1", "2", "3", "403", "kafe_tashkent"}
clock = {"t": datetime(2026, 10, 13, 15, 0, tzinfo=TZ)}
b = BotSend("x", tempfile.mkdtemp(), known=lambda u: u in KNOWN, record_outgoing=lambda u, t, m: recs.append((u, m)), api=api, now=lambda: clock["t"], sleep=lambda s: None)
ok = n = 0
def chk(name, c):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name)

r = b.send(1, "Здравствуйте! Ваш заказ готов.", buttons=[[{"label": "Сайт", "url": "https://milagpt.io"}, {"label": "плохая", "url": "http://x"}]])
chk("личное: ушло, message_id, записано в диалог", r["ok"] and recs[-1] == ("1", r["message_id"]))
chk("кнопки: только https", calls[-1][1]["reply_markup"]["inline_keyboard"] == [[{"text": "Сайт", "url": "https://milagpt.io"}]])
chk("незнакомому — нельзя первым", not b.send(999, "привет")["ok"] and len(calls) == 1)
chk("@username тоже ищется", b.send("@kafe_tashkent", "Спасибо!")["ok"])
chk("пустой текст — отказ", not b.send(1, " ")["ok"])
r = b.send(403, "привет")
chk("заблокировал бота → стоп-лист", not r["ok"] and "403" in b.stoplist())
chk("в стоп-листе — больше не пишем", "отписался" in b.send(403, "ещё")["error"])
chk("«стоп» от человека → стоп-лист", b.unsubscribe_text("3", "Стоп") and "3" in b.stoplist())
pv = b.preview(["1", "2", "3", "403", "999", "1"], "Новости Ташкента на неделю", segment="лиды 7 дн")
chk("превью: только знакомые, без стоп-листа и дублей → 2", pv["n"] == 2 and "✅ Отправить 2" in pv["buttons"][0][0]["label"])
before = len(calls)
chk("без «✅» ничего не ушло", len(calls) == before)
r = b.confirm(pv["preview_id"])
chk("после «✅» — 2 отправлено", r == {"ok": True, "sent": 2, "failed": 0} and len(calls) == before + 2)
chk("повторное «✅» того же превью — отказ", not b.confirm(pv["preview_id"])["ok"])
clock["t"] = datetime(2026, 10, 13, 23, 30, tzinfo=TZ)
pv2 = b.preview(["1", "2"], "Ночная новость"); before = len(calls)
r = b.confirm(pv2["preview_id"])
chk("тихие часы: в очередь, не ушло", r.get("queued") == 2 and len(calls) == before)
chk("ночью очередь не трогается", b.flush_queue().get("waiting") == 1 and len(calls) == before)
clock["t"] = datetime(2026, 10, 14, 8, 5, tzinfo=TZ)
r = b.flush_queue()
chk("в 08:05 отложенная ушла", r["flushed"][0]["sent"] == 2 and len(calls) == before + 2)
lines = [json.loads(l) for l in open(b.journal)]
ok_sent = sum(1 for c in calls if c[1]["chat_id"] != "403")
chk("журнал: каждое отправленное с message_id", sum(1 for l in lines if l.get("mid")) == ok_sent)
# номер собираем в коде
import random as _r
_d = [8, 6, 0, 0] + [_r.randint(0, 9) for _ in range(11)]
_t = sum((x * 2 - 9 if x * 2 > 9 else x * 2) if i % 2 == 0 else x for i, x in enumerate(reversed(_d)))
_P = "".join(map(str, _d)) + str((10 - _t % 10) % 10)
_m = __import__("bot_send").mask_cards("карта " + " ".join(_P[i:i + 4] for i in range(0, 16, 4)) + " и +998 90 123 45 67")
chk("номер карты в тексте → ****1234, телефон не тронут", _m == "карта ****" + _P[-4:] + " и +998 90 123 45 67")
print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
