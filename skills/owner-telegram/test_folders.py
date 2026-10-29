#!/usr/bin/env python3
"""FOLDERS-1025: folders / folders-apply на заглушке клиента (настоящие типы Telethon, без сети и сессии)."""
import asyncio, glob, json, os, re, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(H, "scripts")); sys.path.insert(0, os.path.join(H, "..", "..", "tests", "fixtures"))
from fake_people import OWNER_ID
try:
    import telethon   # настоящие типы Telethon; нет библиотеки (CI без навыка) — пропуск, не ложное «зелено»
except ImportError:
    print("пропуск: нет telethon (pip install telethon) — итог 0/0"); sys.exit(0)
import owner_folders as of
from telethon.tl.types import DialogFilter, DialogFilterChatlist, TextWithEntities, InputPeerUser, InputPeerChannel, InputPeerChat
from telethon.tl.functions.messages import UpdateDialogFilterRequest, GetDialogFiltersRequest, DeleteChatUserRequest

ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)

OWNER = OWNER_ID
U1, U2 = InputPeerUser(1001, 1), InputPeerUser(1002, 2)          # личные
CH = InputPeerChannel(2001, 3); GR = InputPeerChannel(2002, 4); OLD = InputPeerChat(3001)
CHI, GRI = of._pid(CH), of._pid(GR)
NAMES = {1001: "Друг", 1002: "Коллега", CHI: "Канал новостей", GRI: "Рабочая группа", -3001: "Старый чат"}


class Dl:
    def __init__(self, p): self.input_entity, self.name = p, NAMES[of._pid(p)]


class Me:
    id, premium = OWNER, False


class Stub:
    def __init__(self, filters):
        self.filters, self.calls = list(filters), []
    async def get_me(self): return Me()
    async def get_messages(self, peer, limit=30):
        assert type(peer).__name__ == "InputPeerSelf"; return list(SAVED[:limit])
    async def iter_dialogs(self, **kw):
        for p in (U1, U2, CH, GR, OLD): yield Dl(p)
    async def __call__(self, req):
        self.calls.append(req)
        if isinstance(req, GetDialogFiltersRequest):
            return type("R", (), {"filters": self.filters})()
        if isinstance(req, UpdateDialogFilterRequest):
            self.filters = [f for f in self.filters if getattr(f, "id", None) != req.id] + [req.filter]; return True
        raise AssertionError("неожиданный запрос %s" % type(req).__name__)


def F(id, title, include=(), pinned=(), exclude=(), **kw):
    return DialogFilter(id=id, title=TextWithEntities(text=title, entities=[]), pinned_peers=list(pinned),
                        include_peers=list(include), exclude_peers=list(exclude), **kw)

def base():
    return [type("Default", (), {})(), F(2, "Работа", include=[GR], pinned=[CH], emoticon="💼"),
            DialogFilterChatlist(id=3, title=TextWithEntities(text="Общая", entities=[]), pinned_peers=[], include_peers=[CH])]

def run(coro):
    try: return asyncio.run(coro), None
    except SystemExit as e: return None, e.code

D = tempfile.mkdtemp()
import hashlib, time, datetime
SAVED = []   # «Избранное» владельца в заглушке: сюда кладётся его «да <код>»
def card_code(plan_path, st=None):
    """Код — как владелец видит его на карточке: dry-run на том же состоянии папок (FOLDERS-WAS-2710: код = план + «было»)."""
    with contextlib.redirect_stdout(io.StringIO()) as b: run(of.cmd_apply(st or Stub(base()), D, plan_path, OWNER, str(OWNER) + "/1", yes=False))
    m = re.search(r"«да ([0-9a-f]{8})»", b.getvalue()); return m.group(1) if m else "нет-кода"
def consent(msg, plan_path, by=OWNER, ts=None, what="folders-apply", st=None):
    """«да» владельца — его сообщение себе в «Избранное» (c): «да <код с карточки>»."""
    code = card_code(plan_path, st)
    SAVED.insert(0, type("M", (), {"out": by == OWNER, "message": ("да " + code) if what == "folders-apply" else "да, всё ок", "id": 900 + len(SAVED),
                                   "date": datetime.datetime.fromtimestamp(ts or time.time() + 1, datetime.timezone.utc)})())

def plan(obj):
    p = os.path.join(D, "plan.json"); json.dump(obj, open(p, "w"), ensure_ascii=False); return p

# 1. folders — чтение
st = Stub(base()); (out, bak), _ = run(of.cmd_folders(st, D))
chk("folders: две папки (по умолчанию пропущена), общая помечена", len(out) == 2 and out[1]["shared"] and not out[0]["shared"])
w = out[0]
chk("folders: название, эмодзи, закреплённый и включённый с id и названием",
    w["title"] == "Работа" and w["emoticon"] == "💼" and w["pinned"] == [{"id": CHI, "title": "Канал новостей"}] and w["include"][0]["id"] == GRI)
