#!/usr/bin/env python3
"""jev.py — быстрый разборщик для Милы (ROLLOUT №25, слой ядра «Проводник»): за ~0,5 с ответить на узкий вопрос
«отвечать ли мне», «кому это», «нужны ли кнопки» — без большой модели. Нет шлюза Jev, не ответил за 1,2 с, не уверен —
решают простые правила, Мила работает как раньше.

  jev.py reply   --text T [--mentioned] [--reply-to-me] [--dm] [--from-bot]   — отвечать ли Миле на сообщение в группе
                 [--chat-role lead|mention] [--quote-author me|bot|human] [--to-other]
                 (lead — чат веду я: отвечаю на всё, кроме адресованного другим; quote-author — чьё сообщение процитировали;
                  to-other — в тексте назван другой бот или другая Мила)
  (--text - : текст из stdin, не виден в ps)
  jev.py who     --text T --names "Мила Контент,Чат Реклама,…"                  — кому адресовано (или «никому»)
  jev.py buttons --text T                                                       — мой ответ — выбор для человека? (А/Б → кнопки)
  jev.py check   --file sample.jsonl                                            — сверка с правдой: строки {text, флаги reply, truth}
                 (truth — настоящий ход Милы: ответила или нет); итог без текстов — в ~/.claude/jev-check.json
  jev.py stats                                                                  — готовность к main (по сверке с правдой) + журнал shadow
  jev.py config [--set mode=off|shadow|main] [--set url=…] [--set site=…]      — настройки (~/.claude/jev.json)

Режимы: off — только правила (по умолчанию, открытый продукт без нашего сервера); shadow — решают правила, Jev спрашиваем
и пишем расхождения в ~/.claude/jev-diff.jsonl; main — решает Jev, если уверен (≥ min_conf), иначе правила.
Ключ шлюза — env JEV_KEY или ~/secrets/jev.key (заголовок X-Jev-Key), не печатаю. Ответ — JSON {decision, source, conf, ms}.
Готовность к main (ROLLOUT №32, сверка 27.10): только по сверке с правдой — ≥ 100 разных сообщений, Jev ≥ 90 % и не хуже правил.
Согласие Jev с правилами в shadow — не мерило: оба могут ошибаться одинаково («100 % на 62 одинаковых пробах»)."""
import argparse, hashlib, json, os, re, sys, time, urllib.request

HOME = os.path.expanduser("~")
CONF_P = os.path.join(HOME, ".claude", "jev.json")
DIFF_P = os.path.join(HOME, ".claude", "jev-diff.jsonl")
CHECK_P = os.path.join(HOME, ".claude", "jev-check.json")
READY_ROWS, READY_PCT = 100, 90
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


def quote_author(a):
    return "me" if a.reply_to_me else (getattr(a, "quote_author", None) or "")


def rules_reply(a):
    if a.dm or a.mentioned or quote_author(a) == "me":
        return not (a.from_bot and a.dm and not (a.mentioned or quote_author(a) == "me"))   # бот в личке без имени — молчу
    if a.from_bot:
        return False                      # боты между собой — только по имени
    if getattr(a, "chat_role", None) == "lead":   # чат веду я: отвечаю на всё, кроме адресованного другим (сверка 27.10: 388 из 399 промахов)
        return not (getattr(a, "to_other", False) or quote_author(a) == "bot")
    return False


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


def reply_ctx(a):
    qa = quote_author(a)
    return "; ".join(x for x, on in (
        ("чат ведёт Мила — она отвечает на всё, кроме адресованного другим" if getattr(a, "chat_role", None) == "lead" else
         "Мила в этом чате отвечает только когда к ней обращаются", True),
        ("Миле написали лично", a.dm), ("Милу назвали по имени", a.mentioned), ("это ответ на сообщение Милы", qa == "me"),
        ("это ответ на сообщение другого бота", qa == "bot"), ("это ответ на сообщение человека", qa == "human"),
        ("в тексте назван другой бот или другая Мила", getattr(a, "to_other", False)), ("пишет бот", a.from_bot)) if on)


def cmd_reply(a):
    ctx = reply_ctx(a)
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


class Row:
    """Строка сверки → те же поля, что у reply из командной строки."""
    def __init__(self, d):
        self.text = str(d.get("text") or "")[:4000]
        for k in ("dm", "mentioned", "reply_to_me", "from_bot", "to_other"):
            setattr(self, k, bool(d.get(k)))
        self.chat_role = d.get("chat_role") if d.get("chat_role") in ("lead", "mention") else None
        self.quote_author = d.get("quote_author") if d.get("quote_author") in ("me", "bot", "human") else None


