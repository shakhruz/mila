#!/usr/bin/env python3
"""ab_card.py — карточка A/B-теста и вердикт (ab-test). Правила срока и одной переменной — Meta A/B best practices.
  ab_card.py card card.json        — проверка карточки до запуска (код 0 / 2 со списком)
  ab_card.py verdict --a 4000,40 --b 4100,62 --days 8   — показы,действия для A и B; z-критерий двух долей, 95 %
Карточка JSON: {"hypothesis","variable","variants":[{"name","tag"},…],"metric","budget_per_variant","start","end","stop_rule","owner"}
"""
import argparse, datetime, json, math, re, sys

VARIABLES = {"текст", "картинка", "аудитория", "оффер", "заголовок", "формат", "призыв", "страница", "text", "image", "audience", "offer"}


def check_card(c):
    errs = []
    for f in ("hypothesis", "variable", "variants", "metric", "budget_per_variant", "start", "end", "stop_rule", "owner"):
        if c.get(f) is None or c.get(f) == "" or c.get(f) == []:
            errs.append(f"нет поля «{f}»")
    v = str(c.get("variable") or "").lower()
    if v and (re.search(r"[,+/]| и | and ", v) or v not in VARIABLES):
        errs.append(f"переменная «{c.get('variable')}» — нужна ОДНА из: {', '.join(sorted(VARIABLES))}")
    vs = c.get("variants") or []
    if vs and len(vs) < 2:
        errs.append("вариантов меньше двух")
    tags = [str(x.get("tag") or "") for x in vs]
    if vs and (not all(tags) or len(set(tags)) != len(tags)):
        errs.append("у каждого варианта — своя метка (metki-atribuciya), без повторов")
    if c.get("hypothesis") and not re.search(r"(если|if).+(то|then|—).+(потому|because)", str(c["hypothesis"]), re.I | re.S):
        errs.append("гипотеза — «если …, то …, потому что …»")
    try:
        d0, d1 = datetime.date.fromisoformat(c["start"]), datetime.date.fromisoformat(c["end"])
        days = (d1 - d0).days
        if days < 7: errs.append(f"срок {days} дн. — меньше 7 (Meta: минимум 7 дней для надёжного результата)")
        if days > 30: errs.append(f"срок {days} дн. — больше 30 (Meta: A/B-тест не дольше 30 дней)")
    except (KeyError, ValueError, TypeError):
        if c.get("start") and c.get("end"): errs.append("даты — ГГГГ-ММ-ДД")
    try:
        if c.get("budget_per_variant") is not None and float(c["budget_per_variant"]) <= 0: errs.append("бюджет на вариант > 0")
    except (TypeError, ValueError):
        errs.append("бюджет на вариант — число")
    return errs


def verdict(a, b, days):
    (na, xa), (nb, xb) = a, b
    if days < 7:
        return {"verdict": "рано", "why": f"прошло {days} дн. < 7 — итог не подводим"}
    if min(na, nb) <= 0 or xa > na or xb > nb or min(xa, xb) < 0:
        return {"verdict": "ошибка", "why": "действий больше, чем показов, или нули"}
    if min(xa, xb, na - xa, nb - xb) < 5:
        return {"verdict": "нет вывода", "why": "в варианте меньше 5 действий или 5 «не» — z-приближение не работает; нужен больший бюджет",
                "pa": round(xa / na, 4), "pb": round(xb / nb, 4)}
    pa, pb = xa / na, xb / nb
    p = (xa + xb) / (na + nb)
    se = math.sqrt(p * (1 - p) * (1 / na + 1 / nb))
    z = (pb - pa) / se if se else 0.0
    pval = math.erfc(abs(z) / math.sqrt(2))
    res = {"pa": round(pa, 4), "pb": round(pb, 4), "z": round(z, 2), "p_value": round(pval, 4)}
    if pval < 0.05:
        res.update(verdict="победитель B" if pb > pa else "победитель A", why="разница значима на уровне 95 %")
    else:
        res.update(verdict="нет вывода", why=f"p = {pval:.3f} ≥ 0,05 — разница может быть случайной")
    return res


def pair(s):
    a, b = [int(x) for x in s.split(",")]
    return a, b


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("card"); p.add_argument("file")
    p = sp.add_parser("verdict"); p.add_argument("--a", required=True); p.add_argument("--b", required=True); p.add_argument("--days", type=int, required=True)
    a = ap.parse_args()
    if a.cmd == "card":
        try:
            c = json.load(open(a.file, encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(json.dumps({"ok": False, "errors": [f"карточка не читается: {type(e).__name__}"]}, ensure_ascii=False)); return 1
        e = check_card(c if isinstance(c, dict) else {})
        print(json.dumps({"ok": not e, "errors": e}, ensure_ascii=False)); return 0 if not e else 2
    try:
        r = verdict(pair(a.a), pair(a.b), a.days)
    except ValueError:
        print(json.dumps({"verdict": "ошибка", "why": "формат --a/--b: показы,действия"}, ensure_ascii=False)); return 1
    print(json.dumps(r, ensure_ascii=False)); return 0


if __name__ == "__main__":
    sys.exit(main())
