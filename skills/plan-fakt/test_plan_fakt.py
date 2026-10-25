#!/usr/bin/env python3
"""plan-fakt: collect (факты из WEEK.md, пультов дня, MONEY.md — только если есть), make_slides (квадрат, экранирование,
Chromium через CHROME_BIN), send_slideshow (2–10 слайдов, токен не печатается). Без сети и без браузера. python3 test_plan_fakt.py"""
import importlib.util, io, json, os, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); S = os.path.join(H, "scripts")
ok = n = 0
def chk(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + str(x)[:300]))
def run(script, *a, env=None):
    r = subprocess.run([sys.executable, os.path.join(S, script), *a], capture_output=True, text=True, env=dict(os.environ, **(env or {})))
    return r.returncode, r.stdout
W = tempfile.mkdtemp(prefix="pf-"); os.makedirs(os.path.join(W, "state"))
open(os.path.join(W, "WEEK.md"), "w").write("# Неделя\n- [x] Ответы в Instagram\n- [ ] Прайс на сайте\n🔴 Реклама сорвалась\n")
for d, items in (("2026-10-19", [{"no": 1, "text": "Шаблоны ответов", "state": "done", "evidence": "f"}, {"no": 2, "text": "Цены", "state": "wait"}]),
                 ("2026-10-20", [{"no": 2, "text": "Цены", "state": "wait"}, {"no": 3, "text": "CRM", "state": "queue"}])):
    json.dump({"date": d, "items": items}, open(os.path.join(W, "state", "day-%s.json" % d), "w"))
c, o = run("collect.py", "--work", W, "--monday", "2026-10-19"); d = json.loads(o)
chk("collect: план недели из WEEK.md (галочки и светофор)", [r[0] for r in d["slides"][0]["rows"]] == ["🟢", "🟡", "🔴"], d["slides"][0])
chk("collect: сделано 1, ждёт 1 (перенос с тем же номером — без дубля), в очереди 1", d["facts"]["done"] == 1 and d["facts"]["wait"] == 1 and d["facts"]["open"] == 1, d["facts"])
chk("collect: нет MONEY.md — ни слайда, ни плиток про деньги", not d["facts"]["money"] and not any(s["title"] == "Деньги" for s in d["slides"]) and "$" not in json.dumps(d["cover"]))
open(os.path.join(W, "MONEY.md"), "w").write("MRR: $1 200\nОплат за неделю: $300\n")
d2 = json.loads(run("collect.py", "--work", W, "--monday", "2026-10-19")[1])
chk("collect: есть MONEY.md — плитки из него и слайд «Деньги»", d2["facts"]["money"] and d2["cover"]["tiles"][0][0] == "$1 200" and any(s["title"] == "Деньги" for s in d2["slides"]), d2["cover"])
E = tempfile.mkdtemp(prefix="pf0-")
d3 = json.loads(run("collect.py", "--work", E, "--monday", "2026-10-19")[1])
chk("collect: пустой дом — «нет данных», не догадка", "нет данных" in json.dumps(d3, ensure_ascii=False) and d3["facts"]["days_with_board"] == 0)
chk("collect: пустая неделя — без нулей (ноль читается как факт): плитка «нет данных», «Сделано» — «нет данных»",
    d3["cover"]["tiles"] == [["—", "нет данных:<br>пультов дня за неделю нет", "sand"]] and d3["slides"][1]["kicker"] == "нет данных" and "Нет данных: файлов недели нет" in d3["cover"]["lead"], d3)
