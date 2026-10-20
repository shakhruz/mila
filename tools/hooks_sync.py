#!/usr/bin/env python3
"""HOOKS-SYNC-1020 (20.10, после раскатки 2.0: у Мил из образа нет PostToolUse журнала исходящих — tasks/sent.jsonl не пишется, обещания не
закрываются с уликой): у уже живой Милы дописывает в ~/.claude/settings.json недостающие хуки mila-tasks — PostToolUse(reply) task-sent.py
и SessionStart task-open.py. Идемпотентно (второй запуск ничего не меняет), бэкап settings.json, чужие хуки не трогает.
mila-update settings.json не трогает, поэтому нужен этот шаг при раскатке.
  python3 hooks_sync.py [--home DIR] [--dry-run]     выход: JSON {added:[…], hooks_dir, backup}"""
import datetime, json, os, sys

REPLY = "mcp__plugin_(mila-)?telegram_telegram__reply"


def find_tasks(home):
    for d in (os.path.join(home, ".claude", "skills", "mila-tasks", "hooks"), os.path.join(home, ".claude", "hooks")):
        if os.path.isfile(os.path.join(d, "task-sent.py")):
            return d
    return None


def main():
    a = sys.argv[1:]
    home = a[a.index("--home") + 1] if "--home" in a else os.path.expanduser("~")
    dry = "--dry-run" in a
    p = os.path.join(home, ".claude", "settings.json")
    raw = open(p, encoding="utf-8").read() if os.path.exists(p) else "{}"
    cfg = json.loads(raw or "{}"); hooks = cfg.setdefault("hooks", {})
    d = find_tasks(home)
    if not d:
        print(json.dumps({"ok": False, "error": "нет task-sent.py (навык mila-tasks не установлен) — сначала mila-update install-skill mila-tasks"}, ensure_ascii=False)); sys.exit(2)
    added = []
    has = lambda ev, name: any(name in json.dumps(x) for x in hooks.get(ev, []))
    if not has("PostToolUse", "task-sent.py"):
        hooks.setdefault("PostToolUse", []).append({"matcher": REPLY, "hooks": [{"type": "command", "command": "python3 " + os.path.join(d, "task-sent.py")}]})
        added.append("PostToolUse(reply): task-sent.py")
    if os.path.isfile(os.path.join(d, "task-open.py")) and not has("SessionStart", "task-open.py"):
        hooks.setdefault("SessionStart", []).append({"hooks": [{"type": "command", "command": "python3 " + os.path.join(d, "task-open.py")}]})
        added.append("SessionStart: task-open.py")
    backup = None
    if added and not dry:
        if os.path.exists(p):
            backup = p + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            open(backup, "w", encoding="utf-8").write(raw)
        tmp = p + ".tmp"
        open(tmp, "w", encoding="utf-8").write(json.dumps(cfg, ensure_ascii=False, indent=2))
        os.replace(tmp, p)
    print(json.dumps({"ok": True, "added": added, "hooks_dir": d, "backup": backup, "dry_run": dry}, ensure_ascii=False))


if __name__ == "__main__":
    main()
