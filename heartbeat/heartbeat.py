#!/usr/bin/env python3
"""Heartbeat (RU: «Пульс Милы») — Mila's schedule that lives outside the Claude Code session.

Schedules made with CronCreate live inside the session: they die on restart and expire after 7 days. Heartbeat is a small
service (systemd timer / launchd, once a minute) that reads ~/work/heartbeat.yaml and, when a job is due, puts a message
into the same inbound queue the Telegram channel uses. The session takes it like any other message. No model is called here.

Job types:
  beat   — a cheap check without a model: a command prints new findings (one per line, JSON {"key", "text"} or plain text);
           each new finding becomes one message; nothing found — nothing is sent.
  think  — a scheduled thought (morning plan, evening wrap-up): the prompt is queued every time, except in quiet hours.
  once   — one message at a given time, then the job is done.

  heartbeat.py [--config ~/work/heartbeat.yaml] [--dry-run]   # one pass (the service runs it every minute)
  heartbeat.py --list                                          # jobs and their next run
Files: state ~/.local/state/mila-heartbeat/state.json, journal ~/.local/state/mila-heartbeat/heartbeat.log
(time · job · found / nothing / skipped · duration). Keys and tokens never go into heartbeat.yaml — only names of env variables.
Watchdog: a queued message the session has not taken for watchdog.after_min minutes → one Telegram message per incident
(bot token and chat from env). Only stdlib (+ PyYAML if installed; a JSON file works without it)."""
import argparse, datetime as dt, hashlib, json, os, re, shlex, subprocess, sys, time, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

CONFIG = os.environ.get("MILA_HEARTBEAT") or os.path.expanduser("~/work/heartbeat.yaml")
STATE_DIR = os.environ.get("MILA_HEARTBEAT_STATE") or os.path.expanduser("~/.local/state/mila-heartbeat")
QUEUE = os.environ.get("MILA_HEARTBEAT_QUEUE") or os.path.expanduser("~/.claude/channels/telegram/inbound")
GRACE_MIN = 15            # a run missed by the service (sleep, restart) is still made up to 15 minutes late
CHECK_TIMEOUT = 60
SEEN_MAX = 500


