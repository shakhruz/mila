#!/usr/bin/env python3
"""Личный Telegram владельца — ТОЛЬКО ЧТЕНИЕ.

Клиент Telegram доступен только через обёртку ReadOnly: в ней белый список методов
получения диалогов и сообщений. Любой другой метод — отказ (PermissionError).

  reader.py map            — карта: каналы и группы (без личных переписок), непрочитанное → map.json
  reader.py pulse          — пульс: число контактов и личных диалогов, каналы/группы со звуком → live.json
  reader.py last <чат> [N]            — последние N (≤50) сообщений; личный чат — только из списка allowed.json
  reader.py last <чат> N --topic <id>  — последние N сообщений темы форума (супергруппа с темами)
  reader.py topics <чат>               — темы форума: id, название, непрочитано
  reader.py channels-digest <часы>     — посты всех каналов из map.json за N часов (≤72): канал, id, дата, текст ≤500, просмотры,
                           реакции — для ежедневной подборки владельцу; map.json — от reader.py map
  reader.py media <чат> <id>           — скачать вложение (голосовое, кружок, аудио, видео, фото, файл) в media/ — путь для расшифровки
  reader.py get <чат> <id> [N]        — сообщение с этим номером и по N (≤25) до и после него — старое задание в группе,
                           которого уже нет среди последних; личный чат — только из allowed.json; в drafts.jsonl — строка без текста
  reader.py draft <чат> --text «…» [--replace] — ЧЕРНОВИК в поле ввода чата владельца: не отправляется,
                           отправляет сам владелец; личный чат — только из allowed.json; свой черновик владельца в чате
                           не затираю без --replace (его «да» на замену). Журнал drafts.jsonl (без текста).
  reader.py allow <чат> --by <user_id> --msg <чат/сообщение> — добавить личный чат в allowed.json: --by должен быть
                           id самого владельца (сверка с аккаунтом сессии), --msg — его нажатие «да» (улика).
  reader.py disallow <чат> — убрать из списка.
  reader.py inbox --by <id владельца> --msg <его слово> — личные чаты с непрочитанным (прочитанным не помечает).
  reader.py react <чат> <id сообщения> --emoji 👍 --by <id владельца> --msg <бот Милы>/<id его сообщения> — реакция от владельца
: белый список эмодзи, только разрешённый личный чат, строка в drafts.jsonl.
  reader.py draft-clear <чат> --by <id владельца> --msg <его слово> — стереть МОЙ черновик; черновик, набранный
                           владельцем, не трогаю без --replace.
  <чат> — id, @ник или часть названия/имени (одно совпадение среди диалогов).
  allowed.json (папка сессии, 600) — личные чаты, которые владелец разрешил (Мила Сила 15.10: имена — не в SKILL, а здесь;
              флаг, который ставит сама Мила, разрешением не считается).

Папка сессии: --dir, иначе env OWNER_TG_DIR, иначе ~/work/secrets/owner-tg.
Ключи приложения: env TG_API_ID / TG_API_HASH, иначе <dir>/api.env.
Итоговые файлы — в папке сессии, права 600.
"""
import argparse, asyncio, hashlib, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import owner_folders   # папки — чтение и применение плана (запись — только FolderWriter)

DEVICE = dict(device_model="Mila reader", system_version="read-only", app_version="1.0")


def session_dir(arg=None):
    d = arg or os.environ.get("OWNER_TG_DIR") or os.path.expanduser("~/work/secrets/owner-tg")
    if not os.path.isdir(d):
        sys.exit("нет папки сессии: сначала вход владельца (сессию заводит администратор)")
    return d


def api_keys(d):
    api_id, api_hash = os.environ.get("TG_API_ID"), os.environ.get("TG_API_HASH")
    if not (api_id and api_hash):
        p = os.path.join(d, "api.env")
        env = dict(l.strip().split("=", 1) for l in open(p) if "=" in l) if os.path.exists(p) else {}
        api_id, api_hash = env.get("TG_API_ID"), env.get("TG_API_HASH")
    if not (api_id and api_hash):
        sys.exit("нет ключей TG_API_ID/TG_API_HASH")
    return int(api_id), api_hash


