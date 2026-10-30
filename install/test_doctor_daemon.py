#!/usr/bin/env python3
"""doctor: демон ЭТОГО дома — по <state>/receiver.pid, иначе по TELEGRAM_STATE_DIR в окружении процесса; соседняя Мила
под тем же пользователем — не моя («демон работает (pid чужой)» обманывал диагностику)."""
import importlib.util, os, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(); ST = os.path.join(T, "mine"); os.makedirs(ST)
os.environ["TELEGRAM_STATE_DIR"] = ST
spec = importlib.util.spec_from_file_location("doc", os.path.join(H, "doctor.py")); D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
ok = n = 0
def chk(m, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:200]))
L = [("101", "bun /x/mila-telegram/receiver.ts"), ("202", "bun /y/mila-telegram/receiver.ts")]
envs = {"101": {"TELEGRAM_STATE_DIR": os.path.join(T, "neighbour")}, "202": {"TELEGRAM_STATE_DIR": ST}}
D._proc_env = lambda pid: envs.get(pid)
chk("без pid-файла: свой — по TELEGRAM_STATE_DIR в окружении, сосед отброшен", D.own_receivers(L) == [L[1]], D.own_receivers(L))
open(os.path.join(ST, "receiver.pid"), "w").write("101\n")
chk("pid-файл моего дома указывает на 101 — он и мой", D.own_receivers(L) == [L[0]], D.own_receivers(L))
os.remove(os.path.join(ST, "receiver.pid")); D._proc_env = lambda pid: None
chk("окружение не прочитать (macOS) — оба считаю своими, как раньше (дальше «две копии»)", D.own_receivers(L) == L)
D._proc_env = lambda pid: envs.get(pid); envs["202"] = {}
chk("у процесса нет TELEGRAM_STATE_DIR — состояние по умолчанию ~/.claude/channels/telegram ≠ моё → не мой", D.own_receivers(L) == [], D.own_receivers(L))
class R:
    def __init__(s): s.rows = []
    def add(s, *a): s.rows.append(a)
envs["202"] = {"TELEGRAM_STATE_DIR": ST}; D.running = lambda pat: list(L); r = R(); D.check_daemon(r)
chk("check_daemon: сосед + мой → «работает (pid 202)», не «запущено 2 копии»", r.rows and "pid 202" in str(r.rows[0]) and "копий" not in str(r.rows[0]), r.rows)
# канал в сессии: MCP-сервер соседнего дома (другой HOME) — не мой
me = os.path.realpath(os.path.expanduser("~"))
S = [("301", "bun /n/mila-telegram/server.ts"), ("302", "bun /m/mila-telegram/server.ts")]
homes = {"301": {"HOME": "/elsewhere/home"}, "302": {"HOME": me}}
D._proc_env = lambda pid: homes.get(pid)
D.running = lambda pat: [S[0]] if pat == "server.ts" else []
r = R(); D.check_flag(r)
chk("канал в сессии: только MCP соседнего HOME → не OK «запущен»", bool(r.rows) and r.rows[0][0] != D.OK, r.rows)
D.running = lambda pat: list(S) if pat == "server.ts" else []
r = R(); D.check_flag(r)
chk("канал в сессии: свой MCP есть → «MCP-сервер плагина запущен»", r.rows and r.rows[0][0] == D.OK, r.rows)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
