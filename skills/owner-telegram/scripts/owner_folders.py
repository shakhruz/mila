#!/usr/bin/env python3
"""Папки Telegram в личном аккаунте владельца (кнопка «Дать умение менять папки»).

Модуль для reader.py; клиент приходит снаружи (ReadOnly для чтения, FolderWriter — только для применения с --yes).

  folders                     — только чтение: папки целиком (название, эмодзи, флаги, закреплённые, включённые,
                                исключённые — id + название) → stdout JSON, folders.json и бэкап folders-<дата>.json
  folders-apply <plan.json> --by <id владельца> --msg <чат/сообщение> [--yes]
                              — без --yes: только дифф «было → станет»; с --yes: бэкап, применение, журнал folders.jsonl.
                                Откат: folders-apply <бэкап.json> — тот же формат.

План: {"folders": [ {...}, ... ]} или список (формат бэкапа). Папка в плане:
  "id" (необязательно) — какую папку менять; без id — ищется по точному названию, не нашлась — создаётся новая;
  "title", "emoticon", "flags": {"contacts", "non_contacts", "groups", "broadcasts", "bots",
                                 "exclude_muted", "exclude_read", "exclude_archived": true/false};
  "include" / "pinned" / "exclude" — список задаётся целиком (id или {"id": …}, как в бэкапе);
  "add" / "remove" / "pin" / "unpin" — правка по месту (pin кладёт в папку и закрепляет, unpin оставляет в папке).
Никогда: удалить папку (запроса с пустым filter нет вовсе), удалить чат, выйти из группы, архивировать, тронуть
папку, которой нет в плане, общую папку (chatlist), чат, которого нет среди диалогов владельца.
Лимиты Telegram (проверка до применения): папок ≤ 10 (Premium — 20), в папке закреплённых + включённых ≤ 100,
исключённых ≤ 100, название 1–12 знаков, в папке есть хотя бы один чат или флаг типа чатов.
"""
import hashlib, json, os, re, sys, time

FLAGS = ("contacts", "non_contacts", "groups", "broadcasts", "bots", "exclude_muted", "exclude_read", "exclude_archived")
TYPE_FLAGS = FLAGS[:5]
MAX_FOLDERS, MAX_FOLDERS_PREMIUM, MAX_PEERS, MAX_TITLE = 10, 20, 100, 12
MSG_RE = re.compile(r"^-?\d+/\d+$")


class FolderWriter:
    """Обёртка записи: наружу ровно один запрос — UpdateDialogFilterRequest с непустой папкой (создать/изменить).
    Удаление папки (filter=None) и любой другой запрос — отказ."""
    def __init__(self, client):
        object.__setattr__(self, "_c", client)

    def __getattr__(self, name):
        raise PermissionError("запись папок: метод %s запрещён" % name)

    def __setattr__(self, name, value):
        raise PermissionError("запись папок: только UpdateDialogFilterRequest")

    async def __call__(self, request):
        if type(request).__name__ != "UpdateDialogFilterRequest":
            raise PermissionError("запись папок: запрос %s запрещён" % type(request).__name__)
        if getattr(request, "filter", None) is None:
            raise PermissionError("запись папок: удалять папки нельзя")
        return await object.__getattribute__(self, "_c")(request)


_SELF = {"id": None}   # id своего аккаунта — для InputPeerSelf («Избранное»), ставит read_state


def _pid(peer):
    """id чата из любого InputPeer*. b (живые папки владельца, 25.10): InputPeerSelf («Избранное») → свой id,
    *FromMessage → id из полей, InputPeerEmpty и непонятное → None (такой чат пропускаем, папку не роняем)."""
    from telethon import utils, types
    t = type(peer).__name__
    if t == "InputPeerSelf":
        return _SELF["id"]
    if t == "InputPeerEmpty":
        return None
    try:
        return utils.get_peer_id(peer)
    except (TypeError, ValueError):
        if getattr(peer, "channel_id", None):
            return utils.get_peer_id(types.PeerChannel(peer.channel_id))
        if getattr(peer, "user_id", None):
            return int(peer.user_id)
        if getattr(peer, "chat_id", None):
            return -int(peer.chat_id)
        return None


