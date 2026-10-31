#!/usr/bin/env python3
"""Heartbeat detector: things whose deadline is near.

  deadlines.py --file <items.json|items.jsonl> [--hours 2]
Items: a JSON list or JSON lines with {"id", "text", "due": "YYYY-MM-DD HH:MM" (or ISO), "done": bool}. Prints one JSON line per
open item due within --hours (or already overdue): {"key": "<id>:<due>", "text": "…"}. Times without a zone are in
--tz (default Asia/Tashkent). The heartbeat remembers keys, so each item is raised once per due time."""
import argparse, datetime as dt, json, sys
from zoneinfo import ZoneInfo


def items(path):
    raw = open(path, encoding="utf-8").read()
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else (v.get("items") or [])
    except ValueError:
        out = []
        for line in raw.splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out


def main(argv=None, now=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--hours", type=float, default=2)
    ap.add_argument("--tz", default="Asia/Tashkent")
    a = ap.parse_args(argv)
    tz = ZoneInfo(a.tz)
    now = now or dt.datetime.now(tz)
    try:
        rows = items(a.file)
    except OSError:
        print("no file %s" % a.file, file=sys.stderr)
        return 1
    for it in rows:
        if not isinstance(it, dict) or it.get("done") or not it.get("due"):
            continue
        try:
            due = dt.datetime.fromisoformat(str(it["due"]))
        except ValueError:
            continue
        due = due.replace(tzinfo=tz) if due.tzinfo is None else due
        left = (due - now).total_seconds() / 3600
        if left <= a.hours:
            when = "overdue by %.0f h" % -left if left < 0 else "due in %.0f min" % (left * 60)
            print(json.dumps({"key": "%s:%s" % (it.get("id") or it.get("text", "")[:40], it["due"]),
                              "text": "%s — %s (%s)" % (str(it.get("text") or it.get("id"))[:300], when, due.strftime("%d.%m %H:%M"))},
                             ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
