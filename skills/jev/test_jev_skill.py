"""jev.py skill (КАТАЛОГ-НАВЫКОВ-2810, шаг 2): 1–3 навыка каталога под задачу. Правила по словам «что даёт» (редкое слово весит
больше); стоящие помечены; в shadow решают правила, Jev — в журнал; в main — Jev, если уверен; нет каталога — понятный отказ.
Заглушка шлюза и каталога на 127.0.0.1. python3 -I test_jev_skill.py"""
import http.server, json, os, subprocess, sys, tempfile, threading
H = os.path.dirname(os.path.abspath(__file__)); ok = tot = 0; SEEN = []; HITS = {"cat": 0}
def chk(n, c, x=""):
    global ok, tot; tot += 1; ok += bool(c); print(("✅ " if c else "❌ ") + n, "" if c else x)
CAT = {"version": "t", "skills": [
    {"name": "mini-podcast", "who": "хозяин", "price": "генерации платные", "gives": "Мини-подкаст двумя голосами по отчёту, статье или уроку"},
    {"name": "audio-master", "who": "хозяин", "price": "бесплатно", "gives": "Чистка звука записи до студийного: подкаст, эфир, медитация"},
    {"name": "tour-pricing", "who": "хозяин", "price": "бесплатно", "gives": "Расчёт турпакета строго по вашему справочнику цен"},
    {"name": "mail-outbound", "who": "хозяин", "price": "бесплатно", "gives": "Письма от вашего имени: адрес проверен, отправка по вашему «да»"},
    {"name": "bot-send", "who": "оператор", "price": "бесплатно", "gives": "Написать человеку от вашего бота"}, "мусор"]}
class S(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        HITS["cat"] += 1; out = json.dumps(CAT, ensure_ascii=False).encode(); self.send_response(200); self.end_headers(); self.wfile.write(out)
    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers["Content-Length"]))); SEEN.append(b)
        ans = {k: {"noul": 0.95 if "audio-master" in v["instructions"] else 0.05} for k, v in b["questions"].items()}
        out = json.dumps({"answers": ans}).encode(); self.send_response(200); self.end_headers(); self.wfile.write(out)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), S); threading.Thread(target=srv.serve_forever, daemon=True).start()
T = tempfile.mkdtemp(); BASE = f"http://127.0.0.1:{srv.server_port}"; CF = os.path.join(T, "catalog.json"); json.dump(CAT, open(CF, "w"), ensure_ascii=False)
os.makedirs(os.path.join(T, ".claude", "skills", "mail-outbound"))
def j(*a, **env):
    e = dict(os.environ, HOME=T, **env); [e.pop(k, None) for k in ("JEV_MODE", "MILA_CATALOG_URL") if k not in env]
    p = subprocess.run([sys.executable, "-I", os.path.join(H, "jev.py"), *a], capture_output=True, text=True, env=e)
    try: return p.returncode, json.loads(p.stdout)
    except Exception: return p.returncode, {"raw": p.stdout + p.stderr}
rc, o = j("skill", "--text", "сделай подкаст")
chk("адреса каталога нет — отказ строкой, код 1", rc == 1 and "адрес каталога не задан" in o.get("error", ""), o)
rc, o = j("skill", "--text", "сделай подкаст по отчёту", "--catalog", CF)
chk("правила: подкаст по отчёту → mini-podcast первым (два слова), audio-master вторым", o.get("decision") == ["mini-podcast", "audio-master"] and o["source"] == "rules", o)
chk("в ответе — что даёт и цена из каталога", o["skills"][0]["price"] == "генерации платные" and "двумя голосами" in o["skills"][0]["gives"], o)
rc, o = j("skill", "--text", "посчитай турпакет на группу", "--catalog", CF)
chk("редкое слово решает: турпакет → tour-pricing", o.get("decision", [None])[0] == "tour-pricing", o)
rc, o = j("skill", "--text", "напиши письмо партнёру", "--catalog", CF)
chk("стоящий навык помечен installed", o["skills"] and o["skills"][0] == {"name": "mail-outbound", "gives": CAT["skills"][3]["gives"], "price": "бесплатно", "installed": True}, o)
rc, o = j("skill", "--text", "какая погода завтра", "--catalog", CF)
chk("ничего не совпало — пусто, не случайный навык", o.get("decision") == [] and o["skills"] == [], o)
rc, o = j("skill", "--text", "подкаст", "--catalog", os.path.join(T, "нет.json"))
chk("каталог не читается — отказ «недоступен»", rc == 1 and "недоступен" in o.get("error", ""), o)
rc, o = j("skill", "--text", "сделай подкаст по отчёту", MILA_CATALOG_URL=BASE + "/catalog.json")
rc, o2 = j("skill", "--text", "почисти звук эфира", MILA_CATALOG_URL=BASE + "/catalog.json")
chk("каталог по адресу — один запрос на сутки (кэш)", HITS["cat"] == 1 and o.get("decision") and o2.get("decision"), (HITS, o, o2))
json.dump({"catalog_url": CF}, open(os.path.join(T, ".claude", "mila-update.json"), "w"))
rc, o = j("skill", "--text", "сделай подкаст по отчёту")
chk("адрес — из настроек mila-update (catalog_url)", o.get("decision", [None])[0] == "mini-podcast", o)
j("config", "--set", "mode=shadow", "--set", f"url={BASE}/decide")
rc, o = j("skill", "--text", "сделай подкаст по отчёту")
chk("shadow: решают правила, Jev (audio-master) — только в ответе и журнале", o["source"] == "rules" and o["decision"][0] == "mini-podcast" and o.get("jev") == ["audio-master"], o)
q = SEEN[-1]["questions"]
chk("в шлюз — вопрос на каждого кандидата правил (не на весь каталог)", len(q) == 2 and all(v["type"] == "noul" for v in q.values()), q)
row = json.loads(open(os.path.join(T, ".claude", "jev-diff.jsonl")).read().splitlines()[-1])
chk("журнал: kind skill, без текста задачи", row["kind"] == "skill" and "text" not in json.dumps(row) and "подкаст" not in json.dumps(row, ensure_ascii=False), row)
rc, o = j("skill", "--text", "сделай подкаст по отчёту", JEV_MODE="main")
chk("main: решает уверенный Jev", o["source"] == "jev" and o["decision"] == ["audio-master"], o)
n = len(SEEN); rc, o = j("skill", "--text", "какая погода завтра", JEV_MODE="main")
chk("нет кандидатов по правилам — в шлюз не хожу", len(SEEN) == n and o["decision"] == [], o)
print(f"итог {ok}/{tot}"); sys.exit(0 if ok == tot else 1)
