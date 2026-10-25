#!/usr/bin/env python3
"""plan-fakt · one slideshow post («Статья» format): sendRichMessage with <tg-slideshow> of the slides + the post HTML.

  send_slideshow.py CHAT_ID post.html s1.jpg s2.jpg …   (2–10 slides)

Prefer the plugin's reply with slideshow:true when your mila-telegram has it; this script is the fallback.
Token: env TELEGRAM_BOT_TOKEN, else TELEGRAM_BOT_TOKEN= in <state>/.env (TELEGRAM_STATE_DIR or ~/.claude/channels/telegram).
The token is never printed. Output: «ok <message_id>» or «fail <reason>»; exit 0 / 1 / 2 (input).
"""
import json, os, re, sys, uuid, urllib.error, urllib.request


def token():
    t = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if t:
        return t
    st = os.environ.get("TELEGRAM_STATE_DIR") or os.path.expanduser("~/.claude/channels/telegram")
    try:
        for line in open(os.path.join(st, ".env"), encoding="utf-8"):
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def build(chat, body_html, files, boundary):
    show = "<tg-slideshow>" + "".join('<img src="tg://photo?id=s%d"/>' % i for i in range(len(files))) + "</tg-slideshow>"
    rich = {"html": show + body_html, "media": [{"id": "s%d" % i, "media": {"type": "photo", "media": "attach://f%d" % i}} for i in range(len(files))]}

    def field(name, val, fn=None, ct=None):
        h = 'Content-Disposition: form-data; name="%s"' % name + ('; filename="%s"' % fn if fn else "")
        return ("--%s\r\n%s\r\n%s\r\n" % (boundary, h, "Content-Type: %s\r\n" % ct if ct else "")).encode() + val + b"\r\n"
    data = field("chat_id", str(chat).encode()) + field("rich_message", json.dumps(rich, ensure_ascii=False).encode())
    for i, f in enumerate(files):
        ct = "image/png" if f.lower().endswith(".png") else "image/jpeg"
        data += field("f%d" % i, open(f, "rb").read(), os.path.basename(f), ct)
    return data + ("--%s--\r\n" % boundary).encode()


def main(argv=None, opener=None):
    a = argv if argv is not None else sys.argv[1:]
    if len(a) < 4:
        print("send_slideshow.py CHAT_ID post.html s1 s2 … (2–10 слайдов)"); return 2
    chat, post, files = a[0], a[1], a[2:]
    if not re.fullmatch(r"-?\d{1,20}", chat):
        print("CHAT_ID — число"); return 2
    if not 2 <= len(files) <= 10:
        print("слайдов %d — нужно 2–10" % len(files)); return 2
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        print("нет файлов: %s" % ", ".join(missing)); return 2
    body = open(post, encoding="utf-8").read() if os.path.isfile(post) else post
    tok = token()
    if not tok:
        print("нет токена бота (TELEGRAM_BOT_TOKEN или .env канала)"); return 2
    b = uuid.uuid4().hex
    req = urllib.request.Request("https://api.telegram.org/bot%s/sendRichMessage" % tok, data=build(chat, body, files, b),
                                 headers={"Content-Type": "multipart/form-data; boundary=" + b})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=60) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            res = json.loads(e.read() or b"{}")
        except ValueError:
            res = {"description": "HTTP %s" % e.code}
    except (urllib.error.URLError, OSError) as e:
        res = {"description": "нет сети: %s" % type(e).__name__}
    if res.get("ok"):
        print("ok", (res.get("result") or {}).get("message_id")); return 0
    print("fail", str(res.get("description") or "")[:200].replace(tok, "<token>")); return 1


if __name__ == "__main__":
    sys.exit(main())
