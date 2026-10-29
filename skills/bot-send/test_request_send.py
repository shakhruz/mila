#!/usr/bin/env python3
"""request_send.py: кнопки, которые служба рассылки выбросила бы молча (не https, choice, ряд >3, рядов >6, подпись >40), — отказ до заявки
(TIHIE-OTKAZY-2910); правильные {label, url https://} — заявка пишется."""
import json, os, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); W = tempfile.mkdtemp(); OUT = os.path.join(W, "outbox", "bot-send")
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
def run(buttons):
    args = [sys.executable, os.path.join(H, "request_send.py"), "personal", "--operator", "demo-cafe", "--to", "555000222", "--text", "Ваш заказ готов",
            "--card", "c1", "--choice", "send_ok"] + (["--buttons", buttons] if buttons is not None else [])
    r = subprocess.run(args, capture_output=True, text=True, env=dict(os.environ, MILA_WORK=W))
    return r.returncode, (r.stdout + r.stderr)
def files(): return [f for f in os.listdir(OUT) if f.endswith(".json")] if os.path.isdir(OUT) else []
for name, btn, frag in [("http (не https)", [[{"label": "Сайт", "url": "http://example.com"}]], "только https"),
                        ("tg://", [[{"label": "Канал", "url": "tg://resolve?domain=example"}]], "только https"),
                        ("choice вместо url", [[{"label": "Да", "choice": "yes"}]], "choice"),
                        ("Bot API {text, url}", [[{"text": "Сайт", "url": "https://example.com"}]], "text"),
                        ("ряд из 4", [[{"label": "a%d" % i, "url": "https://example.com"} for i in range(4)]], "до 3"),
                        ("7 рядов", [[{"label": "a%d" % i, "url": "https://example.com"}] for i in range(7)], "до 6"),
                        ("подпись 41 знак", [[{"label": "я" * 41, "url": "https://example.com"}]], "длиннее 40"),
                        ("не массив рядов", {"label": "Сайт", "url": "https://example.com"}, "массив рядов")]:
    c, out = run(json.dumps(btn, ensure_ascii=False))
    chk("%s → отказ, заявки нет" % name, c != 0 and frag in out and not files(), out)
c, out = run("[[{bad json")
chk("кнопки не JSON → отказ", c != 0 and "не JSON" in out and not files(), out)
c, out = run(json.dumps([[{"label": "Сайт", "url": "https://example.com"}, {"label": "я" * 40, "url": "https://example.com/2"}]], ensure_ascii=False))
chk("правильные кнопки (https, подпись 40) → заявка с ними", c == 0 and len(files()) == 1 and json.load(open(os.path.join(OUT, files()[0])))["buttons"][0][1]["label"] == "я" * 40, out)
c, out = run(None)
chk("без кнопок — как раньше, заявка пишется", c == 0 and len(files()) == 2, out)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
