#!/usr/bin/env python3
"""mila onboard — three steps to a working Mila, each one checked before the next.

  1. Bot token   — asked without echo, checked with getMe, saved to <state>/.env (600, folder 700).
  2. Claude      — `claude auth status`; not signed in → `claude auth login` (Anthropic's own sign-in page).
                   Mila never sees, copies or stores the login.
  3. First pair  — a 6-character code is shown here; you send it to your bot from Telegram. The sender who
                   sends this exact code becomes the owner: allowFrom + dmPolicy allowlist in access.json,
                   OWNER_ID in ~/.claude/settings.json (send-guard answers only the owner and connected chats).

  mila onboard            run the three steps (a step that is already done is only checked)
  mila onboard --check    only check, change nothing; exit 0 when all three are done

Step 3 reads the bot's updates itself, so the bot must not be polled by anything else for a minute:
close the Claude Code session and stop the receiver daemon (`mila onboard` tells you if it sees one).
Env: TELEGRAM_STATE_DIR, TELEGRAM_BOT_TOKEN, MILA_TG_API (tests), MILA_CLAUDE (claude command), MILA_PAIR_WAIT (seconds, 300).
"""
import getpass
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
import urllib.request

STATE = os.environ.get("TELEGRAM_STATE_DIR", os.path.expanduser("~/.claude/channels/telegram"))
ENV_FILE = os.path.join(STATE, ".env")
ACCESS = os.path.join(STATE, "access.json")
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude"))
SETTINGS = os.path.join(CLAUDE_DIR, "settings.json")
API = os.environ.get("MILA_TG_API", "https://api.telegram.org")
CLAUDE = os.environ.get("MILA_CLAUDE", "claude")
TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"   # без 0/o, 1/l/i — код читают глазами


def say(mark, text):
    print("%s %s" % (mark, text), flush=True)


def tg(token, method, params=None, timeout=15):
    """Bot API. The token never appears in an error text."""
    url = "%s/bot%s/%s" % (API, token, method)
    data = urllib.parse.urlencode(params).encode() if params else None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "description": "HTTP %s" % e.code}
    except Exception as e:
        return {"ok": False, "description": str(e).replace(token, "<token>")}


def saved_token():
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if tok:
        return tok
    try:
        for line in open(ENV_FILE, encoding="utf-8"):
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip().strip("\"'")
    except OSError:
        pass
    return ""


def write_private(path, text):
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    os.chmod(os.path.dirname(path), 0o700)
    try:
        os.unlink(path + ".tmp")   # старый tmp с чужими правами: O_CREAT не меняет права существующего файла
    except FileNotFoundError:
        pass
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".tmp", path)
    os.chmod(path, 0o600)


def save_token(tok):
    lines = []
    try:
        lines = [l for l in open(ENV_FILE, encoding="utf-8").read().splitlines() if not l.startswith("TELEGRAM_BOT_TOKEN=")]
    except OSError:
        pass
    write_private(ENV_FILE, "\n".join(lines + ["TELEGRAM_BOT_TOKEN=" + tok]) + "\n")


# ── step 1 ─────────────────────────────────────────────────────────────────
def step_token(check):
    tok = saved_token()
    if tok:
        me = tg(tok, "getMe")
        if me.get("ok"):
            say("✓", "1/3 bot token: @%s" % me["result"].get("username", "?"))
            return tok, me["result"]
        say("✗", "1/3 bot token is saved but Telegram does not accept it: %s" % me.get("description", "?"))
    elif check:
        say("✗", "1/3 bot token: not saved yet")
    if check:
        return None, None
    for _ in range(3):
        tok = getpass.getpass("   Paste the bot token from @BotFather (input is hidden): ").strip()
        if not TOKEN_RE.match(tok):
            say("✗", "   That does not look like a bot token (123456789:AA…). Try again.")
            continue
        me = tg(tok, "getMe")
        if not me.get("ok"):
            say("✗", "   Telegram does not accept this token: %s" % me.get("description", "?"))
            continue
        save_token(tok)
        say("✓", "1/3 bot token: @%s, saved to %s (600)" % (me["result"].get("username", "?"), ENV_FILE))
        return tok, me["result"]
    return None, None


# ── step 2 ─────────────────────────────────────────────────────────────────
def claude_status():
    try:
        r = subprocess.run([CLAUDE, "auth", "status"], capture_output=True, text=True, timeout=30)
        return json.loads(r.stdout or "{}")
    except FileNotFoundError:
        return {"error": "claude not found — install Claude Code first"}
    except Exception as e:
        return {"error": str(e)[:120]}


