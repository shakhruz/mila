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
    per = lambda v: None if v is None else round(v / days, 1)
    return {"days": round(days, 1), "replies": per(replies), "errors": per(errors), "tokens": per(tokens)}


def compare(before, after):
    """Сравнение «до/после» → (строки хозяину, хуже ли). Хуже: ошибок ×1,5 и больше (и не меньше 3 в день) или ответов −30 %."""
    lines, worse = [], False
    def fmt(v): return "нет данных" if v is None else ("%g" % v)
    for k, name in (("replies", "ответов в день"), ("errors", "ошибок в день"), ("tokens", "токенов в день")):
        b, a = before.get(k), after.get(k)
        lines.append("· %s: %s → %s" % (name, fmt(b), fmt(a)))
    b, a = before.get("errors"), after.get("errors")
    if b is not None and a is not None and a >= 3 and a >= 1.5 * max(b, 0.1):
        worse = True
    b, a = before.get("replies"), after.get("replies")
    if b is not None and a is not None and b >= 3 and a <= 0.7 * b:
        worse = True
    return lines, worse
