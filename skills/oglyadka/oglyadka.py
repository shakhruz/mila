#!/usr/bin/env python3
"""Оглядка (слово владельца 28.10): поручения хозяина за окно, у которых нет задачи в журнале задач.
  oglyadka.py [--hours 12] [--owner ID] [--projects DIR] [--ledger FILE]
Источник поручений — журналы разговоров Claude Code (~/.claude/projects/**/*.jsonl): входящие из канала Telegram от хозяина
(OWNER_ID), похожие на поручение. Задача есть — если после поручения в журнале задач (mila-tasks, ledger.jsonl) завели
задачу или обещание, у которого с поручением общие слова или тот же чат и сообщение-якорь. Вывод — время, чат, начало
поручения (60 знаков, телефоны — маской) и итог числом. Ничего не пишет."""
import argparse, datetime as dt, glob, json, os, re, sys

ASK = re.compile(r"\b(сделай|сделать|запомни|напомни|проверь|пришли|подготовь|найди|напиши|посчитай|разбери|добавь|поправь|узнай|собери)\w*", re.I)
CH = re.compile(r'<channel\b([^>]*)>(.*?)</channel>', re.S)
ATTR = lambda s, k: (re.search(r'\b%s="([^"]*)"' % k, s) or [None, None])[1]
PHONE = re.compile(r"(?<!\d)\+?\d[\d\s\-()]{8,}\d(?!\d)")


def _t(s):
    try: return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError): return None


def words(s):
    return {w[:5] for w in re.findall(r"[а-яёa-z0-9]{4,}", (s or "").lower())}


def asks(projects, owner, since):
    out = []
    for f in glob.glob(os.path.join(projects, "**", "*.jsonl"), recursive=True):
        try: fh = open(f, encoding="utf-8", errors="replace")
        except OSError: continue
        with fh:
            for l in fh:
                if '"user"' not in l or "<channel" not in l: continue
                try: d = json.loads(l)
                except ValueError: continue
                c = (d.get("message") or {}).get("content")
                c = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                for attrs, body in CH.findall(c):
                    uid = ATTR(attrs, "user_id") or ATTR(attrs, "user")
                    if owner and str(uid or ATTR(attrs, "chat_id")) != str(owner): continue   # есть отправитель — по нему, нет — по чату лички
                    t = _t(ATTR(attrs, "ts")) or _t(d.get("timestamp"))
                    if t is None or t < since or not ASK.search(body): continue
                    out.append({"t": t, "chat": ATTR(attrs, "chat_id"), "msg": ATTR(attrs, "message_id"), "text": body.strip()})
    return sorted(out, key=lambda x: x["t"])


def tasks(ledger):
    out = []
    try:
        for l in open(ledger, encoding="utf-8"):
            try: e = json.loads(l)
            except ValueError: continue
            if e.get("ev") in ("new", "promise"):
                out.append({"t": _t(e.get("ts")) or 0, "w": words(" ".join(str(e.get(k) or "") for k in ("title", "what", "check"))),
                            "anchor": str(e.get("anchor") or e.get("msg") or "")})
    except OSError:
        pass
    return out


def lost(projects, ledger, owner, hours, now=None):
    now = now or dt.datetime.now().timestamp()
    tk = tasks(ledger)
    res = []
    for a in asks(projects, owner, now - hours * 3600):
        aw = words(a["text"])
        hit = any(x["t"] >= a["t"] - 60 and ((a["msg"] and a["msg"] in x["anchor"]) or len(aw & x["w"]) >= 2) for x in tk)
        if not hit:
            res.append(a)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--hours", type=float, default=12); ap.add_argument("--owner", default=os.environ.get("OWNER_ID", ""))
    ap.add_argument("--projects", default=os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "projects"))
    ap.add_argument("--ledger", default=os.path.join(os.environ.get("MILA_TASKS_DIR") or os.path.expanduser("~/milagpt/tasks"), "ledger.jsonl"))
    a = ap.parse_args()
    rows = lost(a.projects, a.ledger, a.owner, a.hours)
    for r in rows:
        s = PHONE.sub("⟦тел⟧", r["text"].replace("\n", " "))[:60]
        print("%s · чат %s · %s" % (dt.datetime.fromtimestamp(r["t"]).strftime("%d.%m %H:%M"), r["chat"], s))
    print("поручений без задачи: %d" % len(rows))
