#!/usr/bin/env python3
"""Чтение сейфа Милы (work/secrets/<имя>.env, его пишет seif.py по одноразовой ссылке). Значения не печатает никогда.
  safe_read.py <имя> --check ПОЛЕ[,ПОЛЕ…]   → {"ok": true, "есть": [...], "нет": [...], "маска": {"CARD_NUMBER": "****1234"}}
  в коде: from safe_read import read_safe, mask; v = read_safe("login")["CARD_NUMBER"]
Файл с правами шире 600 — отказ (кто-то открыл сейф). Папка — SAFE_DIR или ~/work/secrets."""
import json, os, re, sys

SAFE_DIR = os.path.expanduser(os.environ.get("SAFE_DIR", "~/work/secrets"))


class SafeError(Exception):
    pass


def read_safe(name):
    if not re.fullmatch(r"[a-z0-9_-]{1,40}", name or ""):
        raise SafeError("имя сейфа — латиница, цифры, - и _")
    p = os.path.join(SAFE_DIR, name + ".env")
    if not os.path.exists(p):
        raise SafeError("сейфа «%s» нет — попросить ссылку сейфа у старшей" % name)
    if os.stat(p).st_mode & 0o077:
        raise SafeError("сейф «%s» открыт для других (права не 600) — не читаю, сказать старшей" % name)
    out = {}
    for ln in open(p, encoding="utf-8"):
        m = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", ln.rstrip("\n"))
        if m:
            v = m.group(2)
            if len(v) >= 2 and v[0] == v[-1] == "'":
                v = v[1:-1].replace("'\\''", "'")
            out[m.group(1)] = v
    return out


def mask(field, v):
    v = str(v or "")
    if re.search(r"CARD_NUMBER|PAN", field):
        return "****" + re.sub(r"\D", "", v)[-4:]
    if re.search(r"LOGIN|USER|EMAIL|PHONE", field):
        return v[:3] + "…"
    if re.search(r"EXPIR", field):
        return "есть"
    return "••••"


def main():
    a = sys.argv[1:]
    if not a or "--check" not in a:
        sys.exit(__doc__)
    fields = [f for f in a[a.index("--check") + 1].split(",") if f]
    try:
        d = read_safe(a[0])
    except SafeError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)); sys.exit(2)
    have = [f for f in fields if d.get(f)]
    print(json.dumps({"ok": len(have) == len(fields), "есть": have, "нет": [f for f in fields if f not in have],
                      "маска": {f: mask(f, d[f]) for f in have}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
