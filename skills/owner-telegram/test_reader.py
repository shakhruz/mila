#!/usr/bin/env python3
"""owner-telegram reader.py без сети (поддельный telethon): отправка запрещена; черновик и реакция — только в разрешённом
личном чате и по слову владельца; реакция — белый список; draft-clear стирает только мой черновик. Запуск: python3 test_reader.py"""
import asyncio, json, os, sys, tempfile, types
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(H, "..", "..", "tests", "fixtures"))
from fake_people import OWNER_ID, USER_ID, PEOPLE
class SaveDraftRequest:
    def __init__(s, peer, message): s.peer, s.message = peer, message
class SendReactionRequest:
    def __init__(s, peer, msg_id, reaction): s.peer, s.msg_id, s.reaction = peer, msg_id, reaction
class ReactionEmoji:
    def __init__(s, emoticon): s.emoticon = emoticon
class SendMessageRequest:
    def __init__(s, **k): pass
fm = types.ModuleType("telethon.tl.functions.messages"); fm.SaveDraftRequest = SaveDraftRequest; fm.SendReactionRequest = SendReactionRequest
tt = types.ModuleType("telethon.tl.types"); tt.ReactionEmoji = ReactionEmoji
for k, m in (("telethon", types.ModuleType("telethon")), ("telethon.tl", types.ModuleType("telethon.tl")), ("telethon.tl.functions", types.ModuleType("telethon.tl.functions")),
             ("telethon.tl.functions.messages", fm), ("telethon.tl.types", tt)): sys.modules[k] = m
sys.path.insert(0, os.path.join(H, "scripts")); import reader as r
class User:
    def __init__(s, id, first): s.id, s.first_name, s.last_name = id, first, None
class Channel:
    def __init__(s, id, title): s.id, s.title = id, title
IVAN, MARIA, NEWS, OWNER = User(USER_ID, PEOPLE[0]), User(USER_ID + 1, PEOPLE[1]), Channel(900, "Новости"), User(OWNER_ID, "Владелец")
DRAFTS = {}
class DL:
    def __init__(s, e): s.entity, s.id = e, e.id; s.name = getattr(e, "first_name", None) or e.title
    @property
    def draft(s): return types.SimpleNamespace(text=DRAFTS[s.id]) if DRAFTS.get(s.id) else None
class Fake:
    def __init__(s): s.calls = []
    async def get_entity(s, x): return {USER_ID: IVAN, USER_ID + 1: MARIA, 900: NEWS}[int(x)]
    async def iter_dialogs(s, limit=0):
        for e in (IVAN, MARIA, NEWS): yield DL(e)
    async def get_me(s): return OWNER
    async def __call__(s, req):
        s.calls.append(req)
        if isinstance(req, SaveDraftRequest): DRAFTS[req.peer.id] = req.message
        return True
os.umask(0o022)   # проверка 600 не должна держаться на umask окружения
f = Fake(); c = r.ReadOnly(f); D = tempfile.mkdtemp(); O, REF = str(OWNER_ID), "%d/101" % OWNER_ID
ok = tot = 0
def check(n, cond, x=""):
    global ok, tot; tot += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + n + ("" if cond else "  ← " + str(x)[:300]))
def run(coro):
    try: asyncio.run(coro); return None
    except SystemExit as e: return str(e)
