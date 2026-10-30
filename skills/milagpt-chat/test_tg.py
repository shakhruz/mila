#!/usr/bin/env python3
"""milagpt-chat/tg.py: «\\» и служебный \\x00. Разбор вывода по правилам MarkdownV2 Bot API (мини-проверка). Запуск: python3 test_tg.py [папка_с_tg.py]"""
import os, sys
sys.path.insert(0, os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
import tg
SP = set(r'_*[]()~`>#+-=|{}.!')
def plain_after(s):
    """Текст вне разметки: «\\X» → X; голый спецсимвол вне разрешённой разметки → ошибка. Разметку (* _ ` > [ ] ( )) допускаем парную."""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            if i + 1 >= len(s): raise ValueError("висящий \\\\")
            out.append(s[i + 1]); i += 2; continue
        if c in "*_`>[]()~": i += 1; continue
        if c in SP: raise ValueError("голый " + c)
        out.append(c); i += 1
    return "".join(out)
ok = tot = 0
def chk(n, c, x=""):
    global ok, tot; tot += 1; ok += bool(c); print(("✅ " if c else "❌ ") + n, "" if c else x)
for s in ["C:\\Users\\mila", "a\\.b", "x\\", "путь: \\\\server\\share.txt", "один \\ и точка."]:
    try: r = plain_after(tg.convert(s)); chk(f"«\\» в тексте: {s!r}", r == s, repr(r))
    except Exception as e: chk(f"«\\» в тексте: {s!r}", False, str(e))
for s in ["\x000\x00", "a\x001\x00b **b**", "текст \x00 середина"]:
    try: tg.convert(s); chk(f"служебный \\x00 во входе: {s!r} — без исключения", True)
    except Exception as e: chk(f"служебный \\x00 во входе: {s!r}", False, type(e).__name__)
chk("контроль: **жирный** → *жирный*, __курсив__ → _курсив_", tg.convert("**ж** и __к__") == "*ж* и _к_", tg.convert("**ж** и __к__"))
chk("контроль: точка и дефис экранируются", tg.convert("1.5 - 2!") == "1\\.5 \\- 2\\!")
chk("контроль: код — только ` и \\", tg.convert("`a\\b`") == "`a\\\\b`", tg.convert("`a\\b`"))
chk("контроль: ссылка и цитата", tg.convert("[сайт](https://a.b/c)\n> цитата.") == "[сайт](https://a.b/c)\n>цитата\\.", tg.convert("[сайт](https://a.b/c)\n> цитата."))
print(f"итог {ok}/{tot}"); sys.exit(0 if ok == tot else 1)
