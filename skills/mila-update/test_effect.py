#!/usr/bin/env python3
"""effect.py: числа «до/после» из подложенных журналов; нет источника — «нет данных»; хуже — флаг."""
import json, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import effect as E
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(); HOME = os.path.join(T, "h"); CL = os.path.join(HOME, ".claude"); P = os.path.join(CL, "projects", "-w"); os.makedirs(P)
now = int(time.time()) // 3600 * 3600
def iso(t): return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))
def turn(f, t, replies=1, tok=1000):
    with open(os.path.join(P, f), "a") as fh:
        fh.write(json.dumps({"type": "assistant", "timestamp": iso(t), "message": {"usage": {"input_tokens": tok // 2, "output_tokens": tok // 2},
            "content": [{"type": "tool_use", "name": "mcp__plugin_mila-telegram_telegram__reply", "input": {"text": "секрет клиента"}}] * replies + [{"type": "text", "text": "x"}]}}) + "\n")
t_apply = now - 3 * 86400
for d in range(7):   # до: 7 дней по 10 ответов
    for k in range(10): turn("a.jsonl", t_apply - (d + 1) * 86400 + k * 600)
for d in range(3):   # после: 3 дня по 4 ответа
    for k in range(4): turn("b.jsonl", t_apply + d * 86400 + k * 600)
before = E.metrics(HOME, CL, t_apply - 7 * 86400, t_apply); after = E.metrics(HOME, CL, t_apply, t_apply + 3 * 86400)
chk("до: 10 ответов в день, 10 000 токенов в день", before["replies"] == 10.0 and before["tokens"] == 10000.0, before)
chk("после: 4 ответа в день (окно не берёт дни до обновления)", after["replies"] == 4.0, after)
chk("журнала приёмника нет → ошибки «нет данных» (None), не 0", before["errors"] is None and after["errors"] is None, (before, after))
lines, worse = E.compare(before, after)
chk("ответов −60 %, но входящих не знаю → не «хуже» (может, писали меньше); строки простыми словами", not worse and "· моих ответов в день: 10 → 4" in lines and any("нет данных" in l for l in lines) and not any("токен" in l for l in lines), lines)
lines, worse = E.compare({"inbound": 20, "replies": 18, "errors": 0}, {"inbound": 20, "replies": 8, "errors": 0})
chk("входящих столько же, отвечаю на 90 → 40 из 100 → хуже", worse and any("отвечаю на 90 → 40 из 100" in l for l in lines), lines)
lines, worse = E.compare({"inbound": 20, "replies": 18, "errors": 0}, {"inbound": 8, "replies": 7, "errors": 0})
chk("хозяин писал меньше (20 → 8 в день), доля та же → НЕ хуже (Качество: праздники)", not worse, lines)
lines, worse = E.compare({"inbound": 2, "replies": 2, "errors": 0}, {"inbound": 2, "replies": 0, "errors": 0})
chk("входящих меньше 3 в день → по доле не сужу", not worse, lines)
IN = os.path.join(CL, "channels", "telegram", "inbound"); os.makedirs(IN)
with open(os.path.join(IN, "events.jsonl"), "w") as f:
    for d in range(3):
        for k in range(6): f.write(json.dumps({"ts": int((t_apply + d * 86400 + k * 600) * 1000), "params": {"content": "текст гостя"}}) + "\n")
chk("входящие: 6 в день после обновления (из inbound/events.jsonl), текстов не беру", E.metrics(HOME, CL, t_apply, t_apply + 3 * 86400)["inbound"] == 6.0)
os.makedirs(os.path.join(HOME, "state"))
with open(os.path.join(HOME, "state", "receiver.log"), "w") as f:
    for d in range(3):
        for k in range(5): f.write("%s receiver: send failed 429 Too Many Requests\n" % iso(t_apply + d * 86400 + k * 60)[:19])
    f.write("%s receiver: polling ok\n" % iso(t_apply + 100)[:19])
    f.write("%s receiver: error before\n" % iso(t_apply - 86400)[:19])
after2 = E.metrics(HOME, CL, t_apply, t_apply + 3 * 86400); before2 = E.metrics(HOME, CL, t_apply - 7 * 86400, t_apply)
chk("ошибки: после — 5 в день, до — 1/7 в день; «ok» не ошибка", after2["errors"] == 5.0 and before2["errors"] == round(1 / 7, 1), (before2, after2))
lines, worse = E.compare({"replies": 10, "errors": 1, "tokens": 5}, {"replies": 11, "errors": 1.2, "tokens": 6})
chk("почти то же самое → не хуже", not worse, lines)
lines, worse = E.compare({"replies": 10, "errors": 2, "tokens": 5}, {"replies": 10, "errors": 4, "tokens": 5})
chk("ошибок ×2 и ≥ 3 в день → хуже", worse, lines)
lines, worse = E.compare({"replies": 10, "errors": 0.5, "tokens": 5}, {"replies": 10, "errors": 1.0, "tokens": 5})
chk("ошибок ×2, но всего 1 в день → не «хуже» (порог — от 3 в день)", not worse, lines)
lines, worse = E.compare({"replies": None, "errors": None, "tokens": None}, {"replies": None, "errors": None, "tokens": None})
chk("данных нет ни до, ни после → не «хуже», три строки «нет данных»", not worse and sum("нет данных → нет данных" in l for l in lines) == 3, lines)
chk("тексты сообщений в числа не попадают (только вызовы)", "секрет" not in json.dumps([before, after]))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
