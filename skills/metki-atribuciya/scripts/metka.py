#!/usr/bin/env python3
"""metka.py — метка объявления и ссылки с ней (metki-atribuciya).
  metka.py --channel tgads --topic otvet3min --n 2 [--bot mila_gpt_bot] [--site https://milagpt.io/page] [--medium cpc]
→ метка ad_<канал>_<тема>_<N>, ссылка на бота ?start=<метка> (Telegram: до 64 знаков A-Za-z0-9_-),
  ссылка на сайт с utm_source/utm_medium/utm_campaign (обязательные по Google Analytics) + utm_content=<метка>.
  metka.py --check <метка>  — проверка готовой метки. Код 0 / 2 (не годится) / 1 (ввод).
"""
import argparse, json, re, sys, urllib.parse

PART = re.compile(r"^[a-z0-9]{2,20}$")
TAG = re.compile(r"^(ad_[a-z0-9]{2,20}_[a-z0-9]{2,20}_\d{1,3}|p_[a-z0-9_]{2,40})$")
BOT = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,30}bot$", re.I)


def check(tag):
    errs = []
    if len(tag) > 64: errs.append(f"длиннее 64 знаков ({len(tag)}) — Telegram не примет в ?start=")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", tag): errs.append("только латиница, цифры, _ и -")
    if not TAG.fullmatch(tag): errs.append("формат ad_<канал>_<тема>_<N> (строчные, тема без _) или p_<партнёр>")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel"); ap.add_argument("--topic"); ap.add_argument("--n", type=int)
    ap.add_argument("--bot", default=""); ap.add_argument("--site", default=""); ap.add_argument("--medium", default="cpc")
    ap.add_argument("--check")
    a = ap.parse_args()
    if a.check is not None:
        e = check(a.check)
        print(json.dumps({"ok": not e, "tag": a.check, "errors": e}, ensure_ascii=False)); return 0 if not e else 2
    if not (a.channel and a.topic and a.n is not None):
        print("нужны --channel, --topic, --n (или --check <метка>)"); return 1
    ch, tp = a.channel.lower(), a.topic.lower()
    errs = []
    if not PART.fullmatch(ch): errs.append(f"канал «{a.channel}»: 2–20 строчных латинских букв и цифр")
    if not PART.fullmatch(tp): errs.append(f"тема «{a.topic}»: 2–20 строчных латинских букв и цифр, без _ и пробелов")
    if not 1 <= a.n <= 999: errs.append("N — от 1 до 999")
    if a.bot and not BOT.fullmatch(a.bot.lstrip("@")): errs.append(f"бот «{a.bot}» — имя бота без @, на bot")
    if a.site and not re.match(r"^https://[^\s?#]+", a.site): errs.append("сайт — https://… без пробелов")
    if not PART.fullmatch(a.medium.lower()): errs.append("medium — строчные латинские: cpc, post, partner")
    if errs:
        print(json.dumps({"ok": False, "errors": errs}, ensure_ascii=False)); return 2
    tag = f"ad_{ch}_{tp}_{a.n}"
    out = {"ok": True, "tag": tag}
    if a.bot:
        out["bot_link"] = f"https://t.me/{a.bot.lstrip('@')}?start={tag}"
    if a.site:
        u = urllib.parse.urlsplit(a.site)
        q = urllib.parse.parse_qsl(u.query) + [("utm_source", ch), ("utm_medium", a.medium.lower()), ("utm_campaign", tp), ("utm_content", tag)]
        out["site_link"] = urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, urllib.parse.urlencode(q), ""))
    print(json.dumps(out, ensure_ascii=False)); return 0


if __name__ == "__main__":
    sys.exit(main())
