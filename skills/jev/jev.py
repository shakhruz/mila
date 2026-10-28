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
  jev.py skill   --text T [--catalog путь|адрес]                                — 1–3 навыка каталога под задачу (стоящие и нет)
  jev.py check   --kind skill --file tasks.jsonl                               — сверка навыков: {text, truth: [навыки]}, ≥ 50 задач
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
CAT_CACHE = os.path.join(HOME, ".claude", "jev-catalog.json")
CAT_TTL = 86400
CATALOG_URL = "https://milagpt.io/navyki/catalog.json"
CHECK_SKILL_P = os.path.join(HOME, ".claude", "jev-check-skill.json")
SKILL_ROWS, SKILL_PCT = 50, 80   # навык под задачу: в main — по сверке на ≥ 50 настоящих задачах, попал в тройку ≥ 80 % и не хуже правил   # тот же, что DEFAULT_CATALOG в mila-update
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


def log_diff(kind, text, rules, jev, conf_, ms=None, why=None, mode=None):
    """Строка журнала решения (без текста — только длина). BARABAN-2810 (старшая 10:10): пишу и молчание шлюза —
    jev=None, why «таймаут» | «нет ответа»; ms — время; mode — shadow | main."""
    try:
        os.makedirs(os.path.dirname(DIFF_P), exist_ok=True)
        rec = {"ts": int(time.time()), "kind": kind, "len": len(text), "rules": rules, "jev": jev, "conf": conf_, "same": rules == jev}
        if ms is not None: rec["ms"] = ms
        if why: rec["why"] = why
        if mode: rec["mode"] = mode
        with open(DIFF_P, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
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
    silent = None if j else ("таймаут" if ms >= int(c["timeout"] * 1000 * 0.95) else "нет ответа")
    log_diff(kind, text, rules, j[0] if j else None, round(j[1], 2) if j else None, ms, silent, c["mode"])   # и shadow, и main; молчание — тоже
    if c["mode"] == "shadow":
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


# --- skill: какие навыки каталога подходят задаче (КАТАЛОГ-НАВЫКОВ-2810, шаг 2) ---
STOP = set("это как что для или его она они мне вам нас вас при над под без про уже еще ещё все всё так там тут где когда надо нужно можно сделай сделать хочу".split())


def stems(s):
    """Основа слова: до 5 букв, у коротких — без окончания («звука» и «звук» → «звук»)."""
    return {w[:min(5, max(4, len(w) - 2))] for w in re.findall(r"[а-яёa-z0-9]+", s.lower().replace("ё", "е")) if len(w) >= 4 and w not in STOP}


def load_catalog(src=None):
    """catalog.json: --catalog, иначе MILA_CATALOG_URL, иначе catalog_url из настроек mila-update (по умолчанию CATALOG_URL,
    "" — выключен); адрес — кэш на сутки."""
    if not src:
        src = os.environ.get("MILA_CATALOG_URL", "")
    if not src:
        try:
            src = json.load(open(os.path.join(HOME, ".claude", "mila-update.json"), encoding="utf-8")).get("catalog_url", CATALOG_URL)
        except (OSError, ValueError, AttributeError):
            src = CATALOG_URL
    if not src:
        return None, "адрес каталога не задан (mila-update config --set catalog_url=…)"
    web = bool(re.match(r"https?://", src))
    try:
        if web:
            try:
                cc = json.load(open(CAT_CACHE, encoding="utf-8"))
                if cc.get("src") == src and time.time() - cc.get("t", 0) < CAT_TTL:
                    return cc["catalog"], None
            except (OSError, ValueError, KeyError, AttributeError):
                pass
            with urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "mila-jev"}), timeout=10) as r:
                cat = json.loads(r.read().decode("utf-8"))
        else:
            cat = json.load(open(src, encoding="utf-8"))
        if not isinstance(cat, dict) or not isinstance(cat.get("skills"), list):
            raise ValueError("нет списка skills")
    except Exception as e:
        return None, "каталог недоступен: %s" % type(e).__name__
    if web:
        try:
            json.dump({"src": src, "t": int(time.time()), "catalog": cat}, open(CAT_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        except OSError:
            pass
    return cat, None


def rules_skill(text, skills, k=3):
    """Совпадение основ слов задачи со строкой «что даёт» и именем навыка; редкое слово весит больше частого (idf).
    Ни одного совпадения — не предлагаю."""
    import math
    docs = [(s["name"], stems(s.get("gives", "") + " " + s["name"].replace("-", " "))) for s in skills]
    df = {}
    for _, d in docs:
        for w in d: df[w] = df.get(w, 0) + 1
    st, n = stems(text), max(len(docs), 1)
    sc = [(-sum(math.log(1 + n / df[w]) for w in st & d), name) for name, d in docs if st & d]
    return [name for _, name in sorted(sc)[:k]]


def skill_q(skills):
    """Вопрос Jev — выбор одного навыка из всего каталога, кроме служебных (28.10: «да/нет» по 8 кандидатам правил давал 27 %,
    выбор из 122 навыков — 50 % первым же ответом на 30 задачах владельца: правила не приводят нужный навык в кандидаты)."""
    pool = [s for s in skills if s.get("who") != "наша Мила"][:200]
    crit = {s["name"]: str(s.get("gives") or s["name"])[:160] for s in pool}
    crit["никакой"] = "ни один навык не подходит"
    return {"skill": {"type": "choice", "instructions": "Какой навык Милы лучше всего поможет с задачей человека из текста? "
                      "Не подходит ни один — «никакой».", "criteria": crit}}, set(crit)


def skill_pick(names, rules):
    """Ответ Jev → (тройка, уверенность): выбор Jev первым, к нему — до двух от правил; «никакой» — пусто."""
    def pick(ans):
        v = ans.get("skill") or {}
        ch = v.get("choice") if isinstance(v, dict) else None
        if ch not in names:
            return None
        top = [] if ch == "никакой" else [ch] + [x for x in rules if x != ch][:2]
        return (top, float(v.get("confidence") or 0))
    return pick


def cmd_skill(a):
    cat, err = load_catalog(getattr(a, "catalog", None))
    if err:
        return {"error": err}
    skills = [s for s in cat["skills"] if isinstance(s, dict) and isinstance(s.get("name"), str)]
    by = {s["name"]: s for s in skills}
    sd = os.path.join(HOME, ".claude", "skills")
    have = set(os.listdir(sd)) if os.path.isdir(sd) else set()
    r = rules_skill(a.text, skills)
    q, names = skill_q(skills)
    if conf()["mode"] == "main" and not ready_skill(load_json(CHECK_SKILL_P)):
        os.environ["JEV_MODE"] = "shadow"   # main для «кому/отвечать» не открывает навыки: у них своя сверка (check --kind skill)
    res = decide("skill", a.text, r, q, skill_pick(names, r))
    res["skills"] = [{"name": n, "gives": by[n].get("gives"), "price": by[n].get("price"), "installed": n in have} for n in res["decision"] if n in by]
    return res


def load_json(p):
    try:
        d = json.load(open(p, encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def ready_skill(ch):
    return bool(ch and ch.get("rows", 0) >= SKILL_ROWS and ch.get("jev_pct") is not None and ch["jev_pct"] >= SKILL_PCT
                and ch["jev_pct"] >= (ch.get("rules_pct") or 0))


def check_skill(a, c):
    """Сверка навыков: строки {text, truth: [имена навыков, которые на деле пригодились]}; попадание — хоть один из тройки в truth."""
    cat, err = load_catalog(getattr(a, "catalog", None))
    if err:
        return {"error": err}
    skills = [s for s in cat["skills"] if isinstance(s, dict) and isinstance(s.get("name"), str)]
    by = {s["name"]: s for s in skills}
    rows, seen = [], set()
    try:
        for l in open(a.file, encoding="utf-8"):
            if not l.strip(): continue
            d = json.loads(l)
            tr = d.get("truth") if isinstance(d, dict) else None
            tx = str(d.get("text") or "").strip()[:4000] if isinstance(d, dict) else ""
            if not tx or not isinstance(tr, list) or not tr or tx in seen: continue
            seen.add(tx); rows.append((tx, {x for x in tr if x in by}))
    except (OSError, ValueError) as e:
        return {"error": "файл сверки не прочитан: %s" % type(e).__name__}
    n = jev_ok = rules_ok = answered = 0
    q, names = skill_q(skills)
    for tx, truth in rows:
        rr = rules_skill(tx, skills)
        n += 1; rules_ok += bool(set(rr) & truth)
        ans = ask(c, tx, q); j = skill_pick(names, rr)(ans) if ans else None
        if j:
            answered += 1; jev_ok += bool(set(j[0]) & truth)
        elif n >= 5 and not answered:
            return {"error": "шлюз Jev не ответил на 5 строк подряд — сверка не начата"}
    res = {"ts": int(time.time()), "kind": "skill", "rows": n, "jev_answered": answered,
           "jev_pct": round(100 * jev_ok / n) if n else None, "rules_pct": round(100 * rules_ok / n) if n else None}
    os.makedirs(os.path.dirname(CHECK_SKILL_P), exist_ok=True)
    json.dump(res, open(CHECK_SKILL_P, "w", encoding="utf-8"), ensure_ascii=False)
    return dict(res, ready_for_main=ready_skill(res))


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
    if getattr(a, "kind", "reply") == "skill":
        return check_skill(a, c)
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
    since = time.time() - float(getattr(a, "hours", 0) or 0) * 3600 if getattr(a, "hours", None) else 0
    rows = [r for r in rows if r.get("ts", 0) >= since]
    by = {}
    for r in rows:
        b = by.setdefault(r["kind"], [0, 0])
        b[0] += 1
        b[1] += bool(r.get("same"))
    answered = [r for r in rows if r.get("jev") is not None]
    hi_ = [r for r in answered if (r.get("conf") or 0) >= 0.7]
    calls = {"calls": len(rows), "conf_ge_0_7": len(hi_), "conf_lt_0_7": len(answered) - len(hi_),
             "timeout": sum(1 for r in rows if r.get("why") == "таймаут"), "no_answer": sum(1 for r in rows if r.get("why") == "нет ответа"),
             "same_as_rules": sum(1 for r in answered if r.get("same")), "same_as_rules_conf_ge_0_7": sum(1 for r in hi_ if r.get("same")),
             "by_kind": {k: sum(1 for r in rows if r.get("kind") == k) for k in sorted({r.get("kind") for r in rows})}}
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
            "check": ch, "ready_for_main": ready(ch), "say": say, "calls": calls,
            "check_skill": load_json(CHECK_SKILL_P), "skill_ready_for_main": ready_skill(load_json(CHECK_SKILL_P))}


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
    p = sp.add_parser("check"); p.add_argument("--file", required=True); p.add_argument("--kind", choices=("reply", "skill"), default="reply")
    p.add_argument("--catalog")
    p = sp.add_parser("who"); p.add_argument("--text", required=True); p.add_argument("--names", required=True)
    p = sp.add_parser("buttons"); p.add_argument("--text", required=True)
    p = sp.add_parser("skill"); p.add_argument("--text", required=True); p.add_argument("--catalog")
    p = sp.add_parser("stats"); p.add_argument("--hours", type=float, help="только последние N часов (например 24)")
    p = sp.add_parser("config"); p.add_argument("--set", action="append")
    a = ap.parse_args()
    if getattr(a, "text", None) == "-":   # JEV-STDIN-1022: текст из stdin — не виден в списке процессов (ps)
        a.text = sys.stdin.read()[:4000]
    r = {"reply": cmd_reply, "who": cmd_who, "buttons": cmd_buttons, "skill": cmd_skill, "check": cmd_check, "stats": cmd_stats, "config": cmd_config}[a.cmd](a)
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(1 if "error" in r else 0)


if __name__ == "__main__":
    main()
