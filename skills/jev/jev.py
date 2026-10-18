#!/usr/bin/env python3
"""jev.py — быстрый разборщик для Милы (ROLLOUT №25, слой ядра «Проводник»): за ~0,5 с ответить на узкий вопрос
«отвечать ли мне», «кому это», «нужны ли кнопки» — без большой модели. Нет шлюза Jev, не ответил за 1,2 с, не уверен —
решают простые правила, Мила работает как раньше.

  jev.py reply   --text T [--mentioned] [--reply-to-me] [--dm] [--from-bot]   — отвечать ли Миле на сообщение в группе
  jev.py who     --text T --names "Мила Контент,Чат Реклама,…"                  — кому адресовано (или «никому»)
  jev.py buttons --text T                                                       — мой ответ — выбор для человека? (А/Б → кнопки)
  jev.py stats                                                                  — сверка режима shadow: совпадение правил и Jev
  jev.py config [--set mode=off|shadow|main] [--set url=…] [--set site=…]      — настройки (~/.claude/jev.json)

Режимы: off — только правила (по умолчанию, открытый продукт без нашего сервера); shadow — решают правила, Jev спрашиваем
и пишем расхождения в ~/.claude/jev-diff.jsonl; main — решает Jev, если уверен (≥ min_conf), иначе правила.
Ключ шлюза — env JEV_KEY или ~/secrets/jev.key (заголовок X-Jev-Key), не печатаю. Ответ — JSON {decision, source, conf, ms}."""
import argparse, json, os, re, sys, time, urllib.request

HOME = os.path.expanduser("~")
CONF_P = os.path.join(HOME, ".claude", "jev.json")
DIFF_P = os.path.join(HOME, ".claude", "jev-diff.jsonl")
DEF = {"mode": "off", "url": "", "site": "", "timeout": 1.2, "min_conf": 0.6}


def conf():
    c = dict(DEF)
    try:
        c.update(json.load(open(CONF_P, encoding="utf-8")))
    except (OSError, ValueError):
        pass
    for k in DEF:   # env сильнее файла: JEV_MODE, JEV_URL, JEV_SITE, JEV_TIMEOUT, JEV_MIN_CONF
        v = os.environ.get("JEV_" + k.upper())
        if v:
            c[k] = type(DEF[k])(v)
    if c["mode"] not in ("off", "shadow", "main"):
        c["mode"] = "off"
    return c


def key():
    k = os.environ.get("JEV_KEY", "")
    if not k:
        try:
            k = open(os.path.join(HOME, "secrets", "jev.key"), encoding="utf-8").read().strip()
        except OSError:
            pass
    return k


def ask(c, state, questions):
    """POST /decide {site, state, questions} → answers или None (нет адреса, таймаут, ошибка, мусор)."""
    if not c["url"]:
        return None
    h = {"content-type": "application/json"}
    if key():
        h["X-Jev-Key"] = key()
    body = json.dumps({"site": c["site"] or "companion", "state": state[:600], "questions": questions}, ensure_ascii=False).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(c["url"], data=body, headers=h), timeout=c["timeout"]) as r:
            d = json.loads(r.read() or b"{}")
    except Exception:
        return None
    for k in ("answers", "result", "results"):
        if isinstance(d, dict) and isinstance(d.get(k), dict):
            return d[k]
    return d if isinstance(d, dict) else None


# --- правила (запасной путь и режим off) ---
QUESTION = re.compile(r"\?|^(как|что|где|когда|кто|почему|зачем|сколько|можно|подскаж|скажи|расскаж)", re.I)
CHOICE = re.compile(r"(^|\n)\s*(А|Б|В|A|B)[\)\.:—-]\s|(^|[\s?.!:])(А|Б|В|A|B)\)\s|\bили\b.*\?\s*$|выберите|какой вариант", re.I)


def rules_reply(a):
    if a.from_bot and not (a.mentioned or a.reply_to_me):
        return False                      # боты между собой — только по имени
    return bool(a.dm or a.mentioned or a.reply_to_me)


def rules_who(text, names):
    t = text.lower()
    hit = [n for n in names if n.lower() in t]
    return max(hit, key=len) if hit else "никому"


def rules_buttons(text):
    return bool(CHOICE.search(text))


def log_diff(kind, text, rules, jev, conf_):
    try:
        os.makedirs(os.path.dirname(DIFF_P), exist_ok=True)
        with open(DIFF_P, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()), "kind": kind, "len": len(text), "rules": rules, "jev": jev,
                                "conf": conf_, "same": rules == jev}, ensure_ascii=False) + "\n")   # без текста: только длина
    except OSError:
        pass