chk("folders: бэкап folders-<дата>.json, права 600", os.path.basename(bak).startswith("folders-") and oct(os.stat(bak).st_mode)[-3:] == "600")
chk("folders: запросов записи нет", all(isinstance(c, GetDialogFiltersRequest) for c in st.calls))

# 2. dry-run по умолчанию
st = Stub(base()); p = plan({"folders": [{"title": "Работа", "add": [1001], "pin": [GRI]}, {"title": "Семья", "emoticon": "🏠", "include": [1002]}]})
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf): r, code = run(of.cmd_apply(st, D, p, OWNER, str(OWNER) + "/77"))
txt = buf.getvalue()
chk("dry-run: дифф «было → станет» с названиями", "＋ создать «Семья» 🏠" in txt and "Друг (1001)" in txt and "📌 закреплённые +1" in txt)
chk("dry-run: без --yes ни одного UpdateDialogFilter", not any(isinstance(c, UpdateDialogFilterRequest) for c in st.calls) and code is None)

# 3. применение с --yes
bakn = len(glob.glob(os.path.join(D, "folders-*.json")))
consent(str(OWNER) + "/77", p)
with contextlib.redirect_stdout(io.StringIO()): r, code = run(of.cmd_apply(st, D, p, OWNER, str(OWNER) + "/77", yes=True, writer=of.FolderWriter(st)))
ups = [c for c in st.calls if isinstance(c, UpdateDialogFilterRequest)]
chk("apply: два запроса, новая папка id 4 (2 и 3 заняты)", len(ups) == 2 and ups[1].id == 4 and code is None)
work = next(f for f in st.filters if getattr(f, "id", None) == 2)
chk("apply: «Работа» — закреплены канал и группа, Друг включён, эмодзи сохранено",
    [of._pid(x) for x in work.pinned_peers] == [CHI, GRI] and [of._pid(x) for x in work.include_peers] == [1001] and work.emoticon == "💼")
chk("apply: общая папка не тронута", all(u.id != 3 for u in ups))
j = [json.loads(l) for l in open(os.path.join(D, "folders.jsonl"))]
chk("журнал: кто, по какому сообщению, sha плана, бэкап; без названий чатов",
    j[-1]["by"] == str(OWNER) and j[-1]["msg"] == str(OWNER) + "/77" and len(j[-1]["plan_sha256"]) == 64 and "Друг" not in json.dumps(j[-1], ensure_ascii=False))
chk("apply: бэкап до правки сделан", len(glob.glob(os.path.join(D, "folders-*.json"))) == bakn + 1)

# 4. откат из бэкапа
backup = j[-1]["backup"]; backup = os.path.join(D, backup)
consent(str(OWNER) + "/78", backup, st=st)
with contextlib.redirect_stdout(io.StringIO()): r, code = run(of.cmd_apply(st, D, backup, OWNER, str(OWNER) + "/78", yes=True, writer=of.FolderWriter(st)))
work = next(f for f in st.filters if getattr(f, "id", None) == 2)
chk("откат: «Работа» как до правки, «Семья» осталась (папки не удаляем)",
    [of._pid(x) for x in work.pinned_peers] == [CHI] and [of._pid(x) for x in work.include_peers] == [GRI]
    and any(getattr(f, "id", None) == 4 for f in st.filters) and code is None)

# 5. запреты и лимиты
def bad(planobj, by=OWNER, msg=str(OWNER) + "/9", flt=None, premium=False):
    st = Stub(flt or base()); Me.premium = premium; pp = plan(planobj); consent(msg, pp)
    with contextlib.redirect_stdout(io.StringIO()) as b: r, code = run(of.cmd_apply(st, D, pp, by, msg, yes=True, writer=of.FolderWriter(st)))
    Me.premium = False
    return code, not any(isinstance(c, UpdateDialogFilterRequest) for c in st.calls), b.getvalue()

