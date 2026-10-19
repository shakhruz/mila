#!/usr/bin/env python3
"""alisa.py — your Mila in a Yandex Alice speaker (skill «Моя Мила»). Stdlib only.
  alisa.py code                 → 6-digit code (5 min) for «/alisa»: the owner says it to the speaker to link it to this Mila
  alisa.py summary [--text T]   → upload the hourly voice summary (≤1500 chars; without --text — reads stdin)
Key: ~/.config/mila/alisa.key (given by the fleet admin; never printed). URL: ALISA_API (default https://home.milagpt.io/api/alisa).
Exit 2 — no key (ask the admin), 3 — service refused (bad key / empty), 4 — network."""
import json, os, sys, urllib.error, urllib.request

API = os.environ.get("ALISA_API", "https://home.milagpt.io/api/alisa").rstrip("/")
KEYF = os.path.expanduser(os.environ.get("ALISA_KEY_FILE", "~/.config/mila/alisa.key"))


def post(path, data):
    try: key = open(KEYF).read().strip()
    except OSError: print("no key: " + KEYF + " — ask the admin to connect this Mila to Alice", file=sys.stderr); sys.exit(2)
    r = urllib.request.Request(API + path, data=json.dumps(data, ensure_ascii=False).encode(), method="POST",
                               headers={"Content-Type": "application/json", "X-Mila-Key": key, "User-Agent": "mila-alisa/1.0"})
    try:
        with urllib.request.urlopen(r, timeout=15) as x: return json.load(x)
    except urllib.error.HTTPError as e:
        print("refused: %s %s" % (e.code, e.read()[:200].decode("utf-8", "replace")), file=sys.stderr); sys.exit(3)
    except Exception as e:
        print("network: %s" % e, file=sys.stderr); sys.exit(4)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["code"]:
        j = post("/code", {}); print(json.dumps({"code": j["code"], "ttl_min": j.get("ttl", 300) // 60}, ensure_ascii=False))
    elif a[:1] == ["summary"]:
        t = a[a.index("--text") + 1] if "--text" in a else sys.stdin.read()
        j = post("/summary", {"text": t.strip()[:1500]}); print(json.dumps({"ok": True, "chars": j.get("chars")}))
    else:
        sys.exit(__doc__)
