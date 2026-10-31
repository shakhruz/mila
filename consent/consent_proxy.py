#!/usr/bin/env python3
"""Consent proxy (RU: «согласие без терминала») — an outside action runs only after the owner said yes to THAT action in Telegram.

Why a proxy and not just a hook: if the session holds the service key, it can repeat the same call with curl from Bash and no hook
sees it. So the keys live only with this proxy, which runs as a separate OS user (mila-io); the session asks the proxy, the proxy
shows the owner a card it draws itself, and executes only with a fresh, single-use consent for the exact payload hash.

  consent_proxy.py serve --config /etc/mila-io/<mila>/consent.json     # the service (as mila-io)

Two unix sockets:
  session socket (the Mila may connect): {"op": "request", "category": "...", "payload": {...}}
      → {"status": "done", "result": …} | {"status": "asked", "id": …} | {"status": "waiting", "id": …} | {"status": "denied", "why": …}
  io socket (only mila-io: the Telegram receiver forwards button presses here; the owner's category switches come here too):
      {"op": "callback", "data": "consent:<id>.<sig>", "from_id": "...", "chat_id": "..."}   → {"status": "granted" | "declined" | "ignored"}
      {"op": "category", "name": "...", "enabled": true|false, "from_id": "..."}              → owner turns a category on or off
Every step goes to consents.jsonl (no payload, only hash and a short preview). Fail closed: anything unclear means no.
Config keys, all paths absolute: owner_id_env, bot_token_env, home (the Mila's home — attachments only from inside it),
state_dir, session_socket, io_socket, ttl_min (15), max_attachment_mb (20),
categories: {name: {"enabled": bool, "exec": [command…], "title": "…"}}. Only stdlib."""
import argparse, hashlib, hmac, json, os, re, secrets, socket, stat, subprocess, sys, tempfile, threading, time, unicodedata, urllib.parse, urllib.request

PREFIX = "consent:"
BUF = 64 * 1024
INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿]")


