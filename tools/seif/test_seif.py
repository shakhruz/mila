#!/usr/bin/env python3
"""Сейф Милы целиком на временных папках: ссылка → страница (GET не тратит) → ошибка в карте (ссылка жива, введённое не возвращается)
→ сохранение → .env 600 с прежними ключами, журнал без значений, записка компаньону, повтор — 410, просроченная — 410. python3 test_seif.py"""
import json, os, random, subprocess, sys, tempfile, threading, time, urllib.request, urllib.parse, urllib.error
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="seif-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + str(x)[:300]))
def pan():
    d = [8, 6, 0, 0] + [random.randint(0, 9) for _ in range(11)]
    t = sum((x * 2 - 9 if x * 2 > 9 else x * 2) if i % 2 == 0 else x for i, x in enumerate(reversed(d)))
    return "".join(map(str, d)) + str((10 - t % 10) % 10)
P = pan(); PW = "pw-" + os.urandom(6).hex()
os.environ.update(SEIF_DIR=os.path.join(T, "seif"), SEIF_HOMES=os.path.join(T, "homes"), SEIF_BASE="http://127.0.0.1:0/v/", SEIF_UID=str(os.getuid()))
home = os.path.join(T, "homes", "acme", "home"); os.makedirs(os.path.join(home, "work", "secrets"))
home2 = os.path.join(T, "homes", "fresh", "home"); os.makedirs(home2)   # новорождённая: нет ни work/secrets, ни work/inbox
open(os.path.join(home, "work", "secrets", "acme.env"), "w").write("OLD_KEY='keep'\n")
sys.path.insert(0, H); import seif
r = subprocess.run([sys.executable, os.path.join(H, "seif.py"), "link", "acme", "SITE_LOGIN,SITE_PASSWORD,CARD_NUMBER,CARD_EXPIRY", "--to", "555"], capture_output=True, text=True, env=os.environ)
j = json.loads(r.stdout); tok = j["url"].rstrip("/").split("/")[-1]
check("ссылка: одноразовый токен, 4 поля, 30 мин", j["ok"] and len(tok) >= 30 and j["expires_min"] == 30 and len(j["fields"]) == 4)
check("токен хранится только хешем", not any(tok in f for f in os.listdir(os.path.join(T, "seif", "tokens"))))
srv = seif.ThreadingHTTPServer(("127.0.0.1", 0), seif.H); threading.Thread(target=srv.serve_forever, daemon=True).start()
U = "http://127.0.0.1:%d/v/%s/" % (srv.server_port, tok)
def get(u):
    try:
        with urllib.request.urlopen(u) as x: return x.status, x.read().decode(), dict(x.headers)
    except urllib.error.HTTPError as e: return e.code, e.read().decode(), dict(e.headers)
def post(u, d):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, data=urllib.parse.urlencode(d).encode(), method="POST")) as x: return x.status, x.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()
s, b, hd = get(U); s2, _, _ = get(U)
check("страница: 4 поля с подписями, пароль скрыт, no-store; GET не тратит ссылку", s == 200 and s2 == 200 and "Логин сайта" in b and 'name=SITE_PASSWORD type=password' in b and hd.get("Cache-Control") == "no-store")
bad = P[:-1] + str((int(P[-1]) + 1) % 10)
s, b = post(U, {"SITE_LOGIN": "998901112233", "SITE_PASSWORD": PW, "CARD_NUMBER": bad, "CARD_EXPIRY": "08/28"})
check("ошибка в карте: подсказка, введённое назад не выводится, ссылка жива", s == 200 and "проверьте номер карты" in b and PW not in b and bad not in b and get(U)[0] == 200)
s, b = post(U, {"SITE_LOGIN": "998901112233", "SITE_PASSWORD": PW, "CARD_NUMBER": " ".join(P[i:i + 4] for i in range(0, 16, 4)), "CARD_EXPIRY": "08/28"})
check("сохранено ✅, значений на странице нет", s == 200 and "Сохранено" in b and PW not in b and P not in b)
envp = os.path.join(home, "work", "secrets", "acme.env"); env = seif.read_env(envp)
check("файл .env: 4 поля + прежний ключ, карта цифрами, срок ММГГ, 600", env.get("SITE_PASSWORD") == PW and env.get("CARD_NUMBER") == P and env.get("CARD_EXPIRY") == "0828" and env.get("OLD_KEY") == "keep" and oct(os.stat(envp).st_mode & 0o777) == "0o600")
jr = open(os.path.join(T, "seif", "journal.jsonl")).read()
check("журнал: link и saved, поля без значений", '"ev": "saved"' in jr and "CARD_NUMBER" in jr and PW not in jr and P not in jr and "998901112233" not in jr)
ib = open(os.path.join(home, "work", "inbox", "senior.jsonl")).read()
check("записка компаньону: «в сейфе появились …», без значений", "В сейфе появились" in ib and "SITE_LOGIN" in ib and PW not in ib)
check("повтор ссылки — 410 (одноразовая)", get(U)[0] == 410 and post(U, {"SITE_LOGIN": "x"})[0] == 410)
r = subprocess.run([sys.executable, os.path.join(H, "seif.py"), "link", "acme", "API_KEY", "--ttl", "0"], capture_output=True, text=True, env=os.environ)
t2 = json.loads(r.stdout)["url"].rstrip("/").split("/")[-1]; time.sleep(0.2)
check("просроченная ссылка — 410", get("http://127.0.0.1:%d/v/%s/" % (srv.server_port, t2))[0] == 410)
check("чужой путь/мусорный токен — 410", get("http://127.0.0.1:%d/v/abc/" % srv.server_port)[0] == 410)
r = subprocess.run([sys.executable, os.path.join(H, "seif.py"), "link", "nobody", "API_KEY"], capture_output=True, text=True, env=os.environ)
check("ссылка в несуществующий дом — отказ", r.returncode != 0)
# 20.10 (Хранитель, canary): в доме без work/ сейф создаёт work, secrets, inbox — все с хозяином дома (SEIF_UID), не root
import pwd
chowned = []
_orig = os.chown
def spy(path, uid, gid): chowned.append(os.path.relpath(path, home2)); return _orig(path, uid, gid)
os.chown = spy; seif.os.chown = spy
r = subprocess.run([sys.executable, os.path.join(H, "seif.py"), "link", "fresh", "API_KEY"], capture_output=True, text=True, env=os.environ)
t3 = json.loads(r.stdout)["url"].rstrip("/").split("/")[-1]
s3, b3 = post("http://127.0.0.1:%d/v/%s/" % (srv.server_port, t3), {"API_KEY": "k-" + os.urandom(4).hex()})
os.chown = _orig
check("новый дом: work, work/secrets, work/inbox, .env и senior.jsonl — chown хозяину", s3 == 200 and {"work", "work/secrets", "work/inbox", "work/secrets/fresh.env", "work/inbox/senior.jsonl"} <= set(chowned), chowned)
srv.shutdown(); print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
