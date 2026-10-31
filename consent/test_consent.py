#!/usr/bin/env python3
"""Consent proxy on temp dirs, fake Telegram and a fake executor (no network): without a yes nothing runs; the owner's yes runs
exactly this payload once; a changed payload or a replaced file asks again; forged, foreign, late buttons are ignored; the card
shows targets, length, head and tail, attachments; invisible and bidi characters are stripped; attachments only from inside the
home (symlink to the proxy key, outside path, FIFO, too big — refused); categories on/off only by the owner; fail closed.
Run: python3 test_consent.py"""
import json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="consent-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
sys.path.insert(0, H); import consent_proxy as cp, consent_client as cc
OWNER, OTHER = str(int("555" + "000111")), str(int("555" + "000222"))
os.environ["MILA_OWNER_ID"] = OWNER
HOME = os.path.join(T, "home"); os.makedirs(os.path.join(HOME, "work")); STATE = os.path.join(T, "state")
CFG = {"owner_id_env": "MILA_OWNER_ID", "home": HOME, "state_dir": STATE, "ttl_min": 15, "max_attachment_mb": 1,
       "categories": {"publish_zernio": {"enabled": True, "title": "публикация (Zernio)", "exec": ["true"]}, "mail_send": {"enabled": False, "exec": ["true"]}}}
CARDS, RUNS, NOW = [], [], [1_800_000_000.0]
px = cp.Proxy(CFG, send=lambda text, kb: CARDS.append((text, kb)) or True, run=lambda cmd, body: RUNS.append(body) or {"ok": True, "id": "p1"}, now=lambda: NOW[0])
def btn(i=-1, yes=True): return CARDS[i][1][0][0 if yes else 1]["callback_data"]
P = {"text": "Запуск курса в понедельник", "targets": ["acc-demo-ig", "acc-demo-tg"]}
r = px.request("publish_zernio", P)
check("без согласия: карточка владельцу, ничего не исполнено", r["status"] == "asked" and len(CARDS) == 1 and not RUNS, r)
check("повтор до ответа — «waiting», вторая карточка не уходит", px.request("publish_zernio", P)["status"] == "waiting" and len(CARDS) == 1)
check("кнопка: callback в своём пространстве consent:<id>.<подпись>.y", re.fullmatch(r"consent:[0-9a-f]{8}\.[0-9a-f]{20}\.y", btn()), btn())
r = px.callback(btn(), OWNER, OWNER)
check("владелец в личке нажал «Да, это» → granted", r["status"] == "granted", r)
r = px.request("publish_zernio", P)
check("тот же payload → исполнено один раз, executor получил ровно его", r["status"] == "done" and len(RUNS) == 1 and RUNS[0]["text"] == P["text"] and RUNS[0]["targets"] == P["targets"], r)
check("ещё раз тот же payload — согласие израсходовано, новая карточка", px.request("publish_zernio", P)["status"] == "asked" and len(RUNS) == 1 and len(CARDS) == 2)
px.callback(btn(), OWNER, OWNER)
r = px.request("publish_zernio", dict(P, text=P["text"] + "!"))
check("поменяла текст после «да» — другое действие: карточка, не исполнено", r["status"] == "asked" and len(RUNS) == 1)
# forged / foreign / late buttons
cid = r["id"]; good = btn()
forged = re.sub(r"\.([0-9a-f]{20})\.", ".%s." % ("0" * 20), good)
check("подделанная подпись — ignored", px.callback(forged, OWNER, OWNER)["status"] == "ignored")
check("не владелец — ignored", px.callback(good, OTHER, OTHER)["status"] == "ignored")
check("владелец, но в группе — ignored", px.callback(good, OWNER, str(-(10 ** 12 + 42)))["status"] == "ignored")
check("кнопка сессии «consent:…» с чужим id — ignored", px.callback("consent:deadbeef.%s.y" % ("a" * 20), OWNER, OWNER)["status"] == "ignored")
check("обычная кнопка (choice) не согласие", px.callback("Пульт №20 — да", OWNER, OWNER)["status"] == "ignored")
NOW[0] += 16 * 60
check("нажатие через 16 мин — ignored (карточка истекла)", px.callback(good, OWNER, OWNER)["status"] == "ignored")
r = px.request("publish_zernio", dict(P, text=P["text"] + "!"))
check("после истечения — новая карточка", r["status"] == "asked" and r["id"] != cid)
px.callback(btn(), OWNER, OWNER); NOW[0] += 16 * 60
check("согласие старше 15 мин — не исполняет, спрашивает снова", px.request("publish_zernio", dict(P, text=P["text"] + "!"))["status"] == "asked" and len(RUNS) == 1)
px.callback(btn(yes=False), OWNER, OWNER)
check("«Нет» — declined, повтор того же — новая карточка, не исполнено", px.request("publish_zernio", dict(P, text=P["text"] + "!"))["status"] == "asked" and len(RUNS) == 1)
# a decided card stays decided
r = px.request("publish_zernio", {"text": "решено один раз", "targets": ["a"]}); no_btn, yes_btn = btn(yes=False), btn()
check("«Нет», потом «Да» на той же карточке — второе ignored, не исполнено",
      px.callback(no_btn, OWNER, OWNER)["status"] == "declined" and px.callback(yes_btn, OWNER, OWNER)["status"] == "ignored"
      and px.request("publish_zernio", {"text": "решено один раз", "targets": ["a"]})["status"] == "asked")
