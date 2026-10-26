#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Кормилец сессии: журнал плагина → stdin сессии Claude Code (stream-json).

Почему он нужен (проба 03.09 на хосте): в режиме `claude -p --input-format stream-json`
уведомления канала, которые мост server.ts доигрывает из журнала, НЕ начинают ход —
сессия молчит и после первого, и после второго события. Ход начинается только от
сообщения на stdin. Поэтому мост в сессии смотрит в пустой каталог (telegram-session),
а этот скрипт читает настоящий журнал receiver-демона и подаёт каждое входящее как
сообщение пользователя в конверте <channel …> — том же, что у хука
install/telegram-inbox-feed.py, с тем же экранированием против подделки конверта.

Курсор — свой (inbound/feeder-cursor), чтобы после рестарта ничего не потерять и
ничего не повторить. Секретов не печатает.
"""
import json, os, stat, sys, time

# Пути — через окружение. COMPANION_STATE — каталог состояния сессии (труба, журнал кормильца).
COMPANION_STATE = os.environ.get("COMPANION_STATE", os.path.expanduser("~/.mila-companion/state"))

STATE = os.environ.get("TELEGRAM_STATE_DIR", os.path.expanduser("~/.claude/channels/telegram"))
EV = os.path.join(STATE, "inbound", "events.jsonl")
CUR = os.path.join(STATE, "inbound", "feeder-cursor")
SUSP = os.path.join(STATE, "inbound", "suspicious.jsonl")
FIFO = os.environ.get("COMPANION_FIFO", os.path.join(COMPANION_STATE, "session.in"))
LOG = os.environ.get("COMPANION_FEEDER_LOG", os.path.join(COMPANION_STATE, "feeder.log"))
INJECTION_MARKS = ("</channel", "<channel", "system-reminder", "</antml", "‹", "›", "＜", "＞")
# пока подписка в лимите (429 в транскрипте, время сброса известно и не прошло),
# входящие НЕ подаём — в режиме `claude -p` ход с 429 съедает сообщение безвозвратно.
# Курсор стоит, после сброса или перезапуска сессии (смена подписки) всё уходит по порядку.
sys.path.insert(0, os.environ.get("COMPANION_INSTALL_DIR", os.path.dirname(os.path.abspath(__file__))))
try:
    import limit_watch as _lw
except Exception:
    _lw = None
CLAUDE_DIR = os.path.expanduser("~/.claude")
SESSION_PID = os.environ.get("COMPANION_SESSION_PID", os.path.join(COMPANION_STATE, "session.pid"))


def limit_hold():
    """(держать, до когда, почему). Нет модуля — не держим."""
    if _lw is None:
        return False, None, "limit_watch недоступен"
    try:
        return _lw.hold(CLAUDE_DIR, SESSION_PID)
    except Exception as ex:
        return False, None, "датчик упал: %s" % type(ex).__name__


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s | %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


_SAID = {}


def log_once(key, msg, every=60):
    """Ожидаемое состояние (сессии ещё нет) не должно раздувать журнал:
    одна строка не чаще раза в `every` секунд."""
    now = time.time()
    if now - _SAID.get(key, 0) >= every:
        _SAID[key] = now
        log(msg)


def esc(v):
    return (str("" if v is None else v).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def envelope(p, m):
    user = m.get("user") or ""
    who = user or "id:%s" % m.get("user_id", "?")
    txt = (p.get("content") or "").strip()
    att = ""
    if m.get("image_path"):
        att = " [image: %s]" % m["image_path"]
    elif m.get("attachment_file_id"):
        att = " [attachment_file_id: %s]" % m["attachment_file_id"]
    quote = ""
    if m.get("reply_quote"):
        quote = " (replying to: %s)" % esc(str(m["reply_quote"])[:3000])  # TEAM-HEARING-1006
    if any(k in (p.get("content") or "").lower() for k in INJECTION_MARKS):
        try:
            with open(SUSP, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(), "by": "feeder", "meta": m}, ensure_ascii=False) + "\n")
        except Exception:
            pass
    return ('<channel source="telegram" chat_id="%s" message_id="%s" user="%s" ts="%s">%s%s%s</channel>'
            % (esc(m.get("chat_id")), esc(m.get("message_id")), esc(who), esc(m.get("ts", "")),
               esc(txt), esc(att), quote))


def feed(text):
    """Пишем ТОЛЬКО в живую трубу сессии.
    🔴 Проба 03.09: пока хозяин не вошёл в подписку, сессии нет и трубы нет —
    open(FIFO,"w") молча создавал ОБЫЧНЫЙ файл, курсор уходил вперёд, и первое
    «привет» пропадало навсегда. Теперь нет трубы → исключение: вызывающий не
    двигает курсор и повторит, когда сессия поднимется."""
    try:
        is_fifo = stat.S_ISFIFO(os.stat(FIFO).st_mode)
    except OSError:
        raise OSError("трубы сессии нет — сессия ещё не поднялась")
    if not is_fifo:
        raise OSError("session.in не труба — сессия ещё не поднялась")
    msg = {"type": "user", "message": {"role": "user", "content": text}}
    with open(FIFO, "w", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")


# (D-NNNN): «fed» ещё не значит «сессия получила». Дважды за 23.09 сообщение
# ушло в трубу, но в транскрипте не появилось ни enqueue, ни user — клиент остался без ответа.
# Теперь каждое поданное ждёт подтверждения в транскрипте; нет его за DELIVERY_WAIT с — подаём
# повторно один раз, снова нет — пишем LOST в лог (его видит администратор).
#
# (D-NNNN часть 2): три беды прежней версии —
#   (а) check_delivery() сдавалась после ОДНОГО повтора — реального окна на «сессия занята
#       Bash-ходом 2-4 минуты» не хватало, LOST сыпались на живых доставках;
#   (б) _pending жил только в памяти процесса — рестарт кормильца (обновление образа,
#       перезапуск юнита) стирал незакрытые ожидания молча, без LOST и без повтора;
#   (в) _in_transcript() считала совпадением ЛЮБОЕ вхождение подстроки message_id — попадание
#       в вывод queue-operation enqueue/remove или в текст, который Bash вывел в терминал
#       (например, эхо самого входящего), засчитывалось как «доставлено».
# Теперь: неподтверждённые сообщения — в файле состояния (переживают рестарт), повтор —
# с нарастающим интервалом в сумме до MAX_PENDING_AGE секунд, а доставкой считается только
# запись транскрипта type="user", где message_id встречается в тексте, а не в tool_result.
import glob as _glob
PROJECTS = os.path.expanduser(os.environ.get("COMPANION_PROJECTS", "~/.claude/projects"))
DELIVERY_WAIT = int(os.environ.get("FEEDER_DELIVERY_WAIT", "90"))
MAX_PENDING_AGE = int(os.environ.get("FEEDER_MAX_PENDING_AGE", "900"))     # ~15 минут суммарно
RETRY_CAP = int(os.environ.get("FEEDER_RETRY_CAP", "300"))                 # потолок одного интервала
PENDING_FILE = os.environ.get("COMPANION_FEEDER_PENDING",
                               os.path.join(os.path.dirname(LOG) or ".", "feeder-pending.json"))


def _load_pending():
    """неподтверждённые сообщения переживают рестарт кормильца —
    без этого рестарт молча стирал ожидание, и LOST никогда не писался."""
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_pending():
    try:
        tmp = PENDING_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_pending, f, ensure_ascii=False)
        os.replace(tmp, PENDING_FILE)
    except Exception:
        pass


_pending = _load_pending()  # key -> {text, first_ts, last_ts, tries, backoff, chat, mid}


def _user_text_has(message, needle_plain):
    """доставка — только настоящий текст записи type="user"
    (наш конверт <channel …>), а не queue-operation enqueue/remove и не tool_result
    (вывод Bash может случайно содержать ту же подстроку message_id). `needle_plain` —
    подстрока в РАСПАКОВАННОМ (после json.loads) виде, т.е. с обычными кавычками."""
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return needle_plain in content
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                if needle_plain in str(block):
                    return True
                continue
            if block.get("type") == "tool_result":
                continue  # ответ инструмента (напр. Bash) — не текст канала, не считается
            txt = block.get("text")
            if txt is None:
                txt = json.dumps(block, ensure_ascii=False)
            if needle_plain in txt:
                return True
    return False


def _deep_has(obj, needle):
    """подстрока в любом строковом поле вложенной структуры (без JSON-экранирования)."""
    if isinstance(obj, str):
        return needle in obj
    if isinstance(obj, dict):
        return any(_deep_has(v, needle) for v in obj.values())
    if isinstance(obj, list):
        return any(_deep_has(v, needle) for v in obj)
    return False


def _in_transcript(mid, since):
    # needle_raw — как подстрока message_id выглядит в СЫРЫХ байтах файла (JSON экранирует
    # кавычки внутри строки \"…\"), нужна только для быстрого grep по файлу целиком;
    # needle_plain — та же подстрока ПОСЛЕ json.loads (обычные кавычки), ею проверяем
    # уже распакованный message.content в _user_text_has.
    needle_raw = ('message_id=\\"%s\\"' % mid).encode()
    needle_plain = 'message_id="%s"' % mid
    for f in _glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")):
        try:
            if os.path.getmtime(f) < since - 5:
                continue
            with open(f, "rb") as fh:
                fh.seek(max(0, os.path.getsize(f) - 4_000_000))
                tail = fh.read()
        except OSError:
            continue
        if needle_raw not in tail:
            continue
        for raw in tail.split(b"\n"):
            if needle_raw not in raw:
                continue
            try:
                rec = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            # пока сессия занята ходом, Claude Code вшивает входящее в текущий
            # ход вложением attachment/queued_command («пришло, пока работала»), а не отдельной
            # записью type=user. Прежняя проверка его не видела → refeed до 5 раз → дубли у агента.
            if rec.get("type") == "attachment":
                att = rec.get("attachment") or {}
                if isinstance(att, dict) and att.get("type") == "queued_command" and \
                        _deep_has(att, needle_plain):
                    return True
                continue
            if rec.get("type") != "user":
                continue
            if _user_text_has(rec.get("message") or {}, needle_plain):
                return True
    return False


def check_delivery():
    now = time.time()
    changed = False
    for key, rec in list(_pending.items()):
        mid, chat = rec.get("mid"), rec.get("chat")
        if _in_transcript(mid, rec.get("first_ts", now)):
            _pending.pop(key, None)
            changed = True
            continue
        elapsed = now - rec.get("first_ts", now)
        if elapsed >= MAX_PENDING_AGE:
            _pending.pop(key, None)
            changed = True
            log("LOST chat=%s msg=%s — не дошло за %d с (%d попыток)" % (chat, mid, MAX_PENDING_AGE, rec.get("tries", 1)))
            continue
        backoff = rec.get("backoff", DELIVERY_WAIT)
        if now - rec.get("last_ts", now) < backoff:
            continue
        try:
            feed(rec["text"])
            rec["tries"] = rec.get("tries", 1) + 1
            rec["last_ts"] = now
            rec["backoff"] = min(backoff * 2, RETRY_CAP)
            _pending[key] = rec
            changed = True
            log("refed chat=%s msg=%s (в транскрипте не найдено за %d с, попытка %d)" % (chat, mid, backoff, rec["tries"]))
        except Exception as ex:
            log_once("refeed-failed", "повторная подача не прошла (%s)" % type(ex).__name__)
    if changed:
        _save_pending()


# TEAM-HEARING-1006: сообщения НАШИХ ботов в общих группах доходят до модели, если адресованы этой Миле
# (@упоминание её бота или reply на её сообщение). Прежде фильтр user.endswith("_bot") глушил всех ботов.
# Защита от зацикливания: не больше COMPANION_BOT_PAIR_MAX (по умолчанию 20) поданных сообщений от одного бота за час.
OURS_FILE = os.environ.get("COMPANION_OUR_BOTS", os.path.expanduser("~/.mila-companion/our-bots.json"))
BOT_WINDOW = 3600
_own_cache = {"name": None, "ts": 0}
_pair_hits = {}   # бот-отправитель -> [время поданных сообщений]


def _pair_max():
    try:
        return int(os.environ.get("COMPANION_BOT_PAIR_MAX", "20"))
    except ValueError:
        return 20


def _our_bots():
    try:
        return {x.lower() for x in json.load(open(OURS_FILE, encoding="utf-8"))}
    except Exception:
        return set()


def _own_username():
    if os.environ.get("COMPANION_BOT_USERNAME"):
        return os.environ["COMPANION_BOT_USERNAME"].lstrip("@").lower()
    if _own_cache["name"] and time.time() - _own_cache["ts"] < 600:
        return _own_cache["name"]
    name = None
    try:
        rl = os.path.join(os.path.dirname(LOG), "receiver.log")
        import re as _re
        with open(rl, "rb") as f:
            f.seek(max(0, os.path.getsize(rl) - 200000))
            hits = _re.findall(r"polling as @([A-Za-z0-9_]+)", f.read().decode("utf-8", "replace"))
        name = hits[-1].lower() if hits else None
    except Exception:
        pass
    _own_cache.update(name=name, ts=time.time())
    return name


def gate_message(p, m, own=None, ours=None):
    """True — подать в сессию. Люди — всегда (как прежде); боты — только наши и адресованные."""
    user = (m.get("user") or "")
    chat = str(m.get("chat_id"))
    if not user.endswith("_bot"):
        return True
    own = (own or _own_username() or "").lower()
    ours = ours if ours is not None else _our_bots()
    u = user.lower()
    if not own or u == own or u not in ours:
        return False
    text = (p.get("content") or "").lower()
    addressed = ("@" + own) in text or (m.get("reply_to_user") or "").lower() == own
    if not addressed:
        return False
    now = time.time()
    hits = [t for t in _pair_hits.get(u, []) if now - t < BOT_WINDOW]
    if len(hits) >= _pair_max():
        _pair_hits[u] = hits
        log("bot-loop-guard @%s: %d сообщений за час — не подаю" % (u, len(hits)))
        return False
    hits.append(now)
    _pair_hits[u] = hits
    return True


# ── LOGIN-2610 (ROLLOUT №41 «без повисших задач», улика одной Милы 28.09) ─────────────────────────────────────────
# Пока вход потерян («Not logged in»), каждый поданный ход съеден, а проверка доставки считает его доставленным
# (текст человека в транскрипте есть). Поэтому: 1) при первом обнаружении — курсор назад, к входящим за время простоя;
# 2) держу входящие, раз в PROBE_S подаю пробу — удачный ответ на неё = вход вернулся; 3) после — строка «пропущено за
# простой: N» и всё по порядку; 4) один раз на простой — 🔴 строка старшей (MILA_SENIOR_INBOX).
LOGIN_STATE = os.path.join(COMPANION_STATE, "login-state.json")
PROBE_S = int(os.environ.get("FEEDER_LOGIN_PROBE_S", "600"))
REWIND_SLACK = 180
SENIOR_INBOX = os.environ.get("MILA_SENIOR_INBOX", os.path.expanduser("~/work/inbox/to-admin.jsonl"))
PROBE_TEXT = "[система] Проверка входа после «Not logged in»: ответь одним словом SKIP. В Telegram не пиши."


def auth_down():
    """→ detect_auth() или None (модуля нет / датчик упал)."""
    if _lw is None or not hasattr(_lw, "detect_auth"):
        return None
    try:
        return _lw.detect_auth(CLAUDE_DIR)
    except Exception:
        return None


def _load_login():
    try:
        return json.load(open(LOGIN_STATE, encoding="utf-8"))
    except Exception:
        return {}


def _save_login(st):
    try:
        tmp = LOGIN_STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(st, f)
        os.replace(tmp, LOGIN_STATE)
    except Exception:
        pass


def _event_ts(e):
    t = e.get("ts")
    if isinstance(t, (int, float)):
        return t / 1000.0 if t > 1e11 else float(t)
    m = ((e.get("params") or {}).get("meta") or {}).get("ts")
    if _lw is not None and m:
        try: return _lw.iso_to_epoch(m)
        except Exception: return None
    return None


def rewind_to(cursor, since, last_ok=None):
    """Смещение первого входящего не раньше since−REWIND_SLACK среди уже поданных (до курсора); нет таких — курсор как был.
    Не раньше последнего удачного хода (Качество 26.10): всё, что пришло до него, уже получило ответ — второй ответ не нужен."""
    since = max(since - REWIND_SLACK, (last_ok or 0) + 1)
    pos = 0
    try:
        with open(EV, "rb") as f:
            for raw in f:
                if pos >= cursor:
                    break
                try:
                    e = json.loads(raw.decode("utf-8", "replace"))
                except Exception:
                    e = None
                if e and e.get("method") == "notifications/claude/channel":
                    t = _event_ts(e)
                    if t and t >= since:
                        return pos
                pos += len(raw)
    except OSError:
        pass
    return cursor


def channel_events_after(cursor):
    n = 0
    try:
        with open(EV, "rb") as f:
            f.seek(cursor)
            for raw in f:
                if b'"notifications/claude/channel"' in raw:
                    n += 1
    except OSError:
        pass
    return n


def alert_senior(au, waiting):
    """Одна 🔴 строка старшей на простой: вход потерян, сколько входящих ждёт. Нет её ящика — только журнал кормильца."""
    since = _lw.fmt_hm(au["since"], _lw.DEFAULT_TZ) if _lw else "?"
    text = ("🔴 Вход потерян с %s (ответ сессии «Not logged in»): ждут %d входящих, держу их и подам после входа. Нужен /login." % (since, waiting))
    log("login: " + text)
    d = os.path.dirname(SENIOR_INBOX)
    if not os.path.isdir(d):
        return False
    rec = {"id": "%s-login-%d" % (time.strftime("%Y-%m-%dT%H:%M"), int(au["since"])), "ts": time.strftime("%Y-%m-%dT%H:%M%z"),
           "kind": "alert", "status": "open", "agent": os.environ.get("MILA_AGENT", ""), "text": text}
    try:
        with open(SENIOR_INBOX, "a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def login_step(cursor, now=None):
    """Один шаг сторожа входа. → (cursor, держать_ли). Вызывается в цикле перед подачей."""
    now = now or time.time()
    st = _load_login(); au = auth_down()
    try:
        pid = int(open(SESSION_PID).read().strip() or 0)
    except Exception:
        pid = 0
    if au and au.get("down"):
        inc = int(au["since"])
        if st.get("incident") != inc:   # первое обнаружение этого простоя
            new = rewind_to(cursor, au["since"], au.get("last_ok"))
            if new < cursor:
                log("login: курсор назад %d → %d — входящие за простой подам заново" % (cursor, new))
                cursor = new
                try:
                    with open(CUR, "w") as f: f.write(str(cursor))
                except Exception:
                    pass
                _pending.clear(); _save_pending()   # их доставку не ждём — подадим заново
            st = {"incident": inc, "since": au["since"], "probe_at": now, "pid": pid, "alerted": alert_senior(au, channel_events_after(cursor))}
            _save_login(st)
        elif now - st.get("probe_at", 0) >= PROBE_S or (pid and pid != st.get("pid")):   # рестарт сессии (вошли заново) — проба сразу
            st["pid"] = pid
            try:
                feed(PROBE_TEXT); st["probe_at"] = now; _save_login(st); log("login: проба входа подана")
            except Exception as ex:
                log_once("login-probe", "login: проба не подана (%s)" % type(ex).__name__)
        log_once("login-hold", "login: вход потерян — держу входящие, курсор на месте", every=300)
        return cursor, True
    if st.get("incident"):   # вход вернулся
        n = channel_events_after(cursor)
        if n:
            since = _lw.fmt_hm(st.get("since") or now, _lw.DEFAULT_TZ) if _lw else "?"
            try:
                feed("[система] Вход вернулся. Пропущено за простой с %s: %d входящих — подаю по порядку. Каждому человеку — "
                     "квитанция «Принято, №…» (tasks-discipline), без упрёков и оправданий; перед ответом сверь последний свой ответ в том чате — уже ответила, второй раз не отвечай." % (since, n))
                log("login: вход вернулся — пропущено %d, подаю" % n)
            except Exception as ex:
                log_once("login-pre", "login: строка «пропущено» не подана (%s) — повторю" % type(ex).__name__)
                return cursor, True
        _save_login({})
    return cursor, False


# ── LIMIT-PROBE-2610 (старшая 26.10 10:39: клиент обновил подписку в 10:30, а кормилец держал до «resets 2pm») ───────────
# При лимите подписки — так же, как при потере входа: курсор назад к входящим, съеденным ходами 429; проба «ответь SKIP» раз в
# PROBE_S и сразу после рестарта сессии; удачный ход = лимит снят раньше срока → «пропущено за простой: N» и всё по порядку.
LIMIT_STATE = os.path.join(COMPANION_STATE, "limit-state.json")
LIMIT_PROBE_TEXT = "[система] Проверка подписки после лимита: ответь одним словом SKIP. В Telegram не пиши."


def _load_limit():
    try:
        return json.load(open(LIMIT_STATE, encoding="utf-8"))
    except Exception:
        return {}


def _save_limit(st):
    try:
        tmp = LIMIT_STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(st, f)
        os.replace(tmp, LIMIT_STATE)
    except Exception:
        pass


def limit_detect():
    if _lw is None:
        return None
    try:
        return _lw.detect(CLAUDE_DIR)
    except Exception:
        return None


def limit_step(cursor, now=None):
    """Один шаг сторожа лимита. → (cursor, держать_ли). Держит по limit_hold(); сверху — откат, проба, «пропущено»."""
    now = now or time.time()
    held, until, why = limit_hold()
    st = _load_limit()
    try:
        pid = int(open(SESSION_PID).read().strip() or 0)
    except Exception:
        pid = 0
    if held:
        det = limit_detect() or {}
        hit = det.get("hit") or {}
        inc = str(hit.get("incident") or "limit")
        if st.get("incident") != inc:   # новый простой лимита
            since = hit.get("first_at") or now
            new = rewind_to(cursor, since, det.get("last_ok"))
            if new < cursor:
                log("limit: курсор назад %d → %d — входящие, съеденные ходами 429, подам заново" % (cursor, new))
                cursor = new
                try:
                    with open(CUR, "w") as f: f.write(str(cursor))
                except Exception:
                    pass
                _pending.clear(); _save_pending()
            st = {"incident": inc, "since": since, "probe_at": now, "pid": pid, "why": why}
            _save_limit(st)
        elif now - st.get("probe_at", 0) >= PROBE_S or (pid and pid != st.get("pid")):
            st["pid"] = pid
            try:
                feed(LIMIT_PROBE_TEXT); st["probe_at"] = now; _save_limit(st); log("limit: проба снятия лимита подана")
            except Exception as ex:
                log_once("limit-probe", "limit: проба не подана (%s)" % type(ex).__name__)
        log_once("limit-hold", "лимит подписки — держу входящие (%s), курсор на месте, проба раз в %d с" % (why, PROBE_S), every=300)
        return cursor, True
    if st.get("incident"):   # лимит снят — по сроку или раньше (пробой)
        n = channel_events_after(cursor)
        if n:
            since = _lw.fmt_hm(st.get("since") or now, _lw.DEFAULT_TZ) if _lw else "?"
            try:
                feed("[система] Подписка снова работает. Пропущено за простой с %s: %d входящих — подаю по порядку. Каждому человеку — "
                     "квитанция «Принято, №…» (tasks-discipline), без упрёков и оправданий; перед ответом сверь последний свой ответ в том чате — "
                     "уже ответила, второй раз не отвечай." % (since, n))
                log("limit: лимит снят — пропущено %d, подаю" % n)
            except Exception as ex:
                log_once("limit-pre", "limit: строка «пропущено» не подана (%s) — повторю" % type(ex).__name__)
                return cursor, True
        _save_limit({})
    return cursor, False


def main():
    try:
        cursor = int(open(CUR).read().strip() or 0)
    except Exception:
        cursor = 0
    log("feeder start, cursor=%d, pending=%d" % (cursor, len(_pending)))
    while True:
        try:
            size = os.path.getsize(EV)
        except OSError:
            time.sleep(1); continue
        if size < cursor:          # журнал ротирован/усечён — начинаем сначала
            cursor = 0
        if size == cursor:
            if _pending:
                check_delivery()
            time.sleep(1); continue
        with open(EV, "rb") as f:
            f.seek(cursor)
            chunk = f.read(size - cursor)
        nl = chunk.rfind(b"\n")
        if nl < 0:
            time.sleep(0.5); continue
        cursor, lheld = login_step(cursor)   # LOGIN-2610: потерян вход — держу, назад курсор, проба, «пропущено»
        if lheld:
            time.sleep(5)
            continue
        if size < cursor:
            continue
        cursor, held = limit_step(cursor)   # LIMIT-PROBE-2610: держу, откат, проба раз в PROBE_S, «пропущено»
        if held:
            time.sleep(5)
            continue
        if _pending:
            check_delivery()
        complete = chunk[:nl + 1]
        pos = cursor
        for raw in complete.split(b"\n")[:-1]:
            ln = len(raw) + 1
            try:
                e = json.loads(raw.decode("utf-8", "replace")) if raw.strip() else None
            except Exception:
                e = None
            if e and e.get("method") == "notifications/claude/channel":
                p = e.get("params") or {}
                m = p.get("meta") or {}
                if gate_message(p, m):
                    try:
                        _txt = envelope(p, m)
                        feed(_txt)
                        log("fed chat=%s msg=%s" % (m.get("chat_id"), m.get("message_id")))
                        if m.get("message_id"):
                            _now = time.time()
                            _pending["%s:%s" % (m.get("chat_id"), m.get("message_id"))] = {
                                "text": _txt, "first_ts": _now, "last_ts": _now, "tries": 1,
                                "backoff": DELIVERY_WAIT, "chat": m.get("chat_id"), "mid": m.get("message_id")}
                            _save_pending()
                    except Exception as ex:
                        log_once("feed-failed", "сессия не принимает (%s) — жду, курсор на месте"
                                 % type(ex).__name__)
                        time.sleep(2)
                        break
            pos += ln
            try:
                with open(CUR, "w") as f:
                    f.write(str(pos))
            except Exception:
                pass
        cursor = pos


if __name__ == "__main__":
    main()
