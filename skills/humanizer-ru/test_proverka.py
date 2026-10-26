#!/usr/bin/env python3
"""proverka.py (ROLLOUT №40): пять текстов с известными ошибками ловятся; живой текст проходит; модель — через подменный сервер вместо OpenRouter.
Словарь — выдуманный STIL во временной папке (настоящий STIL владельца в ядро не кладём). Ключ — выдуманный, склейкой."""
import io, json, os, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
HERE = os.path.dirname(os.path.abspath(__file__)); PY = [sys.executable, os.path.join(HERE, "proverka.py")]
ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)
T = tempfile.mkdtemp(); STIL = os.path.join(T, "STIL.md")
open(STIL, "w", encoding="utf-8").write("""# Стиль
## Другое
| Было | Надо | Где |
|---|---|---|
| не в этой таблице | — | — |
## Правки владельца — так по-русски не говорят
| Было | Надо | Где |
|---|---|---|
| отвезти решение | принять решение | письмо 1 |
| засчитано вашим вкладом | засчитано как ваш вклад | оффер 2 |
| адвайзер | советник | пост 3 |
| голос в продукте | голос клиента в продукте | страница 4 |
""")
ENV = dict(os.environ, PROVERKA_STIL=STIL, PROVERKA_COUNT=os.path.join(T, "count.json"), PROVERKA_MAX="1000"); ENV.pop("OPENROUTER_API_KEY", None)   # свой счётчик — не съедать сутки Милы
def run(text, *args, env=None, stdin=True):
    p = subprocess.run(PY + list(args) + ["-"], input=text, capture_output=True, text=True, env=env or ENV, timeout=60)
    return p.returncode, p.stdout
FIVE = [("Мы отвезём решение к понедельнику и сообщим.", "отвезти решение"),
        ("Ваше участие будет засчитано вашим вкладом в общий фонд.", "засчитано вашим вкладом"),
        ("Наш адвайзер свяжется с вами завтра.", "адвайзер"),
        ("Это и есть голос в продукте, о котором мы говорили.", "голос в продукте"),
        ("А мы решили подождать, а они согласились.", "два «а»")]
for text, want in FIVE:
    code, out = run(text, "--no-llm")
    chk("ловится без модели: «%s»" % want, code == 1 and "НАЙДЕНО" in out and want in out)
code, out = run("А сначала мы подумали. А потом решили.", "--no-llm")
chk("два предложения подряд с «А» — ловится", code == 1 and "два предложения подряд" in out)
LIVE = "Анна приедет в пятницу. Мы примем решение к понедельнику и пришлём ответ. Совет директоров соберётся в среду."
code, out = run(LIVE, "--no-llm")
chk("живой текст (имя «Анна», «примем решение») — ПРОШЁЛ, без ложных", code == 0 and out.startswith("ПРОШЁЛ"))
code, out = run("<html><style>.a{}</style><p>Наш <b>адвайзер</b> свяжется.</p></html>", "--no-llm")
chk("HTML очищается от тегов и стилей, находка — по тексту", code == 1 and "адвайзер" in out)
code, out = run("Отвезти решение", "--no-llm", env=dict(ENV, PROVERKA_STIL=os.path.join(T, "нет.md")))
chk("нет словаря владельца — слой пропущен с заметкой, правила работают", code == 0 and "словарь владельца не найден" in out)
code, out = run(LIVE)
chk("нет OPENROUTER_API_KEY — заметка «пропущено», не падение", code == 0 and "нет OPENROUTER_API_KEY" in out)
# модель: подменный сервер
seen = []; mode = {"m": "ok"}
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers["Content-Length"]))); seen.append((b, self.headers.get("Authorization")))
        if mode["m"] == "bad": self.send_response(500); self.end_headers(); return
        txt = '[{"было": "в разрезе продаж", "надо": "по продажам", "почему": "канцелярит"}]' if mode["m"] == "ok" else "Править нечего: []"
        r = json.dumps({"choices": [{"message": {"content": txt}}], "usage": {"cost": 0.0042}}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(r))); self.end_headers(); self.wfile.write(r)
    def log_message(self, *a): pass
srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
KEY = "sk" + "-or-" + "fake" + "-key-0001"
E2 = dict(ENV, OPENROUTER_API_KEY=KEY, PROVERKA_API="http://127.0.0.1:%d/v1/chat/completions" % srv.server_address[1])
code, out = run("Мы растём в разрезе продаж.", env=E2)
chk("модель нашла канцелярит → в выводе «было → надо · почему», код 1", code == 1 and "в разрезе продаж → по продажам · канцелярит" in out)
chk("ключ — своей Милы (OPENROUTER_API_KEY) в заголовке; модель по умолчанию anthropic/claude-sonnet-5.5", seen[-1][1] == "Bearer " + KEY and seen[-1][0]["model"] == "anthropic/claude-sonnet-5.5")
chk("расход виден в выводе ($0.0042) — топливо Милы", "$0.0042" in out)
chk("ключ не печатается", KEY not in out)
mode["m"] = "empty"; code, out = run(LIVE, env=E2)
chk("модель: править нечего ([] в тексте ответа) — ПРОШЁЛ", code == 0 and out.startswith("ПРОШЁЛ"))
mode["m"] = "bad"; code, out = run(LIVE, env=E2)
chk("модель упала (500) — заметка «не удалось», текст не блокирую ложной находкой", code == 0 and "не удалось" in out)
mode["m"] = "ok"; code, out = run("Наш адвайзер растёт в разрезе продаж.", env=E2)
chk("словарь и модель вместе — обе находки, НАЙДЕНО 2", code == 1 and "НАЙДЕНО 2" in out)
long = "Мы растём. " * 3000; run(long, env=E2)
chk("в модель уходит не больше 12 000 знаков текста", len(seen[-1][0]["messages"][0]["content"]) < 12000 + 2000)
run("Позвоните мне +998 90 " + "123 45 67 или ivan@example.com, карта 4111 1111 " + "1111 1111.", env=E2)
sent = seen[-1][0]["messages"][0]["content"]
chk("в модель — без телефона, почты и карты (метки вместо них)", "⟦тел⟧" in sent and "⟦почта⟧" in sent and "⟦карта⟧" in sent and "ivan@" not in sent and "4111" not in sent and "45 67" not in sent)
cf = os.path.join(T, "cnt.json"); E3 = dict(E2, PROVERKA_MAX="2", PROVERKA_COUNT=cf); n0 = len(seen)
outs = [run("Мы растём в разрезе продаж.", env=E3)[1] for _ in range(3)]
chk("лимит в сутки: 2 чтения моделью, третье — заметка «лимит», словарь работает", len(seen) - n0 == 2 and "лимит 2 в сутки" in outs[2] and "в разрезе продаж" not in outs[2])
chk("без аргумента — справка, код 2", subprocess.run(PY, capture_output=True, text=True).returncode == 2)
srv.shutdown()
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
