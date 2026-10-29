#!/usr/bin/env python3
"""PAGES-2910 (№109): screen.py page — своя HTML-страница на свой экран. Заглушка службы экрана на 127.0.0.1:
put шлёт tar.gz папки (без скрытых файлов) с ключом и именем; ссылка в папке — отказ до отправки; show/list/rm — команды хаба. Без сети."""
import gzip, http.server, io, json, os, subprocess, sys, tarfile, tempfile, threading
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0; SEEN = []
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
class S(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)); SEEN.append((self.path, dict(self.headers), body))
        out = {"ok": True, "url": "https://pages.example.test/x/igra/"} if self.path.startswith("/api/screen/page?") else {"ok": True, "screens": 1}
        b = json.dumps(out).encode(); self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), S); threading.Thread(target=srv.serve_forever, daemon=True).start()
ENV = dict(os.environ, SCREEN_API="http://127.0.0.1:%d/api/screen/" % srv.server_port, SCREEN_KEY="test-key-" + "q" * 16)
def sc(*a):
    p = subprocess.run([sys.executable, os.path.join(H, "screen.py"), *a], capture_output=True, text=True, env=ENV, timeout=30)
    try: return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception: return {"raw": p.stdout + p.stderr}
D = tempfile.mkdtemp(); os.makedirs(D + "/img"); os.makedirs(D + "/.git")
open(D + "/index.html", "w").write("<title>Игра</title>"); open(D + "/app.js", "w").write("1"); open(D + "/img/a.png", "wb").write(b"\x89PNG")
open(D + "/.env", "w").write("SECRET=1"); open(D + "/.git/config", "w").write("x")
o = sc("page", "put", D, "igra", "--show")
put = [s for s in SEEN if s[0].startswith("/api/screen/page?")]
names = sorted(tarfile.open(fileobj=io.BytesIO(gzip.decompress(put[-1][2]))).getnames()) if put else []
chk("put: tar.gz папки с ключом в заголовке и именем в адресе", put and put[-1][0] == "/api/screen/page?name=igra" and put[-1][1].get("X-Screen-Key") == ENV["SCREEN_KEY"], put[-1][:2] if put else SEEN)
chk("put: в архиве index.html, app.js, img/a.png — без .env и .git", names == ["app.js", "img/a.png", "index.html"], names)
cmd = [json.loads(s[2]) for s in SEEN if s[0] == "/api/screen/cmd"]
chk("--show: следом команда page с именем (адрес строит хаб)", o.get("ok") and cmd and cmd[-1].get("action") == "page" and cmd[-1].get("name") == "igra" and "url" not in cmd[-1], (o, cmd))
os.symlink("/etc/passwd", D + "/link.txt"); k = len(SEEN)
o = sc("page", "put", D, "igra")
chk("ссылка в папке — отказ до отправки, хаб не вызывался", "ссылки" in str(o.get("error", "")) and len(SEEN) == k, o)
os.remove(D + "/link.txt")
chk("имя с заглавными — отказ без отправки", "index.html" in str(sc("page", "put", D, "Igra").get("error", "")))
chk("нет index.html — отказ", "index.html" in str(sc("page", "put", D + "/img", "img").get("error", "")))
sc("page", "show", "igra"); sc("page", "list"); sc("page", "rm", "igra")
paths = [s[0] for s in SEEN[-3:]]; bodies = [json.loads(s[2]) for s in SEEN[-3:]]
chk("show / list / rm — cmd{action: page}, page-list, page-rm{name}", paths == ["/api/screen/cmd", "/api/screen/page-list", "/api/screen/page-rm"] and bodies[0]["action"] == "page" and bodies[2] == {"name": "igra"}, (paths, bodies))
o = sc("page", "show", "igra", "--user", "5550001")
chk("--user у публичной Милы уходит и в page", json.loads(SEEN[-1][2]).get("user") == "5550001")
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
