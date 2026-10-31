#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Самодиагностика канала: почему бот молчит.

Когда канал не работает, человек видит тишину. Тишина одинакова во всех
случаях: нет токена, бот не добавлен в группу, включён режим приватности у
BotFather, забыт флаг запуска, умер демон, мост не читает журнал, права файлов
не те. Найти причину, не зная устройства, невозможно — а ставить это будут
люди, которые устройства не знают.

Сюда же входит учёт (records.py): базы разговоров и внешних трат проверяются
теми же тремя вопросами — есть ли файл, полна ли схема, растёт ли он. Учёт,
который перестал писать, выглядит как спокойный день.

Здесь проверяется каждое звено по очереди, и у каждой проверки есть ответ на
вопрос «что делать», а не только «плохо». Проверки идут от простого к сложному
и не прекращаются на первой ошибке: часто сломано не одно.

Ничего не чинит сам. Диагност, который лечит без спроса, — это не диагност.

  doctor.py            # проверить всё
  doctor.py --json     # для машины

Язык вывода — язык владельца: MILA_LANG, иначе "lang" из ~/work/owner.json, иначе LANG, иначе английский.
Строки — locales/<код>.json рядом (ru, en; нет строки — английская), новый язык — один файл.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mila_i18n  # noqa: E402 — рядом (install.sh кладёт в hooks вместе с locales/)

