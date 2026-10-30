#!/usr/bin/env python3
"""plan-fakt · draft of the week's facts from the Mila's own files — a starting point she rewrites in her words.

  collect.py [--work ~/work] [--monday YYYY-MM-DD] > data.draft.json

Sources (only what exists; missing → "нет данных", never a guess):
- ~/work/WEEK.md — the week plan (lines "- [x] …", "- [ ] …", "🟢/🟡/🔴/⚪ …" become the plan slide);
- ~/work/state/day-<date>.json Mon–Fri — the day boards (pult-dnya): done with evidence, waiting, carried;
- ~/work/MONEY.md — money only if the Mila keeps it; lines "Ключ: значение" become cover tiles. No file → no money slide.
Output: data.json for make_slides.py with "draft": true and "facts" (counts, sources) for the post text.
"""
import argparse, datetime, glob, json, os, re, sys

MARK = {"done": "🟢", "now": "🟡", "queue": "⚪", "wait": "🟡", "dropped": "⚪"}

# Личные данные на слайд не попадают: WEEK.md и MONEY.md — свободный текст. Как пульт дня (pult-dnya):
# карта → ****1234 (окно 13–19 цифр с Луной), телефон в форме телефона → ⟦тел⟧, почта → ⟦почта⟧.
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


def _is_phone(m, s):
    t = m.group(0); d = re.sub(r"\D", "", t)
    if t.startswith("****") or s[:m.start()].rstrip().endswith("№") or len(d) >= 16:
        return False
    if s[max(0, m.start() - 1):m.start()] == "-" and d.startswith("100"):
        return False
    if t.startswith("+"):
        return 11 <= len(d) <= 13
    if re.search(r"[ ()\-]", t):
        return 9 <= len(d) <= 12
    return (len(d) == 12 and d.startswith("998")) or (len(d) == 11 and d[0] in "78")


def mask(s):
    s = str(s or "")
    def card(m):
        txt = m.group(0); digs = [(g.start(), g.end()) for g in re.finditer(r"\d+", txt)]
        for i in range(len(digs)):
            for j in range(len(digs) - 1, i - 1, -1):
                d = re.sub(r"\D", "", txt[digs[i][0]:digs[j][1]])
                if 13 <= len(d) <= 19 and len(set(d)) > 1 and _luhn(d):
                    return txt[:digs[i][0]] + "****" + d[-4:] + txt[digs[j][1]:]
        return txt
    s = CARD_RE.sub(card, s)
    s = MAIL_RE.sub("⟦почта⟧", s)
    return PHONE_RE.sub(lambda m: "⟦тел⟧" if _is_phone(m, s) else m.group(0), s)


def week_days(monday):
    return [(monday + datetime.timedelta(days=i)).isoformat() for i in range(5)]


def read_boards(work, days):
    items = {}
    for d in days:
        p = os.path.join(work, "state", "day-%s.json" % d)
        try:
            b = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for it in b.get("items") or []:
            items[it.get("no")] = it          # later day wins: carried items keep their number
    return list(items.values())


def plan_rows(work):
    try:
        t = open(os.path.join(work, "WEEK.md"), encoding="utf-8").read()
    except OSError:
        return None
    rows = []
    for line in t.splitlines():
        m = re.match(r"\s*[-*]\s*\[( |x|X)\]\s*(.+)", line)
        if m:
            rows.append(["🟢" if m.group(1).lower() == "x" else "🟡", mask(m.group(2).strip())[:60]]); continue
        m = re.match(r"\s*[-*]?\s*(🟢|🟡|🔴|⚪)\s*(.+)", line)
        if m:
            rows.append([m.group(1), mask(m.group(2).strip())[:60]])
    return rows[:6]


def money_tiles(work):
    try:
        t = open(os.path.join(work, "MONEY.md"), encoding="utf-8").read()
    except OSError:
        return None
    tiles = []
    for line in t.splitlines():
        m = re.match(r"\s*[-*]?\s*([^:#]{2,40}):\s*(.+)$", line)
        if m and re.search(r"\d", m.group(2)):
            tiles.append([mask(m.group(2).strip())[:14], mask(m.group(1).strip())[:40], ""])
    return tiles[:3] or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=os.environ.get("MILA_WORK") or os.path.expanduser("~/work"))
    ap.add_argument("--monday")
    a = ap.parse_args()
    today = datetime.date.today()
    monday = datetime.date.fromisoformat(a.monday) if a.monday else today - datetime.timedelta(days=today.weekday())
    days = week_days(monday)
    items = read_boards(a.work, days)
    done = [i for i in items if i.get("state") == "done"]
    wait = [i for i in items if i.get("state") == "wait"]
    open_ = [i for i in items if i.get("state") in ("now", "queue")]
    plan = plan_rows(a.work)
    money = money_tiles(a.work)
    week = monday.isocalendar()[1]
    dates = "%s–%s" % (monday.strftime("%d.%m"), (monday + datetime.timedelta(days=4)).strftime("%d.%m"))
    boards = sum(os.path.isfile(os.path.join(a.work, "state", "day-%s.json" % d)) for d in days)
    # нет пультов — не «0 сделано» (ноль читается как факт), а «нет данных»
    tiles = money or ([[str(len(done)), "сделано за неделю<br>с уликой", ""], [str(len(wait)), "ждут ответа", "sand"],
                       [str(len(open_)), "переходят<br>на следующую", ""]] if boards else [["—", "нет данных:<br>пультов дня за неделю нет", "sand"]])
    slides = []
    slides.append({"title": "План <em>недели</em>", "kicker": "" if plan else "нет WEEK.md — плана недели нет",
                   "rows": plan or [["⚪", "нет данных: план недели не записан"]]})
    slides.append({"title": "Сделано", "kicker": ("%d с уликой" % len(done)) if boards else "нет данных",
                   "rows": [["🟢", mask(i.get("text") or "")[:60]] for i in done[:5]] or [["⚪", "нет данных: пультов дня за неделю нет" if not boards else "нет данных: сделанного с уликой нет"]]})
    if wait:
        slides.append({"title": "Ждёт <em>вашего слова</em>", "kicker": "%d" % len(wait),
                       "rows": [["⭐", mask("№%s %s" % (i.get("no"), i.get("text") or ""))[:60]] for i in wait[:5]]})
    if money:
        slides.insert(1, {"title": "Деньги", "kicker": "из MONEY.md", "rows": [["💰", "%s — %s" % (t[1], t[0])] for t in money]})
    out = {"draft": True, "week": str(week), "dates": dates, "day": "пятница " + (monday + datetime.timedelta(days=4)).strftime("%d.%m"),
           "brand": "ПЛАН-ФАКТ", "author": "",
           "cover": {"title": "Итог <em>недели</em>", "lead": "Перепишите одной фразой: главный вывод недели." if (boards or plan is not None)
                     else "Нет данных: файлов недели нет (ни WEEK.md, ни пультов дня).", "tiles": tiles},
           "slides": slides,
           "facts": {"days_with_board": boards,
                     "done": len(done), "wait": len(wait), "open": len(open_), "money": bool(money), "week_plan": plan is not None}}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