c, none, _ = bad({"folders": [{"title": "X", "include": [1001]}]}, by=1001)
chk("чужой --by → отказ, записи нет", c and none)
c, none, _ = bad({"folders": [{"title": "X", "include": [1001]}]}, msg="да")
chk("--msg без чат/сообщение → отказ", c and none)
c, none, t = bad({"folders": [{"title": "X", "include": [999999]}]})
chk("чат не из диалогов → отказ", c == 2 and none and "нет среди диалогов" in t)
c, none, t = bad({"folders": [{"id": 3, "title": "Общая", "add": [1001]}]})
chk("общая папка → отказ", c == 2 and none and "общая" in t)
c, none, t = bad({"folders": [{"id": 3, "title": "Общая", "shared": True, "add": [1001]}]})
chk("общая с пометкой shared (из бэкапа) — пропуск, записи нет", c is None and none)
c, none, t = bad({"folders": [{"title": "Очень длинное имя", "include": [1001]}]})
chk("название > 12 → отказ", c == 2 and none)
c, none, t = bad({"folders": [{"title": "Пусто"}]})
chk("пустая папка → отказ", c == 2 and none and "пустая" in t)
many = [F(i, "П%d" % i, include=[U1]) for i in range(2, 12)]
c, none, t = bad({"folders": [{"title": "Новая", "include": [1002]}]}, flt=many)
chk("11-я папка без Premium → отказ", c == 2 and none and "> 10" in t)
c, none, t = bad({"folders": [{"title": "Новая", "include": [1002]}]}, flt=many, premium=True)
chk("11-я папка с Premium → можно", c is None and not none)
big = [F(2, "Большая", include=[InputPeerUser(5000 + i, 1) for i in range(100)])]
c, none, t = bad({"folders": [{"id": 2, "pin": [1001]}]}, flt=big)
chk("101-й чат в папке → отказ", c == 2 and none and "> 100" in t)
c, none, t = bad({"folders": [{"id": 2, "flags": {"archive_all": True}}]})
chk("неизвестный флаг → отказ", c == 2 and none)
c, none, t = bad({"folders": [{"id": 2, "add": [1001]}, {"title": "Работа", "add": [1002]}]})
chk("одна папка в плане дважды → отказ", c == 2 and none and "дважды" in t)
c, none, t = bad({"folders": [{"title": "Работа", "emoticon": "💼", "pinned": [CHI], "include": [GRI]}]})
chk("план = как есть → «менять нечего», записи нет", c is None and none and "менять нечего" in t)

# 5b. «да» — запись в журнале согласий, не вид строки (Качество, закон 4)
def apply_yes(msg, setup=None):
    st = Stub(base()); pp = plan({"folders": [{"title": "Семья", "include": [1002]}]})
    if setup: setup(pp)
    with contextlib.redirect_stdout(io.StringIO()) as b: r, code = run(of.cmd_apply(st, D, pp, OWNER, msg, yes=True, writer=of.FolderWriter(st)))
    return code, not any(isinstance(c, UpdateDialogFilterRequest) for c in st.calls), b.getvalue()
SAVED.clear(); c, none, t = apply_yes(str(OWNER) + "/9001")
chk("нет «да <код>» в «Избранном» владельца → отказ, записи нет", c == 4 and none and "нет «да" in t)
c, none, t = apply_yes(str(OWNER) + "/9002", lambda pp: consent(str(OWNER) + "/9002", pp, by=1002))
chk("«да» написал не владелец (не out) → отказ", c == 4 and none)
def other_plan(pp):
    consent(str(OWNER) + "/9003", pp); open(pp, "a").write(" ")
c, none, t = apply_yes(str(OWNER) + "/9003", other_plan)
chk("план изменён после «да» (код другой) → отказ", c == 4 and none)
c, none, t = apply_yes(str(OWNER) + "/9004", lambda pp: consent(str(OWNER) + "/9004", pp, ts=time.time() - 2 * 86400))
chk("«да» старше суток → отказ", c == 4 and none and "старое" in t)
c, none, t = apply_yes(str(OWNER) + "/9005", lambda pp: consent(str(OWNER) + "/9005", pp, what="other"))
chk("«да» на другое действие → отказ", c == 4 and none)
c, none, t = apply_yes(str(OWNER) + "/9006", lambda pp: consent(str(OWNER) + "/9006", pp))
chk("настоящее «да» на этот план → применено", c is None and not none)

# 5b2. FOLDERS-WAS-2710 (Качество): владелец поправил папку руками между карточкой и «да» — его правку не перезаписываем
def edited_state():
    return [type("Default", (), {})(), F(2, "Работа", include=[GR, U1], pinned=[CH], emoticon="💼"),
            DialogFilterChatlist(id=3, title=TextWithEntities(text="Общая", entities=[]), pinned_peers=[], include_peers=[CH])]
pp = plan({"folders": [{"id": 2, "include": [1002]}]})
consent(str(OWNER) + "/9007", pp)                       # «да» на карточку, показанную при «было» = base()
st = Stub(edited_state())                          # а владелец тем временем добавил в «Работу» ещё чат руками
with contextlib.redirect_stdout(io.StringIO()) as b: r, code = run(of.cmd_apply(st, D, pp, OWNER, str(OWNER) + "/9007", yes=True, writer=of.FolderWriter(st)))
chk("папку поправили руками после карточки → старое «да» не подходит, отказ «новую карточку», запроса нет",
    code == 4 and not any(isinstance(c, UpdateDialogFilterRequest) for c in st.calls) and "новую" in b.getvalue())