LOC = mila_i18n.load(os.environ.get("MILA_LOCALES") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales"))


def _lang():
    """Язык вывода: MILA_LANG → язык владельца (~/work/owner.json) → LANG/LC_ALL → en."""
    owner = None
    try:
        with open(os.environ.get("OWNER_JSON") or os.path.expanduser("~/work/owner.json"), encoding="utf-8") as f:
            owner = json.load(f).get("lang")
    except (OSError, ValueError, AttributeError):
        pass
    env = [(os.environ.get(k) or "").split(".")[0] for k in ("LC_ALL", "LANG")]
    return mila_i18n.pick(LOC, os.environ.get("MILA_LANG"), owner if isinstance(owner, str) else None, [e for e in env if e and e not in ("C", "POSIX")])


LANG = _lang()


def T(key):
    return mila_i18n.t(LOC, LANG, key)

STATE = os.environ.get("TELEGRAM_STATE_DIR",
                       os.path.expanduser("~/.claude/channels/telegram"))
ENV_FILE = os.path.join(STATE, ".env")
ACCESS = os.path.join(STATE, "access.json")
INBOUND = os.path.join(STATE, "inbound")
EVENTS = os.path.join(INBOUND, "events.jsonl")
CURSOR = os.path.join(INBOUND, "cursor")
CHATS_DIR = os.path.join(STATE, "chats")

OK, WARN, BAD = "ok", "warn", "bad"


class Report:
    def __init__(self):
        self.rows = []

    def add(self, level, name, detail, fix=""):
        self.rows.append({"level": level, "name": name, "detail": detail, "fix": fix})

    @property
    def bad(self):
        return [r for r in self.rows if r["level"] == BAD]

    @property
    def warn(self):
        return [r for r in self.rows if r["level"] == WARN]


def read_token():
    """Токен из окружения важнее файла — так же, как его читает сервер."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    if tok:
        return tok.strip(), T("doctor.read_token.1")
    try:
        for line in open(ENV_FILE, encoding="utf-8"):
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"\''), ENV_FILE
    except OSError:
        pass
    return None, None


def api(token, method, timeout=12):
    url = "https://api.telegram.org/bot%s/%s" % (token, method)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        # Токен не должен утечь в текст ошибки — его вырезаем всегда.
        msg = str(e).replace(token, "<token>") if token else str(e)
        return {"ok": False, "error": msg}


def running(pattern):
    """[(pid, командная строка)] — кроссплатформенно.

    `pgrep -fa` отдаёт командную строку на Linux и молча игнорирует -a на
    macOS, возвращая одни pid. Диагност, написанный на Linux, на macOS
    отвечал «код: неизвестно» и «сессия не найдена» при живых процессах —
    то есть врал ровно в том, ради чего его писали. Спрашиваем pid у pgrep,
    а команду у ps: так работает везде.
    """
    try:
        out = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", pattern],   # только свои процессы: демон соседнего дома — не мой
                             capture_output=True, text=True, timeout=8).stdout
    except Exception:
        return []
    pids = [p for p in out.split() if p.isdigit() and p != str(os.getpid())]
    rows = []
    for pid in pids:
        try:
            cmd = subprocess.run(["ps", "-p", pid, "-o", "command="],
                                 capture_output=True, text=True, timeout=8).stdout.strip()
        except Exception:
            cmd = ""
        if cmd and "pgrep" not in cmd:
            rows.append((pid, cmd))
    return rows


def check_token(rep):
    token, src = read_token()
    if not token:
        rep.add(BAD, T("doctor.token.1"), T("doctor.token.2"),
                T("doctor.token.3"))
        return None
    if not re.match(r"^\d{8,12}:[A-Za-z0-9_-]{30,}$", token):
        rep.add(BAD, T("doctor.token.1"), T("doctor.token.5") % len(token),
                T("doctor.token.6"))
        return None

    me = api(token, "getMe")
    if not me.get("ok"):
        # `%` связывает крепче, чем `or`: раньше выражение сводилось к
        # («…: %s» % error) or description, поэтому description не читался
        # никогда, а на живом отказе печаталось «None». «Unauthorized» и
        # «Conflict: terminated by other getUpdates» лечатся противоположно —
        # клиент выпускал новый токен там, где надо было убить второй процесс.
        rep.add(BAD, T("doctor.token.1"), T("doctor.token.8")
                % (me.get("description") or me.get("error") or T("doctor.token.9")),
                T("doctor.token.10"))
        return None
    u = me["result"]
    rep.add(OK, T("doctor.token.11"), T("doctor.token.12")
            % (u.get("username"), u.get("first_name"), src))
    return token


def check_privacy(rep, token):
    """Режим приватности решает, дойдут ли сообщения из групп вообще."""
    me = api(token, "getMe")
    u = me.get("result") or {}
    can_read = u.get("can_read_all_group_messages")
    if can_read is True:
        rep.add(OK, T("doctor.privacy.1"), T("doctor.privacy.2"))
    elif can_read is False:
        rep.add(WARN, T("doctor.privacy.1"),
                T("doctor.privacy.4"),
                T("doctor.privacy.5"))
    else:
        rep.add(WARN, T("doctor.privacy.1"), T("doctor.privacy.7"), "")


def check_access(rep):
    try:
        a = json.load(open(ACCESS, encoding="utf-8"))
    except FileNotFoundError:
        rep.add(WARN, T("doctor.access.1"), T("doctor.access.2"),
                T("doctor.access.3"))
        return
    except json.JSONDecodeError as e:
        rep.add(BAD, T("doctor.access.1"), T("doctor.access.5") % e,
                T("doctor.access.6"))
        return

    allow = a.get("allowFrom") or []
    owners = a.get("owners") or []
    groups = a.get("groups") or {}
    policy = a.get("dmPolicy", "pairing")

    if not allow:
        rep.add(WARN, T("doctor.access.7"), T("doctor.access.8"),
                T("doctor.access.9"))
    else:
        rep.add(OK, T("doctor.access.7"), T("doctor.access.11") % (len(allow), policy))

    if policy == "pairing" and allow:
        rep.add(WARN, T("doctor.access.7"), T("doctor.access.13"),
                T("doctor.access.14"))

    if len(allow) > 1 and not owners:
        rep.add(WARN, T("doctor.access.15"), T("doctor.access.16") % len(allow),
                T("doctor.access.17"))
    elif owners:
        rep.add(OK, T("doctor.access.15"), T("doctor.access.19") % (len(owners), len(allow)))

    rep.add(OK if groups else WARN, T("doctor.access.20"),
            T("doctor.access.21") % len(groups),
            "" if groups else T("doctor.access.22"))

    loud = [g for g, p in groups.items()
            if isinstance(p, dict) and p.get("requireMention") is False
            and not p.get("readOnly") and not p.get("observe")]
    if loud:
        rep.add(WARN, T("doctor.access.20"),
                T("doctor.access.24") % len(loud),
                T("doctor.access.25"))


def own_receivers(lines):
    """Только демон ЭТОГО дома: pid из <state>/receiver.pid; без файла — по TELEGRAM_STATE_DIR в окружении процесса.
    Соседняя Мила под тем же пользователем — не моя (у неё свой каталог состояния)."""
    try:
        mine = open(os.path.join(STATE, "receiver.pid")).read().strip()
    except OSError:
        mine = ""
    if mine and any(pid == mine for pid, _ in lines):
        return [(pid, cmd) for pid, cmd in lines if pid == mine]
    st = os.path.realpath(STATE); out = []
    for pid, cmd in lines:
        env = _proc_env(pid)
        if env is None or os.path.realpath(env.get("TELEGRAM_STATE_DIR") or os.path.expanduser("~/.claude/channels/telegram")) == st:
            out.append((pid, cmd))   # окружение не прочитать (macOS) — считаю своим, как раньше
    return out


def own_home(pid):
    """Процесс этого дома: HOME в его окружении — мой (соседняя Мила под тем же пользователем живёт в своём HOME).
    Окружение не прочитать (macOS) — считаю своим, как раньше."""
    env = _proc_env(pid)
    return env is None or os.path.realpath(env.get("HOME") or "") == os.path.realpath(os.path.expanduser("~"))


def check_daemon(rep):
    """Демон и сессия не должны опрашивать Telegram одновременно."""
    lines = own_receivers(running("receiver.ts"))
    if not lines:
        rep.add(WARN, T("doctor.daemon.1"), T("doctor.daemon.2"),
                T("doctor.daemon.3"))
        return
    if len(lines) > 1:
        rep.add(BAD, T("doctor.daemon.1"), T("doctor.daemon.5") % len(lines),
                T("doctor.daemon.6"))
        return
    pid, cmd = lines[0]
    m = re.search(r"(\S+receiver\.ts)", cmd)
    src = m.group(1) if m else T("doctor.daemon.7")
    rep.add(OK, T("doctor.daemon.1"), T("doctor.daemon.9") % (pid, src))


def check_journal(rep):
    if not os.path.exists(EVENTS):
        rep.add(WARN, T("doctor.journal.1"), T("doctor.journal.2"), T("doctor.journal.3"))
        return
    size = os.path.getsize(EVENTS)
    age = time.time() - os.path.getmtime(EVENTS)
    rep.add(OK, T("doctor.journal.1"), T("doctor.journal.5")
            % (size, int(age // 60)))

    try:
        cur = int(open(CURSOR).read().strip() or 0)
    except Exception:
        cur = 0
    behind = size - cur
    if behind > 0:
        rep.add(WARN, T("doctor.journal.6"), T("doctor.journal.7") % behind,
                T("doctor.journal.8"))
    else:
        rep.add(OK, T("doctor.journal.6"), T("doctor.journal.10"))


def check_perms(rep):
    """Кто может писать в журнал — говорит голосом Telegram."""
    targets = (
        (STATE, 0o700), (INBOUND, 0o700), (CHATS_DIR, 0o700),
        (EVENTS, 0o600), (ENV_FILE, 0o600), (ACCESS, 0o600),
        (os.path.join(STATE, "auth-log.jsonl"), 0o600),
        (os.path.join(STATE, "permission-log.jsonl"), 0o600),
        (os.path.join(STATE, "permissions.json"), 0o600),
    )
    for path, want in targets:
        if not os.path.exists(path):
            continue
        st = os.stat(path)
        mode = st.st_mode & 0o777
        name = os.path.basename(path) or path
        # Сравнивать числом нельзя: 0444 меньше 0600, а читать токен всему
        # миру оно разрешает. Смотреть надо на биты, которых быть не должно.
        extra = mode & ~want
        if extra:
            rep.add(BAD, T("doctor.perms.1"), T("doctor.perms.2") % (name, mode, extra),
                    T("doctor.perms.3") % (want, path))
        elif st.st_uid != os.getuid():
            rep.add(BAD, T("doctor.perms.1"), T("doctor.perms.5")
                    % (name, st.st_uid),
                    T("doctor.perms.6")
                    % path)
        else:
            rep.add(OK, T("doctor.perms.1"), "%s — %o" % (name, mode))


TURNS_LABEL = "com.milagpt.turns-collect"
TURNS_UNIT = "mila-turns-collect.timer"


def timer_installed():
    """(стоит ли, чем именно). Спрашиваем ту службу, что есть на машине."""
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["launchctl", "list", TURNS_LABEL],
                               capture_output=True, text=True, timeout=8)
            return r.returncode == 0, "launchd " + TURNS_LABEL
        r = subprocess.run(["systemctl", "--user", "is-enabled", TURNS_UNIT],
                           capture_output=True, text=True, timeout=8)
        return r.returncode == 0, "systemd " + TURNS_UNIT
    except Exception:
        return False, ""


def check_turns_timer(rep):
    """Часовой сбор: стоит ли таймер и отработал ли он за последние два часа.

    Две проверки, а не одна: загруженный таймер, который падает на старте,
    выглядит здоровым в любом списке служб, а отметка о сборе без таймера
    означает, что кто-то собрал руками один раз и на этом успокоился.
    """
    on, how = timer_installed()
    if on:
        rep.add(OK, T("doctor.turns_timer.1"), T("doctor.turns_timer.2") % how)
    else:
        rep.add(WARN, T("doctor.turns_timer.1"), T("doctor.turns_timer.4"),
                T("doctor.turns_timer.5"))

    try:
        import records
        path = os.path.join(records.RECORDS_DIR, "turns-collect-last.json")
        with open(path, encoding="utf-8") as f:
            last = json.load(f)
    except (OSError, ValueError, ImportError):
        if on:
            rep.add(WARN, T("doctor.turns_timer.6"), T("doctor.turns_timer.7"),
                    T("doctor.turns_timer.8")
                    % os.path.expanduser("~/.claude"))
        return

    age_h = (time.time() - (last.get("finished_ts") or 0)) / 3600.0
    detail = (T("doctor.turns_timer.9")
              % (str(last.get("finished_at"))[:19].replace("T", " "),
                 last.get("took_sec") or 0, last.get("seen") or 0,
                 last.get("written") or 0))
    if age_h > 2:
        rep.add(WARN, T("doctor.turns_timer.6"), T("doctor.turns_timer.11") % (age_h, detail),
                T("doctor.turns_timer.12"))
    else:
        rep.add(OK, T("doctor.turns_timer.6"), detail)


def check_records(rep):
    """Учёт: обе базы на месте, схема полная, пишутся и не пустеют.

    Молчащий учёт выглядит точно так же, как учёт, которому нечего записать.
    Отличить их можно только по трём вещам: есть ли файл, растёт ли он, и не
    пропали ли колонки. Все три проверяем здесь, потому что заметить пропажу
    самому невозможно — отчёт по пустой базе выглядит как спокойный день.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    st = None
    for d in (os.path.join(os.path.expanduser("~"), ".claude", "hooks"), here):
        if os.path.exists(os.path.join(d, "records.py")):
            sys.path.insert(0, d)
            try:
                import records
                st = records.state()
            except Exception as e:
                rep.add(BAD, T("doctor.records.1"), T("doctor.records.2") % e,
                        T("doctor.records.3"))
                return
            break
    if st is None:
        rep.add(WARN, T("doctor.records.1"), T("doctor.records.5"),
                T("doctor.records.6"))
        return

    t, e = st["turns"], st["external"]

    if not t["exists"]:
        rep.add(WARN, T("doctor.records.7"), T("doctor.records.8"),
                T("doctor.records.9"))
    elif t["error"]:
        rep.add(BAD, T("doctor.records.7"), t["error"],
                T("doctor.records.11"))
    elif t["missing_columns"]:
        rep.add(BAD, T("doctor.records.7"),
                T("doctor.records.13") % ", ".join(t["missing_columns"]),
                T("doctor.records.14"))
    else:
        age = ""
        if t["last_ts"]:
            hours = (time.time() - t["last_ts"]) / 3600.0
            age = T("doctor.records.15") % hours
        rep.add(OK, T("doctor.records.7"), "%d %s%s"
                % (t["rows"], records.plural(t["rows"], T("doctor.records.17"), T("doctor.records.18"), T("doctor.records.19")), age))
        if t["rows"] and t["last_ts"] and time.time() - t["last_ts"] > 36 * 3600:
            rep.add(WARN, T("doctor.records.7"), T("doctor.records.21"),
                    T("doctor.records.22"))
        if t["mode"] and t["mode"] & ~0o600:
            rep.add(BAD, T("doctor.records.7"), T("doctor.records.24") % t["mode"],
                    T("doctor.records.25") % t["path"])

    if not e["exists"]:
        rep.add(WARN, T("doctor.records.26"), T("doctor.records.27"),
                T("doctor.records.28"))
    elif e["error"]:
        rep.add(BAD, T("doctor.records.26"), e["error"], T("doctor.records.30"))
    else:
        rep.add(OK, T("doctor.records.26"),
                "%d %s%s" % (e["rows"],
                             records.plural(e["rows"], T("doctor.records.32"), T("doctor.records.33"), T("doctor.records.34")),
                             "" if e["rows"] else T("doctor.records.35")))

    check_turns_timer(rep)

    if st["shrunk"]:
        rep.add(BAD, T("doctor.records.1"), T("doctor.records.37") % "; ".join(st["shrunk"]),
                T("doctor.records.38"))

    if st["text_policy"] != "full":
        rep.add(WARN, T("doctor.records.39"),
                T("doctor.records.40") % st["text_policy"],
                T("doctor.records.41"))

    # Эталон обновляем ПОСЛЕ проверки: иначе усохшая база тут же становится
    # новой нормой и претензии больше никогда не будет.
    try:
        import records as _r
        _r.save_watermark(st)
    except Exception:
        pass


def _proc_env(pid):
    """Окружение процесса своего пользователя (/proc/<pid>/environ) → dict или None (нет доступа / не Linux)."""
    try:
        raw = open("/proc/%s/environ" % pid, "rb").read().split(b"\0")
        return dict(x.decode("utf-8", "replace").split("=", 1) for x in raw if b"=" in x)
    except OSError:
        return None


def check_switches(rep, daemon_env="auto", home=None):
    """
    «включено в настройке, но не работает». Каждая строка — что включено, чего не хватает, что сделать."""
    home = home or os.path.expanduser("~")
    try:
        a = json.load(open(ACCESS, encoding="utf-8"))
    except (OSError, ValueError):
        a = {}
    cc = ((a.get("guestDm") or {}).get("cc") or {}) if (a.get("guestDm") or {}).get("enabled") else {}
    if cc.get("enabled"):
        if daemon_env == "auto":
            lines = running("receiver.ts")
            daemon_env = _proc_env(lines[0][0]) if lines else None
        if daemon_env is None:
            rep.add(WARN, T("doctor.switches.1"), T("doctor.switches.2"),
                    T("doctor.switches.3"))
        elif daemon_env.get("MILAT_GUEST_CC") != "1":
            rep.add(BAD, T("doctor.switches.1"), T("doctor.switches.5"),
                    T("doctor.switches.6"))
        else:
            rep.add(OK, T("doctor.switches.1"), T("doctor.switches.8"))
        for key, what in (("keyFile", T("doctor.switches.9")), ("systemPromptFile", T("doctor.switches.10"))):
            f = cc.get(key)
            if not f or not os.path.isfile(f):
                rep.add(BAD, T("doctor.switches.1"), T("doctor.switches.12") % (what, f or T("doctor.switches.13")), T("doctor.switches.14") % key)
        if cc.get("knowledgeDir") and not os.path.isdir(cc["knowledgeDir"]):
            rep.add(WARN, T("doctor.switches.1"), T("doctor.switches.16") % cc["knowledgeDir"], T("doctor.switches.17"))
        if cc.get("cardToRazbor") and not cc.get("handoffFile"):
            rep.add(BAD, T("doctor.switches.1"), T("doctor.switches.19"),
                    T("doctor.switches.20"))
        st = cc.get("students")
        if isinstance(st, dict) and not (st.get("systemPromptFile") and st.get("knowledgeDir")):
            rep.add(WARN, T("doctor.switches.21"), T("doctor.switches.22"), T("doctor.switches.23"))
    try:
        j = json.load(open(os.path.join(home, ".claude", "jev.json"), encoding="utf-8"))
    except (OSError, ValueError):
        j = {}
    if j.get("mode") in ("shadow", "main") and not j.get("url"):
        rep.add(WARN, "Jev", T("doctor.switches.24") % j["mode"], T("doctor.switches.25"))
    try:
        u = json.load(open(os.path.join(home, ".claude", "mila-update.json"), encoding="utf-8"))
    except (OSError, ValueError):
        u = None
    if u is not None and u.get("channel", "stable") != "manual" and not u.get("owner_chat"):
        rep.add(WARN, T("doctor.switches.26"), T("doctor.switches.27"),
                T("doctor.switches.28"))


def check_flag(rep):
    """Подключён ли канал к сессии.

    Искать флаг в командной строке `claude` бесполезно: под шаблон «claude»
    попадают все процессы, у которых в пути есть каталог .claude — демон,
    отправитель, сам MCP-сервер. Точный признак другой: если канал подключён,
    Claude Code ЗАПУСТИЛ mcp-сервер плагина. Нет процесса — нет канала,
    сколько бы флагов ни было в команде.
    """
    # Живой сервер выглядит как «bun server.ts» — без единого упоминания
    # канала: рабочий каталог задан отдельно, в команде его не видно.
    # Поэтому смотрим на две улики: сам server.ts и запускающую его строку
    # «bun run --cwd <плагин> ... start», где имя канала как раз есть.
    servers = [cmd for pid, cmd in running("server.ts") if own_home(pid)]   # MCP соседнего дома — не канал этой сессии
    servers += [cmd for pid, cmd in running("--cwd")
                if "telegram" in cmd and "start" in cmd and own_home(pid)]
    if servers:
        rep.add(OK, T("doctor.flag.1"), T("doctor.flag.2"))
        return
    sessions = [cmd for pid, cmd in running("claude")
                if re.search(r"/(claude)(\s|$)", cmd) and own_home(pid)]
    if sessions:
        rep.add(BAD, T("doctor.flag.1"), T("doctor.flag.4"),
                T("doctor.flag.5"))
    else:
        rep.add(WARN, T("doctor.flag.1"), T("doctor.flag.7"),
                T("doctor.flag.8"))


def main():
    ap = argparse.ArgumentParser(description=T("doctor.main.1"))
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()

    rep = Report()
    token = check_token(rep)
    if token:
        check_privacy(rep, token)
    check_access(rep)
    check_daemon(rep)
    check_journal(rep)
    check_perms(rep)
    check_records(rep)
    check_switches(rep)
    check_flag(rep)

    if args.as_json:
        json.dump({"rows": rep.rows, "bad": len(rep.bad), "warn": len(rep.warn)},
                  sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 1 if rep.bad else 0

    mark = {OK: "🟢", WARN: "🟡", BAD: "🔴"}
    print(T("doctor.main.2") % STATE)
    print()
    for r in rep.rows:
        print("%s %-18s %s" % (mark[r["level"]], r["name"], r["detail"]))
        if r["fix"]:
            for i, chunk in enumerate(wrap(r["fix"], 66)):
                print("   %s %s" % ("→" if i == 0 else " ", chunk))
    print()
    if rep.bad:
        print(T("doctor.main.3") % len(rep.bad))
    elif rep.warn:
        print(T("doctor.main.4") % len(rep.warn))
    else:
        print(T("doctor.main.5"))
    return 1 if rep.bad else 0


def wrap(text, width):
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        out.append(line)
    return out


if __name__ == "__main__":
    sys.exit(main())
