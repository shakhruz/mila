"""jev.py: off/shadow/main, таймаут 1,2 с → правила, неуверенный Jev → правила, журнал без текста, stats ≥ 90 % → ready, ключ в заголовке.
Заглушка шлюза на 127.0.0.1. python3 -I test_jev.py"""
import http.server, json, os, subprocess, sys, tempfile, threading, time
H = os.path.dirname(os.path.abspath(__file__)); ok = tot = 0; SEEN = []; MODE = {"m": "ok"}
def chk(n, c, x=""):
    global ok, tot; tot += 1; ok += bool(c); print(("✅ " if c else "❌ ") + n, "" if c else x)
class S(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers["Content-Length"]))); SEEN.append((b, dict(self.headers)))
        if MODE["m"] == "slow": time.sleep(2)
        q = b["questions"]; ans = {}
        if "reply" in q: ans["reply"] = {"noul": 0.55 if MODE["m"] == "unsure" else (0.95 if "Мила" in b["state"] or "помоги" in b["state"] else 0.05)}
        if "to" in q: ans["to"] = {"choice": "Мила Контент", "confidence": 0.9}
        if "buttons" in q: ans["buttons"] = {"noul": 0.9}
        out = json.dumps({"answers": ans}).encode(); self.send_response(200); self.end_headers(); self.wfile.write(out)
class Q(http.server.ThreadingHTTPServer):
    def handle_error(self, *a): pass   # «медленный» шлюз: клиент ушёл по таймауту — это и проверяем
srv = Q(("127.0.0.1", 0), S); threading.Thread(target=srv.serve_forever, daemon=True).start()
T = tempfile.mkdtemp(); URL = f"http://127.0.0.1:{srv.server_port}/decide"
def j(*a, **env):
    e = dict(os.environ, HOME=T, **env); e.pop("JEV_MODE", None) if "JEV_MODE" not in env else None
    p = subprocess.run([sys.executable, "-I", os.path.join(H, "jev.py"), *a], capture_output=True, text=True, env=e)
    try: return p.returncode, json.loads(p.stdout)
    except Exception: return p.returncode, {"raw": p.stdout + p.stderr}
rc, o = j("reply", "--text", "помоги с отчётом")
chk("off по умолчанию: правила, в шлюз не ходим", o.get("source") == "rules" and o.get("mode") == "off" and o["decision"] is False and not SEEN, o)
rc, o = j("reply", "--text", "привет", "--mentioned"); chk("правила: назвали по имени → отвечать", o["decision"] is True, o)
rc, o = j("reply", "--text", "бот пишет", "--from-bot", "--dm"); chk("правила: бот в личке без имени → молчать", o["decision"] is False, o)
rc, o = j("config", "--set", "mode=shadow", "--set", f"url={URL}", "--set", "site=test-mila")
chk("config: режим и адрес в ~/.claude/jev.json, ключа нет", o.get("mode") == "shadow" and o.get("key") == "нет" and os.path.exists(os.path.join(T, ".claude", "jev.json")), o)
rc, o = j("config", "--set", "mode=boom"); chk("config: неверный режим — отказ", rc == 1, o)
rc, o = j("reply", "--text", "помоги с отчётом, пожалуйста")
chk("shadow: решают правила (нет), Jev сказал «да» — в ответе jev", o["source"] == "rules" and o["decision"] is False and o.get("jev") is True, o)
row = json.loads(open(os.path.join(T, ".claude", "jev-diff.jsonl")).read().splitlines()[-1])
chk("shadow: журнал расхождения без текста (только длина)", row["same"] is False and "text" not in row and row["len"] > 5, row)
chk("site уходит в шлюз", SEEN[-1][0]["site"] == "test-mila")
os.makedirs(os.path.join(T, "secrets")); open(os.path.join(T, "secrets", "jev.key"), "w").write("KEY123\n")
rc, o = j("config", "--set", "mode=main"); rc, o = j("reply", "--text", "помоги с отчётом")
chk("main: решает Jev (да), уверенность 0,9, источник jev", o["source"] == "jev" and o["decision"] is True and o["conf"] >= 0.89, o)
chk("ключ — в заголовке X-Jev-Key, не в теле", {k.lower(): v for k, v in SEEN[-1][1].items()}.get("x-jev-key") == "KEY123" and "KEY123" not in json.dumps(SEEN[-1][0]))
rc, o = j("config"); chk("config не печатает ключ", "KEY123" not in json.dumps(o) and o["key"] == "есть", o)
MODE["m"] = "unsure"; rc, o = j("reply", "--text", "помоги", "--mentioned")
chk("main: Jev не уверен (0,55) → правила, причина", o["source"] == "rules" and o["decision"] is True and "не уверен" in o.get("why", ""), o)
MODE["m"] = "slow"; t0 = time.time(); rc, o = j("reply", "--text", "помоги"); dt = time.time() - t0
chk("main: Jev молчит 2 с → правила за ≤ 1,6 с", o["source"] == "rules" and "не ответил" in o.get("why", "") and dt < 1.6, (o, dt))
MODE["m"] = "ok"
rc, o = j("who", "--text", "передай контенту про эфир", "--names", "Мила Контент,Чат Реклама")
chk("who: Jev → «Мила Контент»", o["decision"] == "Мила Контент" and o["source"] == "jev", o)
rc, o = j("who", "--text", "напиши в Чат Реклама", "--names", "Мила Контент,Чат Реклама", JEV_MODE="off")
chk("who правилами: имя в тексте → «Чат Реклама»; env сильнее файла", o["decision"] == "Чат Реклама" and o["mode"] == "off", o)
rc, o = j("buttons", "--text", "Как поступим? А) отправить сейчас Б) завтра", JEV_MODE="off"); chk("buttons правилами: А)/Б) → да", o["decision"] is True, o)
rc, o = j("buttons", "--text", "Готово, файл в папке.", JEV_MODE="off"); chk("buttons правилами: просто итог → нет", o["decision"] is False, o)
srv.shutdown(); rc, o = j("reply", "--text", "x", "--dm"); chk("шлюз выключен → правила, без падения", rc == 0 and o["source"] == "rules" and o["decision"] is True, o)
p = os.path.join(T, ".claude", "jev-diff.jsonl"); open(p, "w").write("".join(json.dumps({"kind": "reply", "same": i % 20 != 0, "len": 3}) + "\n" for i in range(60)))
rc, o = j("stats"); chk("stats: 60 решений, 95 % → готово к main", o["rows"] == 60 and o["same_pct"] == 95 and o["ready_for_main"] is True, o)
open(p, "w").write("".join(json.dumps({"kind": "reply", "same": True, "len": 3}) + "\n" for i in range(10)))
rc, o = j("stats"); chk("stats: 10 решений → мало данных", o["ready_for_main"] is False and "Мало" in o["say"], o)
print(f"итог {ok}/{tot}")
