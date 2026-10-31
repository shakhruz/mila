#!/usr/bin/env python3
"""Сейф идёт от root, дом пишет Мила (31.10): подлог симлинками в доме — сейф не пишет и не читает вне дома.
work / work/secrets — симлинк наружу → 409, ссылка цела; .env — симлинк → 409, чужой файл не прочитан; подложенный .env.tmp
и inbox/senior.jsonl — симлинки → чужие файлы целы; FIFO вместо .env/senior.jsonl — не виснет. python3 test_seif_podlog.py"""
import json, os, shutil, subprocess, sys, tempfile, threading, urllib.error, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="seif-podlog-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + str(x)[:300]))
os.environ.update(SEIF_DIR=os.path.join(T, "seif"), SEIF_HOMES=os.path.join(T, "homes"), SEIF_BASE="http://127.0.0.1:0/v/", SEIF_UID=str(os.getuid()))
OUT = os.path.join(T, "outside"); os.makedirs(OUT); SECRET = "ROOT_ONLY='s-%s'\n" % os.urandom(4).hex()
def outside(name, text=SECRET):
    p = os.path.join(OUT, name); open(p, "w").write(text); return p
def home(slug):
    h = os.path.join(T, "homes", slug, "home"); os.makedirs(h); return h
sys.path.insert(0, H); import seif
srv = seif.ThreadingHTTPServer(("127.0.0.1", 0), seif.H); threading.Thread(target=srv.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d" % srv.server_port
def link(slug):
    r = subprocess.run([sys.executable, os.path.join(H, "seif.py"), "link", slug, "API_KEY", "--lang", "ru"], capture_output=True, text=True, env=os.environ)
    return urllib.parse.urlsplit(json.loads(r.stdout)["url"]).path
def req(u, d=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(B + u, data=urllib.parse.urlencode(d).encode() if d else None, method="POST" if d else "GET")) as x: return x.status, x.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()
K = {"API_KEY": "k-" + os.urandom(4).hex()}
h = home("client-a"); od = os.path.join(OUT, "a"); os.makedirs(od); os.symlink(od, os.path.join(h, "work"))
u = link("client-a"); s, b = req(u, K)
check("work — симлинк наружу: 409, наружу ничего, ссылка цела", s == 409 and "Не получилось сохранить" in b and os.listdir(od) == [] and req(u)[0] == 200, (s, os.listdir(od)))
h = home("client-b"); os.makedirs(os.path.join(h, "work")); od = os.path.join(OUT, "b"); os.makedirs(od); os.symlink(od, os.path.join(h, "work", "secrets"))
u = link("client-b"); s, b = req(u, K)
check("work/secrets — симлинк наружу: 409, наружу ничего", s == 409 and os.listdir(od) == [])
h = home("client-c"); os.makedirs(os.path.join(h, "work", "secrets")); src = outside("c.env"); os.symlink(src, os.path.join(h, "work", "secrets", "client-c.env"))
u = link("client-c"); s, b = req(u, K)
check(".env — симлинк на чужой файл: 409, чужой файл цел и не перенесён", s == 409 and open(src).read() == SECRET and os.path.islink(os.path.join(h, "work", "secrets", "client-c.env")))
h = home("client-d"); os.makedirs(os.path.join(h, "work", "secrets")); tgt = outside("d.tmp"); os.symlink(tgt, os.path.join(h, "work", "secrets", "client-d.env.tmp"))
u = link("client-d"); s, b = req(u, K); envp = os.path.join(h, "work", "secrets", "client-d.env")
check("подложенный .env.tmp-симлинк: сохранено в доме, чужой файл цел", s == 200 and open(tgt).read() == SECRET and seif.read_env(envp).get("API_KEY") == K["API_KEY"] and not os.path.islink(envp))
h = home("client-e"); os.makedirs(os.path.join(h, "work", "inbox")); ib = outside("e.jsonl"); os.symlink(ib, os.path.join(h, "work", "inbox", "senior.jsonl"))
u = link("client-e"); s, b = req(u, K)
check("inbox/senior.jsonl — симлинк: сохранено, чужой файл не дописан", s == 200 and open(ib).read() == SECRET)
h = home("client-f"); os.makedirs(os.path.join(h, "work")); od = os.path.join(OUT, "f"); os.makedirs(od); os.symlink(od, os.path.join(h, "work", "inbox"))
u = link("client-f"); s, b = req(u, K)
check("work/inbox — симлинк наружу: сохранено, записки наружу нет", s == 200 and os.listdir(od) == [])
h = home("client-g"); os.makedirs(os.path.join(h, "work", "secrets")); os.mkfifo(os.path.join(h, "work", "secrets", "client-g.env"))
u = link("client-g"); s, b = req(u, K)
check(".env — FIFO: 409 сразу, не виснет", s == 409)
h = home("client-h"); os.makedirs(os.path.join(h, "work", "inbox")); os.mkfifo(os.path.join(h, "work", "inbox", "senior.jsonl"))
u = link("client-h"); s, b = req(u, K)
check("inbox/senior.jsonl — FIFO: сохранено, не виснет", s == 200 and seif.read_env(os.path.join(h, "work", "secrets", "client-h.env")).get("API_KEY") == K["API_KEY"])
calls = []; _orig = os.chown
def spy(path, uid, gid, **kw): calls.append(kw.get("follow_symlinks", True)); return _orig(path, uid, gid, **kw)
seif.os.chown = spy
h = home("client-i"); u = link("client-i"); s, b = req(u, K); seif.os.chown = _orig
check("chown — без перехода по симлинку (follow_symlinks=False на каждом вызове)", s == 200 and len(calls) >= 4 and not any(calls), calls)
jr = open(os.path.join(T, "seif", "journal.jsonl")).read()
check("журнал: отказы записаны без значений", jr.count('"ev": "refused"') == 4 and K["API_KEY"] not in jr)
srv.shutdown(); shutil.rmtree(T, ignore_errors=True); print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
