#!/usr/bin/env python3
"""mila onboard: три шага с проверкой — на подставном Telegram и заглушке claude, без сети. python3 install/test_onboard.py"""
import json, os, re, stat, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = "123456789:" + "A" * 35
S = {"code": None, "sent": [], "bad_token": False, "conflict": False, "owner": 555001}


class TG(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self): self.do_GET()

    def do_GET(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode() if n else ""
        method = self.path.rsplit("/", 1)[-1].split("?")[0]
        if TOKEN not in self.path or S["bad_token"]:
            r = {"ok": False, "error_code": 401, "description": "Unauthorized"}
        elif method == "getMe":
            r = {"ok": True, "result": {"id": 1, "is_bot": True, "username": "test_mila_bot"}}
        elif method == "getUpdates":
            if S["conflict"]:
                r = {"ok": False, "error_code": 409, "description": "Conflict: terminated by other getUpdates request"}
            else:
                time.sleep(0.2)
                res = []
                S.setdefault("bodies", []).append(body)
                if S.get("webhook"):
                    r = {"ok": False, "error_code": 409, "description": "Conflict: can't use getUpdates method while webhook is active; use deleteWebhook to delete the webhook first"}
                    b = json.dumps(r).encode(); self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
                if S["code"]:
                    res = [{"update_id": 10, "message": {"chat": {"type": "group", "id": -5}, "from": {"id": 999}, "text": S["code"]}},
                           {"update_id": 11, "message": {"chat": {"type": "private", "id": 777}, "from": {"id": 777}, "text": "hi"}},
                           {"update_id": 12, "message": {"chat": {"type": "private", "id": S["owner"]}, "from": {"id": S["owner"]}, "text": S["code"].upper()}}]
                r = {"ok": True, "result": res}
        elif method == "sendMessage":
            S["sent"].append(body); r = {"ok": True, "result": {}}
        else:
            r = {"ok": False, "description": "?"}
        b = json.dumps(r).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


srv = ThreadingHTTPServer(("127.0.0.1", 0), TG); threading.Thread(target=srv.serve_forever, daemon=True).start()
T = tempfile.mkdtemp()
CL = os.path.join(T, "claude")
open(CL, "w").write('#!/bin/sh\nF="%s/loggedin"\nif [ "$2" = status ]; then [ -f "$F" ] && echo \'{"loggedIn": true, "authMethod": "claude.ai"}\' || echo \'{"loggedIn": false}\'; fi\n'
                    'if [ "$2" = login ]; then touch "$F"; fi\n' % T)
os.chmod(CL, 0o755)
ENV = dict(os.environ, HOME=T, CLAUDE_CONFIG_DIR=os.path.join(T, ".claude"), TELEGRAM_STATE_DIR=os.path.join(T, "tg"),
           MILA_TG_API="http://127.0.0.1:%d" % srv.server_port, MILA_CLAUDE=CL, MILA_PAIR_WAIT="20")
ENV.pop("TELEGRAM_BOT_TOKEN", None)
ok = n = 0


def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)


def run(args=(), stdin=""):
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "onboard.py"), *args], env=ENV, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = []
    def feed():
        p.stdin.write(stdin); p.stdin.close()
    threading.Thread(target=feed, daemon=True).start()
    for line in p.stdout:
        out.append(line)
        m = re.search(r"\(a private message\):\s+([a-z0-9]{6})", line)
        if m: S["code"] = m.group(1)
    p.wait(timeout=60)
    return p.returncode, "".join(out)


rc, out = run(["--check"])
chk("--check на пустом доме: выход 1, три ✗, ничего не создано", rc == 1 and out.count("✗") >= 3 and not os.path.exists(os.path.join(T, "tg")))
rc, out = run(stdin="not-a-token\n%s\n" % TOKEN)
envf = os.path.join(T, "tg", ".env")
chk("шаг 1: неверный формат — повтор; верный — getMe @test_mila_bot", "does not look like a bot token" in out and "1/3 bot token: @test_mila_bot" in out)
chk("шаг 1: .env 600, папка 700, токен не напечатан", os.path.exists(envf) and stat.S_IMODE(os.stat(envf).st_mode) == 0o600
    and stat.S_IMODE(os.stat(os.path.join(T, "tg")).st_mode) == 0o700 and TOKEN not in out)
chk("шаг 2: не вошёл → claude auth login → вошёл", "Opening Anthropic's sign-in" in out and "2/3 Claude: signed in" in out)
acc = json.load(open(os.path.join(T, "tg", "access.json")))
chk("шаг 3: хозяин — тот, кто прислал код в личку (не группа, не другой текст)", acc.get("allowFrom") == [str(S["owner"])] and acc.get("dmPolicy") == "allowlist")
st = json.load(open(os.path.join(T, ".claude", "settings.json")))
chk("шаг 3: OWNER_ID в settings.json, подтверждение хозяину в Telegram", st["env"]["OWNER_ID"] == str(S["owner"]) and any("Paired" in s for s in S["sent"]))
chk("всё готово: выход 0", rc == 0 and "All three done" in out)
rc, out = run(["--check"])
chk("--check после: выход 0, три ✓", rc == 0 and out.count("✓") == 3)
rc, out = run()
chk("повторный запуск: шаги только проверяются, код не просит", rc == 0 and "Send this code" not in out)
S["bad_token"] = True
rc, out = run(["--check"])
chk("токен отозван: ✗ на шаге 1, выход 1", rc == 1 and "does not accept it" in out)
S["bad_token"] = False
os.remove(os.path.join(T, "tg", "access.json")); S["conflict"] = True; S["code"] = None
rc, out = run()
chk("бота читает другой процесс (409): честная подсказка, выход 1", rc == 1 and "something else is reading this bot" in out)
chk("ничего не подтверждено: getUpdates ни разу с offset (старые сообщения остаются Миле)", not any("offset" in b for b in S.get("bodies", [])))
S["conflict"] = False; S["webhook"] = True
rc, out = run()
chk("у бота webhook: своя подсказка (deleteWebhook), выход 1", rc == 1 and "webhook" in out and "something else" not in out)
S["webhook"] = False
tmp = os.path.join(T, "tg", ".env.tmp"); open(tmp, "w").write("old"); os.chmod(tmp, 0o644)
os.remove(os.path.join(T, "tg", ".env"))
rc, out = run(["--check"]); rc, out = run(stdin="%s\n" % TOKEN)
chk("старый .env.tmp 644 не мешает: .env снова 600", stat.S_IMODE(os.stat(os.path.join(T, "tg", ".env")).st_mode) == 0o600)
print("итог %d/%d" % (ok, n))
sys.exit(0 if ok == n else 1)