def last_call(): return f.calls[-1] if f.calls else None
def jl(): return [json.loads(l) for l in open(os.path.join(D, "drafts.jsonl"))]
try: c.send_message; sent = True
except PermissionError: sent = False
check("отправка (send_message) запрещена обёрткой", not sent)
try: asyncio.run(c(SendMessageRequest())); req_ok = True
except PermissionError: req_ok = False
check("SendMessageRequest запрещён, SendReactionRequest и SaveDraftRequest — в белом списке", not req_ok and {"SendReactionRequest", "SaveDraftRequest"} <= r.ReadOnly.ALLOWED_REQUESTS)
# реакция
e = run(r.cmd_react(c, D, str(USER_ID), 55, "👍", O, REF))
check("реакция в личку, которой нет в allowed.json — отказ, ни одного вызова", e and "разрешил владелец" in e and not f.calls, e)
run(r.cmd_allow(c, D, str(USER_ID), O, REF))
e = run(r.cmd_react(c, D, str(USER_ID), 55, "💩", O, REF))
check("эмодзи не из белого списка — отказ", e and "белого списка" in e and not f.calls, e)
e = run(r.cmd_react(c, D, str(USER_ID), 55, "👍", str(USER_ID), REF))
check("--by не владелец — отказ", e and "слову владельца" in e and not f.calls, e)
e = run(r.cmd_react(c, D, str(USER_ID), 55, "👍", O, ""))
check("без улики --msg — отказ", e and "слову владельца" in e and not f.calls, e)
e = run(r.cmd_react(c, D, str(USER_ID), None, "👍", O, REF))
check("без id сообщения — отказ (не реагирую на «20-е» по умолчанию)", e and "id сообщения" in e and not f.calls, e)
e = run(r.cmd_react(c, D, str(USER_ID), 55, "❤️", O, REF))
lc = last_call()
check("разрешённый чат, слово владельца, ❤️ → SendReactionRequest с ❤ (без U+FE0F) на сообщение 55", e is None and isinstance(lc, SendReactionRequest) and lc.peer is IVAN and lc.msg_id == 55 and lc.reaction[0].emoticon == "❤", (e, vars(lc) if lc else None))
j = jl()[-1]
check("реакция в журнале: kind, чат, сообщение, by, ref; файл 600", j.get("kind") == "react" and j.get("chat_id") == USER_ID and j.get("msg") == 55 and j.get("by") == O and j.get("ref") == REF and oct(os.stat(os.path.join(D, "drafts.jsonl")).st_mode & 0o777) == "0o600", j)
n0 = len(f.calls); e = run(r.cmd_react(c, D, "900", 7, "👍", O, REF))
check("канал/группа — отказ: лайк там видят все", e and "только в личном" in e and len(f.calls) == n0, e)
# черновик и очистка
e = run(r.cmd_draft(c, D, str(USER_ID), "Иван, спасибо, договорились"))
j = jl()[-1]
check("черновик: журнал без текста, с хешем для очистки", e is None and "text" not in j and j.get("h") == r.text_hash("Иван, спасибо, договорились") and "договорились" not in json.dumps(j, ensure_ascii=False), j)
e = run(r.cmd_draft_clear(c, D, str(USER_ID), str(USER_ID), REF))
check("draft-clear не владельцем — отказ, черновик на месте", e and "слову владельца" in e and DRAFTS.get(USER_ID), e)
e = run(r.cmd_draft_clear(c, D, str(USER_ID), O, REF))
check("draft-clear моего черновика по слову владельца → пусто, строка в журнале", e is None and DRAFTS.get(USER_ID) == "" and jl()[-1].get("kind") == "draft-clear", (e, DRAFTS))
DRAFTS[USER_ID] = "Иван, а вот это я сам пишу"
e = run(r.cmd_draft_clear(c, D, str(USER_ID), O, REF))
check("черновик набрал владелец — не стираю без --replace", e and "не стираю" in e and DRAFTS[USER_ID] == "Иван, а вот это я сам пишу", e)
run(r.cmd_draft(c, D, str(USER_ID), "Иван, жду вас", replace=True)); DRAFTS[USER_ID] = "Иван, жду вас завтра"
e = run(r.cmd_draft_clear(c, D, str(USER_ID), O, REF))
check("мой черновик владелец дописал — уже его, не стираю", e and "не стираю" in e and DRAFTS[USER_ID] == "Иван, жду вас завтра", e)
e = run(r.cmd_draft_clear(c, D, str(USER_ID), O, REF, replace=True))
check("--replace после его «да» — стираю, в журнале replace", e is None and DRAFTS[USER_ID] == "" and jl()[-1].get("replace") is True, e)
n1 = len(f.calls); e = run(r.cmd_draft_clear(c, D, str(USER_ID), O, REF))
check("черновика нет — ни одного вызова", e is None and len(f.calls) == n1, e)
e = run(r.cmd_draft_clear(c, D, str(USER_ID + 1), O, REF))
check("draft-clear в личку не из allowed.json — отказ", e and "разрешил владелец" in e, e)
print("итог %d/%d" % (ok, tot)); sys.exit(0 if ok == tot else 1)
