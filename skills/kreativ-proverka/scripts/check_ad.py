#!/usr/bin/env python3
"""check_ad.py — механические правила площадки для текста объявления (kreativ-proverka). Только правила из первоисточника.
  check_ad.py --platform telegram --text "…" [--url https://t.me/канал] [--json]
Telegram Ads (https://ads.telegram.org/guidelines): ≤160 знаков с пробелами; без переносов строк, списков, нумерации; одна ссылка
в тексте и та же, что основная; без сокращателей и IP; без «кричащих» заглавных и замены букв символами; эмодзи не навязчиво;
абсолютные превосходные и «вы выиграли» — нельзя. Смысл (одна мысль, 3 секунды) — чек-листом в SKILL.md, не здесь.
Код: 0 — правила соблюдены; 2 — нарушено (список); 1 — ошибка ввода.
"""
import argparse, json, re, sys, unicodedata

SHORTENERS = ("bit.ly", "tinyurl", "goo.gl", "t.co/", "cutt.ly", "clck.ru", "is.gd", "ow.ly", "rebrand.ly", "vk.cc")
# Telegram запрещает «unsupported use of comparatives and superlatives» — без подтверждения (Качество 22.10)
SUPERLATIVES = r"(?<!\w)(лучш\w*|самы\w+|наилучш\w*|№\s?1|номер\s+один|best|#1|number one|most \w+|eng \w+)(?!\w)"
SUPPORT = r"\d|по данным|по версии|по рейтингу|по оценке|according to|ma'lumotlariga ko"
WON = r"(вы выиграли|вы победили|you( have)? won|siz yutdingiz)"
LINK_RE = re.compile(r"(?:https?://\S+|t\.me/\S+|@[A-Za-z][A-Za-z0-9_]{3,31})")


def emoji_count(t):
    return sum(1 for ch in t if unicodedata.category(ch) == "So" or 0x1F000 <= ord(ch) <= 0x1FAFF)


def norm_link(s):
    s = s.strip().rstrip(".,!?)»").lower()
    s = re.sub(r"^https?://", "", s)
    if s.startswith("@"):
        s = "t.me/" + s[1:]
    return s.rstrip("/")


def check_telegram(text, url):
    bad, warn = [], []
    if len(text) > 160:
        bad.append(f"длина {len(text)} > 160 знаков с пробелами")
    if "\n" in text or "\r" in text:
        bad.append("перенос строки — в Telegram Ads нельзя")
    if re.search(r"(^|\s)([-•*·▪►✔✅]|\d+[.)])\s", text):
        bad.append("похоже на список или нумерацию — нельзя")
    links = LINK_RE.findall(text)
    if len(links) > 1:
        bad.append(f"ссылок в тексте {len(links)} — можно одну")
    if links and url and norm_link(links[0]) != norm_link(url):
        bad.append(f"ссылка в тексте ({links[0]}) ведёт не туда, куда основная ({url})")
    if any(s in text.lower() for s in SHORTENERS) or (url and any(s in url.lower() for s in SHORTENERS)):
        bad.append("сокращатель ссылок — нельзя")
    if re.search(r"https?://\d{1,3}(\.\d{1,3}){3}", text + " " + (url or "")):
        bad.append("IP-адрес вместо домена — нельзя")
    words = re.findall(r"[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ]{4,}", text)
    caps = [w for w in words if w.isupper()]
    if len(caps) >= 2:   # «excessive» — два и больше слова капсом
        bad.append(f"«кричащие» заглавные: {' '.join(caps[:4])}")
    elif caps:
        warn.append(f"слово капсом «{caps[0]}» — площадка может счесть навязчивым; лучше обычным регистром")
    if re.search(r"[A-Za-z][А-Яа-яЁё]|[А-Яа-яЁё][A-Za-z]", text):
        warn.append("латиница и кириллица в одном слове — похоже на замену букв, площадка может отклонить")
    if re.search(r"(?<!\w)(?:[^\W\d_] ){3,}[^\W\d_](?!\w)", text):
        bad.append("разрядка букв («С К И Д К А») — нельзя")
    e = emoji_count(text)
    if e > 2:
        warn.append(f"эмодзи {e} — «не навязчиво»: оставьте 1–2")
    sup = re.search(SUPERLATIVES, text, re.I)
    if sup and re.search(SUPPORT, text, re.I):
        warn.append(f"превосходная «{sup.group(0)}» — нужно подтверждение: цифра или источник рядом есть, проверьте, что это правда")
    elif sup:
        bad.append(f"превосходная «{sup.group(0)}» без подтверждения — нельзя; добавьте цифру или источник («40 сортов», «по данным …») или уберите")
    if re.search(WON, text, re.I):
        bad.append("«вы выиграли» — нельзя")
    if text.count("!") > 1:
        warn.append("больше одного «!» — читается как кликбейт")
    return bad, warn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", default="telegram", choices=["telegram"])
    ap.add_argument("--text", required=True)
    ap.add_argument("--url", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not a.text.strip():
        print("нет текста объявления"); return 1
    bad, warn = check_telegram(a.text, a.url)
    if a.json:
        print(json.dumps({"ok": not bad, "length": len(a.text), "bad": bad, "warn": warn}, ensure_ascii=False))
    else:
        print(("✅ правила площадки соблюдены" if not bad else "❌ нарушены правила площадки:") + f" ({len(a.text)}/160)")
        for b in bad: print("  ✖ " + b)
        for w in warn: print("  ⚠ " + w)
        print("Источник: https://ads.telegram.org/guidelines. Смысл — чек-лист в SKILL.md.")
    return 0 if not bad else 2


if __name__ == "__main__":
    sys.exit(main())