def decide(kind, text, rules, questions, pick):
    """Общий ход: off → правила; shadow → правила + журнал; main → Jev при уверенности, иначе правила."""
    c = conf()
    if c["mode"] == "off":
        return {"decision": rules, "source": "rules", "mode": "off"}
    t0 = time.time()
    ans = ask(c, text, questions)
    ms = int((time.time() - t0) * 1000)
    j = pick(ans) if ans else None          # (решение, уверенность) или None
    if c["mode"] == "shadow":
        if j:
            log_diff(kind, text, rules, j[0], j[1])
        return {"decision": rules, "source": "rules", "mode": "shadow", "jev": j[0] if j else None, "ms": ms}
    if j and j[1] >= c["min_conf"]:
        return {"decision": j[0], "source": "jev", "conf": round(j[1], 2), "mode": "main", "ms": ms}
    return {"decision": rules, "source": "rules", "mode": "main", "why": "Jev не ответил" if not j else "Jev не уверен", "ms": ms}


def noul(name):
    def pick(ans):
        v = (ans.get(name) or {})
        p = v.get("noul") if isinstance(v, dict) else None
        if not isinstance(p, (int, float)):
            return None
        return (p >= 0.5, abs(p - 0.5) * 2)   # вероятность «да» → решение и уверенность 0..1
    return pick


def cmd_reply(a):
    ctx = "; ".join(x for x, on in (("Миле написали лично", a.dm), ("Милу назвали по имени", a.mentioned),
                                     ("это ответ на сообщение Милы", a.reply_to_me), ("пишет бот", a.from_bot)) if on) or "обычное сообщение в группе"
    q = {"reply": {"type": "noul", "instructions": "Мила — помощница в рабочей группе Telegram. Нужен ли здесь её ответ? "
                   "Да — если обращаются к ней, просят помочь или спрашивают то, что знает Мила; нет — люди говорят между собой. "
                   "Контекст: " + ctx}}
    return decide("reply", a.text, rules_reply(a), q, noul("reply"))


def cmd_who(a):
    names = [n.strip() for n in (a.names or "").split(",") if n.strip()][:200]
    r = rules_who(a.text, names)
    q = {"to": {"type": "choice", "instructions": "Кому адресовано сообщение? Не назван — «никому».",
                "criteria": {**{n: n for n in names}, "никому": "адресат не назван"}}}

    def pick(ans):
        v = ans.get("to") or {}
        ch = v.get("choice") if isinstance(v, dict) else None
        if ch not in names and ch != "никому":
            return None
        return (ch, float(v.get("confidence") or 0))
    return decide("who", a.text, r, q, pick)


def cmd_buttons(a):
    q = {"buttons": {"type": "noul", "instructions": "Это сообщение Милы человеку предлагает ему выбрать из вариантов "
                     "(А/Б, да/нет на действие)? Тогда нужны кнопки."}}
    return decide("buttons", a.text, rules_buttons(a.text), q, noul("buttons"))


def cmd_stats(a):
    rows = []
    try:
        rows = [json.loads(l) for l in open(DIFF_P, encoding="utf-8") if l.strip()]
    except (OSError, ValueError):
        pass
    by = {}
    for r in rows:
        b = by.setdefault(r["kind"], [0, 0])
        b[0] += 1
        b[1] += bool(r.get("same"))
    tot, same = len(rows), sum(1 for r in rows if r.get("same"))
    pct = round(100 * same / tot) if tot else None
    return {"rows": tot, "same_pct": pct, "by_kind": {k: {"rows": v[0], "same_pct": round(100 * v[1] / v[0])} for k, v in by.items()},
            "ready_for_main": bool(tot >= 50 and pct is not None and pct >= 90),
            "say": "Мало данных для сверки (нужно ≥ 50)" if tot < 50 else f"Совпадение {pct} % на {tot} решениях"}


def cmd_config(a):
    c = conf()
    try:
        f = json.load(open(CONF_P, encoding="utf-8"))
    except (OSError, ValueError):
        f = {}
    for s in a.set or []:
        k, _, v = s.partition("=")
        if k not in DEF:
            return {"error": f"нет настройки {k}; есть: {', '.join(DEF)}"}
        if k == "mode" and v not in ("off", "shadow", "main"):
            return {"error": "mode — off | shadow | main"}
        f[k] = type(DEF[k])(v)
    if a.set:
        os.makedirs(os.path.dirname(CONF_P), exist_ok=True)
        json.dump(f, open(CONF_P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        c = conf()
    return dict(c, key="есть" if key() else "нет")


def main():
    ap = argparse.ArgumentParser(description="Jev — быстрый разборщик Милы")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("reply"); p.add_argument("--text", required=True)
    for f in ("mentioned", "reply-to-me", "dm", "from-bot"):
        p.add_argument("--" + f, action="store_true")
    p = sp.add_parser("who"); p.add_argument("--text", required=True); p.add_argument("--names", required=True)
    p = sp.add_parser("buttons"); p.add_argument("--text", required=True)
    sp.add_parser("stats")
    p = sp.add_parser("config"); p.add_argument("--set", action="append")
    a = ap.parse_args()
    r = {"reply": cmd_reply, "who": cmd_who, "buttons": cmd_buttons, "stats": cmd_stats, "config": cmd_config}[a.cmd](a)
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(1 if "error" in r else 0)


if __name__ == "__main__":
    main()
