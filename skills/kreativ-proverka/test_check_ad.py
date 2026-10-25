#!/usr/bin/env python3
"""kreativ-proverka: правила Telegram Ads скриптом. python3 test_check_ad.py"""
import os, subprocess, sys
S = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "check_ad.py")
ok = n = 0
def run(text, url="https://t.me/mila_gpt_bot"):
    r = subprocess.run([sys.executable, S, "--text", text, "--url", url], capture_output=True, text=True)
    return r.returncode, r.stdout
def chk(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + x[:300]))
good = "Мила отвечает клиентам за 3 минуты днём и ночью — ни одна заявка не потеряется. Попробуйте 3 дня: t.me/mila_gpt_bot"
c, o = run(good); chk("нормальное объявление (115 знаков, одна ссылка туда же) — код 0", c == 0, o)
c, o = run("а" * 161); chk("161 знак — нарушение длины", c == 2 and "161 > 160" in o, o)
c, o = run("Строка\nвторая"); chk("перенос строки — нельзя", c == 2 and "перенос" in o, o)
c, o = run("1) первое 2) второе"); chk("нумерация — нельзя", c == 2 and "нумерац" in o, o)
c, o = run("Пишите: t.me/a_bot или t.me/b_bot"); chk("две ссылки — нельзя", c == 2 and "ссылок в тексте 2" in o, o)
c, o = run("Пишите: t.me/other_bot", "https://t.me/mila_gpt_bot"); chk("ссылка в тексте не туда, куда основная", c == 2 and "не туда" in o, o)
c, o = run("Подробнее: bit.ly/x1"); chk("сокращатель — нельзя", c == 2 and "сокращатель" in o, o)
c, o = run("ЛУЧШИЙ бот СЕЙЧАС"); chk("два слова капсом и «лучший» без подтверждения — нельзя", c == 2 and "заглавные" in o and "без подтверждения" in o, o)
c, o = run("Лучший чай в городе!"); chk("«Лучший чай в городе!» — без подтверждения, нельзя", c == 2 and "без подтверждения" in o, o)
c, o = run("Самый большой выбор улунов в Ташкенте — 40 сортов"); chk("«самый…» с цифрой — предупреждение, не запрет", c == 0 and "нужно подтверждение" in o, o)
c, o = run("Самый быстрый ответ в городе"); chk("«самый» без цифры — нельзя (раньше не ловился)", c == 2 and "без подтверждения" in o, o)
c, o = run("Лучший тур по данным TripAdvisor 2026"); chk("«лучший» со ссылкой на источник — предупреждение", c == 0 and "нужно подтверждение" in o, o)
c, o = run("НОВИНКА: туры в Самарканд"); chk("одно слово капсом — предупреждение", c == 0 and "капсом" in o, o)
c, o = run("СКИДКА 🔥 на туры в Дубай"); chk("«СКИДКА» с эмодзи — предупреждение, не запрет (выровнено)", c == 0 and "капсом" in o, o)
c, o = run("Курсы IT и SMM для iPhone-фотографов"); chk("IT, SMM, iPhone — не капс", c == 0 and "капсом" not in o, o)
c, o = run("Вы выиграли поездку"); chk("«вы выиграли» — нельзя", c == 2, o)
c, o = run("С К И Д К А на туры"); chk("разрядка — нельзя", c == 2 and "разрядка" in o, o)
c, o = run("Тур в Стамбул 🔥🔥🔥 от $300"); chk("эмодзи ×3 — предупреждение, не запрет", c == 0 and "эмодзи 3" in o, o)
c, o = run("Тур в Дубай за 5 ночей от $450, вылет из Ташкента — t.me/mila_gpt_bot"); chk("цифры и факт — без нарушений", c == 0, o)
print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
