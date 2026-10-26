#!/usr/bin/env python3
"""mila-cron — расписание Милы, которое не теряется при перезапуске сессии (Барабан, RASPISANIE-1025 v3).
Вместо CronCreate: задача живёт в доме Милы (~/work/schedule/jobs.json), срок приходит событием через службу «Барабан»
(вне сессии; в журнал плагина — так же, как ритуалы и тики). Этот скрипт только пишет и читает файл — сам ничего не запускает.

  mila_cron.py add <id> "<cron>" "<текст>" [--by mila|owner|senior] [--word <чат>/<сообщение>] [--expires ГГГГ-ММ-ДД]
                                         [--no-expire] [--quiet respect|ignore] [--catchup one|skip]
  mila_cron.py rm <id> · pause <id> · resume <id> · extend <id> ГГГГ-ММ-ДД
  mila_cron.py next "<cron>" [N]        — ближайшие N сроков (проверка выражения до сохранения)
  mila_cron.py list [--json]           — задачи: следующий срок в поясе хозяина, последний запуск (по журналу плагина), итог
  mila_cron.py done <id> "<итог>"       — итог последнего запуска (одна строка)
  mila_cron.py import <crons.md>        — перенести «Кроны сессии» из снимка (строки «- <id> · «имя» · <cron> · …»)

Правила: id [a-z0-9-]{1,40}; cron — 5 полей, не чаще раза в 5 минут; текст ≤ 2000; задач ≤ 30; срок жизни по умолчанию 30 дней,
максимум 90 для всех — дольше только продлением (extend). by=owner|senior — только с --word (по чьему слову).
Пути: MILA_WORK (по умолчанию ~/work); пояс — «Часовой пояс — Asia/…» из USER.md, иначе Asia/Tashkent. Код 0 — ок, 1 — отказ, 2 — ошибка запуска."""
import datetime as dt, fcntl, json, os, re, sys, zoneinfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cronspec as C

WORK = os.path.expanduser(os.environ.get("MILA_WORK") or "~/work")
DIR = os.path.join(WORK, "schedule")
JOBS = os.path.join(DIR, "jobs.json")
DONE = os.path.join(DIR, "done.jsonl")
EVENTS = os.path.expanduser(os.environ.get("MILA_EVENTS") or "~/.claude/channels/telegram/inbound/events.jsonl")
ID_RE = re.compile(r"[a-z0-9-]{1,40}")
WORD_RE = re.compile(r"-?[0-9A-Za-z_]{1,40}/[0-9A-Za-z_-]{1,60}")
MAX_JOBS, MAX_TEXT, DEF_DAYS, MAX_DAYS = 30, 2000, 30, 90


def tz():
    try:
        m = re.search(r"Часовой пояс\s*[—-]\s*([A-Za-z_]+/[A-Za-z_]+)", open(os.path.join(WORK, "USER.md"), encoding="utf-8").read())
        return zoneinfo.ZoneInfo(m.group(1)) if m else zoneinfo.ZoneInfo("Asia/Tashkent")
    except (OSError, zoneinfo.ZoneInfoNotFoundError):
        return zoneinfo.ZoneInfo("Asia/Tashkent")


def now():
    v = os.environ.get("MILA_CRON_NOW")
    return dt.datetime.fromisoformat(v).astimezone(tz()) if v else dt.datetime.now(tz())


class Refuse(Exception):
    pass


