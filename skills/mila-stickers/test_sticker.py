#!/usr/bin/env python3
"""mila-stickers без сети (поддельный Bot API): язык собеседника → пак (owner.json, язык чата, language_code, по умолчанию ru;
языка без пака → en), смысл → номер в паке, file_id из getStickerSet с кэшем, no_chats, 90 с на чат, токен не печатается;
owner_lang: seen/set/get. Запуск: python3 test_sticker.py"""
import contextlib, io, json, os, shutil, sys, tempfile, time
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="stickers-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
OJ, CFG = os.path.join(T, "owner.json"), os.path.join(T, "stickers.json")
os.environ.update(OWNER_JSON=OJ, MILA_STICKERS=CFG, MILA_STICKERS_CACHE=os.path.join(T, "cache"), BOT_TOKEN="000000:" + "FAKE" + "x" * 8)
sys.path.insert(0, os.path.join(H, "scripts")); import sticker as s, owner_lang as ol
PACKS = {"ru": "demo_ru_by_demo_bot", "uz": "demo_uz_by_demo_bot", "en": "demo_en_by_demo_bot"}
CALLS = []
def api(token, method, params, timeout=20):
    CALLS.append((method, dict(params)))
    if method == "getStickerSet":
        return {"ok": True, "result": {"stickers": [{"file_id": "%s#%d" % (params["name"], i)} for i in range(16 if params["name"] != "short" else 3)]}}
    if method == "sendSticker":
        return {"ok": FAIL[0] is False, "description": "Bad Request: chat not found"} if FAIL[0] else {"ok": True, "result": {"message_id": 1}}
FAIL = [False]; s._api = api
def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = s.main(list(argv))
    return rc, out.getvalue()
