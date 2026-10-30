#!/usr/bin/env python3
"""day_board.py — «Пульт дня»: одна правда о делах Милы за день, одно закреплённое сообщение хозяину.

Файл дня: <work>/state/day-YYYY-MM-DD.json  {"date", "next_no", "pin": {"chat_id", "message_id"}, "items": [...]}
Дело: {"no", "text", "who", "why", "state": now|queue|wait|done|dropped, "prio": red|"", "after", "on", "asked",
       "evidence", "result", "ts"}
Незакрытое вчерашнее (now, queue, wait) переносится в новый день с прежним №, пометкой «со вчера».

  day_board.py add --text T [--who W] [--why Y] [--red]   → строка «№N в очередь, беру после №X, потому что …»
  day_board.py start N                                      → в работу (не больше 2 одновременно; 🔴 — всегда)
  day_board.py wait N --on КТО --asked ССЫЛКА                → ждёт другого: только с уликой, что вопрос ЗАДАН (сообщение с кнопками)
  day_board.py done N --evidence УЛИКА --result ВЫВОД        → закрыто: улика (ссылка, файл, ответ инструмента) + вывод одной строкой
  day_board.py drop N --why Y                                → снято, с причиной
  day_board.py plan --pool "дело1; дело2; …"                 → утро: план дня + авто-пул 3–5 дел в очередь
  day_board.py render [--lang ru|en]                         → текст закреплённого сообщения (≤ 3800 знаков)
  day_board.py evening                                       → вечерний итог: сделано с выводами, перенос, кто кого ждёт
  day_board.py pin --chat C --message M | pin                → запомнить / показать закреплённое сообщение (для edit_message)
Env: MILA_WORK (по умолчанию ~/work), DAY_BOARD_DATE (YYYY-MM-DD, для тестов), MILA_TZ_HOURS (5 — Ташкент).
Выход: JSON {"ok", "line"|"text", …}; ошибка — {"error"} и код 1.
"""
import argparse
import datetime
import json
import os
import re
import sys
import time

WORK = os.environ.get("MILA_WORK") or os.path.expanduser("~/work")
STATE = os.path.join(WORK, "state")
TZ = datetime.timezone(datetime.timedelta(hours=float(os.environ.get("MILA_TZ_HOURS", "5"))))
MAX_NOW = 2
WAIT_RED_MIN = 60   # «ждёт» дольше часа — 🔴 «переспросить или решить сам»
ASKED_RE = re.compile(r"^(https://t\.me/c/\d+/\d+|https://t\.me/[A-Za-z0-9_]{4,}/\d+|\d{1,12})$")
CARD_RE = re.compile(r"(?<![\d+])(?:\d[ -]?){12,}\d(?!\d)")
PHONE_RE = re.compile(r"(?<![\w(])(?:\+|\()?\d[\d ()\-]{7,}\d(?!\w)")
MAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _luhn(d):
    t = 0
    for i, ch in enumerate(reversed(d)):
        x = int(ch)
        if i % 2:
            x *= 2
            if x > 9: x -= 9
        t += x
    return t % 10 == 0


def mask(s):
    """Пульт видят в чате: карта → ****1234 (окно 13–19 цифр с Луной, как во флоте), телефон → ⟦тел⟧, почта → ⟦почта⟧ (как pd-vault)."""
    s = str(s or "")

    def card(m):
        digs = [(g.start(), g.end()) for g in re.finditer(r"\d+", m.group(0))]
        txt = m.group(0)
        for i in range(len(digs)):
            for j in range(len(digs) - 1, i - 1, -1):
                d = re.sub(r"\D", "", txt[digs[i][0]:digs[j][1]])
                if 13 <= len(d) <= 19 and len(set(d)) > 1 and _luhn(d):
                    return txt[:digs[i][0]] + "****" + d[-4:] + txt[digs[j][1]:]
        return txt
    s = CARD_RE.sub(card, s)
    s = MAIL_RE.sub("⟦почта⟧", s)
    return PHONE_RE.sub(lambda m: "⟦тел⟧" if _is_phone(m, s) else m.group(0), s)


