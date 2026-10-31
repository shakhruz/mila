#!/usr/bin/env python3
"""Сейф на языке владельца (31.10): язык из owner.json дома и --lang → в ссылке и странице; ?lang= и Accept-Language; запасной en;
подлог owner.json (симлинк наружу, большой файл, мусор в lang) не принимается; новый язык — одним файлом. python3 test_seif_lang.py"""
import json, os, shutil, subprocess, sys, tempfile, threading, urllib.error, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="seif-lang-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + str(x)[:300]))
os.environ.update(SEIF_DIR=os.path.join(T, "seif"), SEIF_HOMES=os.path.join(T, "homes"), SEIF_BASE="http://127.0.0.1:0/v/", SEIF_UID=str(os.getuid()))
def home(slug, owner=None):
    w = os.path.join(T, "homes", slug, "home", "work"); os.makedirs(w)
    if owner is not None:
        open(os.path.join(w, "owner.json"), "w").write(owner if isinstance(owner, str) else json.dumps(owner))
    return w
home("client-x", {"lang": "uz", "name": "Иван"}); home("client-y"); home("client-z", {"lang": "<script>"})
w = home("client-s"); outside = os.path.join(T, "outside.json"); open(outside, "w").write('{"lang": "zh"}')
os.symlink(outside, os.path.join(w, "owner.json"))                      # подлог: owner.json — симлинк наружу дома
od = os.path.join(T, "outdir"); os.makedirs(od); open(os.path.join(od, "owner.json"), "w").write('{"lang": "zh"}')
os.makedirs(os.path.join(T, "homes", "client-p", "home")); os.symlink(od, os.path.join(T, "homes", "client-p", "home", "work"))   # подлог: work — симлинк наружу
home("client-big", '{"lang": "zh", "pad": "%s"}' % ("x" * 5000))      # больше 4 КБ
sys.path.insert(0, H); import seif, mila_i18n
def link(slug, *extra):
    r = subprocess.run([sys.executable, os.path.join(H, "seif.py"), "link", slug, "API_KEY,CARD_NUMBER", *extra], capture_output=True, text=True, env=os.environ)
    return (json.loads(r.stdout) if r.returncode == 0 else {"rc": r.returncode, "err": r.stderr})