def sent(): return [p for m, p in CALLS if m == "sendSticker"]
def cfg(**kw): json.dump(dict({"packs": PACKS, "default": "ru", "no_chats": []}, **kw), open(CFG, "w"))
def fresh(): shutil.rmtree(os.path.join(T, "cache"), ignore_errors=True)
CH = str(int("-100" + "12345" + "67890"))
rc, out = run("1", "gotovo")
check("нет stickers.json — «Пропущено», ни одного запроса", rc == 0 and "Пропущено" in out and not CALLS, out)
cfg(); json.dump({"lang": "uz"}, open(OJ, "w"))
rc, out = run("11", "gotovo", "--owner")
check("--owner, owner.json uz → пак uz, стикер №3 (gotovo)", rc == 0 and sent()[-1]["sticker"] == "demo_uz_by_demo_bot#2" and sent()[-1]["chat_id"] == "11", (out, sent()))
check("токен не печатается", "FAKE" not in out)
rc, out = run("12", "privet", "--lang", "ru")
check("--lang ru → пак ru, privet = №1", sent()[-1]["sticker"] == "demo_ru_by_demo_bot#0")
rc, out = run("13", "da", "--code", "en-US")
check("--code en-US → пак en, da = №5", sent()[-1]["sticker"] == "demo_en_by_demo_bot#4")
rc, out = run("14", "beru")
check("ничего не знаем → по умолчанию ru", sent()[-1]["sticker"] == "demo_ru_by_demo_bot#1")
rc, out = run("15", "lyublyu", "--lang", "zh")
check("язык без пака (zh) → en, lyublyu = №16", sent()[-1]["sticker"] == "demo_en_by_demo_bot#15", out)
json.dump({"lang": "zh"}, open(OJ, "w")); rc, out = run("16", "utro", "--owner")
check("owner.json zh, --owner → en", sent()[-1]["sticker"] == "demo_en_by_demo_bot#8")
rc, out = run("17", "noch", "--lang", "uz", "--code", "ru")
check("язык чата (uz) важнее language_code (ru)", sent()[-1]["sticker"] == "demo_uz_by_demo_bot#9")
gets = [p for m, p in CALLS if m == "getStickerSet"]
check("getStickerSet — по разу на пак (кэш)", sorted(p["name"] for p in gets) == sorted(PACKS.values()), gets)
c = json.load(open(os.path.join(T, "cache", "packs.json"))); c["demo_ru_by_demo_bot"]["t"] -= 3601; json.dump(c, open(os.path.join(T, "cache", "packs.json"), "w"))
run("18", "spasibo", "--lang", "ru")
check("кэш старше часа — пак перечитан", [p["name"] for m, p in CALLS if m == "getStickerSet"][-1] == "demo_ru_by_demo_bot")
k = len(sent()); rc, out = run("18", "spasibo", "--lang", "ru")
check("второй стикер в тот же чат < 90 с — «Пропущено», не ушёл", len(sent()) == k and "Пропущено" in out)
rc, out = run("18", "spasibo", "--lang", "ru", "--force")
check("--force — уходит", len(sent()) == k + 1)
rc, out = run("19", "pogoda")
check("неизвестный смысл — код 2, ничего не ушло", rc == 2 and len(sent()) == k + 1 and "privet" in out)
cfg(no_chats=[CH]); k = len(sent())
rc, out = run(CH, "privet", "--lang", "ru")
check("чат из no_chats — «Пропущено», не ушло", rc == 0 and "no_chats" in out and len(sent()) == k)
rc, out = run(CH, "privet", "--lang", "ru", "--owner-said", "555/1")
check("no_chats, хозяин попросил — уходит", len(sent()) == k + 1)
cfg(); FAIL[0] = True; rc, out = run("20", "gotovo", "--lang", "ru"); FAIL[0] = False; k = len(sent())
rc2, out2 = run("20", "gotovo", "--lang", "ru")
check("сбой отправки — Error, 90 с не съедены: повтор уходит", rc == 1 and "Error" in out and rc2 == 0 and len(sent()) == k + 1, (out, out2))
cfg(packs={"ru": "short"}); fresh(); rc, out = run("21", "lyublyu")
check("в паке меньше стикеров — понятная ошибка", rc == 1 and "нет стикера №16" in out, out)
cfg(); k = len(CALLS); rc, out = run("22", "otchet", "--lang", "uz", "--dry-run")
j = json.loads(out)
check("--dry-run: язык, пак, номер — без сети", j == {"lang": "uz", "from": "чат", "pack": "demo_uz_by_demo_bot", "n": 7, "mood": "otchet"} and len(CALLS) == k, j)
os.environ.pop("BOT_TOKEN"); rc, out = run("23", "otchet", "--lang", "uz")
check("нет BOT_TOKEN — Error, без отправки", rc == 1 and "BOT_TOKEN" in out)
os.environ["BOT_TOKEN"] = "000000:" + "FAKE" + "y" * 8; fresh(); k = len(sent())
import subprocess
r = subprocess.run([sys.executable, os.path.join(H, "send_sticker.py"), "24", "greet", "--lang", "ru", "--dry-run"], capture_output=True, text=True, env=os.environ)
check("прежний вход send_sticker.py greet → privet (№1), без отправки в dry-run", r.returncode == 0 and json.loads(r.stdout)["n"] == 0 and len(sent()) == k, r.stdout + r.stderr)
rc, out = run("25", "robots", "--lang", "ru")
check("прежний mood без пары (robots) — код 2, ничего не ушло", rc == 2 and len(sent()) == k)
# owner_lang — один источник языка
P = os.path.join(T, "o2", "owner.json")
check("owner_lang: первое сообщение — language_code ru", ol.seen("ru", "👍", P) == "ru" and ol.read(P)["lang_source"] == "telegram")
check("одна фраза по-узбекски не меняет, вторая подряд — uz", ol.seen("ru", "Salom, ishlar qanday?", P) == "ru" and ol.seen("ru", "Rahmat, yaxshi bo'ladi", P) == "uz")
check("set en (выбор владельца) — автоматика не трогает", ol.set_lang("en", P) == "en" and ol.seen("ru", "Привет, как дела у нас?", P) == "en" and ol.seen("ru", "Всё готово к встрече?", P) == "en")
check("угадывание: ru / uz кириллица / zh / коротко", (ol.guess("Привет, как дела?"), ol.guess("Ассалому алайкум, ҳисобот"), ol.guess("你好，报告怎么样"), ol.guess("ок")) == ("ru", "uz", "zh", None))
check("norm: uk → ru, zh-Hans → zh, xx → None", (ol.norm("uk"), ol.norm("zh_Hans"), ol.norm("xx")) == ("ru", "zh", None))
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
