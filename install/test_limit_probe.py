#!/usr/bin/env python3
"""(подписку обновили в 10:30, а кормилец держал до «resets 2pm»): при лимите — откат к съеденным
ходами 429 входящим, проба раз в FEEDER_LOGIN_PROBE_S и сразу после рестарта; удачный ход раньше срока → «пропущено за простой: N»
и все по порядку. Всё во временной папке: HOME, журнал плагина, транскрипт — подменены."""
import importlib.util, json, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)
T = tempfile.mkdtemp(prefix="limit-"); os.environ["HOME"] = T
ST = os.path.join(T, ".claude", "channels", "telegram"); os.makedirs(os.path.join(ST, "inbound")); PROJ = os.path.join(T, ".claude", "projects", "w"); os.makedirs(PROJ)
CS = os.path.join(T, "state"); os.makedirs(CS)
os.environ.update(TELEGRAM_STATE_DIR=ST, COMPANION_STATE=CS, MILA_SENIOR_INBOX=os.path.join(T, "нет", "x.jsonl"), COMPANION_INSTALL_DIR=HERE, CLAUDE_CONFIG_DIR=os.path.join(T, ".claude"))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("lw", os.path.join(HERE, "limit_watch.py")); LW = importlib.util.module_from_spec(spec); spec.loader.exec_module(LW)
spec = importlib.util.spec_from_file_location("feeder", os.path.join(HERE, "companion-feeder.py")); F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
F._lw = LW; F.CLAUDE_DIR = os.path.join(T, ".claude"); fed = []; F.feed = lambda text: fed.append(text)
def fresh(): LW.hold.__defaults__[2].clear()   # кэш датчика 5 с — в тесте время идёт скачками
now = time.time(); t_ok, t_hit = now - 3600, now - 1800; resets = now + 4 * 3600
# CI 27.10: «resets 2pm» был зашит — с 14:00 до ≈14:35 по Ташкенту сброс «уже прошёл», и тест падал по часам.
# Время сброса в тексте — от resets, как пишет сама подписка: «resets 6:26pm (Asia/Tashkent)».
import datetime as _dt, zoneinfo as _zi
RESET_TXT = _dt.datetime.fromtimestamp(resets, _zi.ZoneInfo("Asia/Tashkent")).strftime("%I:%M%p").lstrip("0").lower()
def iso(t): return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))
def rec(**k): return json.dumps(k, ensure_ascii=False) + "\n"
ok_rec = lambda t: rec(type="assistant", timestamp=iso(t), message={"role": "assistant", "model": "claude-x", "content": [{"type": "text", "text": "Готово."}]})
hit_rec = lambda t: rec(type="assistant", timestamp=iso(t), error="rate_limit", apiErrorStatus=429, isApiErrorMessage=True, quotaLimits={"resetsAt": resets, "rateLimitType": "seven_day"},
                        message={"role": "assistant", "model": "<synthetic>", "content": [{"type": "text", "text": "You've hit your weekly limit · resets %s (Asia/Tashkent)" % RESET_TXT}]})
TR = os.path.join(PROJ, "s.jsonl"); open(TR, "w").write(ok_rec(t_ok) + hit_rec(t_hit) + hit_rec(t_hit + 60) + hit_rec(t_hit + 120))
EV = os.path.join(ST, "inbound", "events.jsonl")
def ev(t, mid): return json.dumps({"ts": int(t * 1000), "method": "notifications/claude/channel", "params": {"content": "текст", "meta": {"chat_id": "1", "message_id": mid, "ts": iso(t)}}}) + "\n"
lines = [ev(t_ok - 60, "m0"), ev(t_hit - 5, "m1"), ev(t_hit + 55, "m2"), ev(t_hit + 115, "m3")]
open(EV, "w").write("".join(lines)); end = os.path.getsize(EV); off_m1 = len(lines[0].encode())
open(F.SESSION_PID, "w").write("100"); fresh()
cur, held = F.limit_step(end, now=now)
chk("лимит (сброс через 4 ч) → держу, курсор назад к первому съеденному 429 входящему (m1), m0 не трогаю", held and cur == off_m1)
chk("ждут 3 входящих", F.channel_events_after(cur) == 3)
fresh(); cur2, held = F.limit_step(cur, now=now + 30)
chk("следующий шаг: держу, проба ещё рано", held and cur2 == cur and not fed)
fresh(); F.limit_step(cur, now=now + F.PROBE_S + 1)
chk("через PROBE_S — проба подписки («ответь SKIP»), не сообщение человека", fed and fed[-1] == F.LIMIT_PROBE_TEXT)
# подписку обновили: проба дала удачный ход ЗАДОЛГО до срока сброса
fed.clear(); open(F.SESSION_PID, "w").write("100"); open(TR, "a").write(ok_rec(now + 10)); fresh()
cur3, held = F.limit_step(cur, now=now + 20)
chk("удачный ход раньше «resets 2pm» → не держу, строка «Подписка снова работает. Пропущено … 3 входящих … Принято, №»", not held and len(fed) == 1 and "3 входящих" in fed[0] and "Принято, №" in fed[0])
chk("после — курсор у m1: все 3 к подаче, состояние очищено", cur3 == off_m1 and F.channel_events_after(cur3) == 3 and F._load_limit() == {})
fresh(); chk("второй раз «пропущено» не подаю", F.limit_step(cur3, now=now + 40) == (cur3, False) and len(fed) == 1)
open(TR, "w").write(ok_rec(now - 10)); fresh()
chk("лимита нет — не держу и курсор не трогаю", F.limit_step(end, now=now) == (end, False))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