def _is_phone(m, s):
    """Телефон — только в форме телефона: номер заявки, id чата и id человека — рабочие данные пульта.
    «+» и 11–13 цифр; или 9–12 цифр с разделителями телефона; или 998… (12) / 7…, 8… (11) слитно.
    Не телефон: после «№», «-100…» (id чата), 16+ цифр, уже маска карты."""
    t = m.group(0)
    d = re.sub(r"\D", "", t)
    before = s[:m.start()].rstrip()
    if t.startswith("****") or before.endswith("№") or len(d) >= 16:
        return False
    if s[max(0, m.start() - 1):m.start()] == "-" and d.startswith("100"):
        return False
    if t.startswith("+"):
        return 11 <= len(d) <= 13
    if re.search(r"[ ()\-]", t):
        return 9 <= len(d) <= 12
    return (len(d) == 12 and d.startswith("998")) or (len(d) == 11 and d[0] in "78")


def now_epoch():
    return float(os.environ.get("DAY_BOARD_NOW") or time.time())
OPEN = ("now", "queue", "wait")

L = {
    "ru": {"title": "📋 Пульт дня · %s", "now": "▶️ В работе", "queue": "⏳ Очередь", "wait": "🤝 Ждёт ответа", "done": "✅ Сделано",
           "empty": "пусто", "after": "после №%s", "on": "ждёт: %s · вопрос: %s", "carried": "со вчера", "red": "🔴",
           "added": "№%d в очередь%s, потому что %s", "added_now": "№%d беру сразу%s", "after_x": ", беру после №%s",
           "why_default": "так по порядку", "evening": "Итог дня %s: сделано %d, в работе %d, в очереди %d, ждут %d",
           "carry": "Переносится: %s", "mins": "ждёт %d мин", "stale": "переспросить или решить сам"},
    "en": {"title": "📋 Day board · %s", "now": "▶️ In progress", "queue": "⏳ Queue", "wait": "🤝 Waiting for an answer", "done": "✅ Done",
           "empty": "empty", "after": "after #%s", "on": "waiting: %s · asked: %s", "carried": "from yesterday", "red": "🔴",
           "added": "#%d queued%s, because %s", "added_now": "#%d taking it now%s", "after_x": ", after #%s",
           "why_default": "it is next in order", "evening": "Day %s: done %d, in progress %d, queued %d, waiting %d",
           "carry": "Carried over: %s", "mins": "waiting %d min", "stale": "ask again or decide myself"},
}


def today():
    d = os.environ.get("DAY_BOARD_DATE")
    return d or datetime.datetime.now(TZ).date().isoformat()


def path_of(day):
    return os.path.join(STATE, "day-%s.json" % day)


def save(b):
    os.makedirs(STATE, exist_ok=True)
    p = path_of(b["date"])
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)


def load():
    day = today()
    try:
        return json.load(open(path_of(day), encoding="utf-8"))
    except (OSError, ValueError):
        pass
    b = {"date": day, "next_no": 1, "pin": {}, "items": []}
    prev = sorted(f for f in (os.listdir(STATE) if os.path.isdir(STATE) else []) if f.startswith("day-") and f.endswith(".json") and f < "day-%s.json" % day)
    if prev:
        try:
            old = json.load(open(os.path.join(STATE, prev[-1]), encoding="utf-8"))
            b["next_no"] = old.get("next_no", 1)
            b["pin"] = old.get("pin", {})
            for it in old.get("items", []):
                if it.get("state") in OPEN:
                    b["items"].append(dict(it, carried=True))
        except (OSError, ValueError):
            pass
    return b


def find(b, no):
    for it in b["items"]:
        if it["no"] == no:
            return it
    return None


def now_ts():
    return datetime.datetime.now(TZ).strftime("%H:%M")


def lang_of(a):
    lg = getattr(a, "lang", None) or os.environ.get("MILA_LANG", "ru")
    return lg if lg in L else "ru"


def out(d, code=0):
    print(json.dumps(d, ensure_ascii=False))
    return code


def cmd_add(a, b):
    t = L[lang_of(a)]
    no = b["next_no"]; b["next_no"] += 1
    nows = [i for i in b["items"] if i["state"] == "now"]
    queue = [i for i in b["items"] if i["state"] == "queue"]
    it = {"no": no, "text": mask(a.text.strip()), "who": mask(a.who or ""), "why": mask(a.why or ""), "prio": "red" if a.red else "", "ts": now_ts()}
    if a.red or not nows:
        it["state"] = "now"
        b["items"].append(it); save(b)
        extra = (" (%s)" % t["red"]) if a.red else ""
        return out({"ok": True, "no": no, "state": "now", "line": t["added_now"] % (no, extra)})
    last = (queue[-1] if queue else nows[-1])["no"]
    it.update(state="queue", after=last)
    b["items"].append(it); save(b)
    return out({"ok": True, "no": no, "state": "queue", "line": t["added"] % (no, t["after_x"] % last, a.why or t["why_default"])})