class Proxy:
    def __init__(self, cfg, send=None, run=None, now=time.time):
        self.cfg, self.now = cfg, now
        self.state = cfg["state_dir"]
        os.makedirs(self.state, mode=0o700, exist_ok=True)
        self.key = self._key()
        self.send = send or self._tg_send
        self.run = run or self._exec
        self.lock = threading.Lock()
        self.ttl = float(cfg.get("ttl_min", 15)) * 60
        self.max_bytes = int(float(cfg.get("max_attachment_mb", 20)) * 1024 * 1024)
        self.cats = self._load("categories.json", None) or {k: bool(v.get("enabled")) for k, v in (cfg.get("categories") or {}).items()}

    # ── files ──
    def _key(self):
        p = os.path.join(self.state, "hmac.key")
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.write(fd, secrets.token_bytes(32)); os.close(fd)
        except FileExistsError:
            pass
        with open(p, "rb") as f:
            return f.read()

    def _load(self, name, default):
        try:
            with open(os.path.join(self.state, name), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return default

    def _save(self, name, v):
        p = os.path.join(self.state, name)
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(v, f, ensure_ascii=False)
        os.replace(p + ".tmp", p)

    def journal(self, row):
        with open(os.path.join(self.state, "consents.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(dict({"ts": int(self.now())}, **row), ensure_ascii=False) + "\n")

    # ── attachments: the proxy reads with more rights than the session — only files inside the Mila's home ──
    def attachment(self, path):
        home = os.path.realpath(self.cfg["home"])
        p = os.path.abspath(os.path.join(home, str(path))) if not os.path.isabs(str(path)) else os.path.abspath(str(path))
        cur = "/"
        for part in p.strip("/").split("/"):
            cur = os.path.join(cur, part)
            if os.path.islink(cur):
                raise ValueError("attachment path has a symlink: %s" % os.path.basename(p))
        if os.path.realpath(p) != p or os.path.commonpath([p, home]) != home:
            raise ValueError("attachment outside the Mila's home: %s" % os.path.basename(p))
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as f:
            st = os.fstat(f.fileno())
            if not stat.S_ISREG(st.st_mode):
                raise ValueError("attachment is not a regular file: %s" % os.path.basename(p))
            if st.st_size > self.max_bytes:
                raise ValueError("attachment larger than %d MB: %s" % (self.max_bytes // 1048576, os.path.basename(p)))
            data = f.read(self.max_bytes + 1)
        return {"name": os.path.basename(p), "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "data": data}

    # ── what exactly the owner approves ──
    def digest(self, category, payload):
        """→ (hash, attachments with content). The hash covers the category, the canonical payload and every attachment's content."""
        atts = [self.attachment(a) for a in (payload.get("attachments") or [])]
        body = {k: v for k, v in payload.items() if k != "attachments"}
        material = json.dumps({"category": category, "payload": body, "attachments": [(a["name"], a["sha256"]) for a in atts]},
                              ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(material.encode("utf-8")).hexdigest(), atts

    def preview(self, category, payload, atts):
        clean = lambda s: INVISIBLE.sub("", unicodedata.normalize("NFC", str(s or "")))
        text = clean(payload.get("text"))
        where = ", ".join(clean(x) for x in (payload.get("targets") or [])) or "—"
        lines = ["Публикуем? · %s" % clean((self.cfg["categories"].get(category) or {}).get("title") or category),
                 "Куда: %s" % where, "Текст: %d знаков" % len(text)]
        if len(text) <= 500:
            lines.append(text)
        else:
            lines += [text[:350], "…", text[-120:]]
        if payload.get("when"):
            lines.append("Когда: %s" % clean(payload["when"]))
        for a in atts:
            lines.append("Вложение: %s, %d КБ" % (clean(a["name"]), max(1, a["size"] // 1024)))
        return "\n".join(lines)

    def sig(self, cid, h):
        return hmac.new(self.key, ("%s:%s" % (cid, h)).encode(), hashlib.sha256).hexdigest()[:20]

    # ── session side ──
    def request(self, category, payload):
        if not isinstance(payload, dict) or category not in (self.cfg.get("categories") or {}):
            return {"status": "denied", "why": "unknown category"}
        if not self.cats.get(category):
            self.journal({"ev": "denied", "category": category, "why": "category off"})
            return {"status": "denied", "why": "the owner turned this category off"}
        try:
            h, atts = self.digest(category, payload)
        except (ValueError, OSError) as e:
            self.journal({"ev": "denied", "category": category, "why": str(e)[:160]})
            return {"status": "denied", "why": str(e)[:200]}
        with self.lock:
            cons = self._load("consents.json", {})
            now = self.now()
            for cid, c in cons.items():
                if c["hash"] != h or c.get("used") or c.get("declined"):
                    continue
                if c.get("granted") and now - c["granted"] <= self.ttl:
                    c["used"] = now
                    self._save("consents.json", cons)
                    self.journal({"ev": "used", "id": cid, "category": category, "hash": h[:16]})
                    break
                if not c.get("granted") and now - c["asked"] <= self.ttl:
                    return {"status": "waiting", "id": cid}
            else:
                cid = secrets.token_hex(4)
                cons[cid] = {"hash": h, "category": category, "asked": now}
                self._save("consents.json", cons)
                card = self.preview(category, payload, atts)
                ok = self.send(card, [[{"text": "Да, это", "callback_data": "%s%s.%s.y" % (PREFIX, cid, self.sig(cid, h))},
                                       {"text": "Нет", "callback_data": "%s%s.%s.n" % (PREFIX, cid, self.sig(cid, h))}]])
                self.journal({"ev": "asked", "id": cid, "category": category, "hash": h[:16], "card_sent": bool(ok)})
                return {"status": "asked", "id": cid} if ok else {"status": "denied", "why": "could not show the card to the owner"}
        return self.execute(category, payload, atts, cid)

    def execute(self, category, payload, atts, cid):
        with tempfile.TemporaryDirectory(prefix="consent-") as td:
            files = []
            for a in atts:                                   # the executor gets the checked copies, not the session's paths
                p = os.path.join(td, a["name"])
                with open(p, "wb") as f:
                    f.write(a["data"])
                files.append(p)
            body = dict({k: v for k, v in payload.items() if k != "attachments"}, attachments=files)
            res = self.run(self.cfg["categories"][category]["exec"], body)
        self.journal({"ev": "executed", "id": cid, "category": category, "ok": bool(res.get("ok"))})
        return {"status": "done", "result": res}

    # ── io side (receiver, owner) ──
    def callback(self, data, from_id, chat_id=None):
        owner = os.environ.get(self.cfg.get("owner_id_env") or "MILA_OWNER_ID", "")
        m = re.fullmatch(re.escape(PREFIX) + r"([0-9a-f]{8})\.([0-9a-f]{20})\.([yn])", str(data or ""))
        if not m:
            return {"status": "ignored", "why": "not a consent button"}
        cid, s, yn = m.groups()
        if not owner or str(from_id) != owner or (chat_id is not None and str(chat_id) != owner):
            self.journal({"ev": "rejected", "id": cid, "why": "not the owner in the owner's private chat"})
            return {"status": "ignored", "why": "only the owner in a private chat"}
        with self.lock:
            cons = self._load("consents.json", {})
            c = cons.get(cid)
            if not c or not hmac.compare_digest(s, self.sig(cid, c["hash"])):
                self.journal({"ev": "rejected", "id": cid, "why": "unknown id or bad signature"})
                return {"status": "ignored", "why": "unknown or forged"}
            if c.get("granted") or c.get("declined") or self.now() - c["asked"] > self.ttl:
                return {"status": "ignored", "why": "already answered or expired"}
            c["granted" if yn == "y" else "declined"] = self.now()
            self._save("consents.json", cons)
        self.journal({"ev": "granted" if yn == "y" else "declined", "id": cid, "hash": c["hash"][:16]})
        return {"status": "granted" if yn == "y" else "declined"}

    def category(self, name, enabled, from_id):
        owner = os.environ.get(self.cfg.get("owner_id_env") or "MILA_OWNER_ID", "")
        if not owner or str(from_id) != owner or name not in (self.cfg.get("categories") or {}):
            return {"status": "ignored"}
        before = self.cats.get(name)
        self.cats[name] = bool(enabled)
        self._save("categories.json", self.cats)
        self.journal({"ev": "category", "name": name, "was": before, "now": bool(enabled)})
        return {"status": "ok", "enabled": bool(enabled)}

    # ── outside world ──
    def _tg_send(self, text, keyboard):
        token = os.environ.get(self.cfg.get("bot_token_env") or "BOT_TOKEN", "")
        owner = os.environ.get(self.cfg.get("owner_id_env") or "MILA_OWNER_ID", "")
        if not token or not owner:
            return False
        data = urllib.parse.urlencode({"chat_id": owner, "text": text, "reply_markup": json.dumps({"inline_keyboard": keyboard})}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % token, data=data), timeout=20) as r:
                return bool(json.loads(r.read().decode()).get("ok"))
        except Exception:
            return False

    def _exec(self, cmd, body):
        try:
            r = subprocess.run(list(cmd), input=json.dumps(body, ensure_ascii=False), capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as e:
            return {"ok": False, "error": type(e).__name__}
        try:
            out = json.loads(r.stdout or "{}")
        except ValueError:
            out = {"output": (r.stdout or "")[-500:]}
        out.setdefault("ok", r.returncode == 0)
        return out


def serve(px, path, handler, mode):
    if os.path.lexists(path):
        os.unlink(path)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(path); os.chmod(path, mode); s.listen(16)
    def one(conn):
        with conn:
            try:
                conn.settimeout(10)
                raw = b""
                while not raw.endswith(b"\n") and len(raw) < 1 << 20:
                    chunk = conn.recv(BUF)
                    if not chunk:
                        break
                    raw += chunk
                res = handler(json.loads(raw.decode("utf-8")))
            except Exception as e:                       # fail closed: any error is a no
                res = {"status": "denied", "why": type(e).__name__}
            conn.sendall((json.dumps(res, ensure_ascii=False) + "\n").encode())
    while True:
        c, _ = s.accept()
        threading.Thread(target=one, args=(c,), daemon=True).start()


def session_handler(px):
    return lambda q: px.request(q.get("category"), q.get("payload")) if q.get("op") == "request" else {"status": "denied", "why": "unknown op"}


def io_handler(px):
    def h(q):
        if q.get("op") == "callback":
            return px.callback(q.get("data"), q.get("from_id"), q.get("chat_id"))
        if q.get("op") == "category":
            return px.category(q.get("name"), q.get("enabled"), q.get("from_id"))
        return {"status": "ignored"}
    return h


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["serve"])
    ap.add_argument("--config", required=True)
    a = ap.parse_args(argv)
    cfg = json.load(open(a.config, encoding="utf-8"))
    px = Proxy(cfg)
    threading.Thread(target=serve, args=(px, cfg["io_socket"], io_handler(px), 0o600), daemon=True).start()
    serve(px, cfg["session_socket"], session_handler(px), int(str(cfg.get("session_socket_mode", "660")), 8))
    return 0


if __name__ == "__main__":
    sys.exit(main())
