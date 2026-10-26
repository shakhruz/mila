#!/usr/bin/env python3
"""SCREEN-HAIRPIN-2610: адрес службы экрана — SCREEN_API из окружения; в контейнере — host.containers.internal:8949; вне — tv.milagpt.io.
И голосовой код пары (SCREEN-PAIR-1017) на месте. Без сети. python3 test_screen_api.py"""
import importlib.util, os, sys
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def chk(name, cond, extra=""):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name + ("" if cond else "  " + str(extra)))
SRC = open(os.path.join(H, "screen.py"), encoding="utf-8").read()
HEAD = SRC[:SRC.index("\n", SRC.index("API = "))]   # только шапка до адреса включительно — без запуска команды и без сети
def load(env=None, container=False):
    import types
    fake_os = types.SimpleNamespace(environ=({"SCREEN_API": env} if env else {}), path=types.SimpleNamespace(exists=lambda p: container and p == "/run/.containerenv"))
    g = {"__name__": "scr"}
    exec(compile(HEAD.replace("import ", "import ", 1), "screen.py", "exec"), g)
    g["os"] = fake_os
    line = [l for l in HEAD.splitlines() if l.startswith("API = ")][0]
    exec(line, g); return types.SimpleNamespace(API=g["API"])
chk("в контейнере — служба на хосте напрямую", load(container=True).API == "http://host.containers.internal:8949/api/screen/")
chk("вне контейнера — публичный адрес", load(container=False).API == "https://tv.milagpt.io/api/screen/")
chk("SCREEN_API из окружения — главнее всего", load(env="http://example.test/api/screen/", container=True).API == "http://example.test/api/screen/")
_e = SRC.index("    return (rest[0] if rest else \"\"), \" \".join(rest[1:])", SRC.index("def split_pair")); g = {}; exec(SRC[SRC.index("_W = {"):SRC.index("\n", _e)], g)
chk("голосовой код пары на месте (SCREEN-PAIR-1017): «семьсот тридцать три четыреста восемьдесят девять» → 733489", g["code6"]("семьсот тридцать три четыреста восемьдесят девять".split()) == "733489")
sp = lambda t: g["split_pair"](t.split())
for t, want in (("семьсот тридцать три четыреста восемьдесят девять Кухня", ("733489", "Кухня")), ("сто двадцать три четыреста пятьдесят шесть", ("123456", "")),
                ("двести двадцать два триста тридцать три Зал", ("222333", "Зал")), ("7 3 3 4 8 9 Кухня", ("733489", "Кухня")), ("733489 Большой зал", ("733489", "Большой зал")),
                ("733 489 Кухня", ("733489", "Кухня")), ("семь три три четыре восемь девять", ("733489", ""))):
    chk("pair: «%s» → %s" % (t, want), sp(t) == want, sp(t))
chk("pair: нет шести цифр — код не собирается (дальше pair откажет)", not __import__("re").fullmatch(r"\d{6}", sp("сто двадцать Кухня")[0] or ""))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
