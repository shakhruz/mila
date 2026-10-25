#!/usr/bin/env python3
"""bot-send: края ввода (Мила Сила 25.10 + пауза по лимиту Telegram — Разработка). Без сети: api/now/sleep — подмены. Usage: python3 test_bot_send_kraya.py [папка с bot_send.py]"""
import sys, os, tempfile, json
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))); import bot_send as B   # папка с bot_send.py; без аргумента — рядом
from datetime import datetime
R=[]
def T(name, ok, info=""):
    R.append(bool(ok)); print(("✅" if ok else "🔴"), name, info)
def mk(api, known=lambda u: u in {"111","222","user_a"}, hour=12):
    d=tempfile.mkdtemp(); sl=[]
    b=B.BotSend("X", d, known, api=api, now=lambda: datetime(2026,10,25,hour,0,tzinfo=B.TZ), sleep=lambda s: sl.append(s))
    return b, sl
calls=[]
def ok_api(m,p): calls.append(p["chat_id"]); return {"ok":True,"result":{"message_id":len(calls)}}
# 1 дубль int/str
b,_=mk(ok_api); calls.clear(); pv=b.preview([111,"111","222"],"Привет"); r=b.confirm(pv["preview_id"])
T("превью [111,'111',222] → 2 человека, 2 отправки", pv["n"]==2 and len(calls)==2, "n=%d отправок=%d"%(pv["n"],len(calls)))
# 2 @username → chat not found → стоп-лист
def nf(m,p): return {"ok":False,"error_code":400,"description":"Bad Request: chat not found"}
b,_=mk(nf); r=b.send("@user_a","Здравствуйте")
T("@username → ошибка формата, но НЕ в стоп-листе навсегда", "user_a" not in b.stoplist(), "stoplist=%s"%sorted(b.stoplist()))
# 3 бесконечный 429
n=[0]
def flood(m,p):
    n[0]+=1
    if n[0]>50: raise SystemExit("🔴 бесконечный 429: 50 повторов одному человеку")
    return {"ok":False,"error_code":429,"description":"Too Many Requests","parameters":{"retry_after":30}}
b,sl=mk(flood); pv=b.preview(["111"],"Текст")
try: r=b.confirm(pv["preview_id"]); T("429 без конца → сдаётся после N повторов", n[0]<=5, "повторов=%d"%n[0])
except SystemExit as e: T("429 без конца → сдаётся после N повторов", False, str(e))
# 4 retry_after огромный
n2=[0]
def big(m,p):
    n2[0]+=1
    return {"ok":False,"error_code":429,"parameters":{"retry_after":86400}} if n2[0]==1 else {"ok":True,"result":{"message_id":1}}
b,sl=mk(big); pv=b.preview(["111"],"Текст"); b.confirm(pv["preview_id"])
T("retry_after 86400 → не спит сутки", sum(sl)<=60, "спала %ss"%sum(sl))
# 5 превью на 0 человек
b,_=mk(ok_api); pv=b.preview(["999"],"Текст")
T("превью на 0 человек → отказ, а не кнопка «✅ Отправить 0»", pv.get("n",0)>0 or "error" in pv, "card=%r"%pv.get("card","")[:30])
# 6 пустой текст рассылки
b,_=mk(ok_api); calls.clear(); pv=b.preview(["111"],"   ")
T("рассылка с пустым текстом → отказ на превью", "error" in pv or pv.get("n")==0, "n=%s"%pv.get("n"))
# 7 повторный confirm
b,_=mk(ok_api); calls.clear(); pv=b.preview(["111"],"Т"); b.confirm(pv["preview_id"]); r2=b.confirm(pv["preview_id"])
T("второй ✅ на то же превью → без повторной отправки", len(calls)==1 and not r2.get("ok"))
# 8 «Стоп!» / «stop please»
b,_=mk(ok_api)
T("«Стоп!» → стоп-лист", b.unsubscribe_text("111","Стоп!"))
T("«/stop» → стоп-лист", b.unsubscribe_text("222","/stop"))
# b (Разработка): лимит на весь бот (retry_after > 60) — рассылка встаёт, остаток в очередь, повтора тем, кому ушло, нет
def _b():
    global cl, st
    cl=[]; st={"n":0}
    def flood(m,p):
        st["n"]+=1; cl.append(p["chat_id"])
        return {"ok":False,"error_code":429,"parameters":{"retry_after":3600}} if st["n"]==2 else {"ok":True,"result":{"message_id":st["n"]}}
    b,sl=mk(flood, known=lambda u: u in {"111","222","333"}); pv=b.preview(["111","222","333"],"Новость"); r=b.confirm(pv["preview_id"])
    T("лимит 3600 с на втором → пауза: ушло 1, осталось 2, не спим", r.get("paused") and r.get("sent")==1 and r.get("left")==2 and sum(sl)==0, str(r))
    q=b._rj(b.queue_f, [])
    T("остаток в очереди с not_before, первого там нет", len(q)==1 and q[0]["to"]==["222","333"] and q[0]["not_before"]>0)
    f=b.flush_queue()
    T("до срока очередь не трогается", f.get("flushed")==[] and len(b._rj(b.queue_f, []))==1)
    b.stop_add("333","сам: стоп"); qq=b._rj(b.queue_f, [])
    if qq: qq[0]["not_before"]=0; b._wj(b.queue_f, qq)
    cl.clear()
    f=b.flush_queue()
    T("после срока — уходит остаток; отписавшийся за паузу не получает", cl==["222"], "отправки=%s"%cl)