class ReadOnly:
    """Белая обёртка: наружу только чтение диалогов, сообщений и списка контактов."""
    ALLOWED = {"connect", "disconnect", "is_user_authorized", "get_me",
               "iter_dialogs", "get_dialogs", "iter_messages", "get_messages", "get_entity", "download_media"}   # скачать голосовое — тоже чтение
    ALLOWED_REQUESTS = {"GetContactsRequest", "SaveDraftRequest", "GetDialogFiltersRequest", "SendReactionRequest", "GetForumTopicsRequest"}   # темы форума — чтение   # чтение папок   # черновик — да; отправка/правка/удаление — нет

    def __init__(self, client):
        object.__setattr__(self, "_c", client)

    def __getattr__(self, name):
        if name not in ReadOnly.ALLOWED:
            raise PermissionError(f"только чтение: метод {name} запрещён")
        return getattr(object.__getattribute__(self, "_c"), name)

    def __setattr__(self, name, value):
        raise PermissionError("только чтение")

    async def __call__(self, request):
        if type(request).__name__ not in ReadOnly.ALLOWED_REQUESTS:
            raise PermissionError(f"только чтение: запрос {type(request).__name__} запрещён")
        return await object.__getattribute__(self, "_c")(request)


def kind(d):
    return "channel" if d.is_channel and not d.is_group else "group"


def save(d, name, data):
    p = os.path.join(d, name)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.chmod(p, 0o600)


async def cmd_map(c, d):
    out = []
    async for dl in c.iter_dialogs(limit=None):
        if dl.is_user:
            continue  # личные переписки не трогаем
        e = dl.entity
        out.append({"id": dl.id, "title": dl.title, "kind": kind(dl),
                    "username": getattr(e, "username", None), "unread": dl.unread_count,
                    "members": getattr(e, "participants_count", None), "archived": dl.archived,
                    "last": dl.date.isoformat() if dl.date else None})
        await asyncio.sleep(0.05)
    save(d, "map.json", out)
    ch = [x for x in out if x["kind"] == "channel"]
    gr = [x for x in out if x["kind"] == "group"]
    print("channels", len(ch), "groups", len(gr), "unread_total", sum(x["unread"] or 0 for x in out))


async def cmd_pulse(c, d):
    from telethon.tl.functions.contacts import GetContactsRequest
    cts = await c(GetContactsRequest(hash=0))
    live, users = [], 0
    async for dl in c.iter_dialogs(limit=None):
        if dl.is_user:
            users += 1
            continue  # из личных — только счёт, без имён и текста
        ns = getattr(dl.dialog, "notify_settings", None)
        mu = getattr(ns, "mute_until", None) if ns else None
        muted = bool(mu and mu.timestamp() > time.time())
        if not muted and not dl.archived:
            live.append({"id": dl.id, "title": dl.title, "kind": kind(dl), "unread": dl.unread_count})
    save(d, "live.json", live)
    print("contacts", len(cts.users), "private_dialogs", users, "live_groups_channels", len(live),
          "live_unread", sum(x["unread"] or 0 for x in live))


async def resolve(c, chat):
    """id, @ник или часть названия/имени — одно совпадение среди диалогов, иначе отказ с вариантами."""
    chat = str(chat).strip()
    if chat.lstrip("-").isdigit():
        return await c.get_entity(int(chat))
    if chat.startswith("@"):
        return await c.get_entity(chat)
    q = chat.lower(); hits = []
    async for dl in c.iter_dialogs(limit=500):
        if q in (dl.name or "").lower():
            hits.append(dl)
    if len(hits) == 1:
        return hits[0].entity
    if not hits:
        sys.exit("чат «%s» не найден среди диалогов" % chat)
    sys.exit("несколько совпадений «%s»: %s — уточните id или @ник" % (chat, "; ".join("%s (%s)" % (h.name, h.id) for h in hits[:8])))


