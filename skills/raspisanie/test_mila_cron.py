#!/usr/bin/env python3
"""mila-cron (Барабан): задачи расписания в доме Милы — что принимаю, что отказываю, импорт кронов из снимка, list по журналу плагина.
Всё во временной папке (MILA_WORK, MILA_EVENTS), время подменено (MILA_CRON_NOW). Usage: python3 test_mila_cron.py [папка с mila_cron.py]"""
import json, os, subprocess, sys, tempfile, threading
D = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)); K = os.path.join(D, "mila_cron.py")
ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)
W = tempfile.mkdtemp(prefix="cron-"); EV = os.path.join(W, "events.jsonl")
env = dict(os.environ, MILA_WORK=W, MILA_EVENTS=EV, MILA_CRON_NOW="2026-10-26T10:00:00+05:00")
def k(*a):
    p = subprocess.run([sys.executable, K, *a], env=env, capture_output=True, text=True, timeout=30); return p.returncode, p.stdout
def jobs(): return json.load(open(os.path.join(W, "schedule", "jobs.json")))["jobs"]
code, out = k("add", "vtoroy-vzglyad", "17 10,12,14,16,18,20 * * *", "Второй взгляд: запусти vtoroy_vzglyad.py")
chk("add: задача записана, живёт 30 дней, ближайший срок 26.10 10:17", code == 0 and "до 2026-11-25" in out and "26.10 10:17" in out and jobs()[0]["by"] == "mila")
chk("файл расписания — только владельцу (600)", oct(os.stat(os.path.join(W, "schedule", "jobs.json")).st_mode)[-3:] == "600")
for args, why in ((["add", "Bad_ID", "0 9 * * *", "x"], "id"), (["add", "a", "* * * * *", "x"], "раза в 5"), (["add", "b", "*/3 * * * *", "x"], "раза в 5"),
                  (["add", "c", "61 9 * * *", "x"], "cron"), (["add", "d", "0 9 * * *", ""], "текст"), (["add", "e", "0 9 * * *", "я" * 2001], "текст"),
                  (["add", "f", "0 9 * * *", "x", "--by", "owner"], "--word"), (["add", "g", "0 9 * * *", "x", "--no-expire"], "без срока нельзя"),
                  (["add", "h", "0 9 * * *", "x", "--expires", "2027-03-01"], "срок жизни"), (["add", "vtoroy-vzglyad", "0 9 * * *", "x"], "уже есть")):
    code, out = k(*args)
    chk("отказ: %s → «%s»" % (" ".join(args[1:3]), why), code == 1 and why in out)
code, out = k("add", "vecher", "30 19 * * *", "Вечерняя проверка", "--by", "owner", "--word", "-100" + "1/2189", "--no-expire")
chk("без срока — нельзя никому, даже с --by owner (Качество: вечная задача тратит подписку молча)", code == 1 and "без срока нельзя" in out)
code, out = k("add", "vecher", "30 19 * * *", "Вечерняя проверка", "--by", "owner", "--word", "-100" + "1/2189", "--expires", "2027-01-20")
chk("по слову владельца — с word, до 90 дней", code == 0 and [j for j in jobs() if j["id"] == "vecher"][0]["expires"] == "2027-01-20")
chk("pause / resume / extend", k("pause", "vecher")[0] == 0 and not [j for j in jobs() if j["id"] == "vecher"][0]["enabled"]
    and k("resume", "vecher")[0] == 0 and k("extend", "vtoroy-vzglyad", "2026-12-20")[0] == 0 and [j for j in jobs() if j["id"] == "vtoroy-vzglyad"][0]["expires"] == "2026-12-20")
code, out = k("next", "0 9 * * 1", "3")
chk("next: три ближайших понедельника 09:00", code == 0 and out.count("09:00") == 3 and "Mon 02.11" in out)
open(EV, "w").write(json.dumps({"method": "notifications/claude/channel", "params": {"content": "[⏰ расписание] …", "meta": {"ritual": "cron", "job": "vtoroy-vzglyad",
                                 "message_id": "cron-razrabotka-vtoroy-vzglyad-" + "20261026" + "1017", "ts": "2026-10-26T10:17:00+05:00"}}}) + "\n")
k("done", "vtoroy-vzglyad", "пропусков нет")
code, out = k("list")
chk("list: следующий срок, последний запуск по журналу плагина, итог", code == 0 and "vtoroy-vzglyad" in out and "следующий 2026-10-26T10:17" in out and "последний 2026-10-26T10:17" in out and "итог: пропусков нет" in out)
chk("rm и задачи «нет такой»", k("rm", "vecher")[0] == 0 and k("rm", "vecher")[0] == 1)
snap = os.path.join(W, "crons.md")
open(snap, "w").write("# Снимок\n## Кроны сессии\n- 5223c3ed · «Второй взгляд» · 17 10,12,14,16,18,20 * * * · durable, истекает 01.11\n- 77aa · «Сломанный» · 99 9 * * * · x\n## Обещания\n- 1 · «не крон» · 0 9 * * * · x\n")
code, out = k("import", snap)
chk("import из снимка: «Кроны сессии» → задача c-5223c3ed; битая — пропуск с причиной; чужой раздел не трогаю", code == 0 and "перенесено 1" in out and "c-77aa" in out
    and any(j["id"] == "c-5223c3ed" for j in jobs()) and not any(j["id"] == "c-1" for j in jobs()))
open(os.path.join(W, "schedule", "jobs.json"), "w").write("{не json")
chk("испорченный jobs.json — отказ, не перезаписываю", k("add", "z", "0 9 * * *", "x")[0] == 1 and open(os.path.join(W, "schedule", "jobs.json")).read() == "{не json")
os.remove(os.path.join(W, "schedule", "jobs.json"))
th = [threading.Thread(target=k, args=("add", "p%d" % i, "0 9 * * *", "x")) for i in range(12)]
[t.start() for t in th]; [t.join() for t in th]
chk("12 одновременных add — все 12 записаны (замок, без потерь)", len(jobs()) == 12)
for i in range(12, 30): k("add", "p%d" % i, "0 9 * * *", "x")
chk("31-я задача — отказ (не больше 30)", k("add", "p30", "0 9 * * *", "x") == (1, k("add", "p30", "0 9 * * *", "x")[1]) and len(jobs()) == 30)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
