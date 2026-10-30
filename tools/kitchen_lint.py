#!/usr/bin/env python3
"""kitchen_lint.py — следы «кухни» не в публичном ядре: внутренние коды задач (вида АБВ-ДДММ латиницей), ссылки на номера
чьих-то сообщений («владелец NNNNN», «личка NNNNN», «msg NNN», «dev NNNN»), время приёмок («Качество ЧЧ:ММ»), номера раскаток
(ROLL…OUT с номером), датированные ссылки на чьё-то решение, личные пути одного дома. Смысл правила остаётся — уходит только «кто,
когда, какой номер».
  kitchen_lint.py            — проверка (файлы git, кроме CHANGELOG.md и legacy/), код 1 при находках
  kitchen_lint.py --fix      — убрать метки на месте (только метки и пустые скобки/знаки, оставшиеся от них)
  kitchen_lint.py --log A..B — те же метки в сообщениях коммитов диапазона (история публичная), код 1 при находках"""
import re, subprocess, sys

CODE = r"\b[A-Z][A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]{4}[a-z]?\b(?: [a-f]\b(?=[\s):,—]))?"
TOKENS = [
    CODE,
    r"[Сс]лово владельца(?: MILAGPT)? \d{1,2}\.\d{1,2}(?:\.\d{4})?(?: \d\d:\d\d)?(?: \(\d{3,6}\))?",
    r"\bвладел(?:ец|ьца)(?: MILAGPT)? \d{4,6}\b",
    r"\b(?:личка|msg|dev|dev-чат) \d{3,6}\b",
    r"\b(?:Качество|Качества|старш\w{1,3}|Админ) \d\d:\d\d(?: 🟡\d?| 🔴| 🟢)?",
    r"\bROLL" + r"OUT ?№ ?\d+\b",
    r"\b(?:старш\w{1,3}|Качество|Качества|Вебмастер|Админ)(?: \d{1,2}\.\d{1,2})(?: \d\d:\d\d)?(?: 🟡\d?| 🔴| 🟢)?",
]
RX = re.compile("|".join("(?:%s)" % t for t in TOKENS))
EXCLUDE = re.compile(r"^(CHANGELOG\.md|legacy/|tools/kitchen_lint\.py|tools/test_kitchen_lint\.py)")


def files():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
    return [f for f in out if not EXCLUDE.match(f) and not f.endswith((".png", ".jpg", ".gif", ".mp3", ".mp4", ".bundle", ".ico", ".woff2"))]


T = "(?:%s)" % "|".join("(?:%s)" % x for x in TOKENS)
STEPS = [   # только вокруг самой метки: скобки и знаки, которые без неё остались бы пустыми; чужие «()» в коде не трогаю
    (re.compile(r"\s*#\s*%s\s*$" % T), ""),                     # хвост «  # CODE» в строке кода
    (re.compile(r"\s*\(\s*(?:%s\s*[,;]?\s*)+\)" % T), ""),       # «(CODE)», «(CODE, CODE)»
    (re.compile(r"\(\s*%s\s*[,;:]\s*" % T), "("),                 # «(CODE, остальное)» → «(остальное)»
    (re.compile(r"\s*[,;]\s*%s(?=\s*\))" % T), ""),               # «(остальное, CODE)» → «(остальное)»
    (re.compile(r"%s\s*[:—–;,]\s*" % T), ""),                      # «CODE: текст», «CODE — текст», «CODE, текст»
    (re.compile(r"\s*[,;]\s*%s" % T), ""),                         # «…, CODE»
    (re.compile(r" ?%s" % T), ""),                                    # остальное — просто убрать
]


def clean(line):
    s = line
    for rx, rep in STEPS:
        s = rx.sub(rep, s)
    s = re.sub(r'^(\s*(?:#|//|""")) +(?=\S)', r"\1 ", s)                # «#   текст» → «# текст» (только отступ после маркера)
    return s.rstrip() + ("\n" if line.endswith("\n") else "")


REVIEW = re.compile(r"\((?:Quality|Качество|senior|старш\w*|admin)[^)]*\)", re.I)   # «(Quality 11:21)» — ссылка на приёмку


def check_log(rng):
    out = subprocess.run(["git", "log", "--format=%h%x00%B%x01", rng], capture_output=True, text=True)
    if out.returncode:
        print(out.stderr.strip()); return 2
    found = 0
    for rec in out.stdout.split("\x01"):
        if "\x00" not in rec:
            continue
        h, body = rec.strip().split("\x00", 1)
        for l in body.splitlines():
            if l.startswith("Co-Authored-By:"):
                continue
            if RX.search(l) or REVIEW.search(l):
                found += 1; print("%s: %s" % (h, l.strip()[:140]))
    print("следов кухни в сообщениях коммитов: %d" % found)
    return 1 if found else 0


def main():
    if "--log" in sys.argv:
        sys.exit(check_log(sys.argv[sys.argv.index("--log") + 1]))
    fix = "--fix" in sys.argv
    found = 0
    for f in files():
        try:
            lines = open(f, encoding="utf-8").readlines()
        except (UnicodeDecodeError, OSError):
            continue
        new = []
        for i, l in enumerate(lines, 1):
            if RX.search(l):
                found += 1
                if not fix:
                    print("%s:%d: %s" % (f, i, l.strip()[:140]))
                l = clean(l) if fix else l
            new.append(l)
        if fix and new != lines:
            open(f, "w", encoding="utf-8").writelines(new)
    print(("убрано меток в строках: %d" if fix else "следов кухни: %d") % found)
    sys.exit(0 if fix or not found else 1)


if __name__ == "__main__":
    main()