open(os.path.join(W, "WEEK.md"), "a").write("- [ ] Позвонить +998 90 123 45 67 по карте 4111 1111 1111 1111, почта a.b@mail.uz\n- [ ] Заявка №1234567890123456 в чате -100" "1234567890\n")
d4 = json.loads(run("collect.py", "--work", W, "--monday", "2026-10-19")[1]); js = json.dumps(d4, ensure_ascii=False)
chk("collect: в строках WEEK.md карта ****1111, телефон ⟦тел⟧, почта ⟦почта⟧", "****1111" in js and "⟦тел⟧" in js and "⟦почта⟧" in js and "4111 1111" not in js and "90 123 45 67" not in js, d4["slides"][0])
chk("collect: номер заявки и id чата не принимаются за телефон", "1234567890123456" in js or "№" in js)
# make_slides: поддельный Chromium пишет PNG; экранирование
fake = os.path.join(W, "chrome"); open(fake, "w").write("#!/bin/sh\nfor a in \"$@\"; do case $a in --screenshot=*) f=${a#--screenshot=}; printf 'PNG' > \"$f\";; esac; done\n"); os.chmod(fake, 0o755)
data = json.load(open(os.path.join(H, "data-example.json")))
data["cover"]["title"] = "Итог<br><em>недели</em><script>x()</script>"; data["slides"][0]["rows"][0][1] = "<img src=x onerror=1>"
dp = os.path.join(W, "data.json"); json.dump(data, open(dp, "w"), ensure_ascii=False)
out = os.path.join(W, "out"); c, o = run("make_slides.py", dp, out, env={"CHROME_BIN": fake})
chk("make_slides: слайдов = 1 + slides, через CHROME_BIN", c == 0 and len(json.loads(o)["slides"]) == 1 + len(data["slides"]), o)
h1 = open(os.path.join(out, "s1.html"), encoding="utf-8").read(); h2 = open(os.path.join(out, "s2.html"), encoding="utf-8").read()
chk("make_slides: в заголовке живут только <br> и <em>, <script> экранирован", "<br>" in h1 and "<em>" in h1 and "<script>" not in h1 and "&lt;script&gt;" in h1)
chk("make_slides: строки карточек экранированы", "<img src=x" not in h2 and "&lt;img" in h2)
chk("make_slides: квадрат 1080×1080", "width:1080px;height:1080px" in h1 and "--window-size=1080,1080" in open(os.path.join(S, "make_slides.py")).read())
c, o = run("make_slides.py", dp, out, env={"CHROME_BIN": "/нет/такого"})
chk("make_slides: Chromium не найден — понятная строка, код 2", c == 2 and "CHROME_BIN" in o, o)
bad = dict(data); bad["slides"] = []; json.dump(bad, open(dp, "w")); c, o = run("make_slides.py", dp, out, env={"CHROME_BIN": fake})
chk("make_slides: без слайдов — отказ (в посте 2–10)", c == 2)
# send_slideshow: без сети
spec = importlib.util.spec_from_file_location("ss", os.path.join(S, "send_slideshow.py")); ss = importlib.util.module_from_spec(spec); spec.loader.exec_module(ss)
imgs = [os.path.join(out, "s1.png"), os.path.join(out, "s2.png")]
FAKE_TOK = "123456789:" + "AA" + "secret" * 6   # фальшивка склейкой — сканеры снимков Мил её не видят
os.environ["TELEGRAM_BOT_TOKEN"] = FAKE_TOK
sent = {}
class R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass
def opener(req, timeout=60):
    sent["url"] = req.full_url; sent["body"] = req.data; return R(json.dumps({"ok": True, "result": {"message_id": 77}}).encode())
buf = io.StringIO(); so = sys.stdout; sys.stdout = buf
rc = ss.main(["111", "<p><b>План-факт</b></p>", *imgs], opener=opener); sys.stdout = so
chk("send: один sendRichMessage, слайдшоу из 2 картинок, ok 77", rc == 0 and sent["url"].endswith("/sendRichMessage") and b"tg-slideshow" in sent["body"] and b'attach://f1' in sent["body"] and "ok 77" in buf.getvalue(), buf.getvalue())
def bad_op(req, timeout=60): raise ss.urllib.error.HTTPError(req.full_url, 400, "x", {}, io.BytesIO(json.dumps({"ok": False, "description": "bad token " + FAKE_TOK}).encode()))
buf = io.StringIO(); sys.stdout = buf; rc = ss.main(["111", "x", *imgs], opener=bad_op); sys.stdout = so
chk("send: ошибка — токен в выводе не появляется", rc == 1 and "AAsecret" not in buf.getvalue() and "<token>" in buf.getvalue(), buf.getvalue())
buf = io.StringIO(); sys.stdout = buf; rc = ss.main(["111", "x", imgs[0]], opener=opener); sys.stdout = so
chk("send: одна картинка — отказ (листалке нужно 2–10)", rc == 2)
print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
