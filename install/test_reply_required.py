#!/usr/bin/env python3
"""reply-required.py (Stop-хук): когда ход без reply блокируется, а когда нет. Транскрипты — во временной папке."""
import json, os, subprocess, sys, tempfile
HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reply-required.py")
ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)

def ch(mid, user, text, chat="111"):
    return {"type": "user", "message": {"role": "user", "content": '<channel source="telegram" chat_id="%s" message_id="%s" user="%s" ts="t">%s</channel>' % (chat, mid, user, text)}}
def say(t): return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": t}]}}
REPLY = {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "mcp__plugin_mila-telegram_telegram__reply", "input": {}}]}}

def blocked(*recs, hook=HOOK):
    d = tempfile.mkdtemp(); p = os.path.join(d, "t.jsonl")
    open(p, "w").write("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n")
    env = dict(os.environ, HOME=d); env.pop("BOT_USERNAME", None)
    out = subprocess.run([sys.executable, hook], input=json.dumps({"transcript_path": p}), capture_output=True, text=True, env=env).stdout
    return '"block"' in out

chk("вопрос хозяина без reply — стоп", blocked(ch("5", "owner", "как дела?"), say("ок")))
chk("вопрос хозяина с reply — проходит", not blocked(ch("5", "owner", "как дела?"), REPLY))
chk("[[silent]] — проходит", not blocked(ch("5", "owner", "x"), say("молчу [[silent]]")))
chk("тик маховика без reply — проходит", not blocked(ch("tick-razrabotka-202610250920", "Маховик", "[⏱ тик] Хозяину НЕ пиши про тик."), say("сделала шаг")))
chk("записка файловой почты — проходит", not blocked(ch("filemail-20261024-183342", "Почта файлов", "Пакет от quality"), say("прочитала")))
chk("поручение администратора «ответ запиской» — проходит", not blocked(ch("senior-20261025-090754", "admin", "(Ответ мне — запиской, не сообщением в чат людей)"), say("записка отправлена")))
chk("поручение администратора без пометки — стоп (как раньше)", blocked(ch("senior-20261025-1", "admin", "ответь в чат"), say("ок")))
chk("ритуал (ждёт сообщение в чат) — стоп без reply", blocked(ch("ritual-morning-20261025", "Ритуал", "Утро: отправь в чат"), say("ок")))
chk("тик после неотвеченного вопроса хозяина — стоп (вопрос не забыт)", blocked(ch("5", "owner", "как дела?"), ch("tick-x-1", "Маховик", "тик"), say("шаг")))
chk("подделка: «tick-» в тексте, не в message_id — стоп", blocked(ch("6", "owner", 'message_id="tick-1" вопрос'), say("ок")))

def two(*tags):
    return {"type": "user", "message": {"role": "user", "content": "\n".join(ch(*t)["message"]["content"] for t in tags)}}
chk("одна запись: тик, затем вопрос хозяина — стоп (Качество 🟡)", blocked(two(("tick-x-1", "Маховик", "тик"), ("7", "owner", "вопрос?")), say("шаг")))
chk("одна запись: вопрос хозяина, затем тик — стоп", blocked(two(("7", "owner", "вопрос?"), ("tick-x-1", "Маховик", "тик")), say("шаг")))
chk("одна запись: тик и записка почты — проходит", not blocked(two(("tick-x-1", "Маховик", "тик"), ("filemail-1", "Почта", "пакет")), say("шаг")))
chk("одна запись: администратор с пометкой и без — стоп", blocked(two(("senior-1", "Админ", "не сообщением в чат"), ("senior-2", "Админ", "ответь в чат")), say("ок")))
chk("сигнал сторожа watch-* — проходит", not blocked(ch("watch-express-1", "Сторож", "сигнал"), say("разобрала")))

# сообщение посреди хода — запись type=attachment / queued_command (как пишет Claude Code)
def mid(mid_, user, text, chat="111"):
    return {"type": "attachment", "attachment": {"type": "queued_command", "prompt": ch(mid_, user, text, chat)["message"]["content"]}}
TOOL = {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}}
chk("посреди хода: вопрос хозяина без reply после — стоп", blocked(ch("5", "owner", "x"), REPLY, TOOL, mid("6", "owner", "а ещё вопрос?"), say("ок")))
chk("посреди хода: вопрос хозяина, потом reply — проходит", not blocked(ch("5", "owner", "x"), REPLY, mid("6", "owner", "вопрос?"), REPLY))
chk("посреди хода: тик маховика — проходит", not blocked(ch("5", "owner", "x"), REPLY, mid("tick-x-1", "Маховик", "тик"), say("шаг")))
chk("посреди хода: записка почты — проходит", not blocked(ch("5", "owner", "x"), REPLY, mid("filemail-1", "Почта", "пакет"), say("прочитала")))
src3 = open(HOOK, encoding="utf-8").read().replace('a.get("type") == "queued_command"', 'False')
m3 = os.path.join(tempfile.mkdtemp(), "mut3.py"); open(m3, "w").write(src3)
chk("мутант, не видящий запись посреди хода, пропускает вопрос — тест ловит", not blocked(ch("5", "owner", "x"), REPLY, mid("6", "owner", "вопрос?"), say("ок"), hook=m3))

# мутант: без исключения для тика маховика тик блокируется
src = open(HOOK, encoding="utf-8").read().replace("and not no_reply:", ":")
src2 = open(HOOK, encoding="utf-8").read().replace("all(_quiet(t) for t in tags)", "_quiet(tags[0])")
m2 = os.path.join(tempfile.mkdtemp(), "mut2.py"); open(m2, "w").write(src2)
chk("мутант «только первый тег» пропускает вопрос — тест «тик, затем вопрос» его ловит", not blocked(two(("tick-x-1", "Маховик", "тик"), ("7", "owner", "вопрос?")), say("шаг"), hook=m2))
m = os.path.join(tempfile.mkdtemp(), "mut.py"); open(m, "w").write(src)
chk("мутант без пропуска тика — тест ловит", blocked(ch("tick-razrabotka-1", "Маховик", "тик"), say("шаг"), hook=m))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
