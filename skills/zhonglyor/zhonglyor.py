#!/usr/bin/env python3
"""Жонглёр задач: когда и как браться за новое поручение, если в работе уже что-то есть.
  zhonglyor.py when [--urgent] [--current-left N] [--prio today|week]  → now | finish-first | queue-today | queue-week
  zhonglyor.py how --kind short|search|bulk|routine|other-mila|money|text-out  → способ одной строкой
Правила — из SKILL.md; скрипт ничего не запускает, только отвечает."""
import json, sys

HOW = {
    "short": "сама, сейчас",
    "search": "помощник (Explore): в мой разговор — только вывод",
    "bulk": "параллельно: фоном или workflow, если хозяин разрешил",
    "routine": "помощник на лёгкой модели; «что это» по правилам — Jev",
    "other-mila": "записка другой Миле с фактами и границами, проверка «взяла»",
    "money": "готовлю и спрашиваю «да» кнопками — сама не делаю",
    "text-out": "сама на сильной модели: текст наружу — не лёгкой",
}


def when(urgent=False, current_left=None, prio="week"):
    if urgent:
        return "now"                       # деньги, человек ждёт, сломано, событие сегодня — текущее паузой с заметкой
    if current_left is not None and current_left <= 3:
        return "finish-first"              # почти готовое не бросаю ради несрочного
    return "queue-today" if prio == "today" else "queue-week"


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["when"]:
        cl = int(a[a.index("--current-left") + 1]) if "--current-left" in a else None
        pr = a[a.index("--prio") + 1] if "--prio" in a else "week"
        print(json.dumps({"when": when("--urgent" in a, cl, pr)}))
    elif a[:1] == ["how"] and "--kind" in a:
        k = a[a.index("--kind") + 1]
        if k not in HOW:
            sys.exit("kind — одно из: " + ", ".join(HOW))
        print(json.dumps({"how": HOW[k]}, ensure_ascii=False))
    else:
        sys.exit(__doc__)