# ── config ──
def load_config(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    try:
        import yaml
        cfg = yaml.safe_load(raw)
    except ImportError:
        cfg = json.loads(raw)
    if not isinstance(cfg, dict):
        raise ValueError("heartbeat: the config must be a mapping")
    jobs = cfg.get("jobs") or []
    seen = set()
    for j in jobs:
        jid = str(j.get("id") or "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", jid) or jid in seen:
            raise ValueError("heartbeat: bad or repeated job id %r" % jid)
        seen.add(jid)
        if j.get("type") not in ("beat", "think", "once"):
            raise ValueError("heartbeat: job %s — type must be beat, think or once" % jid)
        if j["type"] == "once":
            if not j.get("at"):
                raise ValueError("heartbeat: job %s — once needs at: \"YYYY-MM-DD HH:MM\"" % jid)
        else:
            parse_cron(str(j.get("cron") or ""))
        if j["type"] == "beat" and not j.get("check"):
            raise ValueError("heartbeat: job %s — beat needs check: <command>" % jid)
        if j["type"] in ("think", "once") and not j.get("prompt"):
            raise ValueError("heartbeat: job %s — needs prompt" % jid)
    return cfg


# ── cron: minute hour day month weekday (0 or 7 = Sunday), lists, ranges, steps ──
def _field(spec, lo, hi):
    out = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            step = int(s)
            if step < 1:
                raise ValueError("step")
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
        else:
            a = b = int(part)
        if a < lo or b > hi or a > b:
            raise ValueError("range")
        out.update(range(a, b + 1, step))
    return out


def parse_cron(expr):
    f = expr.split()
    if len(f) != 5:
        raise ValueError("heartbeat: cron needs 5 fields, got %r" % expr)
    try:
        mi, ho, dom, mon, dow = (_field(f[0], 0, 59), _field(f[1], 0, 23), _field(f[2], 1, 31), _field(f[3], 1, 12), _field(f[4], 0, 7))
    except ValueError:
        raise ValueError("heartbeat: cron %r does not parse" % expr)
    dow = {0 if d == 7 else d for d in dow}
    return mi, ho, dom, mon, dow, f[2] == "*", f[4] == "*"


def cron_match(c, t):
    mi, ho, dom, mon, dow, dom_any, dow_any = c
    if t.minute not in mi or t.hour not in ho or t.month not in mon:
        return False
    d_ok, w_ok = t.day in dom, (t.isoweekday() % 7) in dow
    if dom_any or dow_any:                 # as in cron: when both day-of-month and weekday are set, either one is enough
        return d_ok and w_ok
    return d_ok or w_ok


def quiet(cfg, t):
    q = str(cfg.get("quiet_hours") or "22-08")
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", q)
    if not m:
        return False
    a, b = int(m.group(1)), int(m.group(2))
    return (t.hour >= a or t.hour < b) if a > b else (a <= t.hour < b)


# ── queue (same inbound journal as the Telegram channel) ──
def enqueue(cfg, job, text, key, now, dry):
    chat = os.environ.get(str(cfg.get("chat_id_env") or "MILA_OWNER_CHAT"), "") or str(cfg.get("chat_id") or "")
    ev = {"ts": int(now * 1000), "method": "notifications/claude/channel",
          "params": {"content": text, "meta": {"chat_id": chat, "chat_type": "private",
                                               "message_id": "heartbeat-%s-%s" % (job["id"], key), "user": "Heartbeat",
                                               "user_id": "heartbeat", "ts": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
                                               "heartbeat": job["id"], "heartbeat_type": job["type"]}}}
    if dry:
        print(json.dumps(ev, ensure_ascii=False))
        return
    os.makedirs(QUEUE, exist_ok=True)
    with open(os.path.join(QUEUE, "events.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def run_check(job):
    """Command of a beat job → findings [(key, text)]. Fails or times out → [] and the error for the journal."""
    cmd = os.path.expanduser(str(job["check"]))
    try:
        r = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=int(job.get("timeout") or CHECK_TIMEOUT))
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return [], type(e).__name__
    if r.returncode != 0:
        return [], "exit %d: %s" % (r.returncode, (r.stderr or "").strip()[-160:])
    out = []
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if isinstance(d, dict) and d.get("text"):
                out.append((str(d.get("key") or hashlib.sha256(d["text"].encode()).hexdigest()[:16]), str(d["text"])[:4000]))
                continue
        except ValueError:
            pass
        out.append((hashlib.sha256(line.encode()).hexdigest()[:16], line[:4000]))
    return out, ""


def log(row, dry):
    line = "%s\t%s\t%s\t%s\t%dms" % (row["t"], row["job"], row["kind"], row["what"], row["ms"])
    if dry:
        print("LOG " + line)
        return
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(os.path.join(STATE_DIR, "heartbeat.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state():
    try:
        with open(os.path.join(STATE_DIR, "state.json"), encoding="utf-8") as f:
            st = json.load(f)
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(st):
    os.makedirs(STATE_DIR, exist_ok=True)
    p = os.path.join(STATE_DIR, "state.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(p + ".tmp", p)


def due_minutes(job, last, now_t):
    """Minutes since the last pass (≤ GRACE_MIN) when the job's cron matches."""
    c = parse_cron(str(job["cron"]))
    start = now_t - dt.timedelta(minutes=GRACE_MIN)
    if last:
        start = max(start, dt.datetime.fromtimestamp(last, now_t.tzinfo) + dt.timedelta(minutes=1))
    t, out = start.replace(second=0, microsecond=0), []
    while t <= now_t:
        if cron_match(c, t):
            out.append(t)
        t += dt.timedelta(minutes=1)
    return out


def expired(job, now_t):
    until = job.get("until")
    if not until:
        return False
    try:
        u = dt.datetime.fromisoformat(str(until))
    except ValueError:
        return False
    if u.tzinfo is None:
        u = u.replace(tzinfo=now_t.tzinfo)
    return now_t > u


def tick(cfg, now=None, dry=False):
    now = now or time.time()
    tz = ZoneInfo(str(cfg.get("timezone") or "Asia/Tashkent"))
    now_t = dt.datetime.fromtimestamp(now, tz).replace(second=0, microsecond=0)
    st = load_state() if not dry else {}
    last_all = st.get("last") or {}
    done_once = set(st.get("done_once") or [])
    seen = st.get("seen") or {}
    sent = 0
    for job in cfg.get("jobs") or []:
        jid, kind, t0 = job["id"], job["type"], time.time()
        row = {"t": now_t.strftime("%Y-%m-%d %H:%M"), "job": jid, "kind": kind, "what": "", "ms": 0}
        if job.get("enabled") is False or expired(job, now_t):
            continue
        if kind == "once":
            if jid in done_once:
                continue
            at = dt.datetime.fromisoformat(str(job["at"]))
            at = at.replace(tzinfo=tz) if at.tzinfo is None else at
            if at > now_t:
                continue
            if job.get("quiet", False) and quiet(cfg, now_t):
                row["what"] = "skipped: quiet hours"
            else:
                enqueue(cfg, job, str(job["prompt"]), now_t.strftime("%Y%m%d%H%M"), now, dry); sent += 1
                row["what"] = "queued"
            done_once.add(jid)
            log(row, dry)
            continue
        mins = due_minutes(job, last_all.get(jid), now_t)
        last_all[jid] = now_t.timestamp()
        if not mins:
            continue
        is_quiet = quiet(cfg, now_t)
        if kind == "think":
            if job.get("quiet", True) and is_quiet:
                row["what"] = "skipped: quiet hours"
            else:
                enqueue(cfg, job, str(job["prompt"]), mins[-1].strftime("%Y%m%d%H%M"), now, dry); sent += 1
                row["what"] = "queued" + (" (made up %d min late)" % int((now_t - mins[-1]).total_seconds() // 60) if mins[-1] < now_t else "")
        else:   # beat
            if job.get("quiet", False) and is_quiet:
                row["what"] = "skipped: quiet hours"
            else:
                found, err = run_check(job)
                known = seen.get(jid) or []
                new = [(k, txt) for k, txt in found if k not in known]
                for k, txt in new:
                    head = str(job.get("prompt") or "").strip()
                    enqueue(cfg, job, ("%s\n%s" % (head, txt)) if head else txt, k, now, dry); sent += 1
                seen[jid] = (known + [k for k, _ in new])[-SEEN_MAX:]
                row["what"] = ("error: " + err) if err else ("found %d" % len(new) if new else "nothing")
        row["ms"] = int((time.time() - t0) * 1000)
        log(row, dry)
    if not dry:
        st.update(last=last_all, done_once=sorted(done_once), seen=seen)
        save_state(st)
    return sent


# ── watchdog: the session has not taken a queued message for too long ──
def queue_lag(now=None):
    """→ (age in seconds of the oldest message the session has not taken, its byte offset) or (0, None)."""
    now = now or time.time()
    ev = os.path.join(QUEUE, "events.jsonl")
    cur = None
    for name in ("feeder-cursor", "cursor"):
        try:
            cur = int(open(os.path.join(QUEUE, name)).read().strip() or 0)
            break
        except (OSError, ValueError):
            continue
    if cur is None:
        return 0, None
    try:
        size = os.path.getsize(ev)
    except OSError:
        return 0, None
    if size <= cur:
        return 0, None
    with open(ev, "rb") as f:
        f.seek(cur)
        line = f.readline()
    try:
        ts = json.loads(line.decode("utf-8")).get("ts", 0) / 1000.0
    except (ValueError, AttributeError):
        return 0, cur
    return max(0.0, now - ts), cur


def watchdog(cfg, now=None, dry=False, send=None):
    w = cfg.get("watchdog") or {}
    if w.get("enabled") is False:
        return None
    after = float(w.get("after_min") or 15) * 60
    age, off = queue_lag(now)
    st = load_state() if not dry else {}
    if age < after:
        if st.get("watchdog_alerted") and not dry:
            st["watchdog_alerted"] = None; save_state(st)
        return None
    if st.get("watchdog_alerted") == off:
        return None                                       # one message per incident
    text = str(w.get("text") or "Heartbeat: Mila has not taken her queue for %d min — the session is probably stopped or out of limit.") % int(age // 60)
    token = os.environ.get(str(w.get("token_env") or "BOT_TOKEN"), "")
    chat = os.environ.get(str(w.get("chat_env") or "MILA_ADMIN_CHAT"), "")
    if dry:
        print("WATCHDOG " + text)
        return text
    ok = False
    if token and chat:
        try:
            ok = (send or _tg_send)(token, chat, text)
        except Exception:
            ok = False
    log({"t": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "job": "watchdog", "kind": "watchdog",
         "what": "alert sent" if ok else "alert NOT sent (no token/chat or Telegram error)", "ms": 0}, False)
    st["watchdog_alerted"] = off
    save_state(st)
    return text


def _tg_send(token, chat, text):
    req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % token, data=urllib.parse.urlencode({"chat_id": chat, "text": text}).encode())
    with urllib.request.urlopen(req, timeout=20) as r:
        return bool(json.loads(r.read().decode()).get("ok"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Heartbeat — Mila's schedule outside the session")
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    try:
        cfg = load_config(a.config)
    except FileNotFoundError:
        print("heartbeat: no %s — nothing to do" % a.config)
        return 0
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    if a.list:
        for j in cfg.get("jobs") or []:
            print("%-24s %-6s %s" % (j["id"], j["type"], j.get("cron") or j.get("at")))
        return 0
    tick(cfg, dry=a.dry_run)
    watchdog(cfg, dry=a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