srv = seif.ThreadingHTTPServer(("127.0.0.1", 0), seif.H); threading.Thread(target=srv.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d" % srv.server_port
def path(j): return urllib.parse.urlsplit(j["url"]).path
def get(u, al=None):
    rq = urllib.request.Request(B + u, headers={"Accept-Language": al} if al else {})
    try:
        with urllib.request.urlopen(rq) as x: return x.status, x.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()
def post(u, d):
    try:
        with urllib.request.urlopen(urllib.request.Request(B + u, data=urllib.parse.urlencode(d).encode(), method="POST")) as x: return x.status, x.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()

j = link("client-x")
check("owner.json lang=uz → ссылка ?lang=uz, ответ lang uz", j.get("url", "").endswith("/?lang=uz") and j.get("lang") == "uz", j)
s, b = get(path(j) + "?lang=uz")
check("страница uz: <html lang=uz>, «Saqlash», подпись поля, без «Компаньон»", s == 200 and "<html lang=uz>" in b and "Saqlash" in b and "Karta raqami" in b and "Компаньон" not in b, b[:300])
s, b = get(path(j))
check("без ?lang — язык из ссылки (uz), не из браузера", s == 200 and "<html lang=uz>" in b)
s, b = get(path(j) + "?lang=zh")
check("?lang=zh перекрывает: 中文 и «保存»", "<html lang=zh>" in b and "保存" in b)
s, b = post(path(j) + "?lang=en", {"API_KEY": "k", "CARD_NUMBER": "1234"})
check("ошибка в карте на языке страницы: en «check the card number», форма шлёт ?lang=en", s == 200 and "check the card number" in b and "action='?lang=en'" in b and "проверьте" not in b)
j2 = link("client-y")
check("нет owner.json → ссылка без ?lang, lang=en", "?" not in j2.get("url", "?") and j2.get("lang") == "en", j2)
check("Accept-Language zh-CN,zh;q=0.9 → zh", "<html lang=zh>" in get(path(j2), "zh-CN,zh;q=0.9")[1])
check("Accept-Language de-DE, ru;q=0.5 → ru (первый, что есть в словарях)", "<html lang=ru>" in get(path(j2), "de-DE,ru;q=0.5")[1])
check("Accept-Language de → запасной en", "<html lang=en>" in get(path(j2), "de")[1] and "Save" in get(path(j2), "de")[1])
check("language_code uk → ru (_also)", mila_i18n.pick(seif.LOC, "uk") == "ru" and mila_i18n.pick(seif.LOC, "zh-hans") == "zh")
s, b = get(path(j2) + "?lang=%3Cscript%3E")
check("?lang=<script> — без вставки, запасной en", "<script>" not in b and "<html lang=en>" in b)
check("owner.json lang=<script> — не принят", link("client-z").get("lang") == "en")
check("owner.json симлинк наружу дома — не прочитан (root не верит дому)", link("client-s").get("lang") == "en")
check("work — симлинк наружу дома — owner.json не прочитан", link("client-p").get("lang") == "en")
check("owner.json больше 4 КБ — не прочитан", link("client-big").get("lang") == "en")
hb = home("client-pad"); open(os.path.join(hb, "owner.json"), "w").write('{"lang": "zh"}' + " " * 5000)   # верный JSON в начале, файл > 4 КБ
check("owner.json > 4 КБ с верным lang в начале — не прочитан", link("client-pad").get("lang") == "en")
hf = home("client-fifo"); fp = os.path.join(hf, "owner.json"); os.mkfifo(fp)
wfd = os.open(fp, os.O_RDWR); os.write(wfd, b'{"lang": "zh"}')   # в канале уже лежит верный JSON
check("owner.json — FIFO с данными: не прочитан, без зависания", link("client-fifo").get("lang") == "en")
os.close(wfd)
check("--lang xx — отказ; --lang ZH-cn → zh", link("client-y", "--lang", "xx").get("rc", 0) != 0 and link("client-y", "--lang", "ZH-cn").get("lang") == "zh")
s, b = get("/v/" + "a" * 30 + "/?lang=uz")
check("погасшая ссылка — 410 на языке ?lang (uz)", s == 410 and "Havola endi ishlamaydi" in b)
s, b = get("/v/" + "a" * 30 + "/", "ru-RU")
check("погасшая ссылка без ?lang — по браузеру (ru)", s == 410 and "Ссылка уже не действует" in b)
s, b = post(path(j) + "?lang=zh", {"API_KEY": "k-1", "CARD_NUMBER": "4111 1111 1111 1111"})
check("сохранено на zh: «已保存»", s == 200 and "已保存" in b)
check("переключатель: 4 языка из словарей, текущий без ссылки", all(x in get(path(j2) + "?lang=ru")[1] for x in ("<b>Русский</b>", "?lang=en", "?lang=uz", "?lang=zh", "中文")))
# новый язык одним файлом, недостающая строка — из en
L = os.path.join(T, "loc"); shutil.copytree(os.path.join(H, "locales"), L)
open(os.path.join(L, "tr.json"), "w").write(json.dumps({"_name": "Türkçe", "seif.save": "Kaydet"}))
loc = mila_i18n.load(L)
check("tr.json → в переключателе, «Kaydet», нет строки — английская", ("tr", "Türkçe") in mila_i18n.names(loc) and mila_i18n.t(loc, "tr", "seif.save") == "Kaydet" and mila_i18n.t(loc, "tr", "seif.saved.h1") == "Saved")
r = subprocess.run([sys.executable, os.path.join(H, "mila_i18n.py"), "check", os.path.join(H, "locales")], capture_output=True, text=True)
check("словари ru/en/uz/zh полные, подстановки совпадают", r.returncode == 0 and r.stdout.count("нет 0") == 4, r.stdout)
srv.shutdown(); shutil.rmtree(T, ignore_errors=True); print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
