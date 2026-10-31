#!/usr/bin/env python3
"""Executor for the consent proxy: publish one post through Zernio. Runs as mila-io; the key never reaches the session.

stdin: {"text": "...", "targets": ["<account id>", …], "when": "ISO time or empty = now", "attachments": ["/checked/copy", …]}
env: ZERNIO_API_KEY (required), ZERNIO_API_URL (default below — check against the live account's API docs before enabling).
stdout: {"ok": bool, "id": "...", "error": "..."}; the key is never printed."""
import json, os, sys, urllib.error, urllib.request

URL = os.environ.get("ZERNIO_API_URL", "https://zernio.com/api/v1/posts")


def main():
    key = os.environ.get("ZERNIO_API_KEY", "")
    if not key:
        print(json.dumps({"ok": False, "error": "no ZERNIO_API_KEY for the proxy"}))
        return 1
    p = json.load(sys.stdin)
    if p.get("attachments"):
        print(json.dumps({"ok": False, "error": "media upload is not wired yet — publish text only or upload by hand"}))
        return 1
    body = {"content": p.get("text", ""), "platforms": [{"accountId": t} for t in p.get("targets") or []]}
    if p.get("when"):
        body["scheduledFor"] = p["when"]
    else:
        body["publishNow"] = True
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode() or "{}")
        print(json.dumps({"ok": True, "id": str((d.get("post") or d).get("_id") or d.get("id") or "")}))
        return 0
    except urllib.error.HTTPError as e:
        print(json.dumps({"ok": False, "error": "Zernio HTTP %d" % e.code}))
        return 1
    except (OSError, ValueError) as e:
        print(json.dumps({"ok": False, "error": type(e).__name__}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