def _title(x):
    t = getattr(x, "title", "") or ""
    return getattr(t, "text", t) or ""


def _backup(d, data):
    """Бэкап folders-<дата>[-N].json: существующий файл не перезаписывается никогда (O_EXCL)."""
    stem = "folders-%s" % time.strftime("%Y-%m-%d_%H%M%S")
    for k in range(1, 1000):
        p = os.path.join(d, stem + (".json" if k == 1 else "-%d.json" % k))
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return p
    raise RuntimeError("не нашла свободного имени бэкапа")


CONSENT_TTL = 24 * 3600


def was_sha(changes):
    """sha «было» у папок, которые план трогает. Входит в код «да» — владелец поправил эти папки
    руками между карточкой и применением → код другой, старое «да» не подходит, его правка не перезаписывается."""
    was = [w for _a, w, _n in changes]
    return hashlib.sha256(json.dumps(was, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def plan_code(plan_path, was=""):
    """Код для «да»: первые 8 знаков sha256 (файл плана + sha «было» затронутых папок) — владелец пишет «да <код>»."""
    return hashlib.sha256(open(plan_path, "rb").read() + b"\n" + was.encode()).hexdigest()[:8]


async def consent_saved(c, plan_path, was=""):
    """c («службы кнопки нет»): «да» — сообщение САМОГО владельца в его «Избранном» (Saved Messages)
    вида «да <код плана>», не старше суток и новее файла плана. Написать туда может только он: читалка — только чтение,
    черновик (SaveDraft) сообщением не является. → (ok, причина, id сообщения)."""
    code = plan_code(plan_path, was); now = time.time(); mt = os.path.getmtime(plan_path)
    from telethon.tl.types import InputPeerSelf
    try:
        msgs = await c.get_messages(InputPeerSelf(), limit=30)
    except Exception as e:   # noqa: BLE001
        return False, "не прочитала «Избранное»: %s" % type(e).__name__, None
    rx = re.compile(r"^\s*да\s+%s\s*[.!]?\s*$" % code, re.I)
    for m in msgs or []:
        if not getattr(m, "out", False) or not rx.match(getattr(m, "message", "") or ""):
            continue
        ts = m.date.timestamp() if getattr(m, "date", None) else 0
        if ts < mt - 1 or now - ts > CONSENT_TTL:
            return False, "«да %s» старое или раньше плана — нужно новое" % code, None
        return True, "", getattr(m, "id", None)
    if any(re.match(r"^\s*да\s+[0-9a-f]{8}\s*[.!]?\s*$", getattr(m, "message", "") or "", re.I) and getattr(m, "out", False) for m in msgs or []):
        return False, ("в «Избранном» есть «да» с другим кодом: папки или план изменились после карточки — покажите владельцу новую "
                       "карточку (код теперь %s); его ручные правки не перезаписываю" % code), None
    return False, "в «Избранном» владельца нет «да %s» — попросите его отправить себе это сообщение" % code, None


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _save(d, name, data):
    p = os.path.join(d, name)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.chmod(p, 0o600)
    return p


async def read_state(c):
    """Папки как есть + карта id → (InputPeer, название) по диалогам и по самим папкам."""
    from telethon.tl.functions.messages import GetDialogFiltersRequest
    res = await c(GetDialogFiltersRequest())
    raw = [f for f in (getattr(res, "filters", res) or []) if type(f).__name__ in ("DialogFilter", "DialogFilterChatlist")]
    _SELF["id"] = getattr(await c.get_me(), "id", None)
    peers, names = {}, {}
    async for dl in c.iter_dialogs():
        i = _pid(dl.input_entity)
        if i is None:
            continue
        peers[i], names[i] = dl.input_entity, dl.name or ""
    if _SELF["id"] is not None:
        names.setdefault(_SELF["id"], "Избранное")
    for f in raw:
        for k in ("pinned_peers", "include_peers", "exclude_peers"):
            for p in getattr(f, k, None) or []:
                i = _pid(p)
                if i is not None:
                    peers.setdefault(i, p)
    return raw, peers, names


def norm(f, names):
    def lst(k):
        return [{"id": i, "title": names.get(i, "?")} for i in (_pid(p) for p in (getattr(f, k, None) or [])) if i is not None]
    return {"id": f.id, "title": _title(f), "emoticon": getattr(f, "emoticon", None) or "",
            "shared": type(f).__name__ == "DialogFilterChatlist",
            "flags": {k: bool(getattr(f, k, False)) for k in FLAGS},
            "pinned": lst("pinned_peers"), "include": lst("include_peers"), "exclude": lst("exclude_peers")}


async def cmd_folders(c, d):
    raw, _, names = await read_state(c)
    out = [norm(f, names) for f in raw]
    _save(d, "folders.json", out)
    bak = _backup(d, out)
    print(json.dumps({"folders": out, "backup": bak}, ensure_ascii=False, indent=1))
    return out, bak


def _ids(v):
    out = []
    for x in v or []:
        x = x.get("id") if isinstance(x, dict) else x
        if isinstance(x, bool) or not str(x).lstrip("-").isdigit():
            raise ValueError("чат «%s»: нужен числовой id" % x)
        out.append(int(x))
    return out


def load_plan(path):
    data = json.load(open(path, encoding="utf-8"))
    fl = data.get("folders") if isinstance(data, dict) else data
    if not isinstance(fl, list) or not fl:
        raise ValueError("в плане нет папок")
    return fl


def target(cur, plan, known, premium=False):
    """cur — папки как в norm(); plan — список папок плана; known — id чатов, которые есть у владельца.
    → (изменения [(действие, было|None, станет)], ошибки). Папки вне плана не трогаются."""
    errs, out, used, seen = [], [], {f["id"] for f in cur}, set()
    by_id = {f["id"]: f for f in cur}
    for n, p in enumerate(plan, 1):
        if not isinstance(p, dict):
            errs.append("папка №%d: не объект" % n); continue
        tag = "папка «%s»" % (p.get("title") or p.get("id") or n)
        if p.get("shared"):
            continue   # общая папка из бэкапа — только для сведения, не меняется
        old = None
        if p.get("id") is not None:
            if not str(p["id"]).isdigit() or not 2 <= int(p["id"]) <= 255:
                errs.append("%s: id 2–255" % tag); continue
            old = by_id.get(int(p["id"]))
        elif p.get("title"):
            hits = [f for f in cur if f["title"] == p["title"]]
            if len(hits) > 1:
                errs.append("%s: таких названий %d — укажите id" % (tag, len(hits))); continue
            old = hits[0] if hits else None
        else:
            errs.append("папка №%d: нужен id или title" % n); continue
        if old and old.get("shared"):
            errs.append("%s: общая папка (по ссылке) — не меняю" % tag); continue
        if old and old["id"] in seen:
            errs.append("%s: эта папка в плане дважды" % tag); continue
        new_id = old["id"] if old else (int(p["id"]) if p.get("id") is not None else next(i for i in range(2, 256) if i not in used))
        used.add(new_id); seen.add(new_id)
        base = old or {"id": new_id, "title": "", "emoticon": "", "flags": {k: False for k in FLAGS}, "pinned": [], "include": [], "exclude": []}
        try:
            pinned = _ids(p["pinned"]) if "pinned" in p else [x["id"] for x in base["pinned"]]
            include = _ids(p["include"]) if "include" in p else [x["id"] for x in base["include"]]
            exclude = _ids(p["exclude"]) if "exclude" in p else [x["id"] for x in base["exclude"]]
            add, remove, pin, unpin = (_ids(p.get(k)) for k in ("add", "remove", "pin", "unpin"))
        except ValueError as e:
            errs.append("%s: %s" % (tag, e)); continue
        include += [i for i in add if i not in include and i not in pinned]
        pinned += [i for i in pin if i not in pinned]
        include = [i for i in include if i not in pin] + [i for i in unpin if i in pinned and i not in include]
        pinned = [i for i in pinned if i not in unpin and i not in remove]
        include = [i for i in dict.fromkeys(include) if i not in remove and i not in pinned]
        pinned = list(dict.fromkeys(pinned))
        exclude = [i for i in dict.fromkeys(exclude) if i not in pinned and i not in include]
        flags = dict(base["flags"]); bad = [k for k in (p.get("flags") or {}) if k not in FLAGS]
        if bad:
            errs.append("%s: неизвестные флаги %s" % (tag, ", ".join(bad))); continue
        flags.update({k: bool(v) for k, v in (p.get("flags") or {}).items()})
        old_peers = {x["id"] for k in ("pinned", "include", "exclude") for x in base[k]}
        unknown = [i for i in pinned + include + exclude if i not in known and i not in old_peers]
        if unknown:
            errs.append("%s: чатов нет среди диалогов владельца: %s" % (tag, ", ".join(map(str, unknown[:10])))); continue
        title = p.get("title", base["title"]) or ""
        new = {"id": new_id, "title": title, "emoticon": p.get("emoticon", base["emoticon"]) or "", "flags": flags,
               "pinned": pinned, "include": include, "exclude": exclude}
        if not 1 <= len(title) <= MAX_TITLE:
            errs.append("%s: название 1–%d знаков" % (tag, MAX_TITLE))
        if len(pinned) + len(include) > MAX_PEERS:
            errs.append("%s: закреплённых и включённых %d > %d" % (tag, len(pinned) + len(include), MAX_PEERS))
        if len(exclude) > MAX_PEERS:
            errs.append("%s: исключённых %d > %d" % (tag, len(exclude), MAX_PEERS))
        if not (pinned or include or any(flags[k] for k in TYPE_FLAGS)):
            errs.append("%s: пустая — нужен хотя бы один чат или флаг типа чатов" % tag)
        was = None if not old else {**old, "pinned": [x["id"] for x in old["pinned"]], "include": [x["id"] for x in old["include"]],
                                    "exclude": [x["id"] for x in old["exclude"]]}
        if was and {k: was[k] for k in new} == new:
            continue   # без изменений
        out.append(("create" if not old else "update", was, new))
    total = len(cur) + sum(1 for a, _, _ in out if a == "create")
    lim = MAX_FOLDERS_PREMIUM if premium else MAX_FOLDERS
    if total > lim:
        errs.append("папок станет %d > %d%s" % (total, lim, " (Premium)" if premium else " (без Premium)"))
    return out, errs


def diff_text(changes, names):
    nm = lambda i: "%s (%s)" % (names.get(i, "?"), i)
    lines = []
    for act, was, new in changes:
        head = "＋ создать «%s» %s" % (new["title"], new["emoticon"]) if act == "create" else "✎ папка «%s» (id %d)" % (was["title"], was["id"])
        lines.append(head.rstrip())
        w = was or {"title": "", "emoticon": "", "flags": {}, "pinned": [], "include": [], "exclude": []}
        if was and w["title"] != new["title"]: lines.append("   название: «%s» → «%s»" % (w["title"], new["title"]))
        if was and w["emoticon"] != new["emoticon"]: lines.append("   эмодзи: «%s» → «%s»" % (w["emoticon"], new["emoticon"]))
        for k in FLAGS:
            if bool(w["flags"].get(k)) != new["flags"][k]: lines.append("   флаг %s: %s → %s" % (k, bool(w["flags"].get(k)), new["flags"][k]))
        for k, label in (("pinned", "📌 закреплённые"), ("include", "чаты"), ("exclude", "исключённые")):
            plus = [i for i in new[k] if i not in w[k]]; minus = [i for i in w[k] if i not in new[k]]
            if plus: lines.append("   %s +%d: %s" % (label, len(plus), ", ".join(map(nm, plus))))
            if minus: lines.append("   %s −%d: %s" % (label, len(minus), ", ".join(map(nm, minus))))
    return "\n".join(lines) or "изменений нет"


def build_filter(new, peers):
    from telethon.tl.types import DialogFilter, TextWithEntities
    return DialogFilter(id=new["id"], title=TextWithEntities(text=new["title"], entities=[]),
                        pinned_peers=[peers[i] for i in new["pinned"]], include_peers=[peers[i] for i in new["include"]],
                        exclude_peers=[peers[i] for i in new["exclude"]], emoticon=new["emoticon"] or None,
                        **{k: (True if new["flags"][k] else None) for k in FLAGS})


async def cmd_apply(c, d, plan_path, by, msg, yes=False, writer=None):
    me = await c.get_me()
    if not by or str(by) != str(getattr(me, "id", "")):
        sys.exit("папки меняются только с согласия владельца: --by <его id> (сверка с аккаунтом сессии)")
    if not MSG_RE.match((msg or "").strip()):
        sys.exit("нужна улика «да»: --msg <чат>/<сообщение> с его словом")
    try:
        plan = load_plan(plan_path)
    except (OSError, ValueError) as e:
        sys.exit("план не читается: %s" % e)
    raw, peers, names = await read_state(c)
    cur = [norm(f, names) for f in raw]
    changes, errs = target(cur, plan, set(peers), premium=bool(getattr(me, "premium", False)))
    print(diff_text(changes, names))
    if errs:
        print("\nНЕ ПРИМЕНЯЮ — нарушены правила:\n- " + "\n- ".join(errs)); sys.exit(2)
    if not changes:
        print("\nменять нечего"); return 0
    ws = was_sha(changes)
    if not yes:
        print("\nэто проверка (dry-run). Применить: владелец отправляет себе в «Избранное» «да %s», затем тот же вызов с --yes" % plan_code(plan_path, ws)); return 0
    ok, why, said = await consent_saved(c, plan_path, ws)
    if not ok:
        print("\nНЕ ПРИМЕНЯЮ: " + why); sys.exit(4)
    if writer is None:
        sys.exit("нет обёртки записи")
    bak = _backup(d, cur)
    from telethon.tl.functions.messages import UpdateDialogFilterRequest
    done, err = [], None
    for act, was, new in changes:
        try:
            await writer(UpdateDialogFilterRequest(id=new["id"], filter=build_filter(new, peers)))
            done.append({"action": act, "id": new["id"], "title": new["title"], "pinned": len(new["pinned"]),
                         "include": len(new["include"]), "exclude": len(new["exclude"])})
        except Exception as e:   # noqa: BLE001 — остановка на первой ошибке, остальное не трогаем
            err = "%s: %s" % (type(e).__name__, str(e)[:200]); break
    p = os.path.join(d, "folders.jsonl")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(json.dumps({"ts": _now(), "by": str(by), "msg": msg.strip(), "plan": os.path.basename(plan_path), "consent_msg": said,
                            "plan_sha256": hashlib.sha256(open(plan_path, "rb").read()).hexdigest(), "was_sha256": ws, "backup": os.path.basename(bak),
                            "done": done, "error": err}, ensure_ascii=False) + "\n")
    if err:
        print("\nОСТАНОВЛЕНО на ошибке: %s. Сделано %d из %d. Откат: folders-apply %s" % (err, len(done), len(changes), bak)); sys.exit(3)
    print("\nFOLDERS OK: %d папок; бэкап до правки: %s (откат — folders-apply этого файла)" % (len(done), bak))
    return 0