def cmd_check(a):
    """Сверка с правдой: на каждой строке правила и Jev против настоящего хода. Тексты не сохраняю — только счёт."""
    c = conf()
    if not c["url"]:
        return {"error": "нет адреса шлюза (jev.py config --set url=…)"}
    rows, seen = [], set()
    try:
        for l in open(a.file, encoding="utf-8"):
            if not l.strip():
                continue
            d = json.loads(l)
            if not isinstance(d, dict) or not isinstance(d.get("truth"), bool) or not str(d.get("text") or "").strip():
                continue
            r = Row(d)   # ключ дедупа — все поля, по которым решают правила и Jev (Качество 27.10: иначе «мне или другому» склеивались)
            h = hashlib.sha256(json.dumps([r.text, r.dm, r.mentioned, r.reply_to_me, r.from_bot, r.to_other, r.chat_role, r.quote_author], ensure_ascii=False).encode()).hexdigest()
            if h in seen:
                continue                  # одинаковые пробы считаю один раз
            seen.add(h); rows.append((r, d["truth"]))
    except (OSError, ValueError) as e:
        return {"error": "файл сверки не прочитан: %s" % type(e).__name__}
    n = jev_ok = rules_ok = answered = 0
    for r, truth in rows:
        q = {"reply": {"type": "noul", "instructions": "Мила — помощница в рабочей группе Telegram. Нужен ли здесь её ответ? "
                       "Да — если обращаются к ней, просят помочь или спрашивают то, что знает Мила; нет — люди говорят между собой. "
                       "Контекст: " + reply_ctx(r)}}
        ans = ask(c, r.text, q); j = noul("reply")(ans) if ans else None
        if n == 4 and not answered and not j:
            return {"error": "шлюз Jev не ответил на 5 строк подряд — сверка не начата"}
        n += 1; rules_ok += rules_reply(r) == truth
        if j:
            answered += 1; jev_ok += j[0] == truth
    pj = round(100 * jev_ok / n) if n else None
    pr = round(100 * rules_ok / n) if n else None
    res = {"ts": int(time.time()), "rows": n, "jev_answered": answered, "jev_pct": pj, "rules_pct": pr}
    os.makedirs(os.path.dirname(CHECK_P), exist_ok=True)
    json.dump(res, open(CHECK_P, "w", encoding="utf-8"), ensure_ascii=False)
    return dict(res, ready_for_main=ready(res))


def ready(chk_):
    return bool(chk_ and chk_.get("rows", 0) >= READY_ROWS and chk_.get("jev_pct") is not None and chk_["jev_pct"] >= READY_PCT
                and chk_["jev_pct"] >= (chk_.get("rules_pct") or 0))


def load_check():
    try:
        d = json.load(open(CHECK_P, encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


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
    ch = load_check()
    if not ch:
        say = "Нет сверки с правдой: jev.py check --file <выборка с настоящими ходами>. Согласие с правилами — не мерило"
    elif ready(ch):
        say = f"Сверка с правдой: Jev {ch['jev_pct']} %, правила {ch['rules_pct']} % на {ch['rows']} разных сообщениях — можно main"
    else:
        say = (f"Сверка с правдой: Jev {ch['jev_pct']} %, правила {ch['rules_pct']} % на {ch['rows']} разных сообщениях — для main нужно "
               f"≥ {READY_ROWS} сообщений, Jev ≥ {READY_PCT} % и не хуже правил")
    return {"rows": tot, "same_pct": pct, "by_kind": {k: {"rows": v[0], "same_pct": round(100 * v[1] / v[0])} for k, v in by.items()},
            "check": ch, "ready_for_main": ready(ch), "say": say}


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
        if k == "mode" and v == "main" and not ready(load_check()):
            return {"error": f"main — только после сверки с правдой (jev.py check): ≥ {READY_ROWS} сообщений, Jev ≥ {READY_PCT} % и не хуже правил"}
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
    for f in ("mentioned", "reply-to-me", "dm", "from-bot", "to-other"):
        p.add_argument("--" + f, action="store_true")
    p.add_argument("--chat-role", choices=("lead", "mention")); p.add_argument("--quote-author", choices=("me", "bot", "human"))
    p = sp.add_parser("check"); p.add_argument("--file", required=True)
    p = sp.add_parser("who"); p.add_argument("--text", required=True); p.add_argument("--names", required=True)
    p = sp.add_parser("buttons"); p.add_argument("--text", required=True)
    sp.add_parser("stats")
    p = sp.add_parser("config"); p.add_argument("--set", action="append")
    a = ap.parse_args()
    if getattr(a, "text", None) == "-":   # JEV-STDIN-1022: текст из stdin — не виден в списке процессов (ps)
        a.text = sys.stdin.read()[:4000]
    r = {"reply": cmd_reply, "who": cmd_who, "buttons": cmd_buttons, "check": cmd_check, "stats": cmd_stats, "config": cmd_config}[a.cmd](a)
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(1 if "error" in r else 0)


if __name__ == "__main__":
    main()
