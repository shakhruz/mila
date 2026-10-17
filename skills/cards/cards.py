#!/usr/bin/env python3
"""cards.py — «Входящие» и «Задачи»: карточки владельцу в одном формате для чата и мини-аппа «Офис Мил»
. Только stdlib.

Файлы Милы (~/work, append-only; одна строка = событие; состояние карточки = последняя строка с её id):
  inbox.jsonl      — мои вопросы владельцу        proposals.jsonl — мои предложения задач

  cards.py ask  --q «≤12 слов» --why «почему сейчас» --opt «a|Да, выкладывай|итог» --opt «b|Подожди|итог»
                    [--rec a] [--due ISO] [--urgent] [--link URL] [--from slug]          → id
  cards.py task --task «≤12 слов» --why «польза» --to slug [--due YYYY-MM-DD] [--est минут] [--cost $] [--prio 1|2|3]
                    [--from slug]                                                       → id
  cards.py next  inbox|proposals [--home DIR …]   → следующая карточка: {"card", "text", "buttons", "left"} для reply
  cards.py list  inbox|proposals [--home DIR …]   → открытые по порядку колоды
  cards.py answer ID --pick a | --text «…» | --explain | --snooze | --self | --close «почему»     (вопрос)
  cards.py answer ID --yes | --no | --edit «…» | --move slug                                    (задача)
                    [--via chat|voice|miniapp] [--by owner|mila] [--home DIR]
  cards.py button «[кнопка] ⭐ Да, выкладывай»     → нажатие на последней показанной карточке (next запоминает её) → тот же answer
Время — ISO с поясом владельца (OWNER_TZ, по умолчанию Asia/Tashkent). --home — чужой дом (администратор читает команду).
"""
import argparse, datetime as dt, json, os, random, re, string, sys

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(os.environ.get("OWNER_TZ", "Asia/Tashkent"))
except Exception:  # pragma: no cover
    TZ = dt.timezone(dt.timedelta(hours=5))

FILES = {"inbox": "inbox.jsonl", "proposals": "proposals.jsonl"}
OPEN = {"inbox": ("open", "snoozed"), "proposals": ("open",)}
LETTERS = "АБВГ"


def now():
    return dt.datetime.now(TZ).replace(microsecond=0)


def iso(t):
    return t.isoformat()


def parse(s):
    if not s: return None
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=TZ)


def home_dir(h=None):
    return os.path.expanduser(h or os.environ.get("MILA_WORK", "~/work"))


def path(kind, h=None):
    return os.path.join(home_dir(h), FILES[kind])


def me():
    return os.environ.get("MILA_SLUG") or os.path.basename(os.path.dirname(home_dir().rstrip("/"))) or "mila"


def new_id(kind):
    return ("q-" if kind == "inbox" else "t-") + now().strftime("%Y%m%d-%H%M") + "-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=3))


def append(kind, row, h=None):
    p = path(kind, h)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def state(kind, h=None):
    """Текущее состояние: последняя строка по id (контракт v0). Битые строки пропускаем."""
    cur = {}
    try:
        lines = open(path(kind, h), encoding="utf-8").read().splitlines()
    except OSError:
        return cur
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("id"):
            cur[r["id"]] = r
    return cur


def words(s):
    return len(str(s or "").split())


def is_open(kind, c, t=None):
    t = t or now()
    if c.get("status") not in OPEN[kind]: return False
    if c.get("status") == "snoozed":
        u = parse(c.get("until"))
        return bool(u and u <= t)
    return True


def deck(kind, homes=None, t=None):
    """Открытые карточки колодой: вопросы — срочные, по сроку, по времени; задачи — по prio, сроку, времени."""
    homes = homes or [None]
    cards = []
    for h in homes:
        for c in state(kind, h).values():
            if is_open(kind, c, t):
                cards.append(dict(c, _home=h))
    far = dt.datetime(9999, 1, 1, tzinfo=dt.timezone.utc)
    due = lambda c: parse(c.get("due")) or far
    if kind == "inbox":
        cards.sort(key=lambda c: (not c.get("urgent"), due(c), str(c.get("ts"))))
    else:
        cards.sort(key=lambda c: (int(c.get("prio") or 3), due(c), str(c.get("ts"))))
    return cards