def allowed_list(d):
    try:
        return json.load(open(os.path.join(d, "allowed.json"), encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


async def owner_word(c, by, ref, what):
    """Слово владельца на действие: --by — id самого владельца (сверка с аккаунтом сессии), --msg — улика его «да»."""
    me = await c.get_me()
    if not by or str(by) != str(getattr(me, "id", "")) or not (ref or "").strip():
        sys.exit("%s только с согласия владельца: --by <его id> --msg <чат/сообщение>" % what)


WORD_TTL = int(os.environ.get("OWNER_TG_WORD_MIN") or 30) * 60   # согласие владельца на действие — не старше 30 мин


def mila_bot(d):
    """Бот Милы, в личке с которым владелец даёт слово: env MILA_BOT (id или @ник), иначе <dir>/mila_bot (одна строка)."""
    v = (os.environ.get("MILA_BOT") or "").strip()
    if not v:
        try: v = open(os.path.join(d, "mila_bot"), encoding="utf-8").read().strip()
        except OSError: v = ""
    return int(v) if re.fullmatch(r"-?\d+", v) else v


def ref_used(d, key):
    try:
        for l in open(os.path.join(d, "drafts.jsonl"), encoding="utf-8"):
            try: r = json.loads(l)
            except ValueError: continue
            if isinstance(r, dict) and r.get("kind") in ("react", "draft-clear") and r.get("ref") == key:
                return True
    except OSError:
        pass
    return False


async def owner_said(c, d, by, ref, what, reply=False):
    """--by и --msg передаёт сама Мила — строка «--msg что угодно» не слово.
    --msg = <бот Милы>/<id сообщения> — сообщение в личке владельца с его Милой. Читаю его с аккаунта владельца и проверяю:
    чат — тот самый бот Милы, автор — владелец (out), не старше WORD_TTL, это сообщение ещё не использовано. → ключ «<id бота>/<id>»."""
    await owner_word(c, by, ref, what)
    m = re.fullmatch(r"(@?\w{1,64}|-?\d+)/(\d+)", (ref or "").strip())
    bot = mila_bot(d)
    if not m or not bot:
        sys.exit("%s: --msg <бот Милы>/<id его сообщения>; бот Милы — env MILA_BOT или файл mila_bot в папке сессии" % what)
    try:
        ent = await c.get_entity(int(m.group(1)) if re.fullmatch(r"-?\d+", m.group(1)) else m.group(1))
        want = await c.get_entity(bot)
    except (ValueError, KeyError, TypeError):   # чат или бот не нашёлся в аккаунте владельца
        sys.exit("%s: согласие владельца — только в его личке с ботом Милы" % what)
    if not getattr(ent, "bot", False) or getattr(ent, "id", None) != getattr(want, "id", None):
        sys.exit("%s: согласие владельца — только в его личке с ботом Милы" % what)
    try:
        msg = await c.get_messages(ent, ids=int(m.group(2)))
    except (ValueError, KeyError, TypeError):
        msg = None
    if isinstance(msg, list): msg = msg[0] if msg else None
    if not msg or not getattr(msg, "out", False):
        sys.exit("%s: такого сообщения владельца в личке с Милой нет" % what)
    ts = msg.date.timestamp() if getattr(msg, "date", None) else 0
    if not (time.time() - WORD_TTL <= ts <= time.time() + 60):
        sys.exit("%s: согласие владельца старше %d мин — нужно новое" % (what, WORD_TTL // 60))
    if reply:   # необратимое (стереть набранное им) — смысл проверяет код: его сообщение — ОТВЕТ на предложение Милы
        rid = getattr(getattr(msg, "reply_to", None), "reply_to_msg_id", None) or getattr(msg, "reply_to_msg_id", None)
        try:
            prev = await c.get_messages(ent, ids=int(rid)) if rid else None
        except (ValueError, KeyError, TypeError):
            prev = None
        if isinstance(prev, list): prev = prev[0] if prev else None
        if not prev or getattr(prev, "out", True):
            sys.exit("%s: стереть набранное владельцем — только если его сообщение — ответ на моё предложение в личке с Милой" % what)
    key = "%s/%s" % (ent.id, m.group(2))
    if ref_used(d, key):
        sys.exit("%s: это согласие владельца уже использовано — одно слово, одно действие" % what)
    return key


def journal(d, rec):
    p = os.path.join(d, "drafts.jsonl")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(json.dumps(dict({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, **rec), ensure_ascii=False) + "\n")


def text_hash(s):
    return hashlib.sha256((s or "").strip().encode("utf-8")).hexdigest()[:16]


def private_guard(d, ent, what):
    if type(ent).__name__ == "User" and str(getattr(ent, "id", "")) not in allowed_list(d):
        sys.exit("личный чат: %s только для чатов, которые разрешил владелец (allowed.json; добавить — reader.py allow после его «да»)" % what)


async def cmd_allow(c, d, chat, by, msg):
    me = await c.get_me()
    if not by or str(by) != str(getattr(me, "id", "")):
        sys.exit("разрешение даёт только владелец: --by <его id>, нажатие с его аккаунта")
    if not (msg or "").strip():
        sys.exit("нужна улика «да»: --msg <чат/сообщение> с его нажатием")
    ent = await resolve(c, chat)
    name = " ".join(x for x in (getattr(ent, "first_name", None), getattr(ent, "last_name", None)) if x) or getattr(ent, "title", "") or str(ent.id)
    lst = allowed_list(d); lst[str(ent.id)] = {"name": name, "by": str(by), "msg": msg.strip(), "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    save(d, "allowed.json", lst)
    print("ALLOWED", name, ent.id)


async def cmd_disallow(c, d, chat):
    ent = await resolve(c, chat)
    lst = allowed_list(d); gone = lst.pop(str(ent.id), None); save(d, "allowed.json", lst)
    print("DISALLOWED" if gone else "NOT IN LIST", ent.id)


async def own_draft(c, ent):
    """Черновик, который владелец уже набрал в этом чате (Dialog.draft), — чтобы не затереть его."""
    async for dl in c.iter_dialogs(limit=500):
        if getattr(dl.entity, "id", None) == getattr(ent, "id", None):
            dr = getattr(dl, "draft", None)
            return (getattr(dr, "text", "") or "").strip() if dr else ""
    return ""


def media_kind(m):
    """что вложено — voice/round/audio/video/photo/sticker/poll/doc (+секунды), чтобы видеть голосовые и кругляшки в last."""
    if getattr(m, "voice", None): k = "voice"
    elif getattr(m, "video_note", None): k = "round"
    elif getattr(m, "sticker", None): k = "sticker"
    elif getattr(m, "poll", None): k = "poll"
    elif getattr(m, "audio", None): k = "audio"
    elif getattr(m, "video", None): k = "video"
    elif getattr(m, "photo", None): k = "photo"
    elif getattr(m, "document", None): k = "doc"
    else: return None
    dur = getattr(getattr(m, "file", None), "duration", None)
    return k + (":%ds" % int(dur) if dur else "")


async def cmd_voice(c, d, chat, msg_id):
    """скачать голосовое/кружок/аудио одного сообщения разрешённого чата в media/ (0700) и напечатать путь."""
    ent = await resolve(c, chat)
    private_guard(d, ent, "слушаю")
    m = await c.get_messages(ent, ids=int(msg_id))
    mk = media_kind(m) if m else None
    if not mk or mk.split(":")[0] not in ("voice", "round", "audio", "video", "doc", "photo"):   # файлы (шаблоны), фото — тоже чтение
        sys.exit("в сообщении %s нет голосового/аудио" % msg_id)
    md = os.path.join(d, "media")
    os.makedirs(md, mode=0o700, exist_ok=True)
    path = await c.download_media(m, file=os.path.join(md, "%s-%s" % (getattr(ent, "id", "x"), msg_id)))
    os.chmod(path, 0o600)
    print("VOICE", path)



async def cmd_inbox(c, d, by, msg, n=15):
    """(«веди людей, которые пишут мне в личку»): личные чаты с непрочитанными — кто, сколько, последнее входящее. Только по его «да» (--by/--msg), прочитанным не помечает."""
    me = await c.get_me()
    if not by or str(by) != str(getattr(me, "id", "")) or not (msg or "").strip():
        sys.exit("inbox только с согласия владельца: --by <его id> --msg <чат/сообщение>")
    k = 0
    async for dl in c.iter_dialogs(limit=200):
        if not dl.is_user or not dl.unread_count or getattr(dl.entity, "bot", False):
            continue
        last = dl.message
        txt = (getattr(last, "message", "") or "")[:300] if last and not getattr(last, "out", False) else ""
        print(json.dumps({"id": dl.id, "name": dl.name, "unread": dl.unread_count,
                          "date": last.date.isoformat() if last and last.date else None, "last_in": txt,
                          "allowed": str(dl.id) in allowed_list(d)}, ensure_ascii=False))
        k += 1
        if k >= n:
            break

def _peer_id(p):
    return getattr(p, "user_id", None) or getattr(p, "channel_id", None) or getattr(p, "chat_id", None)


def row(m):
    """Строка сообщения: текст (у вложения — подпись), вложение (вид, файл, размер), реакции, ответ на, переслано от."""
    d = {"id": m.id, "date": m.date.isoformat() if getattr(m, "date", None) else None, "from": getattr(m, "sender_id", None),
         "out": bool(getattr(m, "out", False)), "text": (getattr(m, "message", None) or "")[:2000], "media": media_kind(m)}
    f = getattr(m, "file", None)
    if d["media"] and f is not None and (getattr(f, "name", None) or getattr(f, "size", None)):
        d["file"] = {"name": getattr(f, "name", None), "size": getattr(f, "size", None)}
    poll = getattr(getattr(m, "poll", None), "poll", None)
    if poll is not None:
        q = getattr(poll, "question", "")
        d["poll"] = getattr(q, "text", q) if not isinstance(q, str) else q
    res = getattr(getattr(m, "reactions", None), "results", None) or []
    reac = [{"emoji": getattr(r.reaction, "emoticon", None) or "custom", "count": r.count} for r in res if getattr(r, "reaction", None) is not None]
    if reac:
        d["reactions"] = reac
    rt = getattr(m, "reply_to", None)
    if rt is not None and getattr(rt, "reply_to_msg_id", None):
        d["reply_to"] = rt.reply_to_msg_id
        if getattr(rt, "forum_topic", False):
            d["topic"] = getattr(rt, "reply_to_top_id", None) or rt.reply_to_msg_id
    fw = getattr(m, "fwd_from", None)
    if fw is not None:
        d["forward_from"] = getattr(fw, "from_name", None) or _peer_id(getattr(fw, "from_id", None))
    return json.dumps(d, ensure_ascii=False)


async def cmd_last(c, d, chat, n, topic=None):
    n = max(1, min(n, 50))
    ent = await resolve(c, chat)
    private_guard(d, ent, "читаю")
    kw = {"reply_to": int(topic)} if topic else {}   # тема форума: сообщения внутри темы
    for m in reversed(await c.get_messages(ent, limit=n, **kw)):
        print(row(m))


async def cmd_digest(c, d, hours):
    """Посты каналов из map.json за последние hours часов, по одному JSON на пост; каналы без постов — молча."""
    import datetime as _dt
    hours = max(1, min(int(hours), 72))
    try:
        rows = json.load(open(os.path.join(d, "map.json"), encoding="utf-8"))
    except (OSError, ValueError):
        sys.exit("нет map.json — сначала reader.py map")
    since = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=hours)
    n = 0
    for ch in [r for r in rows if isinstance(r, dict) and r.get("kind") == "channel"]:
        try:
            ent = await c.get_entity(int(ch["id"]))
        except Exception:
            continue
        for m in await c.get_messages(ent, limit=30):
            if not getattr(m, "date", None) or m.date < since:
                break
            reac = [{"emoji": getattr(r.reaction, "emoticon", None) or "custom", "count": r.count}
                    for r in (getattr(getattr(m, "reactions", None), "results", None) or []) if getattr(r, "reaction", None) is not None]
            print(json.dumps({"channel": ch.get("title"), "channel_id": ch["id"], "username": ch.get("username"), "id": m.id,
                              "date": m.date.isoformat(), "text": (getattr(m, "message", None) or "")[:500], "media": media_kind(m),
                              "views": getattr(m, "views", None), "reactions": reac}, ensure_ascii=False))
            n += 1
        await asyncio.sleep(0.05)
    print(json.dumps({"total": n, "hours": hours}), file=sys.stderr)


async def cmd_topics(c, d, chat):
    """Темы форума: id, название, непрочитано, последнее сообщение. Не форум — понятный отказ."""
    from telethon.tl.functions.messages import GetForumTopicsRequest
    ent = await resolve(c, chat)
    if not getattr(ent, "forum", False):
        sys.exit("это не форум (нет тем) — читай last <чат> N")
    r = await c(GetForumTopicsRequest(peer=ent, offset_date=None, offset_id=0, offset_topic=0, limit=100))
    for t in getattr(r, "topics", None) or []:
        if type(t).__name__ == "ForumTopicDeleted":
            continue
        print(json.dumps({"id": t.id, "title": t.title, "unread": getattr(t, "unread_count", 0),
                          "top_message": getattr(t, "top_message", None), "closed": bool(getattr(t, "closed", False))}, ensure_ascii=False))


async def cmd_get(c, d, chat, msg_id, n=0):
    """Сообщение по номеру и n вокруг: get_messages(ids=[…]) — только чтение, прочитанным не помечает."""
    if not isinstance(msg_id, int) or msg_id < 1:
        sys.exit("нужен номер сообщения: get <чат> <id> [N]")
    n = max(0, min(int(n or 0), 25))
    ent = await resolve(c, chat)
    private_guard(d, ent, "читаю")
    ids = list(range(max(1, msg_id - n), msg_id + n + 1))
    got = await c.get_messages(ent, ids=ids)
    got = [m for m in (got if isinstance(got, list) else [got]) if m is not None and getattr(m, "id", None) in ids]
    journal(d, {"op": "get", "chat": getattr(ent, "id", None), "id": msg_id, "n": n, "found": len(got)})
    if not any(m.id == msg_id for m in got):
        sys.exit("сообщения %d в этом чате нет (удалено, служебное или не тот чат); рядом найдено: %d" % (msg_id, len(got)))
    for m in sorted(got, key=lambda m: m.id):
        print(row(m))


async def cmd_draft(c, d, chat, text, replace=False):
    """Черновик в поле ввода чата владельца. Не отправка: сообщение увидит и отправит (или сотрёт) сам владелец."""
    text = (text or "").strip()
    if not text:
        sys.exit("пустой черновик")
    if len(text) > 4096:
        sys.exit("черновик длиннее 4096 знаков")
    ent = await resolve(c, chat)
    private_guard(d, ent, "черновик")
    mine = await own_draft(c, ent)
    if mine and mine != text and not replace:
        sys.exit("у владельца в этом чате свой черновик: «%s» — спросить, заменить ли (--replace после его «да»)" % mine[:200])
    from telethon.tl.functions.messages import SaveDraftRequest
    await c(SaveDraftRequest(peer=ent, message=text))
    title = getattr(ent, "title", None) or " ".join(x for x in (getattr(ent, "first_name", None), getattr(ent, "last_name", None)) if x) or str(getattr(ent, "id", ""))
    p = os.path.join(d, "drafts.jsonl")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "chat_id": getattr(ent, "id", None), "chat": title, "len": len(text), "h": text_hash(text)}, ensure_ascii=False) + "\n")
    print("DRAFT OK", title, len(text))


REACT_OK = {"👍", "❤", "🔥", "🙏", "👏", "🤝", "😁", "🎉", "💯"}   # ❤ — без U+FE0F: так его принимает Telegram


async def cmd_react(c, d, chat, msg_id, emoji, by, ref):
    """Реакция от имени владельца: лайк вместо текста на «спасибо / ок».
    Только по его слову (--by = id владельца, --msg — улика), только эмодзи из белого списка, только в разрешённом личном чате."""
    emoji = (emoji or "").replace("\ufe0f", "").strip()
    if emoji not in REACT_OK:
        sys.exit("эмодзи не из белого списка: %s" % " ".join(sorted(REACT_OK)))
    if not str(msg_id or "").isdigit():
        sys.exit("нужен id сообщения: react <чат> <id сообщения>")
    ent = await resolve(c, chat)
    if type(ent).__name__ != "User":   # в группе и канале лайк видят все — только личные чаты
        sys.exit("реакция — только в личном чате (группы и каналы — нет)")
    private_guard(d, ent, "реакция")
    key = await owner_said(c, d, by, ref, "реакция")
    from telethon.tl.functions.messages import SendReactionRequest
    from telethon.tl.types import ReactionEmoji
    await c(SendReactionRequest(peer=ent, msg_id=int(msg_id), reaction=[ReactionEmoji(emoticon=emoji)]))
    journal(d, {"kind": "react", "chat_id": getattr(ent, "id", None), "msg": int(msg_id), "emoji": emoji, "by": str(by), "ref": key})
    print("REACT OK", getattr(ent, "id", ""), msg_id, emoji)


def my_last_hash(d, chat_id):
    """Хеш последнего черновика, который положила я (drafts.jsonl), — чтобы стирать только своё."""
    h = ""
    try:
        for l in open(os.path.join(d, "drafts.jsonl"), encoding="utf-8"):
            try: r = json.loads(l)
            except ValueError: continue
            if isinstance(r, dict) and r.get("chat_id") == chat_id and r.get("h") and r.get("kind", "draft") == "draft":
                h = r["h"]
    except OSError:
        pass
    return h


async def cmd_draft_clear(c, d, chat, by, ref, replace=False):
    """Стереть черновик в поле ввода — только с согласия владельца и только мой. Набранное или дописанное им — только с --replace
    и только если его слово — ответ на моё предложение стереть (его черновик не вернуть)."""
    ent = await resolve(c, chat)
    private_guard(d, ent, "черновик")
    cur = await own_draft(c, ent)
    if not cur:
        print("DRAFT EMPTY", getattr(ent, "id", "")); return
    theirs = text_hash(cur) != my_last_hash(d, getattr(ent, "id", None))
    if theirs and not replace:
        sys.exit("в чате черновик, который положила не я (или его правил владелец) — не стираю; заменить — --replace после его «да»")
    key = await owner_said(c, d, by, ref, "очистка черновика", reply=theirs)
    from telethon.tl.functions.messages import SaveDraftRequest
    await c(SaveDraftRequest(peer=ent, message=""))
    journal(d, {"kind": "draft-clear", "chat_id": getattr(ent, "id", None), "by": str(by), "ref": key, "replace": bool(replace)})
    print("DRAFT CLEARED", getattr(ent, "id", ""))


async def main():
    ap = argparse.ArgumentParser(description="Личный Telegram владельца — только чтение")
    ap.add_argument("cmd", choices=["map", "pulse", "last", "get", "topics", "media", "channels-digest", "draft", "draft-clear", "react", "allow", "disallow", "voice", "folders", "folders-apply", "inbox"])
    ap.add_argument("chat", nargs="?")
    ap.add_argument("n", nargs="?", type=int, default=None)
    ap.add_argument("around", nargs="?", type=int, default=None)   # get <чат> <id> [N]
    ap.add_argument("--text")
    ap.add_argument("--emoji")
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--by")
    ap.add_argument("--msg")
    ap.add_argument("--dir")
    ap.add_argument("--topic", type=int)   # last <чат> N --topic <id>: тема форума
    ap.add_argument("--yes", action="store_true")   # folders-apply: применить (без него — только дифф)
    a = ap.parse_args()
    d = session_dir(a.dir)
    api_id, api_hash = api_keys(d)
    from telethon import TelegramClient
    raw = TelegramClient(os.path.join(d, "owner"), api_id, api_hash, **DEVICE)
    c = ReadOnly(raw)
    writer = owner_folders.FolderWriter(raw) if a.cmd == "folders-apply" and a.yes else None   # запись — только здесь и только папки
    await c.connect()
    try:
        if not await c.is_user_authorized():
            sys.exit("не авторизован: нужен вход владельца (сессию заводит администратор)")
        if a.cmd == "map":
            await cmd_map(c, d)
        elif a.cmd == "folders":
            await owner_folders.cmd_folders(c, d)
        elif a.cmd == "folders-apply":
            if a.chat is None:
                sys.exit("нужен план: folders-apply <plan.json> --by <id владельца> --msg <чат/сообщение> [--yes]")
            await owner_folders.cmd_apply(c, d, a.chat, a.by, a.msg, a.yes, writer)
        elif a.cmd == "inbox":
            await cmd_inbox(c, d, a.by, a.msg)
        elif a.cmd == "pulse":
            await cmd_pulse(c, d)
        elif a.cmd == "react":
            if a.chat is None or a.n is None:
                sys.exit("нужны чат и id сообщения: react <чат> <id> --emoji 👍 --by … --msg …")
            await cmd_react(c, d, a.chat, a.n, a.emoji or a.text, a.by, a.msg)
        elif a.cmd == "draft-clear":
            if a.chat is None:
                sys.exit("нужен чат: id, @ник или часть имени")
            await cmd_draft_clear(c, d, a.chat, a.by, a.msg, a.replace)
        elif a.cmd == "draft":
            if a.chat is None:
                sys.exit("нужен чат: id, @ник или часть имени")
            await cmd_draft(c, d, a.chat, a.text, a.replace)
        elif a.cmd in ("voice", "media"):
            if a.chat is None:
                sys.exit("нужен чат и id сообщения")
            if a.n is None:
                sys.exit("нужен id сообщения")
            await cmd_voice(c, d, a.chat, a.n)
        elif a.cmd == "channels-digest":
            await cmd_digest(c, d, 24 if a.chat is None else a.chat)
        elif a.cmd == "topics":
            if a.chat is None:
                sys.exit("нужен чат: id, @ник или часть названия")
            await cmd_topics(c, d, a.chat)
        elif a.cmd == "get":
            if a.chat is None or a.n is None:
                sys.exit("нужны чат и номер сообщения: get <чат> <id> [N]")
            await cmd_get(c, d, a.chat, a.n, a.around or 0)
        elif a.cmd in ("allow", "disallow"):
            if a.chat is None:
                sys.exit("нужен чат: id, @ник или часть имени")
            await (cmd_allow(c, d, a.chat, a.by, a.msg) if a.cmd == "allow" else cmd_disallow(c, d, a.chat))
        else:
            if a.chat is None:
                sys.exit("нужен чат: id, @ник или часть имени")
            await cmd_last(c, d, a.chat, 20 if a.n is None else a.n, a.topic)
    finally:
        await c.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
