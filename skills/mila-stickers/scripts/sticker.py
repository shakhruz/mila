#!/usr/bin/env python3
"""Стикер Милы на языке собеседника: sticker.py <chat_id> <смысл> [--lang uz] [--code <language_code>] [--owner] [--reply-to <id>]

Смыслы — по порядку стикеров в паке (у всех языковых паков он один):
  privet beru gotovo proveryayu da dumayu oplata otchet utro noch spasibo sait vstrecha srochno otdyh lyublyu
Язык: --owner — из ~/work/owner.json "lang" (собеседник — владелец); иначе --lang (язык чата, как его видит Мила),
затем --code (language_code Telegram); не знаем — пак по умолчанию (default, обычно ru). Языка без своего пака — en, если он есть.
Паки — в ~/work/stickers.json (или MILA_STICKERS): {"packs": {"ru": "<имя пака>", "uz": "…", "en": "…"}, "default": "ru",
"no_chats": ["<chat_id>", …]} — no_chats: чаты, куда стикеры не шлём (госорганы и т. п.); снять — только --owner-said <улика>.
file_id — getStickerSet своим ботом (BOT_TOKEN), кэш ~/.cache/mila-stickers на час: у каждого бота file_id свои, в коде их нет.
Не чаще одного стикера в чат за 90 с (дубль); меру «один на сообщение, не в серьёзном» решает Мила по SKILL.md.
--dry-run — что ушло бы (язык, пак, номер), без сети и без отправки. Токен не печатается. Только stdlib."""
import argparse, json, os, sys, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import owner_lang  # noqa: E402

MOODS = ["privet", "beru", "gotovo", "proveryayu", "da", "dumayu", "oplata", "otchet",
         "utro", "noch", "spasibo", "sait", "vstrecha", "srochno", "otdyh", "lyublyu"]
# прежние имена (пак «один на всех», до языковых паков) → смысл нового пака; без пары — стикера нет
OLD = {"greet": "privet", "done": "gotovo", "report": "otchet", "beru": "beru", "thinking": "dumayu", "paid": "oplata",
       "invoice": "oplata", "thanks": "spasibo", "night": "noch", "match": "proveryayu", "watch": "proveryayu"}
COOLDOWN = 90.0
CACHE_TTL = 3600
CACHE_DIR = os.environ.get("MILA_STICKERS_CACHE") or os.path.expanduser("~/.cache/mila-stickers")
CONFIG = os.environ.get("MILA_STICKERS") or os.path.expanduser("~/work/stickers.json")


def _api(token, method, params, timeout=20):
    req = urllib.request.Request("https://api.telegram.org/bot%s/%s" % (token, method), data=urllib.parse.urlencode(params).encode())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except ValueError:
            return {"ok": False, "description": "HTTP %d" % e.code}


def _load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def _save(p, v):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False)
    os.replace(tmp, p)


def config():
    c = _load(CONFIG, {})
    packs = {owner_lang.norm(k): v for k, v in (c.get("packs") or {}).items() if owner_lang.norm(k) and isinstance(v, str) and v}
    default = owner_lang.norm(c.get("default")) or "ru"
    return packs, default, {str(x) for x in c.get("no_chats") or []}


def pick_lang(packs, default, lang=None, code=None, owner=False):
    """→ (язык пака, откуда взят)."""
    for src, v in (("owner.json", owner_lang.get() if owner else None), ("чат", lang), ("language_code", code)):
        c = owner_lang.norm(v)
        if c:
            if c in packs:
                return c, src
            if "en" in packs:
                return "en", src + " (%s без пака)" % c
    return default, "по умолчанию"


def file_ids(token, pack):
    """[file_id по порядку пака] — из кэша (час) или getStickerSet."""
    cp = os.path.join(CACHE_DIR, "packs.json")
    cache = _load(cp, {})
    ent = cache.get(pack)
    if isinstance(ent, dict) and ent.get("ids") and time.time() - ent.get("t", 0) < CACHE_TTL:
        return ent["ids"]
    r = _api(token, "getStickerSet", {"name": pack})
    if not r.get("ok"):
        raise RuntimeError("getStickerSet %s: %s" % (pack, str(r.get("description", ""))[:120]))
    ids = [s.get("file_id") for s in (r.get("result") or {}).get("stickers") or [] if s.get("file_id")]
    cache[pack] = {"t": time.time(), "ids": ids}
    _save(cp, cache)
    return ids


def main(argv=None):
    ap = argparse.ArgumentParser(description="Стикер Милы на языке собеседника")
    ap.add_argument("chat_id")
    ap.add_argument("mood", help=" ".join(MOODS))
    ap.add_argument("--lang"); ap.add_argument("--code"); ap.add_argument("--owner", action="store_true")
    ap.add_argument("--reply-to"); ap.add_argument("--owner-said"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    mood = a.mood.strip().lower()
    mood = OLD.get(mood, mood)
    if mood not in MOODS:
        print("Неизвестный смысл %r. Есть: %s" % (a.mood, " ".join(MOODS)))
        return 2
    packs, default, no_chats = config()
    if not packs:
        print("Пропущено: нет паков (~/work/stickers.json) — стикер не шлю, текст уже ушёл.")
        return 0
    if str(a.chat_id) in no_chats and not a.owner_said:
        print("Пропущено: в этот чат стикеры не шлём (no_chats); только если хозяин сам попросил (--owner-said).")
        return 0
    lang, src = pick_lang(packs, default, a.lang, a.code, a.owner)
    if lang not in packs:
        lang = next(iter(packs))
    pack, n = packs[lang], MOODS.index(mood)
    if a.dry_run:
        print(json.dumps({"lang": lang, "from": src, "pack": pack, "n": n, "mood": mood}, ensure_ascii=False))
        return 0
    token = (os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        print("Error: нет BOT_TOKEN у этой Милы.")
        return 1
    lp = os.path.join(CACHE_DIR, "last_sent.json")
    last = _load(lp, {})
    if not a.force and time.time() - float(last.get(str(a.chat_id), 0)) < COOLDOWN:
        print("Пропущено: стикер в этот чат уходил меньше 90 с назад.")
        return 0
    try:
        ids = file_ids(token, pack)
    except RuntimeError as e:
        print("Error: %s" % e)
        return 1
    if len(ids) <= n:
        print("Error: в паке %s нет стикера №%d (%s) — в паке %d." % (pack, n + 1, mood, len(ids)))
        return 1
    params = {"chat_id": a.chat_id, "sticker": ids[n]}
    if a.reply_to:
        params["reply_to_message_id"] = a.reply_to
    r = _api(token, "sendSticker", params)
    if not r.get("ok"):
        print("Error: sendSticker: %s" % str(r.get("description", ""))[:160])
        return 1
    last[str(a.chat_id)] = time.time()
    _save(lp, last)
    print("OK: %s · %s (%s) → %s" % (mood, lang, src, a.chat_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