def cmd_start(a, b):
    it = find(b, a.no)
    if not it: return out({"error": "нет №%d" % a.no}, 1)
    busy = [i for i in b["items"] if i["state"] == "now" and i["no"] != a.no and i.get("prio") != "red"]
    if len(busy) >= MAX_NOW and it.get("prio") != "red":
        return out({"error": "в работе уже %d (№%s) — сначала закрой или поставь в ожидание; одновременно не больше %d" % (len(busy), ", №".join(str(i["no"]) for i in busy), MAX_NOW)}, 1)
    it["state"] = "now"; it.pop("after", None); save(b)
    return out({"ok": True, "no": a.no, "state": "now"})


def cmd_wait(a, b):
    it = find(b, a.no)
    if not it: return out({"error": "нет №%d" % a.no}, 1)
    if not (a.on or "").strip() or not ASKED_RE.match((a.asked or "").strip()):
        return out({"error": "«ждёт» без заданного вопроса не бывает: --on кто и --asked — ссылка t.me/c/<чат>/<id> или номер сообщения с вопросом (кнопками)"}, 1)
    it.update(state="wait", on=mask(a.on.strip()), asked=a.asked.strip(), wait_since=now_epoch()); save(b)
    return out({"ok": True, "no": a.no, "state": "wait"})


def cmd_done(a, b):
    it = find(b, a.no)
    if not it: return out({"error": "нет №%d" % a.no}, 1)
    if not (a.evidence or "").strip() or not (a.result or "").strip():
        return out({"error": "закрыть можно только с уликой (--evidence: ссылка, файл, ответ инструмента) и выводом (--result)"}, 1)
    it.update(state="done", evidence=mask(a.evidence.strip()), result=mask(a.result.strip().splitlines()[0][:200]), closed=now_ts()); save(b)
    nxt = next((i for i in b["items"] if i["state"] == "queue"), None)
    return out({"ok": True, "no": a.no, "state": "done", "next": nxt["no"] if nxt else None})


def cmd_drop(a, b):
    it = find(b, a.no)
    if not it: return out({"error": "нет №%d" % a.no}, 1)
    if not (a.why or "").strip(): return out({"error": "снять можно только с причиной (--why)"}, 1)
    it.update(state="dropped", why=mask(a.why.strip())); save(b)
    return out({"ok": True, "no": a.no, "state": "dropped"})


def cmd_plan(a, b):
    pool = [x.strip() for x in (a.pool or "").split(";") if x.strip()]
    if not 3 <= len(pool) <= 5:
        return out({"error": "авто-пул утра — от 3 до 5 дел через «;» (сейчас %d)" % len(pool)}, 1)
    lines = []
    for x in pool:
        no = b["next_no"]; b["next_no"] += 1
        nows = [i for i in b["items"] if i["state"] == "now"]
        it = {"no": no, "text": mask(x), "who": "сама", "why": "пул дня", "prio": "", "ts": now_ts(), "pool": True}
        if not nows: it["state"] = "now"
        else:
            q = [i for i in b["items"] if i["state"] == "queue"]
            it.update(state="queue", after=(q[-1] if q else nows[-1])["no"])
        b["items"].append(it); lines.append(no)
    save(b)
    return out({"ok": True, "pool": lines, "text": render_text(b, lang_of(a))})


