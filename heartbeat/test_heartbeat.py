#!/usr/bin/env python3
"""Heartbeat on temp dirs and fixed times (no network, no model): cron parsing and matching, think in quiet hours, once fires
once, beat queues only new findings, a missed minute is made up within 15 min, nothing fires twice, journal lines, watchdog
sends one message per incident, detectors tg_unread and deadlines. Times are built from now in Asia/Tashkent.
Run: python3 test_heartbeat.py"""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile
from zoneinfo import ZoneInfo
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="heartbeat-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
os.environ.update(MILA_HEARTBEAT_STATE=os.path.join(T, "state"), MILA_HEARTBEAT_QUEUE=os.path.join(T, "inbound"), MILA_OWNER_CHAT=str(int("555" + "000111")))
sys.path.insert(0, H); sys.path.insert(0, os.path.join(H, "detectors"))
import heartbeat as hb, deadlines, tg_unread
TZ = ZoneInfo("Asia/Tashkent")
today = dt.datetime.now(TZ).replace(second=0, microsecond=0)
def at(h, m, days=0): return (today.replace(hour=h, minute=m) + dt.timedelta(days=days)).timestamp()
def events():
    p = os.path.join(T, "inbound", "events.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []
def reset():
    shutil.rmtree(os.path.join(T, "state"), ignore_errors=True); shutil.rmtree(os.path.join(T, "inbound"), ignore_errors=True)
# cron
c = hb.parse_cron("13 7 * * 1-5")
mon = today - dt.timedelta(days=today.weekday())   # Monday this week
check("cron «13 7 * * 1-5»: пн 07:13 да, 07:14 нет, вс 07:13 нет",
      hb.cron_match(c, mon.replace(hour=7, minute=13)) and not hb.cron_match(c, mon.replace(hour=7, minute=14)) and not hb.cron_match(c, (mon + dt.timedelta(days=6)).replace(hour=7, minute=13)))
c2 = hb.parse_cron("*/10 8-21 * * *")
check("cron «*/10 8-21 * * *»: 08:20 да, 08:25 нет, 22:00 нет", hb.cron_match(c2, today.replace(hour=8, minute=20)) and not hb.cron_match(c2, today.replace(hour=8, minute=25)) and not hb.cron_match(c2, today.replace(hour=22, minute=0)))
c3 = hb.parse_cron("0 9 1 * 0")
first = today.replace(day=1, hour=9, minute=0)
sunday = (today - dt.timedelta(days=(today.weekday() + 1) % 7)).replace(hour=9, minute=0)
check("cron с днём месяца и днём недели — любой из двух (как cron)", hb.cron_match(c3, first) and hb.cron_match(c3, sunday))
bad = []
for e in ("13 7 * *", "61 * * * *", "* 25 * * *", "*/0 * * * *", "a b c d e"):
    try:
        hb.parse_cron(e); bad.append(e)
    except ValueError:
        pass
check("неверный cron — ошибка, не тихий пропуск", not bad, bad)
# config validation
def cfg(jobs, **kw): return dict({"timezone": "Asia/Tashkent", "quiet_hours": "22-08", "jobs": jobs}, **kw)
p = os.path.join(T, "hb.json")
for broken, why in (([{"id": "X", "type": "think", "cron": "* * * * *", "prompt": "a"}], "id"), ([{"id": "a", "type": "nap", "cron": "* * * * *"}], "type"),
                    ([{"id": "a", "type": "beat", "cron": "* * * * *"}], "check"), ([{"id": "a", "type": "once", "prompt": "p"}], "at")):
    json.dump(cfg(broken), open(p, "w"))
    try:
        hb.load_config(p); check("конфиг без %s — отказ" % why, False)
    except ValueError:
        check("конфиг без %s — отказ" % why, True)
# think
reset()
C = cfg([{"id": "morning", "type": "think", "cron": "13 7 * * *", "prompt": "Утро: план дня", "quiet": False},   # 07:13 внутри 22–08: явно quiet: false
         {"id": "late", "type": "think", "cron": "30 23 * * *", "prompt": "Ночная мысль"},
         {"id": "early", "type": "think", "cron": "0 7 * * *", "prompt": "Ранняя мысль"}])
hb.tick(C, at(7, 12)); check("07:00 «early» без quiet: false — тихие часы, не идёт; 07:12 — утро ещё не пришло", events() == [])
hb.tick(C, at(7, 13)); ev = events()
check("07:13 (quiet: false) — одно сообщение в очередь канала: текст, чат владельца, метка heartbeat",
      len(ev) == 1 and ev[0]["params"]["content"] == "Утро: план дня" and ev[0]["params"]["meta"]["chat_id"] == os.environ["MILA_OWNER_CHAT"] and ev[0]["params"]["meta"]["heartbeat"] == "morning", ev)
hb.tick(C, at(7, 13)); hb.tick(C, at(7, 14)); check("тот же час повторно и 07:14 — не дублирует", len(events()) == 1)
hb.tick(C, at(23, 30)); check("23:30 (тихие часы) — мысль не идёт, в журнале «skipped: quiet hours»", len(events()) == 1 and "skipped: quiet hours" in open(os.path.join(T, "state", "heartbeat.log")).read())
reset(); hb.tick(C, at(7, 0)); hb.tick(C, at(7, 20))
check("служба спала 07:01–07:19 — утро догоняется (≤15 мин), одно", len(events()) == 1 and "made up 7 min late" in open(os.path.join(T, "state", "heartbeat.log")).read())
reset(); hb.tick(C, at(6, 0)); hb.tick(C, at(7, 40))
check("пропуск дольше 15 мин — не догоняем", events() == [])
# once
reset(); C1 = cfg([{"id": "call", "type": "once", "at": today.replace(hour=10, minute=0).strftime("%Y-%m-%d %H:%M"), "prompt": "Звонок в 10:30"}])
hb.tick(C1, at(9, 59)); hb.tick(C1, at(10, 0)); hb.tick(C1, at(10, 5)); hb.tick(C1, at(11, 0, 1))
check("once — ровно один раз в своё время", [e["params"]["content"] for e in events()] == ["Звонок в 10:30"])
# beat
reset()
script = os.path.join(T, "check.sh"); out = os.path.join(T, "found.txt")
open(script, "w").write("#!/bin/sh\ncat %s 2>/dev/null || true\n" % out); os.chmod(script, 0o755)
CB = cfg([{"id": "chats", "type": "beat", "cron": "*/5 * * * *", "check": script, "prompt": "Новое в чате программы:"}])
hb.tick(CB, at(9, 0)); check("beat без находок — ничего", events() == [] and "nothing" in open(os.path.join(T, "state", "heartbeat.log")).read())
open(out, "w").write('{"key": "a1", "text": "Анонсы: слоты на демо-день"}\nпросто строка\n')
hb.tick(CB, at(9, 5)); ev = events()
check("beat: две находки → два сообщения, prompt сверху", len(ev) == 2 and ev[0]["params"]["content"].startswith("Новое в чате программы:\nАнонсы"), ev)
hb.tick(CB, at(9, 10)); check("те же находки — повторно не шлёт", len(events()) == 2)
open(out, "a").write('{"key": "a2", "text": "Материалы: запись урока"}\n'); hb.tick(CB, at(9, 15))
check("новая находка — только она", len(events()) == 3 and "запись урока" in events()[-1]["params"]["content"])
open(script, "w").write("#!/bin/sh\necho boom >&2; exit 3\n"); hb.tick(CB, at(9, 20))
check("проверка упала — в журнале «error: exit 3», сообщений нет", len(events()) == 3 and "error: exit 3" in open(os.path.join(T, "state", "heartbeat.log")).read())
open(script, "w").write("#!/bin/sh\nsleep 5\n"); CBt = cfg([dict(CB["jobs"][0], timeout=1)]); hb.tick(CBt, at(9, 25))
check("проверка зависла — таймаут, «error: TimeoutExpired»", "TimeoutExpired" in open(os.path.join(T, "state", "heartbeat.log")).read())
check("until в прошлом — задание не идёт", hb.tick(cfg([{"id": "old", "type": "think", "cron": "* * * * *", "prompt": "x", "until": "2020-01-01"}]), at(12, 0)) == 0)
# journal format
line = open(os.path.join(T, "state", "heartbeat.log")).read().splitlines()[-1].split("\t")
check("журнал: время · задание · вид · что · длительность", len(line) == 5 and line[1] == "chats" and line[2] == "beat" and line[4].endswith("ms"), line)
# watchdog
reset(); os.makedirs(os.path.join(T, "inbound"))
EV = os.path.join(T, "inbound", "events.jsonl"); CUR = os.path.join(T, "inbound", "feeder-cursor")
open(EV, "w").write(json.dumps({"ts": int((at(9, 0)) * 1000), "params": {}}) + "\n"); open(CUR, "w").write("0")
sent = []
def fake_send(tok, chat, text): sent.append((tok, chat, text)); return True
os.environ.update(BOT_TOKEN="000000:" + "FAKE" + "z" * 8, MILA_ADMIN_CHAT=str(int("555" + "000222")))
W = cfg([], watchdog={"after_min": 15})
check("очередь взята — сторож молчит", hb.watchdog(W, at(9, 10), send=fake_send) is None and not sent)
hb.watchdog(W, at(9, 16), send=fake_send); hb.watchdog(W, at(9, 30), send=fake_send)
check("не берёт > 15 мин — одно сообщение на случай, текст с минутами", len(sent) == 1 and "16 min" in sent[0][2] and sent[0][1] == os.environ["MILA_ADMIN_CHAT"], sent)
open(CUR, "w").write(str(os.path.getsize(EV))); hb.watchdog(W, at(9, 40), send=fake_send)
open(EV, "a").write(json.dumps({"ts": int(at(9, 41) * 1000), "params": {}}) + "\n"); hb.watchdog(W, at(10, 0), send=fake_send)
check("взяла, потом новый затор — новое сообщение", len(sent) == 2)
check("в журнале — «alert sent», без токена", "alert sent" in open(os.path.join(T, "state", "heartbeat.log")).read() and "FAKE" not in open(os.path.join(T, "state", "heartbeat.log")).read())
# detectors
D = os.path.join(T, "dl.json"); now = dt.datetime.now(TZ)
json.dump([{"id": "d1", "text": "Сдать отчёт", "due": (now + dt.timedelta(minutes=90)).strftime("%Y-%m-%d %H:%M")},
           {"id": "d2", "text": "Далеко", "due": (now + dt.timedelta(hours=30)).strftime("%Y-%m-%d %H:%M")},
           {"id": "d3", "text": "Просрочено", "due": (now - dt.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")},
           {"id": "d4", "text": "Сделано", "due": now.strftime("%Y-%m-%d %H:%M"), "done": True}], open(D, "w"), ensure_ascii=False)
r = subprocess.run([sys.executable, os.path.join(H, "detectors", "deadlines.py"), "--file", D, "--hours", "2"], capture_output=True, text=True)
got = [json.loads(l) for l in r.stdout.splitlines()]
check("deadlines: ближе 2 ч и просроченное — да; далёкое и сделанное — нет", sorted(g["key"].split(":")[0] for g in got) == ["d1", "d3"] and any("overdue" in g["text"] for g in got), got)
M = os.path.join(T, "map.json")
json.dump([{"id": -100123, "title": "Program A · Анонсы", "unread": 2, "last": "x"}, {"id": -100456, "title": "Другой", "unread": 9}], open(M, "w"), ensure_ascii=False)
run = lambda: subprocess.run([sys.executable, os.path.join(H, "detectors", "tg_unread.py"), "--chat", "program a", "--map", M], capture_output=True, text=True, env=os.environ).stdout
first = run()
json.dump([{"id": -100123, "title": "Program A · Анонсы", "unread": 5, "last": "y"}, {"id": -100456, "title": "Другой", "unread": 20}], open(M, "w"), ensure_ascii=False)
second = [json.loads(l) for l in run().splitlines()]
check("tg_unread: первый проход только запоминает; рост 2 → 5 — одна находка, чужой чат не смотрим",
      first == "" and len(second) == 1 and "5 unread (was 2)" in second[0]["text"] and "-100123" in second[0]["key"], second)
check("tg_unread: прочитали (5 → 0) — ничего", (json.dump([{"id": -100123, "title": "Program A", "unread": 0}], open(M, "w")), run())[1] == "")
# CLI
json.dump(C, open(p, "w"))
r = subprocess.run([sys.executable, os.path.join(H, "heartbeat.py"), "--config", p, "--list"], capture_output=True, text=True)
check("--list: задания и расписание", "morning" in r.stdout and "13 7 * * *" in r.stdout)
r = subprocess.run([sys.executable, os.path.join(H, "heartbeat.py"), "--config", os.path.join(T, "nope.yaml")], capture_output=True, text=True)
check("нет heartbeat.yaml — тихий выход 0", r.returncode == 0 and "nothing to do" in r.stdout)
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