consent(str(OWNER) + "/9008", pp, st=Stub(edited_state()))   # новая карточка на новом «было» → новое «да»
st = Stub(edited_state())
with contextlib.redirect_stdout(io.StringIO()) as b: r, code = run(of.cmd_apply(st, D, pp, OWNER, str(OWNER) + "/9008", yes=True, writer=of.FolderWriter(st)))
j = [json.loads(l) for l in open(os.path.join(D, "folders.jsonl"))]
chk("новая карточка → новое «да» → применено; в журнале sha «было»", code is None and any(isinstance(c, UpdateDialogFilterRequest) for c in st.calls) and len(j[-1].get("was_sha256", "")) == 64)
chk("правка ДРУГОЙ папки (не из плана) код не меняет", card_code(pp, Stub(base())) == card_code(pp, Stub([base()[0], base()[1], DialogFilterChatlist(id=3, title=TextWithEntities(text="Общая", entities=[]), pinned_peers=[], include_peers=[CH, U1])])))

# 5c. живые папки владельца (Админ 25.10): «Избранное» = InputPeerSelf, пустой InputPeerEmpty — folders не падает
from telethon.tl.types import InputPeerSelf, InputPeerEmpty
class StubSelf(Stub):
    async def iter_dialogs(self, **kw):
        for p in (U1, U2, CH, InputPeerSelf()):
            yield type("Dl", (), {"input_entity": p, "name": "Избранное" if isinstance(p, InputPeerSelf) else NAMES[of._pid(p)]})()
st = StubSelf([F(2, "Моё", include=[InputPeerSelf(), U1, InputPeerEmpty()], pinned=[CH])])
with contextlib.redirect_stdout(io.StringIO()): (out, bak), code = run(of.cmd_folders(st, D))
f0 = out[0] if out else {}
chk("folders с «Избранным» (InputPeerSelf) и InputPeerEmpty — не падает", code is None and bool(out))
chk("«Избранное» = свой id и название, пустой пропущен", [x["id"] for x in f0.get("include", [])] == [OWNER, 1001] and f0["include"][0]["title"] == "Избранное")
st = StubSelf([F(2, "Моё", include=[InputPeerSelf(), U1], pinned=[CH])]); pp = plan({"folders": [{"id": 2, "add": [1002]}]}); consent(str(OWNER) + "/77001", pp, st=StubSelf([F(2, "Моё", include=[InputPeerSelf(), U1], pinned=[CH])]))
with contextlib.redirect_stdout(io.StringIO()): r, code = run(of.cmd_apply(st, D, pp, OWNER, str(OWNER) + "/77001", yes=True, writer=of.FolderWriter(st)))
up = [c for c in st.calls if isinstance(c, UpdateDialogFilterRequest)]
inc = up[-1].filter.include_peers if up else []
chk("правка папки с «Избранным»: оно остаётся (InputPeerSelf в запросе), новый чат 1002 добавлен", code is None and any(isinstance(x, InputPeerSelf) for x in inc) and 1002 in [of._pid(x) for x in inc])

# 6. обёртка записи
async def fw():
    w = of.FolderWriter(Stub(base())); res = []
    for req in (UpdateDialogFilterRequest(id=2), DeleteChatUserRequest(chat_id=1, user_id=U1)):
        try: await w(req); res.append(False)
        except PermissionError: res.append(True)
    try: w.iter_dialogs; res.append(False)
    except PermissionError: res.append(True)
    return res
chk("FolderWriter: удаление папки (filter=None), чужой запрос и любой метод — отказ", all(asyncio.run(fw())))

# 7. мутант: без проверки --by запись проходит чужим id
src = open(of.__file__, encoding="utf-8").read()
mut = src.replace('if not by or str(by) != str(getattr(me, "id", "")):', 'if False:')
ns = {"__name__": "mut"}; exec(compile(mut, "mut", "exec"), ns)
st = Stub(base()); pm = plan({"folders": [{"title": "X", "include": [1001]}]}); consent("1/1", pm)   # «да» владельца есть; мутант проверяет только --by
with contextlib.redirect_stdout(io.StringIO()): run(ns["cmd_apply"](st, D, pm, 1001, "1/1", yes=True, writer=ns["FolderWriter"](st)))
chk("мутант без сверки --by пишет — тест его ловит", any(isinstance(c, UpdateDialogFilterRequest) for c in st.calls))

if __name__ == "__main__":
    print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