def when(s):
    t = parse(s)
    if not t: return str(s)
    t = t.astimezone(TZ)
    return t.strftime("%d.%m %H:%M") if (t.hour or t.minute) else t.strftime("%d.%m")


def render(kind, c):
    """Текст и кнопки для reply (≤6 кнопок, рекомендация — зелёная со ⭐). Без кодов и путей — по навыку plain-words."""
    if kind == "inbox":
        opts = c.get("options") or []
        lines = [c["q"], c.get("why", "")]
        for i, o in enumerate(opts[:3]):
            lines.append(f"{LETTERS[i]} — {o['label']}" + (f": {o['result']}" if o.get("result") else ""))
        rec = next((i for i, o in enumerate(opts[:3]) if o["key"] == c.get("rec")), None)
        if rec is not None: lines.append(f"⭐ Советую: {LETTERS[rec]}")
        if c.get("due"): lines.append(f"Нужно до: {when(c['due'])}")
        if c.get("urgent"): lines.insert(0, "🔴 Срочно")
        if c.get("from") and c.get("from") != me(): lines.append(f"Спрашивает: {c.get('from_name') or c['from']}")
        if c.get("link"): lines.append(c["link"])
        row = []
        for i, o in enumerate(opts[:3]):
            b = {"label": ("⭐ " if i == rec else "") + o["label"][:40], "choice": f"pick_{o['key']}"}
            if i == rec: b["style"] = "success"
            row.append(b)
        buttons = [row, [{"label": "💬 Поясни", "choice": "explain"}, {"label": "⏸ До завтра", "choice": "snooze"},
                         {"label": "🤷 Реши сама", "choice": "self"}]]
    else:
        lines = [c["task"], c.get("why", "")]
        meta = []
        if c.get("to"): meta.append(f"Кому: {c.get('to_name') or c['to']}")
        if c.get("due"): meta.append(f"срок {when(c['due'])}")
        if c.get("est_min"): meta.append(f"≈{c['est_min']} мин")
        if c.get("cost_usd"): meta.append(f"${c['cost_usd']}")
        if meta: lines.append(" · ".join(meta))
        buttons = [[{"label": "✅ Да", "choice": "yes", "style": "success"}, {"label": "✏️ Изменить", "choice": "edit"},
                    {"label": "Нет", "choice": "no"}], [{"label": "➡️ Другой Миле", "choice": "move"}]]
    return {"text": "\n".join(l for l in lines if l), "buttons": buttons}


def check_card(kind, c):
    """Правила формата до записи: короткий вопрос/задача, «почему» есть, варианты с ключами, рекомендация — из вариантов."""
    err = []
    head = c.get("q") if kind == "inbox" else c.get("task")
    if not head: err.append("нет вопроса" if kind == "inbox" else "нет задачи")
    elif words(head) > 12: err.append(f"{words(head)} слов в первой строке (≤12)")
    if re.search(r"\b(M-\d+|A-\d+|P-\d+)\b", str(head) + " " + str(c.get("why", ""))): err.append("код задачи в тексте — человеку без кодов")
    if not c.get("why"): err.append("нет «почему сейчас»" if kind == "inbox" else "нет «зачем»")
    if kind == "inbox":
        keys = [o.get("key") for o in c.get("options") or []]
        if len(keys) < 2: err.append("вариантов меньше двух")
        if len(keys) > 3: err.append("вариантов больше трёх — карточка не влезет в 6 кнопок")
        if len(set(keys)) != len(keys): err.append("ключи вариантов повторяются")
        if c.get("rec") and c["rec"] not in keys: err.append("рекомендация не из вариантов")
    else:
        if not c.get("to"): err.append("нет исполнителя (--to)")
        if c.get("prio") not in (1, 2, 3): err.append("prio — 1, 2 или 3")
    if c.get("due") and not parse(c["due"]) and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(c["due"])): err.append("срок не ISO")
    return err


def shown_path():
    return os.path.join(home_dir(), ".kartochki-shown.json")


