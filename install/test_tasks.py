#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Журнал задач: цена задачи из ходов её отрезка, итоги, отчёт по видам. Временная база."""
import importlib, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["MILA_RECORDS_DIR"] = tempfile.mkdtemp(prefix="mila-tasks-")
os.environ.pop("MILA_AGENT", None)
import records; importlib.reload(records)
import tasks; importlib.reload(tasks)

ok = n = 0
def chk(name, cond, got=""):
    global ok, n
    n += 1; ok += bool(cond)
    print(("✅ " if cond else "❌ ") + name + ("" if cond else "  → %r" % (got,)))

con = tasks.open_db()
T0 = time.time() - 3600
def turn(dt, model, pin, pout, usd, chat="c1", key=None):
    records.record_turn(con, ts=T0 + dt, chat_id=chat, model=model, prompt_tokens=pin, completion_tokens=pout,
                        usd_cost=usd, idempotency_key=key or "k%s-%s" % (dt, chat), price=False)

a = tasks.start("post", chat_id="c1", now=T0, con=con)
turn(10, "haiku", 1000, 200, 0.002); turn(20, "opus", 3000, 500, 0.08)
tasks.done(a, now=T0 + 30, con=con)
b = tasks.start("post", chat_id="c1", now=T0 + 100, con=con)
turn(110, "haiku", 900, 300, 0.003)
tasks.done(b, now=T0 + 120, con=con); tasks.done(b, "redo", con=con)
c = tasks.start("email", chat_id="c2", now=T0 + 200, con=con)
turn(210, "opus", 5000, 800, 0.12, chat="c2"); turn(215, "opus", 100, 10, 0.5, chat="c1")   # чужой чат — не считается
tasks.done(c, "complaint", now=T0 + 230, con=con)
open_task = tasks.start("doc", now=T0 + 300, con=con)                                      # не закрыта — не в отчёте

rep = {g["kind"]: g for g in tasks.report(days=1, now=time.time(), con=con)}
p, e = rep.get("post", {}), rep.get("email", {})
chk("две задачи post, одна с первого раза", p.get("tasks") == 2 and p.get("done") == 1 and p.get("redo") == 1, p)
chk("цена post = сумма ходов её отрезков (0.085)", abs(p.get("usd", 0) - 0.085) < 1e-9, p.get("usd"))
chk("модели post: haiku×2, opus×1", p.get("models") == {"haiku": 2, "opus": 1}, p.get("models"))
chk("email: только ходы своего чата, жалоба", e.get("turns") == 1 and abs(e.get("usd", 0) - 0.12) < 1e-9 and e.get("complaint") == 1, e)
chk("$ за удачную: post 0.085, email — нет удачных", p.get("usd_per_good") == 0.085 and e.get("usd_per_good") is None, (p.get("usd_per_good"), e.get("usd_per_good")))
chk("незакрытая задача в отчёт не попала", "doc" not in rep, list(rep))
chk("повторное done не сдвигает конец, меняет итог", con.execute("SELECT ts_end, outcome FROM tasks WHERE id=?", (b,)).fetchone()[:] == (T0 + 120, "redo"))
try:
    tasks.done(a, "maybe", con=con); chk("неизвестный итог — ошибка", False)
except ValueError:
    chk("неизвестный итог — ошибка", True)
txt = tasks.render(tasks.report(days=1, now=time.time(), con=con), 1)
chk("отчёт — таблица с видами и пометкой «справочная»", "post" in txt and "email" in txt and "справочная" in txt, txt)
chk("база 600", oct(os.stat(records.TURNS_DB).st_mode & 0o777) == "0o600", oct(os.stat(records.TURNS_DB).st_mode & 0o777))
print("итог %d/%d" % (ok, n))
sys.exit(0 if ok == n else 1)
