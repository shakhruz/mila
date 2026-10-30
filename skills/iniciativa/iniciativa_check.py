#!/usr/bin/env python3
"""Инициативность: вопрос хозяину — только с предложением и рекомендацией.
check(text, options=None) → список замечаний; пусто — можно отправлять.
Usage: iniciativa_check.py "<текст>" | [--file] <путь> [--options N]  (или текст из stdin) → замечания и код 1, если они есть."""
import os
import re
import sys

PROPOSE = re.compile(r"\b(предлагаю|советую|рекомендую|если не против)\b|[★⭐]", re.I)
CARD_REC = re.compile(r"^[★⭐]\s*Советую", re.M)   # карточка cards.py: вопрос + варианты + «⭐ Советую: Б» — формат пульта


def check(text, options=None):
    out = []
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    if not lines:
        return ["пусто"]
    first = lines[0]
    asks = "?" in text
    if asks and not PROPOSE.search(text):
        out.append("вопрос без предложения и рекомендации — приходи с решением: «Предлагаю … Если не против, сделаю …»")
    if first.endswith("?") and not PROPOSE.search(first) and not CARD_REC.search(text):
        out.append("первая строка — голый вопрос: «%s» — первой строкой моё предложение" % first[:60])
    if options is not None and options < 2 and (asks or PROPOSE.search(text)):
        out.append("вариантов %d — нужно 2–3, у каждого последствие" % options)
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    n = None
    if "--options" in a:
        i = a.index("--options"); n = int(a[i + 1]); a = a[:i] + a[i + 2:]
    if a[:1] == ["--file"]: a = a[1:]
    t = " ".join(a) if a else sys.stdin.read()
    if len(a) == 1 and "\n" not in t and os.path.isfile(t):   # путь к файлу — проверяю файл, а не строку пути
        t = open(t, encoding="utf-8").read()
    issues = check(t, n)
    for x in issues:
        print("•", x)
    print("инициатива ✓" if not issues else "")
    sys.exit(1 if issues else 0)
