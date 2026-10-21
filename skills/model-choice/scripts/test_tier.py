#!/usr/bin/env python3
"""Пять вопросов → уровень модели: таблица задач Мил 21.10 как тест."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tier import tier
cases = [
    ("гость 24/7: приветствие, частый вопрос", dict(), "light"),
    ("ответы оператора продуктового бота", dict(), "light"),
    ("рутина агента: пульс, «ничего нового»", dict(can_wait=True), "light"),
    ("документ, предложение для дела клиента", dict(hard=True, costly=True, rare=True, can_wait=True, valuable=True), "strong"),
    ("проверка качества, публичный текст", dict(hard=True, costly=True, can_wait=True, valuable=True), "strong"),
    ("гость хочет купить или оплатить", dict(costly=True, valuable=True), "strong"),
    ("шаблон, но ошибка вредит (доза, цена клиенту, срок визы)", dict(costly=True), "strong"),
    ("письмо от имени владельца", dict(in_name=True), "strong+yes"),
    ("оплата или удаление", dict(irreversible=True), "strong+yes"),
]
ok = 0
for name, kw, want in cases:
    got = tier(**kw)["tier"]
    ok += got == want
    print(("✅ " if got == want else "❌ ") + f"{name}: {got}" + ("" if got == want else f" (ждали {want})"))
print(f"итог {ok}/{len(cases)}")
sys.exit(0 if ok == len(cases) else 1)