r = px.request("publish_zernio", {"text": "один раз", "targets": ["a"]}); y = btn(); px.callback(y, OWNER, OWNER); k = len(RUNS)
px.request("publish_zernio", {"text": "один раз", "targets": ["a"]})
check("повторное «Да» после исполнения — ignored, повтор не исполняется", px.callback(y, OWNER, OWNER)["status"] == "ignored"
      and px.request("publish_zernio", {"text": "один раз", "targets": ["a"]})["status"] == "asked" and len(RUNS) == k + 1)
# card content
long = "Начало поста. " + "середина " * 80 + "Конец поста и ссылка."
open(os.path.join(HOME, "work", "cover.png"), "wb").write(b"\x89PNG" + b"0" * 3000)
px.request("publish_zernio", {"text": long, "targets": ["acc-demo-ig"], "when": "2026-11-02 10:00", "attachments": ["work/cover.png"]})
card = CARDS[-1][0]
check("карточка: куда целиком, длина, начало и конец, когда, вложение с размером",
      "Куда: acc-demo-ig" in card and "Текст: %d знаков" % len(long) in card and "Начало поста" in card and "Конец поста и ссылка." in card
      and "Когда: 2026-11-02 10:00" in card and "Вложение: cover.png, 2 КБ" in card, card)
