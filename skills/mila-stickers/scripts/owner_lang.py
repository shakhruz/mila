#!/usr/bin/env python3
"""Язык собеседника для всего, что Мила показывает человеку: стикеры, мини-аппы, приветствие — один источник.

Язык владельца — свойство Милы: ~/work/owner.json → "lang" (ru, en, uz, zh, …). Мила пишет его сама:
  owner_lang.py seen [--code <language_code Telegram>] [--text "…"]  — после сообщения владельца
  owner_lang.py set uz                                                 — владелец сам выбрал язык (автоматика его не трогает)
  owner_lang.py get                                                    — код (нет — пусто, код выхода 1)
Язык текста важнее language_code, но меняет язык только два сообщения владельца подряд на одном языке.
OWNER_JSON — путь (тесты). Только stdlib."""
import json, os, re, sys, time

PATH = os.environ.get("OWNER_JSON") or os.path.expanduser("~/work/owner.json")
KNOWN = {"ru": ["uk", "be", "kk", "ky", "tg"], "en": [], "uz": [], "zh": ["zh-cn", "zh-hans", "zh-tw", "zh-hk", "zh-hant"]}
UZ_WORDS = set("va bilan uchun men siz sizga menga qanday rahmat yaxshi kerak nima emas ham salom assalomu alaykum qilib qiling "
               "boʻladi bo'ladi boladi yoʻq yo'q yoq bor iltimos qachon nega hozir bugun ertaga juda ishlar biz qilish".split())
EN_WORDS = set("the and is are you please what how can i my to of it this that with for do does have need want thanks hello".split())


def norm(raw):
    """'ru-RU' / 'zh_Hans' / 'UK' → ru|en|uz|zh или None."""
    raw = str(raw or "").strip().lower().replace("_", "-")
    if not raw:
        return None
    base = raw.split("-")[0]
    for code, also in KNOWN.items():
        if raw == code or base == code or raw in also or base in also:
            return code
    return None


def guess(text):
    """Язык текста или None (коротко, смайлы, цифры, непонятно)."""
    s = (text or "").strip()
    if len(s) < 4:
        return None
    cjk = len(re.findall(r"[一-鿿]", s))
    cyr = re.findall(r"[Ѐ-ӿ]", s)
    lat = re.findall(r"[A-Za-z]", s)
    if cjk >= 2 and cjk >= len(cyr) and cjk * 3 >= len(lat):
        return "zh"
    if len(cyr) > len(lat):
        return "uz" if re.search(r"[ўқғҳЎҚҒҲ]", s) else "ru"
    if len(lat) < 4:
        return None
    if re.search(r"[oOgG][ʻʼ'‘`]", s):
        return "uz"
    words = re.findall(r"[a-zʻʼ']+", s.lower())
    uz, en = sum(w in UZ_WORDS for w in words), sum(w in EN_WORDS for w in words)
    return "uz" if uz > en else ("en" if en > uz else None)


def read(path=None):
    try:
        with open(path or PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write(d, path=None):
    path = path or PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def get(path=None):
    return norm(read(path).get("lang"))


def seen(code=None, text=None, path=None):
    d = read(path)
    if d.get("lang_source") == "owner" and norm(d.get("lang")):
        return norm(d["lang"])
    by_text, by_code, cur = norm(guess(text)), norm(code), norm(d.get("lang"))
    new, src = cur, d.get("lang_source")
    if by_code:
        d["tg_language_code"] = str(code)
    if by_text:
        if not cur or (by_text != cur and d.get("lang_last_text") == by_text):
            new, src = by_text, "text"
        d["lang_last_text"] = by_text
    elif not cur and by_code:
        new, src = by_code, "telegram"
    if new and new != d.get("lang"):
        d["lang"], d["lang_source"], d["lang_ts"] = new, src, time.strftime("%Y-%m-%dT%H:%M:%S%z")
    write(d, path)
    return new


def set_lang(code, path=None):
    c = norm(code)
    if not c:
        raise ValueError("язык %r не знаю; есть: %s" % (code, ", ".join(KNOWN)))
    d = read(path)
    d.update(lang=c, lang_source="owner", lang_ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    write(d, path)
    return c


def main(a):
    opt = lambda k: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else None
    if a[:1] == ["get"]:
        c = get()
        print(c or "")
        return 0 if c else 1
    if a[:1] == ["seen"]:
        print(seen(opt("--code"), opt("--text")) or "")
        return 0
    if a[:1] == ["set"] and len(a) == 2:
        try:
            print(set_lang(a[1]))
            return 0
        except ValueError as e:
            print("ERROR: %s" % e, file=sys.stderr)
            return 2
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
