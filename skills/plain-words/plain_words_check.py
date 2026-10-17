#!/usr/bin/env python3
"""Проверка карточки пульта по правилам «Ясно» (SKILL.md). Печатает замечания; код 1, если они есть."""
import re
import sys

# Целые слова/корни с границей слова: «прод» не должен ловить «продлить», «продукт», «продажи».
BANNED = [r"превью", r"деплой\w*", r"прод(?:е|а|у)?", r"стенд\w*", r"прогон\w*", r"перегон\w*", r"трекшн\w*",
          r"milestone", r"онбординг\w*", r"эскалац\w*", r"дедлайн\w*", r"апрув\w*", r"таргет\w*", r"лид(?:ы|ов|а|у)?",
          r"выкладк\w*"]
CODE = re.compile(r"\b(M-\d+|D-\d+|R\d+|\d{4,6})\b")


def check(text: str) -> list[str]:
    out = []
    body = text.split("\n")
    first = next((l for l in body if l.strip()), "")
    if len(first.split()) > 12:
        out.append(f"первая строка {len(first.split())} слов (≤12): «{first[:60]}…»")
    if text.count("?") > 1:
        out.append(f"вопросов {text.count('?')} — одна карточка, одно решение")
    for s in re.split(r"(?<=[.!?…])\s+|\n", text):
        n = len(s.split())
        if n > 20:
            out.append(f"предложение {n} слов (≤20): «{s[:60]}…»")
    for w in BANNED:
        m = re.search(r"(?<!\w)" + w + r"(?!\w)", text, re.I)
        if m:
            out.append(f"слово «{m.group(0)}» — см. таблицу замен")
    for m in CODE.findall(text):
        out.append(f"код/номер «{m}» в тексте — перенести в конец в скобки или убрать")
    if re.search(r"Решай сама|Пауза|Как дела", text):
        out.append("кнопки движения на карточке выбора — убрать")
    return out


if __name__ == "__main__":
    t = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    issues = check(t)
    for i in issues:
        print("•", i)
    if not issues:
        print("ясно ✓")
    sys.exit(1 if issues else 0)
