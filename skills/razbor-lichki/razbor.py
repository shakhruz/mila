#!/usr/bin/env python3
"""Разбор лички (слово владельца 28.10): что на самом деле было в чате по журналу агента — до ответа на претензию.
  razbor.py --chat ID [--hours 24] [--projects DIR] [--now ISO]
Журнал — журналы разговоров Claude Code агента (по умолчанию ~/.claude/projects): входящие из канала Telegram с этим
chat_id и вызовы инструмента reply в этот chat_id. Вывод JSON: inbound / replies (время), ответил ли после последнего
входящего, минут молчания, первые ответы — без текстов (только время и длина). Ничего не пишет."""
import argparse, datetime as dt, glob, json, os, re

CH = re.compile(r'<channel\b([^>]*)>', re.S)
ATTR = lambda s, k: (re.search(r'\b%s="([^"]*)"' % k, s) or [None, None])[1]


def _t(s):
    try: return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError): return None


def scan(projects, chat, since):
    inbound, replies = [], []
    for f in glob.glob(os.path.join(projects, "**", "*.jsonl"), recursive=True):
        try: fh = open(f, encoding="utf-8", errors="replace")
        except OSError: continue
        with fh:
            for l in fh:
                if chat not in l: continue
                try: d = json.loads(l)
                except ValueError: continue
                ts = _t(d.get("timestamp"))
                c = (d.get("message") or {}).get("content")
                if d.get("type") == "user":
                    s = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                    for attrs in CH.findall(s):
                        if ATTR(attrs, "chat_id") == chat:
                            t = _t(ATTR(attrs, "ts")) or ts
                            if t and t >= since: inbound.append(t)
                elif d.get("type") == "assistant" and isinstance(c, list):
                    for x in c:
                        if isinstance(x, dict) and x.get("type") == "tool_use" and str(x.get("name", "")).endswith("__reply") \
                                and str((x.get("input") or {}).get("chat_id")) == chat and ts and ts >= since:
                            replies.append((ts, len(str((x.get("input") or {}).get("text") or ""))))
    return sorted(set(inbound)), sorted(set(replies))


def report(projects, chat, hours=24, now=None):
    now = now or dt.datetime.now().timestamp()
    inb, rep = scan(projects, chat, now - hours * 3600)
    hm = lambda t: dt.datetime.fromtimestamp(t).astimezone().strftime("%H:%M %z")
    last_in = inb[-1] if inb else None
    after = [t for t, _ in rep if last_in and t >= last_in]
    silent = None if not last_in or after else round((now - last_in) / 60)
    return {"chat": chat, "inbound": [hm(t) for t in inb], "replies": [{"at": hm(t), "len": n} for t, n in rep],
            "answered_last": bool(after) if last_in else None, "first_answer_min": round((after[0] - last_in) / 60) if after else None,
            "silent_min": silent}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--chat", required=True); ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--projects", default=os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "projects"))
    ap.add_argument("--now")
    a = ap.parse_args()
    print(json.dumps(report(a.projects, a.chat, a.hours, _t(a.now) if a.now else None), ensure_ascii=False, indent=1))