try: _b()
except Exception as e: T("секция b (пауза по лимиту) не упала", False, "%s: %s" % (type(e).__name__, e))

# c (Качество, закон 3): пауза дольше часа или в тихие часы — остаток только по новому ✅
def _c():
    import bot_send as BB
    from datetime import timedelta
    clk={"t": datetime(2026,10,25,12,0,tzinfo=B.TZ)}; out=[]; st2={"n":0}
    def api(m,p):
        st2["n"]+=1; out.append(p["chat_id"])
        return {"ok":False,"error_code":429,"parameters":{"retry_after":3*86400}} if st2["n"]==2 else {"ok":True,"result":{"message_id":st2["n"]}}
    d=tempfile.mkdtemp(); b=B.BotSend("X", d, lambda u: u in {"111","222","333"}, api=api, now=lambda: clk["t"], sleep=lambda s: None)
    pv=b.preview(["111","222","333"],"Новость"); r=b.confirm(pv["preview_id"])
    T("пауза 3 сут → не в очередь, новое превью «осталось 2»", r.get("paused") and r.get("left")==2 and r.get("preview_id") and b._rj(b.queue_f, [])==[], str({k:r.get(k) for k in ("left","until","preview_id")}))
    clk["t"]+=timedelta(days=4); out.clear(); f=b.flush_queue()
    T("через 4 дня без ✅ — ничего не ушло", out==[], "отправки=%s"%out)
    clk["t"]-=timedelta(days=2); r2=b.confirm(r["preview_id"])
    T("✅ раньше срока Telegram → в очередь с not_before (свежее «да»), сейчас 0 отправок", r2.get("queued")==2 and out==[], str(r2))
    clk["t"]+=timedelta(days=1, minutes=1); out.clear(); b.flush_queue()
    T("в срок → уходит только остаток 222, 333", out==["222","333"], "отправки=%s"%out)
    clk["t"]=datetime(2026,10,25,21,30,tzinfo=B.TZ); st2["n"]=0; out.clear()
    def api2(m,p):
        st2["n"]+=1; out.append(p["chat_id"])
        return {"ok":False,"error_code":429,"parameters":{"retry_after":3600}} if st2["n"]==2 else {"ok":True,"result":{"message_id":st2["n"]}}
    b.api=api2; pv=b.preview(["111","222"],"Вечер"); r4=b.confirm(pv["preview_id"])
    T("пауза 1 ч, срок в тихие часы (22:30) → новое превью, не очередь", r4.get("preview_id") and b._rj(b.queue_f, [])==[], str(r4.get("until")))
try: _c()
except Exception as e: T("секция c (новое ✅ после долгой паузы) не упала", False, "%s: %s" % (type(e).__name__, e))

# c3 (Качество): «Отменить» у отложенного остатка до срока
def _c3():
    from datetime import timedelta
    clk={"t": datetime(2026,10,25,12,0,tzinfo=B.TZ)}; out=[]; st3={"n":0}
    def api(m,p):
        st3["n"]+=1; out.append(p["chat_id"])
        return {"ok":False,"error_code":429,"parameters":{"retry_after":2*86400}} if st3["n"]==2 else {"ok":True,"result":{"message_id":st3["n"]}}
    d=tempfile.mkdtemp(); b=B.BotSend("X", d, lambda u: u in {"111","222","333"}, api=api, now=lambda: clk["t"], sleep=lambda s: None)
    pv=b.preview(["111","222","333"],"Н"); r=b.confirm(pv["preview_id"]); r2=b.confirm(r["preview_id"])
    T("остаток в очереди → кнопка «Отменить»", any("bc_cancel_" in x.get("choice","") for row in r2.get("buttons",[]) for x in row), str(r2.get("buttons")))
    c=b.cancel(r["preview_id"]); clk["t"]+=timedelta(days=3); out.clear(); b.flush_queue()
    T("«Отменить» до срока → в срок ничего не ушло", c.get("ok") and out==[], "cancel=%s отправки=%s"%(c,out))
    T("повторная отмена → «нечего»", not b.cancel(r["preview_id"]).get("ok"))