px.request("publish_zernio", {"text": "Цена ‮001‬ сум​ и⁦скрыто⁩", "targets": ["a"]})
check("невидимые и bidi-символы сняты из превью", not re.search("[​-‏‪-‮⁦-⁩]", CARDS[-1][0]), repr(CARDS[-1][0]))
# attachments: only inside the home, never through a link
KEY = os.path.join(STATE, "hmac.key"); k0 = len(CARDS)
os.symlink(KEY, os.path.join(HOME, "work", "photo.jpg"))
r = px.request("publish_zernio", {"text": "x", "targets": ["a"], "attachments": ["work/photo.jpg"]})
check("вложение — симлинк на ключ прокси: denied, карточки нет, ключ не читается", r["status"] == "denied" and "symlink" in r["why"] and len(CARDS) == k0, r)
os.symlink(os.path.join(T, "state"), os.path.join(HOME, "work", "dirlink"))
check("путь через папку-симлинк — denied", px.request("publish_zernio", {"text": "x", "targets": ["a"], "attachments": ["work/dirlink/hmac.key"]})["status"] == "denied")
open(os.path.join(T, "outside.txt"), "w").write("secret")
check("путь вне дома — denied", px.request("publish_zernio", {"text": "x", "targets": ["a"], "attachments": [os.path.join(T, "outside.txt")]})["status"] == "denied")
check("../ из дома наружу — denied", px.request("publish_zernio", {"text": "x", "targets": ["a"], "attachments": ["../outside.txt"]})["status"] == "denied")
os.mkfifo(os.path.join(HOME, "work", "pipe"))
check("FIFO вместо файла — denied без зависания", px.request("publish_zernio", {"text": "x", "targets": ["a"], "attachments": ["work/pipe"]})["status"] == "denied")
open(os.path.join(HOME, "work", "big.bin"), "wb").write(b"0" * (1024 * 1024 + 10))
check("вложение больше лимита — denied", "larger" in px.request("publish_zernio", {"text": "x", "targets": ["a"], "attachments": ["work/big.bin"]})["why"])
# file replaced after yes → different hash
A = {"text": "с картинкой", "targets": ["a"], "attachments": ["work/cover.png"]}
r = px.request("publish_zernio", A); px.callback(btn(), OWNER, OWNER); runs0 = len(RUNS)
open(os.path.join(HOME, "work", "cover.png"), "wb").write(b"\x89PNG" + b"1" * 3000)
r2 = px.request("publish_zernio", A)
check("файл подменили после «да» — новый hash: карточка, не исполнено", r2["status"] == "asked" and len(RUNS) == runs0, r2)
px.callback(btn(), OWNER, OWNER); r3 = px.request("publish_zernio", A)
check("исполнителю — проверенная копия файла, не путь сессии", r3["status"] == "done" and RUNS[-1]["attachments"][0] != os.path.join(HOME, "work", "cover.png") and not os.path.exists(RUNS[-1]["attachments"][0]))
# categories
check("категория выключена — denied без карточки", px.request("mail_send", {"text": "x"})["status"] == "denied")
check("неизвестная категория — denied", px.request("drop_db", {"x": 1})["status"] == "denied")
check("не владелец категорию не включает", px.category("mail_send", True, OTHER)["status"] == "ignored" and not px.cats["mail_send"])
check("владелец включил — запись в журнале «было/стало»", px.category("mail_send", True, OWNER)["status"] == "ok" and '"ev": "category"' in open(os.path.join(STATE, "consents.jsonl")).read())
px2 = cp.Proxy(CFG, send=lambda *a: True, run=lambda *a: {"ok": True}, now=lambda: NOW[0])
check("переключатель категории переживает перезапуск прокси", px2.cats["mail_send"] is True)
jr = open(os.path.join(STATE, "consents.jsonl")).read()
check("журнал: asked/granted/used/declined/denied, без текста поста", all('"ev": "%s"' % e in jr for e in ("asked", "granted", "used", "declined", "denied")) and "Запуск курса" not in jr)
check("ключ HMAC — 600", oct(os.stat(KEY).st_mode & 0o777) == "0o600")
# fail closed + sockets
r = subprocess.run([sys.executable, os.path.join(H, "consent_client.py"), "publish_zernio", "--socket", os.path.join(T, "nope.sock")], input=json.dumps(P), capture_output=True, text=True)
check("прокси нет — клиент: denied, «nothing is published», код 2", r.returncode == 2 and "nothing is published" in r.stdout, r.stdout)
check("сокет не задан — denied", subprocess.run([sys.executable, os.path.join(H, "consent_client.py"), "publish_zernio"], input=json.dumps(P), capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "MILA_CONSENT_SOCKET"}).returncode == 2)
SS, IO = os.path.join(T, "s.sock"), os.path.join(T, "io.sock")
threading.Thread(target=cp.serve, args=(px, SS, cp.session_handler(px), 0o660), daemon=True).start()
threading.Thread(target=cp.serve, args=(px, IO, cp.io_handler(px), 0o600), daemon=True).start()
for _ in range(50):
    if os.path.exists(SS) and os.path.exists(IO): break
    time.sleep(0.05)
Q = {"text": "через сокет", "targets": ["a"]}
r = cc.ask("publish_zernio", Q, SS)
check("через сокет сессии: asked", r["status"] == "asked", r)
check("сессионный сокет не принимает callback (op только request)", cc.ask.__module__ and json.loads(json.dumps(cp.session_handler(px)({"op": "callback", "data": btn(), "from_id": OWNER})))["status"] == "denied")
def io(q):
    s = socket.socket(socket.AF_UNIX); s.connect(IO); s.sendall((json.dumps(q) + "\n").encode()); out = s.recv(cp.BUF); s.close(); return json.loads(out)
check("io-сокет: callback владельца → granted", io({"op": "callback", "data": btn(), "from_id": OWNER, "chat_id": OWNER})["status"] == "granted")
check("io-сокет 600, сессионный 660", oct(os.stat(IO).st_mode & 0o777) == "0o600" and oct(os.stat(SS).st_mode & 0o777) == "0o660")
check("после «да» через сокет — done", cc.ask("publish_zernio", Q, SS)["status"] == "done")
s = socket.socket(socket.AF_UNIX); s.connect(SS); s.sendall(b"not json\n"); bad = json.loads(s.recv(4096)); s.close()
check("мусор в сокет — denied (fail closed)", bad["status"] == "denied")
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
