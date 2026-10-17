#!/usr/bin/env python3
"""pd-mask.py — PostToolUse hook (Write|Edit|MultiEdit): после записи в то, что Мила ХРАНИТ (память, журналы, карточки, клиенты),
личные данные в файле заменяются ярлыками хранилища pd_vault (слой 2а ядра, по умолчанию включён; выключить — PD_MASK=0).
Не трогает: само хранилище и ключ, код (.py .js .ts .sh .json настроек), файлы вне списка папок. Ошибка хука не мешает работе (молча)."""
import json, os, re, subprocess, sys

HOME = os.path.expanduser("~")
WORK = os.environ.get("MILA_WORK", os.path.join(HOME, "work"))
VAULT_PY = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR", os.path.join(HOME, ".claude")), "skills", "pd-vault", "pd_vault.py")
GUARD = [os.path.join(WORK, d) for d in ("memory", "journal", "clients", "chats", "notes", "state/cards")] + \
        [os.path.join(WORK, f) for f in ("NOW.md", "CLIENTS.md", "USER.md", "DECISIONS.md")] + \
        [os.path.join(HOME, ".claude", "projects")]
SKIP = re.compile(r"(/state/pd/|pd\.key|\.(py|js|mjs|ts|sh|json|jsonl\.enc|enc)$)")


def guarded(p):
    p = os.path.realpath(p)
    if SKIP.search(p): return False
    if "/.claude/projects/" in p and "/memory/" not in p: return False   # в projects — только memory/, не транскрипты
    return any(p == g or p.startswith(g.rstrip("/") + "/") for g in map(os.path.realpath, GUARD))


def main():
    if os.environ.get("PD_MASK", "1") == "0": return
    try: ev = json.load(sys.stdin)
    except Exception: return
    if ev.get("tool_name") not in ("Write", "Edit", "MultiEdit"): return
    f = (ev.get("tool_input") or {}).get("file_path") or ""
    if not f or not guarded(f) or not os.path.isfile(VAULT_PY): return
    try:
        r = subprocess.run([sys.executable, "-I", VAULT_PY, "mask-file", f], capture_output=True, text=True, timeout=20)
        new = (json.loads(r.stdout or "{}").get("masked_new") or []) if r.returncode == 0 else []
        if new:   # Миле — короткая заметка, чтобы не удивлялась ярлыкам в своём файле
            print(json.dumps({"systemMessage": "pd-vault: личные данные в файле заменены ярлыками (" + ", ".join(new[:5]) + "). Значение — `pd_vault.py reveal ЯРЛЫК`, только для хозяина."}, ensure_ascii=False))
    except Exception:
        return


if __name__ == "__main__":
    main()
