#!/usr/bin/env python3
"""LOGIN-2610 (ROLLOUT №41 «без повисших задач»): потерян вход («Not logged in») — входящие не теряются.
Искусственный простой: 3 входящих съедены ходами «Not logged in» → кормилец возвращает курсор к ним, держит, шлёт пробу,
🔴 строку старшей (один раз); вход вернулся → строка «пропущено за простой: 3» и все 3 снова к подаче.
Форма записи — улика одной Милы 28.09 (type=assistant, isApiErrorMessage=true, error=authentication_failed, model=<synthetic>).
Всё во временной папке: HOME, журнал плагина, транскрипт, труба — подменены."""
import importlib.util, json, os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "fixtures")); import fake_people as FP
HERE = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)
T = tempfile.mkdtemp(prefix="login-"); os.environ["HOME"] = T
ST = os.path.join(T, ".claude", "channels", "telegram"); os.makedirs(os.path.join(ST, "inbound")); PROJ = os.path.join(T, ".claude", "projects", "w"); os.makedirs(PROJ)
CS = os.path.join(T, "state"); os.makedirs(CS); os.makedirs(os.path.join(T, "work", "inbox"))
os.environ.update(TELEGRAM_STATE_DIR=ST, COMPANION_STATE=CS, MILA_SENIOR_INBOX=os.path.join(T, "work", "inbox", "to-admin.jsonl"), COMPANION_INSTALL_DIR=HERE, CLAUDE_CONFIG_DIR=os.path.join(T, ".claude"))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("lw", os.path.join(HERE, "limit_watch.py")); LW = importlib.util.module_from_spec(spec); spec.loader.exec_module(LW)
spec = importlib.util.spec_from_file_location("feeder", os.path.join(HERE, "companion-feeder.py")); F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
F._lw = LW; fed = []; F.feed = lambda text: fed.append(text)
now = time.time(); t_ok, t_down = now - 3600, now - 1800
TR = os.path.join(PROJ, "s.jsonl")
def iso(t): return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))
def rec(**k): return json.dumps(k, ensure_ascii=False) + "\n"
ok_rec = lambda t: rec(type="assistant", timestamp=iso(t), message={"role": "assistant", "model": "claude-x", "content": [{"type": "text", "text": "Готово."}]})
auth_rec = lambda t: rec(type="assistant", timestamp=iso(t), isApiErrorMessage=True, error="authentication_failed", apiErrorStatus=None,
                         message={"role": "assistant", "model": "<synthetic>", "content": [{"type": "text", "text": "Not logged in · Please run /login"}]})
