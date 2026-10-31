#!/usr/bin/env python3
"""Session side of the consent proxy: ask for an outside action; the proxy runs it only after the owner's yes to this exact payload.

  consent_client.py <category> [--payload file.json | < payload.json] [--socket PATH]
Answers (one JSON line): done (with the service's result) · asked (a card went to the owner — wait for the yes, then send the SAME
payload again) · waiting (the card is still open) · denied (why). No proxy, no answer, anything unclear — denied: nothing is published.
Socket: --socket, else MILA_CONSENT_SOCKET. Only stdlib."""
import argparse, json, os, socket, sys

BUF = 64 * 1024


def ask(category, payload, path, timeout=150):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(path)
        s.sendall((json.dumps({"op": "request", "category": category, "payload": payload}, ensure_ascii=False) + "\n").encode())
        raw = b""
        while not raw.endswith(b"\n"):
            chunk = s.recv(BUF)
            if not chunk:
                break
            raw += chunk
        return json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as e:
        return {"status": "denied", "why": "consent proxy unavailable (%s) — nothing is published" % type(e).__name__}
    finally:
        s.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("category")
    ap.add_argument("--payload")
    ap.add_argument("--socket", default=os.environ.get("MILA_CONSENT_SOCKET", ""))
    a = ap.parse_args(argv)
    try:
        payload = json.load(open(a.payload, encoding="utf-8")) if a.payload else json.load(sys.stdin)
    except (OSError, ValueError) as e:
        print(json.dumps({"status": "denied", "why": "payload does not read: %s" % type(e).__name__}))
        return 2
    res = ask(a.category, payload, a.socket) if a.socket else {"status": "denied", "why": "no consent socket configured — nothing is published"}
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("status") in ("done", "asked", "waiting") else 2


if __name__ == "__main__":
    sys.exit(main())
