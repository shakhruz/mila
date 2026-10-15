#!/usr/bin/env python3
"""mila_export.py — навык mila-export: выгрузить Милу в архив и возродить её из архива.

  mila_export.py export  [--home DIR | --claude DIR --work DIR] [--name NAME] [--out DIR]
                         [--with-history] [--with-media] [--allow GLOB ...] [--dry-run]
  mila_export.py restore ARCHIVE [--home DIR | --claude DIR --work DIR] [--overwrite] [--dry-run]
  mila_export.py verify  ARCHIVE            # манифест и sha256, ничего не пишет
  mila_export.py scan    DIR                # сканер секретов по папке

Мила принадлежит владельцу: архив + открытое ядро = она же, на любой машине.
Секретов в архиве нет: файлы с секретными именами не берутся, содержимое каждого файла проходит сканер,
находка — export падает со списком файлов (значения не печатаются). Только стандартная библиотека, Python 3.10+.
Формат архива: format=1 (tar.gz: <корень>/manifest.json, <корень>/RESTORE.md, <корень>/files/<zone>/<путь>).
"""
import argparse, fnmatch, hashlib, io, json, os, re, shutil, sys, tarfile, time
from datetime import datetime, timezone

FORMAT = 1
HOME = os.path.expanduser("~")
MAX_FILE = 5 * 1024 * 1024

# ── что не берём ────────────────────────────────────────────────────────────
SECRET_NAME = re.compile(r"(^\.env|token|key|credential|secret|passw|\.pem$|\.p12$|\.pfx$|^id_(rsa|ed25519|ecdsa)|\.netrc$|\.npmrc$)", re.I)
SECRET_DIRS = {"secrets", ".ssh", ".gnupg", ".aws"}
JUNK_DIRS = {"__pycache__", "node_modules", ".git", ".cache", "venv", ".venv", "dist", ".DS_Store"}
WORK_SKIP_DIRS = {"inbox", "outbox", "media", "backups", "export", "tmp", "_panel"}
HISTORY_CLAUDE = {"projects", "session-env", "sessions", "shell-snapshots", "todos", "history.jsonl"}  # транскрипты
HISTORY_WORK = {"journal"}
MEDIA_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav", ".ogg", ".m4a", ".oga",
             ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".zip", ".tar", ".gz", ".7z"}
CLAUDE_TOP_SKIP = {"mila-update", "plugins", "channels", "cache", "ide", "statsig", "telemetry", "debug",
                   "backups", "file-history", "paste-cache", "image-cache", "downloads"}