user_rec = lambda t: rec(type="user", timestamp=iso(t), message={"role": "user", "content": "<channel …>"})
open(TR, "w").write(ok_rec(t_ok) + user_rec(t_down) + auth_rec(t_down + 1) + user_rec(t_down + 60) + auth_rec(t_down + 61) + user_rec(t_down + 120) + auth_rec(t_down + 121))
EV = os.path.join(ST, "inbound", "events.jsonl")
def ev(t, mid, uid=str(FP.USER_ID)): return json.dumps({"ts": int(t * 1000), "method": "notifications/claude/channel", "params": {"content": "текст", "meta": {"chat_id": "1", "message_id": mid, "user_id": uid, "ts": iso(t)}}}) + "\n"
lines = [ev(t_ok - 60, "m0"), ev(t_down - 5, "m1"), ev(t_down + 55, "m2"), ev(t_down + 115, "m3")]
open(EV, "w").write("".join(lines)); end = os.path.getsize(EV); off_m1 = len(lines[0].encode())
# 1) датчик
au = LW.detect_auth(os.path.join(T, ".claude"), now=now)
chk("улика: «Not logged in» после удачного хода → вход потерян, начало простоя — первая такая запись, 3 хода", au["down"] and abs(au["since"] - (t_down + 1)) < 2 and au["count"] == 3)
open(os.path.join(PROJ, "old.jsonl"), "w").write(rec(type="assistant", timestamp=iso(t_ok - 100), error="rate_limit", apiErrorStatus=429, message={"role": "assistant", "content": [{"type": "text", "text": "You've hit your session limit · resets 2:10pm (Asia/Tashkent)"}]}))
det = LW.detect(os.path.join(T, ".claude"), now=now)
chk("лимит 429 по-прежнему видится датчиком лимита (вход его не путает)", det["hit"] and det["hit"]["kind"] and det["recovered_at"])
# 2) кормилец: первое обнаружение
open(F.SESSION_PID, "w").write("100")
cur, held = F.login_step(end, now=now)
chk("простой обнаружен → курсор назад к первому входящему простоя (m1), раньше не трогаю (m0)", held and cur == off_m1 and int(open(F.CUR).read()) == off_m1)
chk("ждут 3 входящих (m1–m3)", F.channel_events_after(cur) == 3)
al = [json.loads(l) for l in open(os.environ["MILA_SENIOR_INBOX"])]
chk("🔴 строка старшей: «Вход потерян … ждут 3 … Нужен /login»", len(al) == 1 and al[0]["kind"] == "alert" and "ждут 3" in al[0]["text"] and "/login" in al[0]["text"])
cur2, held = F.login_step(cur, now=now + 30)
chk("следующий шаг: держу, курсор не двигаю, повторной 🔴 нет, проба ещё рано", held and cur2 == cur and len(open(os.environ["MILA_SENIOR_INBOX"]).readlines()) == 1 and not fed)
cur2, held = F.login_step(cur, now=now + F.PROBE_S + 1)
chk("через PROBE_S — проба входа («ответь SKIP»), не сообщение человека", fed and fed[-1] == F.PROBE_TEXT)
fed.clear(); open(F.SESSION_PID, "w").write("200"); F.login_step(cur, now=now + F.PROBE_S + 5)
chk("сессию перезапустили (новый pid) — проба сразу, не ждёт 10 мин", fed == [F.PROBE_TEXT])
# 3) вход вернулся: удачный ход после простоя
fed.clear(); open(TR, "a").write(ok_rec(now + 10))
cur3, held = F.login_step(cur, now=now + 20)
chk("вход вернулся → строка «пропущено за простой … 3 входящих … квитанция», держать перестала", not held and len(fed) == 1 and "3 входящих" in fed[0] and "Принято, №" in fed[0])
chk("после — курсор у m1: все 3 входящих снова к подаче (будет 3 квитанции)", cur3 == off_m1 and F.channel_events_after(cur3) == 3)
chk("состояние простоя очищено — второй раз «пропущено» не подаю", F._load_login() == {} and F.login_step(cur3, now=now + 30) == (cur3, False) and len(fed) == 1)
# 4) края
open(TR, "w").write(ok_rec(now - 10)); open(os.path.join(PROJ, "old.jsonl"), "w").write("")
chk("входа никто не терял — кормилец не держит и курсор не трогает", F.login_step(end, now=now) == (end, False))
os.environ["MILA_SENIOR_INBOX"] = os.path.join(T, "нет", "to-admin.jsonl"); F.SENIOR_INBOX = os.environ["MILA_SENIOR_INBOX"]
chk("нет ящика старшей — 🔴 только в журнал кормильца, не падаю", F.alert_senior({"since": now}, 2) is False)
# Качество 26.10: откат не раньше последнего удачного хода — на что ответ уже ушёл, второй раз не подаю
sn = now - 600; open(EV, "w").write(ev(sn - 100, "a1") + ev(sn + 10, "a2")); first = len(ev(sn - 100, "a1").encode())
chk("откат: входящее до последнего удачного хода (в запасе 3 мин) не подаю повторно, после — подаю", F.rewind_to(os.path.getsize(EV), sn, last_ok=sn - 50) == first)
chk("без удачного хода рядом — запас 3 мин берёт и его", F.rewind_to(os.path.getsize(EV), sn, last_ok=sn - 3600) == 0)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
