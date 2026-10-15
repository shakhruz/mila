#!/usr/bin/env python3
"""crons-keeper.py — кроны Компаньона переживают рестарт.
Рестарт сессии стирает CronCreate без durable, повторы живут 7 дней. Поэтому ведём файл
~/work/state/crons.json и при старте просим сессию поднять недостающее.
  PostToolUse (CronCreate|CronDelete) — пишет/вычёркивает запись в файле.
  SessionStart — одна строка контекста: CronList → CronCreate недостающих по файлу.
Никогда не падает и не блокирует инструмент."""
import json, os, re, sys, time
from datetime import datetime

P = os.path.join(os.path.expanduser("~"), "work", "state", "crons.json")


def load():
    try:
        d = json.load(open(P, encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:
        return []


def save(rows):
    os.makedirs(os.path.dirname(P), exist_ok=True)
    tmp = P + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    os.replace(tmp, P)


def text_of(resp):
    if isinstance(resp, str):
        return resp
    try:
        return json.dumps(resp, ensure_ascii=False)
    except Exception:
        return str(resp)


def one_shot_passed(cron, now):
    """Разовый крон с закреплёнными минутой, часом, днём и месяцем — прошло ли его время в этом году."""
    f = cron.split()
    if len(f) != 5 or not all(x.isdigit() for x in f[:4]):
        return False
    try:
        t = datetime(now.year, int(f[3]), int(f[2]), int(f[1]), int(f[0]))
    except ValueError:
        return False
    return t < now


def on_tool(ev):
    name = ev.get("tool_name", "")
    inp = ev.get("tool_input") or {}
    resp = text_of(ev.get("tool_response"))
    rows = load()
    if name == "CronCreate":
        m = re.search(r"\b(?:job|task) ([0-9a-zA-Z_-]{6,})", resp)
        if not m:
            return  # не создан — нечего помнить
        cron, prompt = str(inp.get("cron", "")), str(inp.get("prompt", ""))
        # тот же крон с тем же текстом после рестарта — заменяем, не копим дубли
        rows = [r for r in rows if not (r.get("cron") == cron and r.get("prompt") == prompt)]
        rows.append({"id": m.group(1), "cron": cron, "prompt": prompt,
                     "recurring": inp.get("recurring", True) is not False,
                     "durable": bool(inp.get("durable")), "created": int(time.time())})
        save(rows)
    elif name == "CronDelete":
        jid = str(inp.get("id") or inp.get("job_id") or "")
        if jid:
            save([r for r in rows if r.get("id") != jid])


def on_start():
    rows, now = load(), datetime.now()
    keep, missed = [], []
    for r in rows:
        if not r.get("recurring") and one_shot_passed(r.get("cron", ""), now):
            missed.append(r)
        else:
            keep.append(r)
    if missed:
        save(keep)
    if not keep and not missed:
        return
    lines = []
    if keep:
        lines.append("кроны из state/crons.json (%d): сначала CronList; чего там нет по cron+prompt — "
                     "CronCreate с теми же cron, prompt, recurring (durable как в записи); помеченные «пересоздать» — "
                     "CronDelete старого id и CronCreate заново (повтор истекает на 7-й день). Список: %s"
                     % (len(keep), "; ".join("[%s%s%s] %s — %s" % (r.get("cron"), "" if r.get("recurring") else ", разово",
                                              ", пересоздать" if r.get("recurring") and time.time() - r.get("created", 0) > 6 * 86400 else "",
                                              r.get("id"), str(r.get("prompt", ""))[:120]) for r in keep)))
    if missed:
        lines.append("разовые, чьё время прошло (%d; могли и сработать до рестарта — сверь по NOW/журналу), не сделано — сделай сейчас: %s"
                     % (len(missed), "; ".join("[%s] %s" % (r.get("cron"), str(r.get("prompt", ""))[:160]) for r in missed)))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": "Кроны: " + " · ".join(lines)}}, ensure_ascii=False))


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        ev = {}
    try:
        if ev.get("hook_event_name") == "PostToolUse":
            on_tool(ev)
        else:
            on_start()
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
