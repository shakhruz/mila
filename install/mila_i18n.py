#!/usr/bin/env python3
"""Словари строк Мил (i18n): один язык = один файл locales/<код>.json, код без правки.
Файл: {"_name": "Русский", "_also": ["uk", "be"], "ключ": "строка с {подстановкой}", …}.
Недостающая строка — из en.json; нет и там — сам ключ (видно, чего не хватает). Только stdlib.
  load(dir) → {код: словарь}     pick(locales, *кандидаты) → код     t(locales, lang, key, **kw) → строка
  python3 mila_i18n.py check [dir]  → каких ключей en нет в других файлах (для приёмки нового языка)
  python3 mila_i18n.py index [dir]  → dir/index.json {код: {name, also, order}} для mila-i18n.js (после добавления файла)"""
import json, os, re, sys

FALLBACK = "en"
CODE_RE = re.compile(r"^[a-z]{2,3}$")
HERE = os.path.dirname(os.path.abspath(__file__))


def load(d=None):
    d = d or os.path.join(HERE, "locales")
    out = {}
    for fn in sorted(os.listdir(d)):
        code = fn[:-5] if fn.endswith(".json") else ""
        if not CODE_RE.match(code):
            continue
        with open(os.path.join(d, fn), encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            out[code] = {k: v for k, v in data.items() if isinstance(v, str) or (isinstance(v, list) and all(isinstance(x, str) for x in v))}
    if FALLBACK not in out:
        raise RuntimeError("i18n: нет %s.json в %s" % (FALLBACK, d))
    return out


def norm(locales, raw):
    """'ru-RU' / 'zh_Hans' / 'UK' → код, который есть в словарях, или None."""
    raw = (raw or "").strip().lower().replace("_", "-")
    if not raw:
        return None
    base = raw.split("-")[0]
    for c in (raw, base):
        if c in locales:
            return c
    for code, d in locales.items():
        also = d.get("_also") or []
        if raw in also or base in also:
            return code
    return None


def accept_language(header):
    """Accept-Language → коды по весу (q), лучшие первыми."""
    items = []
    for i, part in enumerate((header or "").split(",")[:20]):
        p = part.strip().split(";")
        q = 1.0
        for x in p[1:]:
            if x.strip().startswith("q="):
                try:
                    q = float(x.strip()[2:])
                except ValueError:
                    q = 0
        if p[0] and p[0] != "*":
            items.append((-q, i, p[0]))
    return [c for _, _, c in sorted(items)]


def pick(locales, *cands):
    """Первый кандидат, который нашёлся в словарях; иначе en. Кандидат может быть списком (Accept-Language)."""
    for c in cands:
        for x in (c if isinstance(c, (list, tuple)) else [c]):
            code = norm(locales, x)
            if code:
                return code
    return FALLBACK


def t(locales, lang, key, **kw):
    s = locales.get(lang, {}).get(key)
    if s is None:
        s = locales[FALLBACK].get(key, key)
    if isinstance(s, list):
        s = "".join(s)
    return s.format(**kw) if kw else s


def names(locales):
    """[(код, название)] для переключателя: порядок — по полю _order, потом по коду."""
    return sorted(((c, d.get("_name", c)) for c, d in locales.items()), key=lambda x: (str(locales[x[0]].get("_order", "9")), x[0]))


def owner_lang(locales, home):
    """"lang" из <home>/work/owner.json — для служб от root над домом Милы: файл только внутри дома (realpath), без симлинков
    (O_NOFOLLOW), обычный, до 4 КБ; значение принимается, только если такой словарь есть. Иначе None."""
    import stat
    home = os.path.realpath(home)
    p = os.path.join(home, "work", "owner.json")
    try:
        if os.path.realpath(p) != p or os.path.commonpath([p, home]) != home:
            return None
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as f:
            st = os.fstat(f.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_size > 4096:
                return None
            v = json.loads(f.read(4097).decode("utf-8")).get("lang")
    except (OSError, ValueError, AttributeError):
        return None
    return norm(locales, v) if isinstance(v, str) else None


def check(d=None):
    loc = load(d)
    keys = {k for k in loc[FALLBACK] if not k.startswith("_")}
    bad = 0
    for code, data in loc.items():
        miss = sorted(keys - set(data))
        extra = sorted(k for k in data if not k.startswith("_") and k not in keys)
        ph = sorted(k for k in keys & set(data) if set(re.findall(r"\{(\w+)\}", t(loc, code, k))) != set(re.findall(r"\{(\w+)\}", t(loc, FALLBACK, k))))
        print("%s: %d строк, нет %d%s%s%s" % (code, len(keys) - len(miss), len(miss), (" — " + ", ".join(miss[:8])) if miss else "",
                                          ("; лишние: " + ", ".join(extra[:8])) if extra else "", ("; подстановки не те: " + ", ".join(ph)) if ph else ""))
        bad += len(extra) + len(ph)
    return bad


def index(d=None):
    d = d or os.path.join(HERE, "locales")
    loc = {c: v for c, v in load(d).items()}
    out = {c: {"name": v.get("_name", c), "also": v.get("_also", []), "order": v.get("_order", "9")} for c, v in loc.items()}
    tmp = os.path.join(d, "index.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(d, "index.json"))
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["index"]:
        print(json.dumps(index(sys.argv[2] if len(sys.argv) > 2 else None), ensure_ascii=False)); sys.exit(0)
    if sys.argv[1:2] == ["check"]:
        sys.exit(1 if check(sys.argv[2] if len(sys.argv) > 2 else None) else 0)
    sys.exit(__doc__)
