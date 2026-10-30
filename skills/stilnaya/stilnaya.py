#!/usr/bin/env python3
"""Мила стильная: задания трём независимым взглядам и свод их ответов.
  stilnaya.py prompts --audience «кто смотрит» --goal «что должно случиться»   → JSON: три задания, каждое отдельно
  stilnaya.py svod a.json b.json c.json   → {"ready", "amateur_by", "main_fix", "minor", "agree", "disagree"}; код 1 — не готово
Ответ взгляда (JSON): {"role", "verdict": "профи"|"любитель", "main_fix": "…", "minor": ["…"], "sources": ["…"]}."""
import json, sys
from collections import Counter

ROLES = {
    "бренд": "Ты арт-директор сильной студии. Смотри только на картинки: типографика, сетка, цвет, система, единство. ",
    "тренды": "Ты знаешь визуальные тренды этого и прошлого года и персонажей брендов. Что выглядит дорого, что устарело. "
              "Где оценка, а где источник — помечай. ",
    "доверие": "Ты — представитель аудитории. Что снижает твоё доверие к этому материалу и к деньгам или времени, которые просят. ",
}
OUT = ('Ответ строго JSON: {"role": "%s", "verdict": "профи" или "любитель", "main_fix": "одна главная правка", '
       '"minor": ["до двух второстепенных"], "sources": ["ссылки, если есть"]}. Мнений других экспертов ты не видишь.')


def prompts(audience, goal):
    return [{"role": r, "prompt": ROLES[r] + "Аудитория: %s. Цель: %s. " % (audience, goal) + OUT % r} for r in ROLES]


def svod(answers):
    v = {a.get("role", "?"): a for a in answers}
    amateur = [r for r, a in v.items() if a.get("verdict") != "профи"]
    fixes = Counter((a.get("main_fix") or "").strip() for a in v.values() if (a.get("main_fix") or "").strip())
    main = ""
    if fixes:
        top, cnt = fixes.most_common(1)[0]
        main = top if cnt > 1 else next((v[r]["main_fix"] for r in ("доверие", "бренд", "тренды") if r in v and v[r].get("main_fix")), top)
    minor = []
    for a in v.values():
        for m in a.get("minor") or []:
            if m and m != main and m not in minor: minor.append(m)
    return {"ready": not amateur and len(v) >= 3, "amateur_by": amateur, "main_fix": main, "minor": minor[:2],
            "agree": [f for f, c in fixes.items() if c > 1], "disagree": sorted(set(r for r in v) - set(amateur)) if amateur else []}


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["prompts"] and "--audience" in a and "--goal" in a:
        print(json.dumps(prompts(a[a.index("--audience") + 1], a[a.index("--goal") + 1]), ensure_ascii=False, indent=1))
    elif a[:1] == ["svod"] and len(a) >= 2:
        try: ans = [json.load(open(p, encoding="utf-8")) for p in a[1:]]
        except (OSError, ValueError) as e: sys.exit("ответ взгляда не прочитан: %s" % type(e).__name__)
        r = svod(ans); print(json.dumps(r, ensure_ascii=False, indent=1)); sys.exit(0 if r["ready"] else 1)
    else:
        sys.exit(__doc__)
