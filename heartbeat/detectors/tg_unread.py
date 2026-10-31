#!/usr/bin/env python3
"""Heartbeat detector: new unread messages in chosen chats of the owner's Telegram (read-only, owner-telegram reader).

  tg_unread.py --chat <id|@name|title part> [--chat …] [--map ~/work/secrets/owner-tg/map.json] [--refresh "<command>"]
Reads map.json (written by `reader.py map`), compares unread counts with the last run and prints one JSON line per chat where
unread grew: {"key": "<chat id>:<count>", "text": "…"}. First run only remembers the counts. --refresh runs the map command first.
State: ~/.local/state/mila-heartbeat/tg_unread.json. Prints nothing when there is nothing new."""
import argparse, json, os, shlex, subprocess, sys

STATE = os.path.join(os.environ.get("MILA_HEARTBEAT_STATE") or os.path.expanduser("~/.local/state/mila-heartbeat"), "tg_unread.json")


def match(row, want):
    w = str(want).strip()
    if w.lstrip("-").isdigit():
        return str(row.get("id")) == w
    if w.startswith("@"):
        return (row.get("username") or "").lower() == w[1:].lower()
    return w.lower() in str(row.get("title") or "").lower()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", action="append", required=True)
    ap.add_argument("--map", default=os.path.expanduser(os.path.join(os.environ.get("OWNER_TG_DIR") or "~/work/secrets/owner-tg", "map.json")))
    ap.add_argument("--refresh")
    a = ap.parse_args(argv)
    if a.refresh:
        subprocess.run(shlex.split(os.path.expanduser(a.refresh)), capture_output=True, timeout=50)
    try:
        rows = json.load(open(a.map, encoding="utf-8"))
    except (OSError, ValueError):
        print("no map.json at %s" % a.map, file=sys.stderr)
        return 1
    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        st = None
    first = st is None
    st = st or {}
    for r in rows if isinstance(rows, list) else []:
        if not any(match(r, w) for w in a.chat):
            continue
        cid, unread = str(r.get("id")), int(r.get("unread") or 0)
        before = int(st.get(cid, 0))
        if not first and unread > before:
            print(json.dumps({"key": "%s:%d:%s" % (cid, unread, r.get("last") or ""),
                              "text": "New in «%s»: %d unread (was %d). Read: reader.py last %s %d" % (r.get("title"), unread, before, cid, min(unread, 50))},
                             ensure_ascii=False))
        st[cid] = unread
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(STATE + ".tmp", STATE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