def mark_shown(kind, c):
    """Какую карточку показали последней — нажатие придёт «[кнопка] <подпись>», без id (плагин режет choice до 16 латиницей)."""
    try:
        d = json.load(open(shown_path(), encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d[kind] = {"id": c["id"], "home": c.get("_home"), "ts": iso(now())}
    with open(shown_path() + ".tmp", "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False)
    os.replace(shown_path() + ".tmp", shown_path())


def by_label(label):
    """«[кнопка] ⭐ Да, выкладывай» → (id, действие, значение, дом) по последней показанной карточке."""
    try:
        d = json.load(open(shown_path(), encoding="utf-8"))
    except (OSError, ValueError):
        return None
    l = re.sub(r"^\[кнопка\]\s*", "", str(label)).replace("⭐", "").strip()
    fixed = {"💬 Поясни": "explain", "⏸ До завтра": "snooze", "🤷 Реши сама": "self", "✅ Да": "yes", "✏️ Изменить": "edit", "Нет": "no", "➡️ Другой Миле": "move"}
    for kind in ("inbox", "proposals"):
        sh = d.get(kind)
        if not sh: continue
        homes = [sh.get("home")]
        k2, c, h = find(sh["id"], homes)
        if not c: continue
        if kind == "inbox":
            o = next((o for o in c.get("options") or [] if o["label"][:40].strip() == l), None)
            if o: return sh["id"], "pick", o["key"], homes
        for lab, act in fixed.items():
            if l == lab.replace("⭐", "").strip() and (act in ("explain", "snooze", "self")) == (kind == "inbox"):
                return sh["id"], act, None, homes
    return None


def find(cid, homes):
    kind = "inbox" if cid.startswith("q-") else "proposals"
    for h in homes or [None]:
        c = state(kind, h).get(cid)
        if c: return kind, c, h
    return kind, None, None


def tomorrow_9():
    t = now() + dt.timedelta(days=1)
    return t.replace(hour=9, minute=0, second=0)


def answer(cid, act, val=None, via="chat", by="owner", homes=None):
    kind, c, h = find(cid, homes)
    if not c: return {"ok": False, "error": f"нет карточки {cid}"}
    if not is_open(kind, c) and c.get("status") != "snoozed":
        return {"ok": False, "error": f"карточка уже {c.get('status')}"}
    base = {k: v for k, v in c.items() if not k.startswith("_") and k not in ("answer", "until", "reason", "edit")}
    t = iso(now())
    if kind == "inbox":
        keys = [o["key"] for o in c.get("options") or []]
        if act == "pick":
            if val not in keys: return {"ok": False, "error": f"нет варианта {val}"}
            row = dict(base, ts=t, status="answered", answer={"key": val, "by": by, "via": via, "ts": t})
        elif act == "text":
            row = dict(base, ts=t, status="answered", answer={"text": str(val)[:1000], "by": by, "via": via, "ts": t})
        elif act == "snooze":
            row = dict(base, ts=t, status="snoozed", until=iso(tomorrow_9()))
        elif act == "self":
            row = dict(base, ts=t, status="delegated")
        elif act == "close":
            row = dict(base, ts=t, status="closed", reason=str(val or "")[:300])
        elif act == "explain":
            return {"ok": True, "explain": True, "card": c}   # карточка остаётся: Мила поясняет подробнее и снова показывает её
        else:
            return {"ok": False, "error": f"для вопроса нет действия {act}"}
    else:
        if act == "yes": row = dict(base, ts=t, status="accepted")
        elif act == "no": row = dict(base, ts=t, status="rejected")
        elif act == "edit": row = dict(base, ts=t, status="edited", edit=str(val or "")[:1000])
        elif act == "move":
            if not val: return {"ok": False, "error": "кому передать?"}
            row = dict(base, ts=t, status="moved", to=str(val))
        else:
            return {"ok": False, "error": f"для задачи нет действия {act}"}
    append(kind, row, h)
    return {"ok": True, "card": row, "home": h}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask"); a.add_argument("--q", required=True); a.add_argument("--why", required=True)
    a.add_argument("--opt", action="append", default=[]); a.add_argument("--rec"); a.add_argument("--due"); a.add_argument("--urgent", action="store_true")
    a.add_argument("--link"); a.add_argument("--from", dest="frm")
    t = sub.add_parser("task"); t.add_argument("--task", required=True); t.add_argument("--why", required=True); t.add_argument("--to", required=True)
    t.add_argument("--due"); t.add_argument("--est", type=int); t.add_argument("--cost", type=float); t.add_argument("--prio", type=int, default=2); t.add_argument("--from", dest="frm")
    for name in ("next", "list"):
        n = sub.add_parser(name); n.add_argument("kind", choices=FILES); n.add_argument("--home", action="append")
    an = sub.add_parser("answer"); an.add_argument("id")
    g = an.add_mutually_exclusive_group(required=True)
    g.add_argument("--pick"); g.add_argument("--text"); g.add_argument("--explain", action="store_true"); g.add_argument("--snooze", action="store_true")
    g.add_argument("--self", action="store_true"); g.add_argument("--close"); g.add_argument("--yes", action="store_true"); g.add_argument("--no", action="store_true")
    g.add_argument("--edit"); g.add_argument("--move")
    an.add_argument("--via", default="chat"); an.add_argument("--by", default="owner"); an.add_argument("--home", action="append")
    b = sub.add_parser("button"); b.add_argument("data")
    x = ap.parse_args(argv)
    out = None
    if x.cmd == "ask":
        opts = []
        for o in x.opt:
            k, _, rest = o.partition("|"); label, _, res = rest.partition("|")
            opts.append({"key": k.strip(), "label": label.strip(), "result": res.strip()})
        c = {"id": new_id("inbox"), "ts": iso(now()), "from": x.frm or me(), "status": "open", "q": x.q.strip(), "why": x.why.strip(),
             "options": opts, "rec": x.rec, "due": x.due, "urgent": bool(x.urgent)}
        if x.link: c["link"] = x.link
        err = check_card("inbox", c)
        if err: print(json.dumps({"ok": False, "errors": err}, ensure_ascii=False)); return 1
        out = {"ok": True, "id": append("inbox", c)["id"], **render("inbox", c)}
    elif x.cmd == "task":
        c = {"id": new_id("proposals"), "ts": iso(now()), "from": x.frm or me(), "to": x.to, "status": "open", "task": x.task.strip(), "why": x.why.strip(),
             "due": x.due, "est_min": x.est, "cost_usd": x.cost, "prio": x.prio}
        err = check_card("proposals", c)
        if err: print(json.dumps({"ok": False, "errors": err}, ensure_ascii=False)); return 1
        out = {"ok": True, "id": append("proposals", c)["id"], **render("proposals", c)}
    elif x.cmd in ("next", "list"):
        d = deck(x.kind, x.home)
        if x.cmd == "list":
            out = {"left": len(d), "cards": [{k: v for k, v in c.items() if not k.startswith("_")} for c in d]}
        elif not d:
            out = {"left": 0, "text": "Все ответы розданы." if x.kind == "inbox" else "Задач на раздачу нет."}
        else:
            c = d[0]; mark_shown(x.kind, c); out = {"left": len(d), "card": {k: v for k, v in c.items() if not k.startswith("_")}, **render(x.kind, c)}
    elif x.cmd == "answer":
        act, val = next((k, v) for k, v in (("pick", x.pick), ("text", x.text), ("explain", x.explain), ("snooze", x.snooze), ("self", x.self),
                                             ("close", x.close), ("yes", x.yes), ("no", x.no), ("edit", x.edit), ("move", x.move)) if v)
        out = answer(x.id, act, val, x.via, x.by, x.home)
    elif x.cmd == "button":
        hit = by_label(x.data)
        if not hit: print(json.dumps({"ok": False, "error": "не кнопка показанной карточки"}, ensure_ascii=False)); return 1
        cid, act, key, homes = hit
        if act in ("edit", "move"):
            out = {"ok": True, "ask": act, "id": cid}   # спросить текст правки / кому передать, потом answer --edit/--move
        else:
            out = answer(cid, act, key, "chat", "owner", homes)
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
