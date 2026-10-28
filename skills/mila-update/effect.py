#!/usr/bin/env python3
"""UPDATE-EFFECT-2810 (владелец 37034, часть Б): три числа работы Милы за окно дней — до обновления и после.
Источники — только то, что есть в любом доме Компаньона; нет источника — None («нет данных»), не ноль.
  replies — ответов в день: вызовы инструмента reply в журналах сессий (~/.claude/projects/**/*.jsonl);
  errors  — ошибок в день: строки с error/429/timeout/ECONN в журнале приёмника канала;
  tokens  — токенов в день (вход + выход + кэш-создание) по тем же журналам сессий — мера расхода без цены.
Без текстов сообщений: считаю только вызовы и числа."""
import glob, json, os, re, time

ERR = re.compile(r"\b(error|ошибк|429|timeout|timed out|ECONN\w*|ETIMEDOUT|failed)\b", re.I)


def _ts(s):
    """ISO-время журнала Claude Code → epoch; не разобрали — None."""
    if not isinstance(s, str) or len(s) < 19:
        return None
    try:
        return time.mktime(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone   # журналы — UTC
    except ValueError:
        return None


def session_files(claude):
    return glob.glob(os.path.join(claude, "projects", "**", "*.jsonl"), recursive=True)


def receiver_logs(home, claude):
    cands = [os.path.join(home, "state", "receiver.log"), os.path.join(claude, "channels", "telegram", "receiver.log"),
             os.path.join(os.environ.get("TELEGRAM_STATE_DIR", "") or os.path.join(claude, "channels", "telegram"), "receiver.log")]
    return sorted({p for p in cands if os.path.isfile(p)})


def inbound_files(home, claude):
    base = os.environ.get("TELEGRAM_STATE_DIR", "") or os.path.join(claude, "channels", "telegram")
    return sorted({p for p in (os.path.join(base, "inbound", "events.jsonl"), os.path.join(claude, "channels", "telegram", "inbound", "events.jsonl")) if os.path.isfile(p)})


def metrics(home, claude, t0, t1):
    """Средние в день за [t0, t1): {"days", "replies", "errors", "tokens"}; источника нет — значение None."""
    days = max((t1 - t0) / 86400.0, 1e-9)
    files = session_files(claude)
    replies = tokens = None
    if files:
        replies = tokens = 0
        for f in files:
            if not (t0 - 86400 <= os.path.getmtime(f)):   # файл не трогали с окна — пропускаю целиком
                continue
            try:
                fh = open(f, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with fh:
                for l in fh:
                    if '"assistant"' not in l:
                        continue
                    try:
                        d = json.loads(l)
                    except ValueError:
                        continue
                    t = _ts(d.get("timestamp"))
                    if t is None or not (t0 <= t < t1):
                        continue
                    m = d.get("message") or {}
                    u = m.get("usage") or {}
                    tokens += sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens"))
                    for c in m.get("content") or []:
                        if isinstance(c, dict) and c.get("type") == "tool_use" and str(c.get("name", "")).endswith("__reply"):
                            replies += 1
    logs = receiver_logs(home, claude)
    errors = None
    if logs:
        errors = 0
        for p in logs:
            if os.path.getmtime(p) < t0:
                continue
            for l in open(p, encoding="utf-8", errors="replace"):
                m = re.match(r"^\[?(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", l)
                t = _ts(m.group(1)) if m else None
                if t is not None and t0 <= t < t1 and ERR.search(l):
                    errors += 1
    inbound = None   # Качество 11:50 🟡1: входящие — чтобы «хозяин тише писал» не выглядело как «Мила хуже»
    ins = inbound_files(home, claude)
    if ins:
        inbound = 0
        for p in ins:
            if os.path.getmtime(p) < t0:
                continue
            for l in open(p, encoding="utf-8", errors="replace"):
                try: ts = json.loads(l).get("ts")
                except ValueError: continue
                if isinstance(ts, (int, float)) and t0 <= ts / 1000.0 < t1:
                    inbound += 1
    per = lambda v: None if v is None else round(v / days, 1)
    return {"days": round(days, 1), "inbound": per(inbound), "replies": per(replies), "errors": per(errors), "tokens": per(tokens)}


def share(m):
    """Доля отвеченных: ответов на 100 входящих; входящих меньше 3 в день или нет данных — None (по ней не сужу)."""
    i, r = m.get("inbound"), m.get("replies")
    return None if i is None or r is None or i < 3 else round(100.0 * r / i)


def compare(before, after):
    """Сравнение «до/после» → (строки хозяину простыми словами, хуже ли). Хуже: ошибок ×1,5 и ≥ 3 в день, или доля отвеченных
    (ответы на 100 входящих) упала на 30 % при ≥ 3 входящих в день до и после — «хозяин тише писал» хуже не считается (Качество 11:50)."""
    lines, worse = [], False
    def fmt(v): return "нет данных" if v is None else ("%g" % v)
    for k, name in (("inbound", "сообщений вам в день"), ("replies", "моих ответов в день"), ("errors", "сбоев в день")):
        lines.append("· %s: %s → %s" % (name, fmt(before.get(k)), fmt(after.get(k))))
    sb, sa = share(before), share(after)
    if sb is not None or sa is not None:
        lines.append("· отвечаю на %s → %s из 100 сообщений" % (fmt(sb), fmt(sa)))
    b, a = before.get("errors"), after.get("errors")
    if b is not None and a is not None and a >= 3 and a >= 1.5 * max(b, 0.1):
        worse = True
    if sb is not None and sa is not None and sb > 0 and sa <= 0.7 * sb:
        worse = True
    return lines, worse