# ── сканер секретов (имя вида → регулярка); значения не печатаются ──────────
def _p(s): return re.compile(s)
PLACEHOLDER = re.compile(r"^(\$|\{|<|%|\(|os\.|process\.|env|your|xxx|\*{3}|\.{3}|example|changeme)", re.I)
SCANNERS = [
    ("openai/anthropic-style key (sk-)", _p(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("anthropic key (sk-ant-)", _p(r"\bsk-ant-[A-Za-z0-9_-]{10,}")),
    ("telegram bot token", _p(r"(?<![0-9A-Za-z])\d{8,10}:AA[A-Za-z0-9_-]{30,}")),
    ("github token (ghp_)", _p(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("aws access key (AKIA)", _p(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("resend key (re_)", _p(r"\bre_[A-Za-z0-9]{20,}")),
    ("private key block", _p(r"-----BEGIN [A-Z ]*PRIVATE KEY")),
]
KV = re.compile(r"""(?i)\b(?:password|passwd|pwd|api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)["']?\s*[=:]\s*["']?([A-Za-z0-9/+_.\-]{8,})""")


def scan_bytes(data, rel="", allow=()):
    """список (строка, вид) находок; значения в ответ не попадают."""
    if any(fnmatch.fnmatch(rel, g) for g in allow): return []
    text = data.decode("utf-8", "replace") if b"\0" not in data[:4096] else data.decode("latin-1")
    hits = []
    for n, line in enumerate(text.split("\n"), 1):
        if len(line) > 20000: line = line[:20000]
        for kind, rx in SCANNERS:
            if rx.search(line): hits.append((n, kind))
        for m in KV.finditer(line):
            v = m.group(1)
            if PLACEHOLDER.match(v) or len(v) < 12: continue
            if re.search(r"[A-Za-z]", v) and re.search(r"\d", v): hits.append((n, "password/key assignment"))
    return hits


# ── вспомогательное ─────────────────────────────────────────────────────────
def sha(b): return hashlib.sha256(b).hexdigest()
def die(msg, code=2): print(msg, file=sys.stderr); sys.exit(code)


def paths(a):
    if getattr(a, "home", None):
        claude, work = os.path.join(a.home, ".claude"), os.path.join(a.home, "work")
        home = a.home
    else:
        claude = a.claude or os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")
        work = a.work or os.environ.get("MILA_WORK") or os.path.join(HOME, "work")
        home = os.path.dirname(claude.rstrip("/")) or HOME
    return os.path.abspath(home), os.path.abspath(claude), os.path.abspath(work)


def sanitize_ids(o):
    """шаблон access.json: настройки политики остаются, id людей и чатов (числа, ключи-числа) — нет."""
    if isinstance(o, dict):
        return {k: sanitize_ids(v) for k, v in o.items()
                if not re.fullmatch(r"-?\d+", str(k)) and (isinstance(v, bool) or not isinstance(v, (int, float)))}
    if isinstance(o, list): return []
    if isinstance(o, str): return "" if re.fullmatch(r"-?\d+", o) else o
    return o


def sanitize_settings(o):
    """settings.json: хуки и права остаются, значения секретных env — нет."""
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if k == "env" and isinstance(v, dict):
                out[k] = {ek: ("" if SECRET_NAME.search(ek) else ev) for ek, ev in v.items()}
            else: out[k] = sanitize_settings(v)
        return out
    if isinstance(o, list): return [sanitize_settings(x) for x in o]
    return o


def env_names(data):
    names = []
    for line in data.decode("utf-8", "replace").splitlines():
        m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if m: names.append(m.group(1))
    return names


class Collector:
    def __init__(self, a, home, claude, work):
        self.a, self.home, self.claude, self.work = a, home, claude, work
        self.files, self.meta, self.skipped = {}, [], []
        self.env_names, self.mcp_servers = set(), set()
        self.hits = []       # (arcpath, строка, вид)

    def skip(self, where, reason): self.skipped.append({"path": where, "reason": reason})

    def add(self, zone, rel, data, mode=0o644):
        arc = "%s/%s" % (zone, rel)
        hits = scan_bytes(data, arc, self.a.allow or ())
        if hits:
            self.hits += [(arc, n, k) for n, k in hits]
            return
        self.files[arc] = data
        self.meta.append({"path": arc, "zone": zone, "rel": rel, "sha256": sha(data), "size": len(data),
                          "exec": bool(mode & 0o111)})

    def take_file(self, zone, rel, full):
        base = os.path.basename(full)
        if os.path.islink(full): return self.skip("%s/%s" % (zone, rel), "symlink")
        if SECRET_NAME.search(base):
            if base.startswith(".env") or base.endswith(".env"):
                try: self.env_names.update(env_names(open(full, "rb").read()))
                except OSError: pass
            return self.skip("%s/%s" % (zone, rel), "secret-like name")
        if not os.path.isfile(full): return
        ext = os.path.splitext(base)[1].lower()
        if ext in MEDIA_EXT and not self.a.with_media: return self.skip("%s/%s" % (zone, rel), "media/archive (use --with-media)")
        if os.path.getsize(full) > MAX_FILE: return self.skip("%s/%s" % (zone, rel), "larger than 5 MB")
        if ".bak" in base or base.endswith((".pyc", ".tmp", ".lock", "~")): return
        try: data = open(full, "rb").read()
        except OSError as e: return self.skip("%s/%s" % (zone, rel), "unreadable: %s" % e.strerror)
        mode = os.stat(full).st_mode
        self.add(zone, rel, data, mode)

    def walk(self, zone, root, rel_root, drop_top=()):
        """обход каталога; drop_top — имена верхнего уровня, которые не берём."""
        if not os.path.isdir(root): return
        for d, dirs, files in os.walk(root):
            relD = os.path.relpath(d, root)
            top = relD.split(os.sep)[0] if relD != "." else ""
            keep = []
            for x in sorted(dirs):
                rel = os.path.normpath(os.path.join(rel_root, relD, x)) if relD != "." else os.path.join(rel_root, x)
                if x in JUNK_DIRS or ".bak" in x: continue
                if x.lower() in SECRET_DIRS or SECRET_NAME.search(x):
                    self.skip("%s/%s/" % (zone, rel), "secret-like directory"); continue
                if os.path.islink(os.path.join(d, x)):
                    self.skip("%s/%s" % (zone, rel), "symlink"); continue
                keep.append(x)
            dirs[:] = [x for x in keep if not (relD == "." and x in drop_top)]
            for x in keep:
                if relD == "." and x in drop_top: self.skip("%s/%s/" % (zone, os.path.join(rel_root, x)), "excluded by default")
            for f in sorted(files):
                if relD == "." and f in drop_top:
                    self.skip("%s/%s" % (zone, os.path.join(rel_root, f)), "excluded by default"); continue
                rel = os.path.join(rel_root, f) if relD == "." else os.path.join(rel_root, relD, f)
                self.take_file(zone, rel, os.path.join(d, f))


def collect(a):
    home, claude, work = paths(a)
    if not (os.path.isdir(claude) or os.path.isdir(work)):
        die("не нашла дом Милы: нет %s и нет %s (укажите --home или --claude/--work)" % (claude, work))
    c = Collector(a, home, claude, work)
    hist = a.with_history
    # work/: инструкции, canon, память, ритуалы, кроны, знания, документы — всё, кроме служебного
    wskip = set(WORK_SKIP_DIRS) | (set() if hist else set(HISTORY_WORK))
    c.walk("work", work, "", drop_top=wskip)
    # ~/.claude: навыки, хуки, команды, агенты, инструкции верхнего уровня
    cskip = set(CLAUDE_TOP_SKIP) | (set() if hist else set(HISTORY_CLAUDE))
    for name in sorted(os.listdir(claude)) if os.path.isdir(claude) else []:
        full = os.path.join(claude, name)
        if name in ("settings.json", "settings.local.json"): continue
        if name.startswith(".") and os.path.isfile(full):
            c.skip("claude/" + name, "hidden state file of Claude Code (account data), not part of the Mila"); continue
        if name in cskip:
            c.skip("claude/%s%s" % (name, "/" if os.path.isdir(full) else ""),
                   "transcripts/history (use --with-history)" if name in HISTORY_CLAUDE else "handled separately or not part of the Mila")
            continue
        if os.path.isdir(full) and not os.path.islink(full): c.walk("claude", full, name)
        elif os.path.isfile(full): c.take_file("claude", name, full)
    if hist:
        for name in sorted(HISTORY_CLAUDE):
            full = os.path.join(claude, name)
            if os.path.isdir(full): c.walk("claude", full, name)
            elif os.path.isfile(full): c.take_file("claude", name, full)
    # settings.json без секретов
    for sname in ("settings.json",):
        sp = os.path.join(claude, sname)
        if os.path.isfile(sp):
            try:
                o = json.load(open(sp)); c.env_names.update((o.get("env") or {}).keys() if isinstance(o.get("env"), dict) else [])
                c.add("claude", sname, (json.dumps(sanitize_settings(o), ensure_ascii=False, indent=1) + "\n").encode())
            except (ValueError, OSError): c.skip("claude/" + sname, "not valid JSON")
    # плагины: список и версии (без кэша кода и без конфигов с токенами)
    for pj in ("installed_plugins.json", "known_marketplaces.json"):
        pp = os.path.join(claude, "plugins", pj)
        if os.path.isfile(pp): c.take_file("claude", "plugins/" + pj, pp)
    # состояние Telegram-канала: шаблон access.json, реестры/конфиги без токенов; карточки чатов — только с историей
    tg = os.path.join(claude, "channels", "telegram")
    if os.path.isdir(tg):
        ap = os.path.join(tg, "access.json")
        if os.path.isfile(ap):
            try: c.add("claude", "channels/telegram/access.template.json",
                       (json.dumps(sanitize_ids(json.load(open(ap))), ensure_ascii=False, indent=1) + "\n").encode())
            except (ValueError, OSError): c.skip("claude/channels/telegram/access.json", "not valid JSON")
        for f in sorted(os.listdir(tg)):
            fp = os.path.join(tg, f)
            if os.path.isfile(fp) and f.endswith((".json", ".md")) and f != "access.json":
                c.take_file("claude", "channels/telegram/" + f, fp)
            elif f.startswith(".env"): c.skip("claude/channels/telegram/" + f, "secret-like name (bot token)")
        for sub in ("inbound", "outbox", "inbox"): 
            if os.path.isdir(os.path.join(tg, sub)): c.skip("claude/channels/telegram/%s/" % sub, "people's messages, never exported")
        if hist and os.path.isdir(os.path.join(tg, "chats")): c.walk("claude", os.path.join(tg, "chats"), "channels/telegram/chats")
        elif os.path.isdir(os.path.join(tg, "chats")): c.skip("claude/channels/telegram/chats/", "other people's data (use --with-history)")
    # имена (не значения!) того, что вводить заново
    for envp in (os.path.join(work, ".env"), os.path.join(tg, ".env")):
        if os.path.isfile(envp):
            try: c.env_names.update(env_names(open(envp, "rb").read()))
            except OSError: pass
    for mj in (os.path.join(home, ".claude.json"), os.path.join(work, ".mcp.json")):
        try:
            for k in (json.load(open(mj)).get("mcpServers") or {}): c.mcp_servers.add(k)
        except (OSError, ValueError, AttributeError): pass
    return c


def core_version(claude):
    try:
        v = json.load(open(os.path.join(claude, "mila-update", "version.json")))
        return {"version": v.get("version"), "tag": v.get("tag"), "installed_at": v.get("installed_at")}
    except (OSError, ValueError): return {"version": None, "tag": None, "installed_at": None}


def restore_md(m):
    re_ = m["reenter"]
    names = ", ".join(re_["env_names"]) or "—"
    mcps = ", ".join(re_["mcp_servers"]) or "—"
    sk = "\n".join("- `%s` — %s" % (s["path"], s["reason"]) for s in m["skipped"][:200]) or "- —"
    hist = "да (в архиве чужие данные — храните закрыто)" if m["with_history"] else "нет"
    return f"""# Как возродить Милу «{m['name']}» · How to revive this Mila

Архив: формат {m['format']}, создан {m['created']}, версия ядра: {m['core']['version'] or 'не записана'} ({m['core']['tag'] or '-'}).
Файлов: {len(m['files'])}. История переписки и транскрипты в архиве: {hist}.

## Шаги
1. Поставьте открытое ядро: https://github.com/shakhruz/mila-companion (`install/install.sh`, на сервере `deploy/bootstrap.sh`).
2. Распакуйте архив во временную папку и проверьте: `mila export verify <архив>` (манифест и sha256).
3. Разложите: `mila restore <архив>` (сначала `--dry-run`). Существующие файлы не перезаписываются: расхождения
   лежат в `~/.claude/mila-restore/<время>/conflicts/`; `--overwrite` заменяет их, оставляя копию.
4. **Введите заново то, чего в архиве нет по замыслу (секреты):**
   - токен бота: `/telegram:configure <токен от @BotFather>`; допуск людей: `/telegram:access pair`, затем
     `/telegram:access policy allowlist` (в архиве только шаблон `access.template.json` без id);
   - вход в Claude: `claude` → `/login` (подписка владельца, чужую не используйте);
   - ключи сервисов (имена из окружения исходной Милы): {names};
   - MCP-серверы, подключённые у исходной Милы: {mcps} — подключите заново (`claude mcp add`);
   - плагин Telegram: `/plugin marketplace add shakhruz/mila-telegram`, `/plugin install mila-telegram@mila`.
5. Запустите `mila`, напишите боту, проверьте `mila doctor`. Кроны — из `work/state/crons.*` поднимет SessionStart.

## English, short
Install the open core, verify (`mila export verify <archive>`), run `mila restore <archive>` (existing files are kept;
differences go to `~/.claude/mila-restore/<ts>/conflicts/`). Re-enter secrets by hand: bot token, Claude login, service keys
({names}), MCP servers ({mcps}). The archive never contains secrets.

## Что не вошло (и почему)
{sk}
"""


def cmd_export(a):
    c = collect(a)
    if c.hits:
        print("ОТКАЗ: в файлах найдено похожее на секреты — архив не создан. Значения не печатаются.", file=sys.stderr)
        for arc, n, k in sorted(set(c.hits)): print("  %s:%d  %s" % (arc, n, k), file=sys.stderr)
        print("Уберите секрет из файла или, если это ложное срабатывание, добавьте --allow '<путь-или-маска>' (путь вида work/…).", file=sys.stderr)
        sys.exit(3)
    name = re.sub(r"[^A-Za-z0-9_.-]", "-", a.name or os.environ.get("MILA_NAME") or os.path.basename(c.home.rstrip("/")) or "mila")
    now = datetime.now(timezone.utc)
    m = {"format": FORMAT, "name": name, "created": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "core": core_version(c.claude),
         "home_root": c.home, "with_history": bool(a.with_history), "with_media": bool(a.with_media),
         "files": sorted(c.meta, key=lambda r: r["path"]), "skipped": sorted(c.skipped, key=lambda r: r["path"]),
         "reenter": {"bot_token": True, "claude_login": True, "env_names": sorted(c.env_names), "mcp_servers": sorted(c.mcp_servers)}}
    if a.dry_run:
        print(json.dumps({"files": len(m["files"]), "bytes": sum(r["size"] for r in m["files"]), "skipped": len(m["skipped"])}, ensure_ascii=False)); return
    rmd = restore_md(m).encode()
    root = "mila-export-%s-%s" % (name, now.strftime("%Y%m%d"))
    out = os.path.abspath(a.out or os.path.join(HOME, "mila-backups")); os.makedirs(out, mode=0o700, exist_ok=True)
    dst = os.path.join(out, root + ".tar.gz")
    tmp = dst + ".part"
    mb = (json.dumps(m, ensure_ascii=False, indent=1) + "\n").encode()
    with tarfile.open(tmp, "w:gz") as t:
        def put(path, data, mode=0o644):
            ti = tarfile.TarInfo(path); ti.size = len(data); ti.mtime = int(now.timestamp()); ti.mode = mode
            ti.uname = ti.gname = ""; ti.uid = ti.gid = 0
            t.addfile(ti, io.BytesIO(data))
        put(root + "/manifest.json", mb); put(root + "/RESTORE.md", rmd)
        for r in m["files"]: put("%s/files/%s" % (root, r["path"]), c.files[r["path"]], 0o755 if r["exec"] else 0o644)
    os.chmod(tmp, 0o600); os.replace(tmp, dst)
    print(json.dumps({"archive": dst, "bytes": os.path.getsize(dst), "files": len(m["files"]), "skipped": len(m["skipped"]),
                      "secrets_found": 0, "with_history": bool(a.with_history), "format": FORMAT}, ensure_ascii=False))
    if a.with_history: print("ВНИМАНИЕ: в архиве переписка и транскрипты — чужие данные. Храните закрыто и не пересылайте.", file=sys.stderr)


# ── проверка и восстановление ───────────────────────────────────────────────
def read_archive(path):
    """-> (root, manifest, {путь внутри files/: bytes}); падает на любом расхождении."""
    if not os.path.isfile(path): die("архив не найден: %s" % path)
    files, mb, root = {}, None, None
    with tarfile.open(path, "r:gz") as t:
        for ti in t:
            parts = ti.name.split("/")
            if ti.name.startswith("/") or ".." in parts: die("небезопасный путь в архиве: %s" % ti.name)
            if not ti.isfile(): die("в архиве не файл (ссылка/устройство): %s" % ti.name)
            if root is None: root = parts[0]
            if parts[0] != root: die("в архиве больше одной корневой папки")
            data = t.extractfile(ti).read()
            rest = "/".join(parts[1:])
            if rest == "manifest.json": mb = data
            elif rest.startswith("files/"): files[rest[6:]] = data
    if mb is None: die("в архиве нет manifest.json — это не архив mila-export")
    m = json.loads(mb)
    if m.get("format") != FORMAT: die("формат архива %s не поддерживается (умею %d) — обновите ядро: mila-update" % (m.get("format"), FORMAT))
    listed = {r["path"]: r for r in m["files"]}
    bad = [p for p, r in listed.items() if p not in files or sha(files[p]) != r["sha256"]]
    extra = [p for p in files if p not in listed]
    if bad or extra:
        for p in bad: print("  повреждён/отсутствует: %s" % p, file=sys.stderr)
        for p in extra: print("  лишний файл вне манифеста: %s" % p, file=sys.stderr)
        die("проверка sha256 не пройдена: %d файлов" % (len(bad) + len(extra)), 4)
    return root, m, files


def cmd_verify(a):
    root, m, files = read_archive(a.archive)
    leak = [(p, n, k) for p, d in files.items() for n, k in scan_bytes(d, p)]
    print(json.dumps({"ok": True, "format": m["format"], "name": m["name"], "created": m["created"], "core": m["core"],
                      "files": len(files), "secrets_found": len(leak)}, ensure_ascii=False))
    if leak: print("ВНИМАНИЕ: в архиве есть похожее на секреты: %s" % ", ".join(sorted({p for p, _, _ in leak})), file=sys.stderr); sys.exit(3)


def cmd_restore(a):
    root, m, files = read_archive(a.archive)
    home, claude, work = paths(a)
    zones = {"claude": claude, "work": work}
    stamp = time.strftime("%Y%m%d-%H%M%S")
    side = os.path.join(claude, "mila-restore", stamp)
    done = {"placed": 0, "same": 0, "conflict": 0, "replaced": 0, "refused": 0}
    for r in m["files"]:
        zone, rel = r["zone"], r["rel"]
        base = zones.get(zone)
        parts = rel.split("/")
        if base is None or ".." in parts or rel.startswith("/") or SECRET_NAME.search(parts[-1]):
            done["refused"] += 1; print("  отказ (небезопасный/секретный путь): %s" % r["path"], file=sys.stderr); continue
        dst, data = os.path.join(base, rel), files[r["path"]]
        if zone == "claude" and rel == "settings.json":
            data = data.replace(m.get("home_root", "").encode(), home.encode()) if m.get("home_root") and m["home_root"] != home else data
        if os.path.exists(dst):
            if open(dst, "rb").read() == data: done["same"] += 1; continue
            if a.overwrite:
                done["replaced"] += 1
                if not a.dry_run:
                    keep = os.path.join(side, "replaced", zone, rel); os.makedirs(os.path.dirname(keep), exist_ok=True); shutil.copy2(dst, keep)
            else:
                done["conflict"] += 1
                if not a.dry_run:
                    cf = os.path.join(side, "conflicts", zone, rel); os.makedirs(os.path.dirname(cf), exist_ok=True); open(cf, "wb").write(data)
                continue
        else: done["placed"] += 1
        if not a.dry_run:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, "wb").write(data); os.chmod(dst, 0o755 if r["exec"] else 0o644)
    print(json.dumps({"restored_into": {"claude": claude, "work": work}, "dry_run": bool(a.dry_run), **done,
                      "conflicts_dir": os.path.join(side, "conflicts") if done["conflict"] and not a.dry_run else None}, ensure_ascii=False))
    re_ = m["reenter"]
    print("\nВведите заново (секретов в архиве нет по замыслу):")
    print("  [ ] токен бота: /telegram:configure <токен от @BotFather>; допуск людей: /telegram:access pair (шаблон — channels/telegram/access.template.json)")
    print("  [ ] вход в Claude: claude → /login (своя подписка)")
    print("  [ ] плагин: /plugin marketplace add shakhruz/mila-telegram → /plugin install mila-telegram@mila")
    if re_["env_names"]: print("  [ ] ключи сервисов (имена): %s" % ", ".join(re_["env_names"]))
    if re_["mcp_servers"]: print("  [ ] MCP-серверы: %s" % ", ".join(re_["mcp_servers"]))
    print("  [ ] затем: mila doctor")
    if done["conflict"]: print("\nЕсть расхождения с существующими файлами — они не тронуты, версии из архива в mila-restore/%s/conflicts/ (или --overwrite)." % stamp)


def cmd_scan(a):
    n = 0
    for d, dirs, files in os.walk(a.dir):
        dirs[:] = [x for x in dirs if x not in (".git",)]
        for f in files:
            p = os.path.join(d, f)
            try: data = open(p, "rb").read()
            except OSError: continue
            for ln, k in scan_bytes(data, os.path.relpath(p, a.dir), a.allow or ()): n += 1; print("%s:%d  %s" % (os.path.relpath(p, a.dir), ln, k))
    print("секретов: %d" % n); sys.exit(3 if n else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    def loc(p):
        p.add_argument("--home"); p.add_argument("--claude"); p.add_argument("--work"); return p
    e = loc(sp.add_parser("export")); e.add_argument("--name"); e.add_argument("--out"); e.add_argument("--with-history", action="store_true")
    e.add_argument("--with-media", action="store_true"); e.add_argument("--allow", action="append"); e.add_argument("--dry-run", action="store_true")
    r = loc(sp.add_parser("restore")); r.add_argument("archive"); r.add_argument("--overwrite", action="store_true"); r.add_argument("--dry-run", action="store_true")
    v = sp.add_parser("verify"); v.add_argument("archive")
    s = sp.add_parser("scan"); s.add_argument("dir"); s.add_argument("--allow", action="append")
    a = ap.parse_args()
    {"export": cmd_export, "restore": cmd_restore, "verify": cmd_verify, "scan": cmd_scan}[a.cmd](a)


if __name__ == "__main__":
    main()
