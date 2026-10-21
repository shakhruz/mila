#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Журнал задач: чем сделана задача, сколько стоила и чем кончилась.

records.py знает ходы (turns): модель, токены, цену каждого обмена. Он не знает,
что эти ходы были ОДНОЙ задачей — «пост про акцию», «письмо клиенту» — и чем
задача кончилась. Без этого уровень модели выбирают по привычке, а не по данным
(«пять вопросов», 21.10.2026: мерить качество за доллар).

Задача = отрезок времени [start, end] + вид + итог. Цена задачи считается в
отчёте из turns за этот отрезок (тот же агент, тот же чат, если он задан) —
сборщик ходов может отставать, поэтому в момент закрытия ничего не суммируем.

  tasks.py start --kind post [--chat <id>] [--note "акция недели"]   → id задачи
  tasks.py done <id> [--outcome done|redo|complaint]                  закрыть (по умолчанию done)
  tasks.py mark <id> redo|complaint                                   позже: переделка или жалоба
  tasks.py report [--days 7] [--json]                                 неделя по видам задач

Итоги: done — принято с первого раза; redo — пришлось переделывать;
complaint — жалоба человека. Виды — короткие слова (post, email, doc, reply,
analysis, image…); отчёт группирует по ним.

🔴 usd — справочная цена по прейскуранту API, как в records.py (paid_by):
по подписке её никто не списывал. Пересекающиеся задачи в одном чате делят ходы
— такие строки отчёт помечает «пересечение».
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import records  # noqa: E402

OUTCOMES = ("done", "redo", "complaint")
TASKS_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_start  REAL NOT NULL,
    ts_end    REAL,
    kind      TEXT NOT NULL,
    outcome   TEXT NOT NULL DEFAULT '',
    agent     TEXT NOT NULL DEFAULT '',
    chat_id   TEXT NOT NULL DEFAULT '',
    note      TEXT NOT NULL DEFAULT ''
)"""


def open_db(path=None):
    con = records.open_turns(path)
    con.execute(TASKS_SQL)
    con.execute("CREATE INDEX IF NOT EXISTS idx_tasks_ts ON tasks(ts_start)")
    con.commit()
    return con


def start(kind, chat_id="", note="", agent=None, now=None, con=None):
    kind = (kind or "").strip().lower()
    if not kind or len(kind) > 32:
        raise ValueError("вид задачи — короткое слово: post, email, doc…")
    own = con is None
    con = con or open_db()
    try:
        cur = con.execute("INSERT INTO tasks(ts_start, kind, agent, chat_id, note) VALUES (?,?,?,?,?)",
                          (now or time.time(), kind, agent if agent is not None else os.environ.get("MILA_AGENT", ""),
                           str(chat_id or ""), note[:200]))
        con.commit()
        return cur.lastrowid
    finally:
        if own:
            con.close()


def done(task_id, outcome="done", now=None, con=None):
    if outcome not in OUTCOMES:
        raise ValueError("итог: done | redo | complaint")
    own = con is None
    con = con or open_db()
    try:
        n = con.execute("UPDATE tasks SET ts_end = COALESCE(ts_end, ?), outcome = ? WHERE id = ?",
                        (now or time.time(), outcome, int(task_id))).rowcount
        con.commit()
        if not n:
            raise KeyError("нет задачи %s" % task_id)
    finally:
        if own:
            con.close()


def report(days=7, now=None, con=None):
    own = con is None
    con = con or open_db()
    try:
        since = records._since_ts(days=days) if now is None else now - days * 86400
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM tasks WHERE ts_start >= ? AND ts_end IS NOT NULL ORDER BY ts_start", (since,))]
        by = {}
        for t in rows:
            q = "SELECT model, prompt_tokens, completion_tokens, cache_read_tokens, cache_write_tokens, usd_cost FROM turns WHERE ts >= ? AND ts <= ?"
            a = [t["ts_start"], t["ts_end"]]
            if t["agent"]:
                q += " AND agent = ?"; a.append(t["agent"])
            if t["chat_id"]:
                q += " AND chat_id = ?"; a.append(t["chat_id"])
            turns = [dict(r) for r in con.execute(q, a)]
            overlap = con.execute("SELECT COUNT(*) FROM tasks WHERE id != ? AND chat_id = ? AND agent = ? AND ts_start < ? AND COALESCE(ts_end, ts_start) > ?",
                                  (t["id"], t["chat_id"], t["agent"], t["ts_end"], t["ts_start"])).fetchone()[0]
            g = by.setdefault(t["kind"], {"kind": t["kind"], "tasks": 0, "done": 0, "redo": 0, "complaint": 0, "turns": 0,
                                          "tokens": 0, "usd": 0.0, "models": {}, "overlap": 0})
            g["tasks"] += 1
            g[t["outcome"] or "done"] += 1
            g["overlap"] += bool(overlap)
            for r in turns:
                g["turns"] += 1
                g["tokens"] += sum(int(r[k] or 0) for k in ("prompt_tokens", "completion_tokens", "cache_read_tokens", "cache_write_tokens"))
                g["usd"] += float(r["usd_cost"] or 0)
                g["models"][r["model"] or "?"] = g["models"].get(r["model"] or "?", 0) + 1
        out = []
        for g in sorted(by.values(), key=lambda x: -x["usd"]):
            g["usd"] = round(g["usd"], 4)
            g["usd_per_task"] = round(g["usd"] / g["tasks"], 4) if g["tasks"] else 0
            g["first_time_pct"] = round(100 * g["done"] / g["tasks"]) if g["tasks"] else 0
            g["usd_per_good"] = round(g["usd"] / g["done"], 4) if g["done"] else None
            out.append(g)
        return out
    finally:
        if own:
            con.close()


def render(rep, days):
    if not rep:
        return "За %d дн. закрытых задач нет — журнал пуст (tasks.py start/done)." % days
    lines = ["Задачи за %d дн. · цена справочная (прейскурант API, по подписке не списана)" % days,
             "%-10s %5s %6s %5s %6s %9s %10s  %s" % ("вид", "задач", "с 1-го", "перед", "жалоб", "$ всего", "$ за удачн", "модели")]
    for g in rep:
        models = ", ".join("%s×%d" % (m, n) for m, n in sorted(g["models"].items(), key=lambda x: -x[1])) or "—"
        lines.append("%-10s %5d %5d%% %5d %6d %9.2f %10s  %s%s" % (
            g["kind"], g["tasks"], g["first_time_pct"], g["redo"], g["complaint"], g["usd"],
            ("%.2f" % g["usd_per_good"]) if g["usd_per_good"] is not None else "—", models,
            "  (пересечение: %d)" % g["overlap"] if g["overlap"] else ""))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="журнал задач: модель, токены, цена, итог")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("--kind", required=True); s.add_argument("--chat", default=""); s.add_argument("--note", default="")
    d = sub.add_parser("done"); d.add_argument("id"); d.add_argument("--outcome", default="done", choices=OUTCOMES)
    m = sub.add_parser("mark"); m.add_argument("id"); m.add_argument("outcome", choices=("redo", "complaint"))
    r = sub.add_parser("report"); r.add_argument("--days", type=int, default=7); r.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "start":
        print(start(a.kind, a.chat, a.note))
    elif a.cmd in ("done", "mark"):
        done(a.id, a.outcome)
        print("ok")
    else:
        rep = report(a.days)
        print(json.dumps(rep, ensure_ascii=False, indent=1) if a.json else render(rep, a.days))


if __name__ == "__main__":
    sys.exit(main())