def render_text(b, lang):
    t = L[lang]
    d = datetime.date.fromisoformat(b["date"]).strftime("%d.%m")
    parts = [t["title"] % d]

    def row(i):
        s = "№%d %s%s" % (i["no"], (t["red"] + " ") if i.get("prio") == "red" else "", i["text"])
        if i.get("who"): s += " · " + i["who"]
        if i.get("carried"): s += " · " + t["carried"]
        if i["state"] == "queue" and i.get("after"): s += " · " + t["after"] % i["after"]
        if i["state"] == "wait":
            s += " · " + t["on"] % (i.get("on", "?"), i.get("asked", "?"))
            mins = int((now_epoch() - float(i.get("wait_since") or now_epoch())) // 60)
            s += " · " + t["mins"] % mins
            if mins >= WAIT_RED_MIN: s = "🔴 " + s + " — " + t["stale"]
        if i["state"] == "done": s += " → " + i.get("result", "") + (" · " + i["evidence"] if i.get("evidence") else "")
        return mask(s)
    for st in ("now", "queue", "wait", "done"):
        rows = [row(i) for i in b["items"] if i["state"] == st]
        parts.append("\n%s\n%s" % (t[st], "\n".join(rows) if rows else t["empty"]))
    text = "\n".join(parts)
    return text if len(text) <= 3800 else text[:3790] + "\n…"


OWNER_RE = re.compile(r"хозя|владел|owner|^вы$|^you$", re.I)


def waiting_owner(b):
    """«Ждёт вас» — дела в ожидании, где ждём хозяина (on: хозяин/владелец/owner или имя из MILA_OWNER_NAME). Для кнопок /status."""
    names = [x.strip().lower() for x in os.environ.get("MILA_OWNER_NAME", "").split(",") if x.strip()]
    res = []
    for i in b["items"]:
        if i["state"] != "wait":
            continue
        on = str(i.get("on") or "").strip()
        if OWNER_RE.search(on) or on.lower() in names:
            res.append({"no": i["no"], "text": mask(i["text"])[:60]})
    return res


def cmd_render(a, b):
    # /status (плагин): empty — плана на сегодня нет; waiting — «ждёт вас» для кнопок. render файл дня не меняет.
    return out({"ok": True, "text": render_text(b, lang_of(a)), "pin": b.get("pin") or {},
                "empty": not b["items"], "waiting": waiting_owner(b)})


def cmd_evening(a, b):
    t = L[lang_of(a)]
    c = {s: [i for i in b["items"] if i["state"] == s] for s in ("done", "now", "queue", "wait")}
    d = datetime.date.fromisoformat(b["date"]).strftime("%d.%m")
    lines = [t["evening"] % (d, len(c["done"]), len(c["now"]), len(c["queue"]), len(c["wait"]))]
    lines += ["✅ №%d %s → %s" % (i["no"], i["text"], i.get("result", "")) for i in c["done"]]
    lines += ["🤝 №%d %s · %s" % (i["no"], i["text"], t["on"] % (i.get("on", "?"), i.get("asked", "?"))) for i in c["wait"]]
    rest = c["now"] + c["queue"]
    if rest: lines.append(t["carry"] % ", ".join("№%d" % i["no"] for i in rest))
    return out({"ok": True, "text": mask("\n".join(lines))})


def cmd_pin(a, b):
    if a.chat and a.message:
        b["pin"] = {"chat_id": str(a.chat), "message_id": str(a.message)}; save(b)
    return out({"ok": True, "pin": b.get("pin") or {}})


def main():
    ap = argparse.ArgumentParser(description="Пульт дня")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add"); p.add_argument("--text", required=True); p.add_argument("--who"); p.add_argument("--why"); p.add_argument("--red", action="store_true")
    p = sp.add_parser("start"); p.add_argument("no", type=int)
    p = sp.add_parser("wait"); p.add_argument("no", type=int); p.add_argument("--on"); p.add_argument("--asked")
    p = sp.add_parser("done"); p.add_argument("no", type=int); p.add_argument("--evidence"); p.add_argument("--result")
    p = sp.add_parser("drop"); p.add_argument("no", type=int); p.add_argument("--why")
    p = sp.add_parser("plan"); p.add_argument("--pool", required=True)
    sp.add_parser("render"); sp.add_parser("evening")
    p = sp.add_parser("pin"); p.add_argument("--chat"); p.add_argument("--message")
    for x in sp.choices.values():
        x.add_argument("--lang", choices=list(L))
    a = ap.parse_args()
    b = load()
    return {"add": cmd_add, "start": cmd_start, "wait": cmd_wait, "done": cmd_done, "drop": cmd_drop, "plan": cmd_plan,
            "render": cmd_render, "evening": cmd_evening, "pin": cmd_pin}[a.cmd](a, b)


if __name__ == "__main__":
    sys.exit(main())
