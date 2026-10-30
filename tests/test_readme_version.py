#!/usr/bin/env python3
"""«Текущий выпуск» во всех четырёх README = версия release.json (в трёх переводах строка стояла на v1.5.3 с 17.10 — никто не заметил)."""
import json, os, re, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tag = json.load(open(os.path.join(R, "release.json")))["tag"]
ok = n = 0
for f in ("README.md", "README.ru.md", "README.uz.md", "README.zh-CN.md"):
    t = open(os.path.join(R, f), encoding="utf-8").read()
    got = re.findall(r"\[(v\d+\.\d+\.\d+)\]\(https://github\.com/shakhruz/mila-agent/releases/latest\)", t)
    if not got and "releases/latest" in t and f == "README.md":   # первый экран — бейдж выпуска (тянет версию сам), строки нет
        n += 1; ok += 1; print("✅ %s: бейдж выпуска, строки версии нет" % f); continue
    n += 1; good = got == [tag]; ok += good
    print(("✅ " if good else "❌ ") + "%s: текущий выпуск %s (release.json %s)" % (f, got, tag))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
