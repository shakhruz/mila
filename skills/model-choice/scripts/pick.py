#!/usr/bin/env python3
"""Выбор модели под задачу (идея партнёра 20.10: правило одной Милы → навык всех Мил): два варианта — «недорого» и «лучшее качество»
(модель, что даёт, цена за эту работу) + рекомендация; выбор — кнопкой владельца. Цены — из catalog.json (дата проверки) или
живые OpenRouter (--live). Не выдумываю: нет цены — так и пишу.
  pick.py <задача> [--x N] [--best] [--live]
     задача: text | analysis | translate | image | video | voice | transcribe;  --x N — объём в N раз больше типового (10 картинок → --x 10)
     --best — рекомендовать «лучшее качество» (важная работа наружу); иначе рекомендация «недорого»
Выход JSON: {card_text, buttons, options[], checked, stale}"""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CAT = json.load(open(os.path.join(HERE, "catalog.json"), encoding="utf-8"))


def live_prices(ids):
    try:
        d = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=20))["data"]
        return {m["id"]: (float(m["pricing"]["prompt"]) * 1e6, float(m["pricing"]["completion"]) * 1e6) for m in d if m["id"] in ids}
    except Exception:
        return {}


def cost(o, units, x, live):
    if o.get("openrouter"):
        pin, pout = live.get(o["openrouter"], (o["in"], o["out"]))
        return (units["in_tok"] * pin + units["out_tok"] * pout) / 1e6 * x
    per = o["per"]; p = o["price"]
    q = {"image": units.get("images", 1), "mp": units.get("mp", 1), "second": units.get("seconds", 0),
         "kchar": units.get("chars", 0) / 1000, "hour": units.get("hours", 0)}[per]
    return p * q * x


def money(v):
    if v == 0:
        return "бесплатно"
    if v < 0.01:
        return "меньше 1 цента"
    return "$%.2f" % v if v < 10 else "$%.0f" % v


def main():
    a = sys.argv[1:]
    if not a or a[0] not in CAT["tasks"]:
        sys.exit(__doc__)
    t = CAT["tasks"][a[0]]; x = float(a[a.index("--x") + 1]) if "--x" in a else 1.0
    ids = {t[k].get("openrouter") for k in ("cheap", "best")} - {None}
    live = live_prices(ids) if "--live" in a and ids else {}
    age = (time.time() - time.mktime(time.strptime(CAT["checked"], "%Y-%m-%d"))) / 86400
    stale = age > 14 and not live
    opts = []
    for k, lab in (("cheap", "Недорого"), ("best", "Лучшее качество")):
        o = t[k]; c = cost(o, t["units"], x, live)
        opts.append({"key": k, "label": lab, "model": o["name"], "gives": o["gives"], "usd": round(c, 4), "money": money(c)})
    rec = "best" if "--best" in a else "cheap"
    job = t["job"] + (" × %g" % x if x != 1 else "")
    lines = ["Задача: %s — %s." % (t["title"], job.rstrip("."))]
    for o in opts:
        lines.append("%s %s: %s — %s, %s." % ("★" if o["key"] == rec else "•", o["label"], o["model"], o["gives"], o["money"]))
    lines.append("Советую: %s." % ("лучшее качество — работа уходит наружу" if rec == "best" else "недорого — для пробы и черновика хватит"))
    lines.append("Цены: %s." % ("живые OpenRouter, " + time.strftime("%d.%m") if live else "на " + time.strftime("%d.%m.%Y", time.strptime(CAT["checked"], "%Y-%m-%d"))
                                 + (" — могли измениться, уточню перед запуском" if stale else "")))
    btn = [[{"label": "%s · %s" % (o["label"], o["money"]), "choice": "Модель: %s (%s)" % (o["model"], o["label"].lower()),
             "style": "success" if o["key"] == rec else "primary"} for o in (sorted(opts, key=lambda o: o["key"] != rec))]]
    print(json.dumps({"card_text": "\n".join(lines), "buttons": btn, "options": opts, "recommend": rec, "checked": CAT["checked"],
                      "live": bool(live), "stale": stale}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