def _load():
    try:
        with open(JOBS, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        return {"version": 1, "jobs": []}
    except ValueError:
        raise Refuse("jobs.json испорчен — не перезаписываю, поправьте руками или удалите")
    if not isinstance(d, dict) or not isinstance(d.get("jobs"), list):
        raise Refuse("jobs.json не того вида — не перезаписываю")
    return d


class _Locked:
    """flock на весь цикл «прочитал — изменил — записал»; запись — tmp + rename."""
    def __enter__(self):
        os.makedirs(DIR, mode=0o700, exist_ok=True)
        self.fd = os.open(os.path.join(DIR, ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.d = _load()
        return self

    def save(self):
        tmp = JOBS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.d, f, ensure_ascii=False, indent=1)
        os.chmod(tmp, 0o600); os.replace(tmp, JOBS)

    def __exit__(self, *a):
        fcntl.flock(self.fd, fcntl.LOCK_UN); os.close(self.fd)


def _spec(cron):
    try:
        s = C.parse(cron)
    except ValueError as e:
        raise Refuse("cron: %s" % e)
    if s.min_step_minutes() < C.MIN_STEP:
        raise Refuse("cron: не чаще раза в %d минут (сейчас %d)" % (C.MIN_STEP, s.min_step_minutes()))
    return s


def _date(v):
    try:
        return dt.date.fromisoformat(v)
    except ValueError:
        raise Refuse("дата «%s» — ГГГГ-ММ-ДД" % v)


def _find(d, jid):
    for j in d["jobs"]:
        if j.get("id") == jid:
            return j
    raise Refuse("задачи «%s» нет" % jid)


def add(jid, cron, text, by="mila", word="", expires="", no_expire=False, quiet="respect", catchup="one"):
    if not ID_RE.fullmatch(jid or ""):
        raise Refuse("id — [a-z0-9-], до 40 знаков")
    _spec(cron)
    text = (text or "").strip()
    if not text or len(text) > MAX_TEXT:
        raise Refuse("текст — от 1 до %d знаков" % MAX_TEXT)
    if by not in ("mila", "owner", "senior"):
        raise Refuse("by — mila, owner или senior")
    if by in ("owner", "senior") and not WORD_RE.fullmatch(word or ""):
        raise Refuse("by=%s — только с --word <чат>/<сообщение> (по чьему слову)" % by)
    if quiet not in ("respect", "ignore") or catchup not in ("one", "skip"):
        raise Refuse("quiet — respect|ignore, catchup — one|skip")
    today = now().date()
    if no_expire:   # Качество 26.10: «вечная» задача тратит подписку молча, а --word проверяется только по виду — без срока нет ни у кого
        raise Refuse("без срока нельзя: максимум %d дней; нужно дольше — extend, когда придёт «продлить?»" % MAX_DAYS)
    exp = _date(expires) if expires else today + dt.timedelta(days=DEF_DAYS)
    if exp <= today or exp > today + dt.timedelta(days=MAX_DAYS):
        raise Refuse("срок жизни — от завтра до %d дней вперёд" % MAX_DAYS)
    with _Locked() as lk:
        d = lk.d
        if any(j.get("id") == jid for j in d["jobs"]):
            raise Refuse("задача «%s» уже есть — rm или другой id" % jid)
        if len(d["jobs"]) >= MAX_JOBS:
            raise Refuse("задач уже %d — больше нельзя" % MAX_JOBS)
        rec = {"id": jid, "cron": cron, "text": text, "by": by, "word": word or "", "created": now().isoformat(timespec="minutes"),
               "expires": exp.isoformat() if exp else None, "quiet": quiet, "catchup": catchup, "enabled": True}
        d["jobs"].append(rec)
        lk.save()
    return rec


def _mutate(jid, fn):
    with _Locked() as lk:
        j = _find(lk.d, jid); fn(lk.d, j); lk.save(); return j


def rm(jid):
    return _mutate(jid, lambda d, j: d["jobs"].remove(j))


def pause(jid):
    return _mutate(jid, lambda d, j: j.update(enabled=False))


def resume(jid):
    return _mutate(jid, lambda d, j: j.update(enabled=True))


def extend(jid, date):
    e = _date(date); today = now().date()
    if e <= today or e > today + dt.timedelta(days=MAX_DAYS):
        raise Refuse("срок жизни — от завтра до %d дней вперёд" % MAX_DAYS)
    return _mutate(jid, lambda d, j: j.update(expires=e.isoformat(), enabled=True))


def next_runs(cron, n=5):
    s = _spec(cron); t = now(); out = []
    for _ in range(max(1, min(int(n), 20))):
        t = s.next_after(t); out.append(t)
    return out


def last_runs():
    """id → время последнего события расписания в журнале плагина (message_id cron-<slug>-<id>-<срок>)."""
    out = {}
    try:
        with open(EVENTS, encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"cron-' not in line:
                    continue
                try:
                    m = json.loads(line)["params"]["meta"]
                except (ValueError, KeyError, TypeError):
                    continue
                if m.get("ritual") == "cron" and m.get("job"):
                    out[m["job"]] = m.get("ts") or out.get(m["job"])
    except OSError:
        pass
    return out


def done(jid, result):
    with _Locked() as lk:
        _find(lk.d, jid)
    with open(DONE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": jid, "at": now().isoformat(timespec="minutes"), "result": str(result)[:300]}, ensure_ascii=False) + "\n")
    return True


def results():
    out = {}
    try:
        for line in open(DONE, encoding="utf-8"):
            try:
                r = json.loads(line); out[r["id"]] = r
            except (ValueError, KeyError):
                pass
    except OSError:
        pass
    return out


def listing():
    d = _load(); last = last_runs(); res = results(); t = now(); rows = []
    for j in d["jobs"]:
        try:
            nx = C.parse(j["cron"]).next_after(t).isoformat(timespec="minutes") if j.get("enabled") else None
        except ValueError:
            nx = None
        exp = j.get("expires")
        rows.append(dict(j, next=nx, last=last.get(j["id"]), result=(res.get(j["id"]) or {}).get("result"),
                         expired=bool(exp and dt.date.fromisoformat(exp) < t.date())))
    return rows


def import_md(path):
    """«Кроны сессии» из снимка: «- <id> · «имя» · <cron> · …» → задачи by=mila (id = c-<id>)."""
    out, skipped = [], []
    on = False
    for line in open(path, encoding="utf-8"):
        if line.startswith("## "):
            on = "крон" in line.lower(); continue
        m = re.match(r"-\s*([0-9a-z]+)\s*·\s*«([^»]+)»\s*·\s*([0-9*/,\- ]+?)\s*·", line.strip()) if on else None
        if not m:
            continue
        jid = ("c-" + m.group(1))[:40]
        try:
            out.append(add(jid, m.group(3).strip(), m.group(2).strip()))
        except Refuse as e:
            skipped.append("%s: %s" % (jid, e))
    return out, skipped


def main(argv):
    if not argv:
        print(__doc__); return 2
    cmd, a = argv[0], argv[1:]
    opt = {}
    pos = []
    i = 0
    while i < len(a):
        if a[i].startswith("--"):
            k = a[i][2:].replace("-", "_")
            if k in ("no_expire", "json"):
                opt[k] = True; i += 1
            else:
                if i + 1 >= len(a):
                    print("нет значения у --%s" % k); return 2
                opt[k] = a[i + 1]; i += 2
        else:
            pos.append(a[i]); i += 1
    try:
        if cmd == "add" and len(pos) == 3:
            r = add(*pos, by=opt.get("by", "mila"), word=opt.get("word", ""), expires=opt.get("expires", ""), no_expire=opt.get("no_expire", False),
                    quiet=opt.get("quiet", "respect"), catchup=opt.get("catchup", "one"))
            print("добавлена %s · %s · живёт до %s · ближайший срок %s" % (r["id"], r["cron"], r["expires"] or "без срока",
                                                                       next_runs(r["cron"], 1)[0].strftime("%d.%m %H:%M")))
        elif cmd in ("rm", "pause", "resume") and len(pos) == 1:
            {"rm": rm, "pause": pause, "resume": resume}[cmd](pos[0]); print("%s: %s" % (cmd, pos[0]))
        elif cmd == "extend" and len(pos) == 2:
            extend(*pos); print("продлена %s до %s" % tuple(pos))
        elif cmd == "next" and pos:
            for t in next_runs(pos[0], pos[1] if len(pos) > 1 else 5):
                print(t.strftime("%a %d.%m %H:%M %Z"))
        elif cmd == "list":
            rows = listing()
            if opt.get("json"):
                print(json.dumps(rows, ensure_ascii=False, indent=1))
            elif not rows:
                print("задач нет")
            for r in ([] if opt.get("json") else rows):
                print("%s · %s · %s · следующий %s · последний %s%s%s" % (
                    r["id"], r["cron"], "вкл" if r["enabled"] else "пауза", (r["next"] or "—")[:16], (r["last"] or "—")[:16],
                    " · ИСТЕКЛА" if r["expired"] else "", (" · итог: " + r["result"]) if r.get("result") else ""))
        elif cmd == "done" and len(pos) == 2:
            done(*pos); print("итог записан: %s" % pos[0])
        elif cmd == "import" and len(pos) == 1:
            out, skipped = import_md(pos[0])
            print("перенесено %d%s" % (len(out), ("; пропущено: " + "; ".join(skipped)) if skipped else ""))
        else:
            print(__doc__); return 2
    except Refuse as e:
        print("отказ: %s" % e); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
