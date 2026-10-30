#!/usr/bin/env python3
"""iniciativa_check: вопрос без варианта и рекомендации → отказ; предложение с «если не против» → можно;
карточка cards.py (вопрос + «⭐ Советую») → можно; вариантов меньше двух → отказ. Пробы — как в SKILL.md."""
import os, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from iniciativa_check import check
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
bad = ["Хотите №4 завтра утром или послезавтра?", "Когда выпускаем?", "Сколько сделать?", "Что посоветуете?", "Ответить ей? Что сказать?",
       "Ролик готов.\nКогда выпускаем?"]
for t in bad:
    chk("вопрос без варианта и рекомендации → отказ: «%s»" % t.replace("\n", " / "), any("без предложения" in x for x in check(t)), check(t))
chk("первая строка — голый вопрос → отдельное замечание", any("голый вопрос" in x for x in check("Когда выпускаем?")))
good = "Предлагаю «Фото дня» №4 сегодня в 19:00 — вечером охват выше.\nЕсли не против, выпущу в 19:00 и пришлю ссылку."
chk("пример «Хорошо» из SKILL.md → можно", check(good, 3) == [], check(good, 3))
card = "Платим за домен?\nСрок истекает сегодня.\nА — Да: домен наш\nБ — Нет: сайт ляжет\n⭐ Советую: А"
chk("карточка cards.py (вопрос + варианты + ⭐ Советую) → можно", check(card, 2) == [], check(card, 2))
chk("рекомендация есть, но вариант один → отказ", any("вариантов 1" in x for x in check(good, 1)), check(good, 1))
chk("отчёт без вопроса и без предложения → не мешаю", check("Выложила сайт, дым 5/5.") == [])
chk("«посоветуете?» не считается рекомендацией (целое слово «советую»)", check("Что посоветуете?") != [])
r = subprocess.run([sys.executable, os.path.join(H, "iniciativa_check.py"), "Когда выпускаем?"], capture_output=True, text=True)
chk("командная строка: замечание и код 1", r.returncode == 1 and "без предложения" in r.stdout, r.stdout)
r = subprocess.run([sys.executable, os.path.join(H, "iniciativa_check.py"), "--options", "3"], input=good, capture_output=True, text=True)
chk("командная строка: текст из stdin, --options 3 → код 0", r.returncode == 0 and "✓" in r.stdout, r.stdout + r.stderr)
import tempfile
f = os.path.join(tempfile.mkdtemp(), "ic.txt"); open(f, "w").write("Ответить ей?")
for args in ([f], ["--file", f]):
    r = subprocess.run([sys.executable, os.path.join(H, "iniciativa_check.py"), *args], capture_output=True, text=True)
    chk("путь к файлу с голым вопросом (%s) — проверяю файл, замечание" % " ".join(a if a == "--file" else "путь" for a in args), r.returncode == 1 and "без предложения" in r.stdout, r.stdout)
r = subprocess.run([sys.executable, os.path.join(os.path.dirname(H), "plain-words", "plain_words_check.py"), f], capture_output=True, text=True)
chk("plain_words_check тоже читает файл по пути", r.returncode == 1 and "инициатива" in r.stdout, r.stdout)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