try: _c3()
except Exception as e: T("секция c3 (отмена) не упала", False, "%s: %s" % (type(e).__name__, e))

# c4 (Качество): ночная рассылка тоже отменяема; cancel(None) не снимает чужое
def _c4():
    from datetime import timedelta
    clk={"t": datetime(2026,10,25,23,0,tzinfo=B.TZ)}; out=[]
    def api(m,p): out.append(p["chat_id"]); return {"ok":True,"result":{"message_id":len(out)}}
    d=tempfile.mkdtemp(); b=B.BotSend("X", d, lambda u: u in {"111","222"}, api=api, now=lambda: clk["t"], sleep=lambda s: None)
    pv=b.preview(["111","222"],"Ночь"); r=b.confirm(pv["preview_id"])
    ch=[x.get("choice","") for row in r.get("buttons",[]) for x in row]
    T("✅ в 23:00 → очередь на 08:00 с кнопкой «Отменить отправку 08:00»", r.get("queued")==2 and any(c.startswith("bc_cancel_") for c in ch), str(r.get("buttons")))
    T("cancel(None) и cancel('') → «нечего», очередь цела", not b.cancel(None).get("ok") and not b.cancel("").get("ok") and len(b._rj(b.queue_f, []))==1)
    qid=ch[0][len("bc_cancel_"):] if ch else ""; c=b.cancel(qid); clk["t"]=datetime(2026,10,26,8,10,tzinfo=B.TZ); out.clear(); b.flush_queue()
    T("отмена ночной → в 08:10 ничего не ушло", c.get("ok") and out==[], "cancel=%s отправки=%s"%(c,out))
try: _c4()
except Exception as e: T("секция c4 (ночная отмена) не упала", False, "%s: %s" % (type(e).__name__, e))
# c3-Р (Разработка): отмена через id из кнопки — отложенный остаток и тихая очередь
def _c3r():
    cid=lambda r: (json.dumps((r or {}).get('buttons')).split('bc_cancel_')+[''])[1].split('"')[0]
    clk={"t": datetime(2026,10,25,12,0,tzinfo=B.TZ)}; out=[]; st3={"n":0}
    def flood(m,p):
        st3["n"]+=1; out.append(p["chat_id"])
        return {"ok":False,"error_code":429,"parameters":{"retry_after":3*86400}} if st3["n"]==2 else {"ok":True,"result":{"message_id":st3["n"]}}
    d=tempfile.mkdtemp(); b=B.BotSend("X", d, lambda u: u in {"111","222","333"}, api=flood, now=lambda: clk["t"], sleep=lambda s: None)
    pv=b.preview(["111","222","333"],"Новость"); r=b.confirm(pv["preview_id"]); r2=b.confirm(r["preview_id"])
    T("«да» на остаток → в ответе кнопка «Отменить» (bc_cancel_<id>)", bool(cid(r2)))
    c=b.cancel(cid(r2))
    T("отмена до срока → снято 2, очередь пуста", c.get("ok") and c.get("cancelled")==2 and b._rj(b.queue_f, [])==[], str(c))
    clk["t"]=datetime(2026,10,28,13,0,tzinfo=B.TZ); out.clear(); b.flush_queue()
    T("отменил → после срока 0 отправок", out==[], "отправки=%s"%out)
    T("повторная отмена → понятный отказ", b.cancel(cid(r2)).get("ok") is False)
    clk["t"]=datetime(2026,10,25,23,0,tzinfo=B.TZ); out.clear()
    def okapi(m,p): out.append(p["chat_id"]); return {"ok":True,"result":{"message_id":1}}
    b2=B.BotSend("X", tempfile.mkdtemp(), lambda u: u in {"111"}, api=okapi, now=lambda: clk["t"], sleep=lambda s: None)
    rq=b2.confirm(b2.preview(["111"],"Ночью")["preview_id"]); b2.cancel(cid(rq))
    clk["t"]=datetime(2026,10,26,8,30,tzinfo=B.TZ); b2.flush_queue()
    T("тихие часы: «Отменить» у очереди на 08:00 → утром ничего не ушло", rq.get("queued")==1 and out==[], "отправки=%s"%out)
try: _c3r()
except Exception as e: T("секция c3-Р (отмена по кнопке) не упала", False, "%s: %s" % (type(e).__name__, e))
print("итог %d/%d"%(sum(R),len(R))); sys.exit(0 if all(R) else 1)