def step_claude(check):
    st = claude_status()
    if st.get("loggedIn"):
        say("✓", "2/3 Claude: signed in (%s)" % st.get("authMethod", "?"))
        return True
    if st.get("error"):
        say("✗", "2/3 Claude: %s" % st["error"])
        return False
    if check:
        say("✗", "2/3 Claude: not signed in — run `claude auth login`")
        return False
    say("…", "2/3 Claude: not signed in. Opening Anthropic's sign-in (your own plan or API key; Mila never sees it).")
    subprocess.run([CLAUDE, "auth", "login"])
    if claude_status().get("loggedIn"):
        say("✓", "2/3 Claude: signed in")
        return True
    say("✗", "2/3 Claude: still not signed in — run `claude auth login` and then `mila onboard` again")
    return False


# ── step 3 ─────────────────────────────────────────────────────────────────
def load_access():
    try:
        a = json.load(open(ACCESS, encoding="utf-8"))
        return a if isinstance(a, dict) else {}
    except (OSError, ValueError):
        return {}


def owner_ids():
    return [str(x) for x in load_access().get("allowFrom", [])]


def set_owner(uid):
    a = load_access()
    allow = [str(x) for x in a.get("allowFrom", [])]
    if uid not in allow:
        allow.append(uid)
    a["allowFrom"] = allow
    a["dmPolicy"] = "allowlist"
    a.setdefault("groups", {})
    write_private(ACCESS, json.dumps(a, ensure_ascii=False, indent=2) + "\n")
    try:
        s = json.load(open(SETTINGS, encoding="utf-8"))
    except (OSError, ValueError):
        s = {}
    if s.get("env", {}).get("OWNER_ID") != uid:
        s.setdefault("env", {})["OWNER_ID"] = uid
        os.makedirs(CLAUDE_DIR, exist_ok=True)
        tmp = SETTINGS + ".tmp"
        json.dump(s, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        os.replace(tmp, SETTINGS)


def step_pair(tok, me, check):
    ids = owner_ids()
    if ids and load_access().get("dmPolicy") == "allowlist":
        say("✓", "3/3 owner paired: %d id in allowFrom, policy allowlist" % len(ids))
        return True
    if check:
        say("✗", "3/3 owner: not paired yet")
        return False
    code = "".join(secrets.choice(ALPHABET) for _ in range(6))
    wait = int(os.environ.get("MILA_PAIR_WAIT", "300"))
    say("…", "3/3 Send this code to @%s in Telegram (a private message):  %s" % (me.get("username", "your bot"), code))
    say(" ", "    waiting up to %d s; Ctrl-C to stop" % wait)
    # Читаем без offset и ничего не подтверждаем: всё, что писали боту до и во время onboard, остаётся для Милы (Качество 22.10)
    end = time.time() + wait
    while time.time() < end:
        r = tg(tok, "getUpdates", {"timeout": 20, "allowed_updates": json.dumps(["message"])}, timeout=30)
        if not r.get("ok"):
            desc = str(r.get("description", ""))
            if "webhook" in desc.lower():
                say("✗", "3/3 the bot has a webhook set, so it can't be read here. Remove it (Bot API deleteWebhook) "
                         "and run `mila onboard` again.")
                return False
            if r.get("error_code") == 409 or "terminated by other getUpdates" in desc:
                say("✗", "3/3 something else is reading this bot (a Claude Code session or the receiver daemon). "
                         "Close it for a minute (`mila fix` restarts it later) and run `mila onboard` again.")
                return False
            time.sleep(2)
            continue
        for u in r.get("result", []):
            m = u.get("message") or {}
            if (m.get("chat") or {}).get("type") != "private":
                continue
            if (m.get("text") or "").strip().lower() == code:
                uid = str((m.get("from") or {}).get("id", ""))
                if not uid.isdigit():
                    continue
                set_owner(uid)
                tg(tok, "sendMessage", {"chat_id": uid, "text": "Paired ✓ You are my owner. Start Claude Code with `mila` in your terminal."})
                say("✓", "3/3 owner paired (id %s): allowFrom + allowlist, OWNER_ID in settings.json" % uid)
                return True
        if r.get("result"):
            time.sleep(2)   # в очереди есть непрочитанное — не крутимся вхолостую
    say("✗", "3/3 no message with the code arrived. Run `mila onboard` again.")
    return False


def main():
    check = "--check" in sys.argv[1:]
    print("Mila · onboard%s" % (" · check only" if check else ""))
    tok, me = step_token(check)
    ok1 = bool(tok)
    ok2 = step_claude(check) if ok1 or check else False
    ok3 = step_pair(tok, me or {}, check) if ok1 and (ok2 or check) else False
    if not ok1:
        say("✗", "3/3 owner: needs the bot token first")
    elif not ok2 and not check:
        say("✗", "3/3 owner: needs Claude signed in first")
    if ok1 and ok2 and ok3:
        print("\nAll three done. Start Mila:  mila      Check any time:  mila doctor")
        return 0
    print("\nNot done yet — fix the ✗ line and run `mila onboard` again.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nstopped")
        sys.exit(130)
