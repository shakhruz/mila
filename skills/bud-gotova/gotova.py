#!/usr/bin/env python3
"""Будь готова: проверка инспекции перед событием (слово владельца 28.10).
  gotova.py check inspekciya.json [--now ISO]  → {"ready", "missing", "weak", "gaps", "owner_card"}; код 0 — готова, 1 — нет.
Готова — только когда у всех семи пунктов инспекции есть улика (не «помню / вроде / должно») и у каждой нехватки
есть «кто» и «к когда», и ни одна нехватка не просрочена. Хозяину — карточка только из нехваток с who=хозяин."""
import datetime as dt, json, re, sys

ITEMS = ["цель", "люди", "материалы", "инструменты", "вопросы", "шаг", "запасной"]
WEAK = re.compile(r"^\s*$|\b(помню|вроде|должно|наверно|наверное|скорее всего|как обычно|todo)\b", re.I)


def _t(s):
    try: return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError): return None


def check(d, now=None):
    now = now or dt.datetime.now().astimezone()
    items = d.get("items") or {}
    missing = [k for k in ITEMS if k not in items]
    weak = [k for k in ITEMS if k in items and WEAK.search(str(items[k] or ""))]
    gaps, bad = [], []
    for g in d.get("gaps") or []:
        w, who, by = str(g.get("what") or "").strip(), str(g.get("who") or "").strip(), _t(g.get("by"))
        why = [x for x, c in (("нет «кто»", not who), ("нет «к когда»", not by), ("просрочено", by and by.tzinfo and by < now)) if c]
        gaps.append({"what": w, "who": who, "by": g.get("by"), "problem": why})
        if why: bad.append(w)
    owner = [g["what"] for g in gaps if g["who"].lower() in ("хозяин", "владелец", "owner")]
    ready = not missing and not weak and not gaps
    card = ("К «%s» не хватает от вас:\n" % d.get("event", "событию") + "\n".join("· " + x for x in owner)) if owner else ""
    return {"ready": ready, "missing": missing, "weak": weak, "gaps": gaps, "gaps_without_owner_or_time": bad, "owner_card": card}


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2 or a[0] != "check":
        sys.exit(__doc__)
    now = _t(a[a.index("--now") + 1]) if "--now" in a else None
    try: d = json.load(open(a[1], encoding="utf-8"))
    except (OSError, ValueError) as e: sys.exit("инспекция не прочитана: %s" % type(e).__name__)
    r = check(d, now)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r["ready"] else 1)
