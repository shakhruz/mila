#!/usr/bin/env python3
"""update.py — навык mila-update: версия ядра Милы, сверка с релизом, обновление с бэкапом и откатом.

  update.py status                       — какая версия стоит, когда и откуда; последние записи журнала
  update.py check [--src DIR|--tag v1.1] — есть ли релиз новее; без --tag берёт последний тег репо
  update.py diff  [--src DIR|--tag v1.0] [--json] — что изменится: новое / обновится / ваша правка (не трогаю) / как есть
  update.py apply [--src DIR|--tag v1.0] --yes "<чьё да и где>" [--take a,b] — бэкап → обновление → версия и журнал;
                                         «отличается» (первая сверка) берётся только по --take, остальное — в mila-update/new/<tag>/
  update.py rollback                     — вернуть всё, как было до последнего обновления
  update.py install-skill DIR --from "<кто прислал>" [--yes "<да хозяина>"] — навык от Милы-администратора, с бэкапом и журналом
  update.py installed                    — список моих навыков: ядро / личные (для рекомендации из каталога)

Ядро — git-репозиторий MILA_CORE_REPO (этот открытый репозиторий или ваш форк),
релизы — теги vX.Y. Нет MILA_CORE_REPO или нет доступа — навык не падает: одна строка хозяину «адрес репозитория ядра не задан».
Что обновляется и что никогда — release.json релиза + неприкосновенный список ниже (он сильнее манифеста).
Пути: {claude}=~/.claude (CLAUDE_CONFIG_DIR), {work}=~/work (MILA_WORK), {home}=~. Только stdlib."""
import argparse, fnmatch, glob, hashlib, json, os, re, shutil, subprocess, sys, tarfile, tempfile, time

HOME = os.path.expanduser("~")
CLAUDE = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")
WORK = os.environ.get("MILA_WORK") or os.path.join(HOME, "work")
REPO = os.environ.get("MILA_CORE_REPO") or ""   # адрес по умолчанию не зашит: задаёт хозяин
NO_ACCESS = "Адрес репозитория ядра не задан: укажите MILA_CORE_REPO (URL git-репозитория)."
GIT_ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0")   # закрытый репо без ключа — не спрашивать пароль, а сразу отказ
STATE = os.path.join(CLAUDE, "mila-update")
VERSION = os.path.join(STATE, "version.json")
JOURNAL = os.path.join(STATE, "journal.jsonl")
BACKUPS = os.path.join(STATE, "backups")
# Неприкосновенное: не пишется НИКОГДА, даже если манифест релиза скажет иное (защита от ошибки в релизе).
NEVER = ["{work}/NOW.md", "{work}/USER.md", "{work}/CLIENTS.md", "{work}/DECISIONS.md", "{work}/CLAUDE.md",
         "{work}/memory", "{work}/journal", "{work}/BACKLOG.md", "{work}/AUTO-POOL.md", "{work}/PERMISSIONS.md",
         "{claude}/settings.json", "{claude}/channels", "{claude}/projects", "{home}/secrets", "{work}/.env", "{work}/rituals",
         "{work}/canon/TEAM-CONTACTS.md"]
SECRET = re.compile(r"(^|/)(secrets?|\.ssh|channels)(/|$)|\.env$|\.key$|token|passw|access\.json$", re.I)


def P(t): return t.replace("{claude}", CLAUDE).replace("{work}", WORK).replace("{home}", HOME)


def never(path):
    rp = os.path.realpath(path)
    return bool(SECRET.search(rp)) or any(rp == os.path.realpath(P(n)) or rp.startswith(os.path.realpath(P(n)) + os.sep) for n in NEVER)


def sha(path):
    """sha256 файла или папки (папка — по относительным путям и содержимому, без __pycache__ и .bak-*)."""
    h = hashlib.sha256()
    if os.path.isdir(path):
        for root, dirs, files in sorted(os.walk(path)):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__" and ".bak-" not in d)
            for f in sorted(files):
                if f.endswith(".pyc"): continue
                fp = os.path.join(root, f); h.update(os.path.relpath(fp, path).encode()); h.update(open(fp, "rb").read())
    elif os.path.isfile(path):
        h.update(open(path, "rb").read())
    else:
        return None
    return h.hexdigest()[:16]


def jlog(rec):
    os.makedirs(STATE, exist_ok=True)
    rec = dict({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, **rec)
    open(JOURNAL, "a").write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_version():
    try: return json.load(open(VERSION))
    except Exception: return {}


def no_access(detail=""):
    """Нет адреса ядра или нет доступа: не ошибка навыка — одна строка хозяину, код 0."""
    print(json.dumps({"no_access": True, "message": NO_ACCESS, **({"detail": detail[-200:]} if detail else {})}, ensure_ascii=False))
    jlog({"event": "no_access", "repo_set": bool(REPO)}); sys.exit(0)


def tags():
    if not REPO: no_access()
    try:
        r = subprocess.run(["git", "ls-remote", "--tags", "--refs", REPO], capture_output=True, text=True, timeout=60, env=GIT_ENV)
    except subprocess.TimeoutExpired:
        no_access("нет ответа от репо ядра")
    if r.returncode: no_access(r.stderr)
    out = r.stdout
    ts = [l.split("refs/tags/")[1] for l in out.splitlines() if "refs/tags/v" in l]
    return sorted(ts, key=lambda t: [int(x) if x.isdigit() else 0 for x in re.findall(r"\d+", t)])


def fetch(tag):
    d = tempfile.mkdtemp(prefix="mila-core-")
    if not REPO: no_access()
    r = subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", tag, REPO, d], capture_output=True, text=True, timeout=300, env=GIT_ENV)
    if r.returncode and re.search(r"Authentication|could not read Username|Repository not found|403|401|Permission denied", r.stderr, re.I): no_access(r.stderr)
    if r.returncode: sys.exit(json.dumps({"error": "релиз не скачался", "tag": tag, "detail": r.stderr[-300:]}, ensure_ascii=False))
    return d


def source(a):
    """Папка релиза: --src (локальная копия, для проверки и для сервера) или скачанный тег."""
    if a.src: return os.path.abspath(a.src)
    t = a.tag or (tags() or [None])[-1]
    if not t: sys.exit(json.dumps({"error": "в репо нет релизов (тегов v*)"}, ensure_ascii=False))
    return fetch(t)


def plan(src):
    """Пары (что, откуда, куда, вид) по манифесту релиза; запретное отбрасывается."""
    m = json.load(open(os.path.join(src, "release.json")))
    pairs = []
    for z in m.get("zones", []):
        skip = z.get("skip", [])
        for s in sorted(glob.glob(os.path.join(src, z["src"]))):
            name = os.path.basename(s.rstrip("/"))
            if any(fnmatch.fnmatch(name, k) for k in skip) or name == "__pycache__": continue
            if z["kind"] == "dir" and not os.path.isdir(s): continue
            if z["kind"] == "file" and not os.path.isfile(s): continue
            dst = P(z["dst"]).replace("*", name)
            if never(dst): continue
            pairs.append({"what": z["what"], "name": name, "src": s, "dst": dst, "kind": z["kind"]})
    return m, pairs


def compare(src):
    m, pairs = plan(src)
    known = load_version().get("files", {})   # хэши того, что ставили мы в прошлый раз
    rows = []
    for p in pairs:
        new, cur = sha(p["src"]), sha(p["dst"])
        if cur is None: st = "новое"
        elif cur == new: st = "как есть"
        elif known.get(p["dst"]) == cur: st = "обновится"           # стоит наша прошлая версия — хозяин не правил
        elif p["dst"] not in known: st = "отличается"                           # первая сверка: у Милы может быть НОВЕЕ релиза — не беру без --take
        else: st = "ваша правка"                                    # хозяин правил нашу версию — не затираю, новую кладу в mila-update/new/
        rows.append(dict(p, state=st, new=new, cur=cur))
    return m, rows


def cmd_status(a):
    v = load_version(); last = []
    if os.path.exists(JOURNAL): last = [json.loads(l) for l in open(JOURNAL).read().splitlines()[-5:]]
    print(json.dumps({"version": v.get("version") or "не записана (до mila-update)", "tag": v.get("tag"), "installed_at": v.get("installed_at"),
                      "source": v.get("source"), "journal_last": last}, ensure_ascii=False, indent=1))


def cmd_check(a):
    v = load_version(); ts = tags(); cur = v.get("tag")
    newer = ts[ts.index(cur) + 1:] if cur in ts else ts[-1:]
    print(json.dumps({"installed": cur or "нет", "latest": ts[-1] if ts else None, "newer": newer}, ensure_ascii=False))


def summary(rows):
    out = {}
    for r in rows: out.setdefault(r["state"], []).append(r["name"])
    return out


def cmd_diff(a):
    src = source(a); m, rows = compare(src)
    if a.json: print(json.dumps({"release": m.get("version"), "rows": [{k: r[k] for k in ("what", "name", "dst", "state")} for r in rows]}, ensure_ascii=False, indent=1)); return
    print(json.dumps({"release": m.get("version"), "tag": m.get("tag"), "itog": {k: len(v) for k, v in summary(rows).items()},
                      "obnovitsya": summary(rows).get("обновится", []), "novoe": summary(rows).get("новое", []),
                      "vasha_pravka": summary(rows).get("ваша правка", []),
                      "otlichaetsya": summary(rows).get("отличается", []),   # первая сверка: сравнить, брать по --take
                      "ne_trogayu": "NOW, USER, CLIENTS, DECISIONS, CLAUDE.md, memory, journal, BACKLOG, настройки, ключи, личные навыки"}, ensure_ascii=False, indent=1))


def backup(paths, tag):
    os.makedirs(BACKUPS, exist_ok=True)
    b = os.path.join(BACKUPS, time.strftime("%Y%m%d-%H%M%S") + "-" + re.sub(r"\W", "_", tag or "x") + ".tgz")
    with tarfile.open(b, "w:gz") as t:
        for p in paths:
            if os.path.exists(p): t.add(p, arcname=p.lstrip("/"))
    return b


def put(src, dst, kind):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if kind == "dir":
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        shutil.copy2(src, dst)


def newborn_block():
    """новорождённая до конца знакомства (нет «знакомство: пройдено» в USER.md) живёт на малом запасе с 7 навыками —
    26 навыков ядра ей сейчас лишние и жгут топливо. Обновление — после знакомства (и подписки)."""
    u = os.path.join(WORK, "USER.md")
    if not os.path.isfile(u): return ""
    t = open(u, encoding="utf-8", errors="replace").read()
    return "" if re.search(r"знакомство:\s*пройдено", t) else "знакомство ещё не пройдено — обновление ядра после него (USER.md «знакомство: пройдено»)"


def cmd_apply(a):
    if not a.yes: sys.exit(json.dumps({"error": "нужно «да» хозяина: --yes \"<кто, где, когда>\" — без него не обновляюсь"}, ensure_ascii=False))
    nb = newborn_block()
    if nb and not a.newborn_ok: sys.exit(json.dumps({"error": nb, "hint": "--newborn-ok — только по слову администратора"}, ensure_ascii=False))
    src = source(a); m, rows = compare(src)
    take = set((a.take or "").split(",")) - {""}
    todo = [r for r in rows if r["state"] in ("новое", "обновится") or (r["state"] == "отличается" and r["name"] in take)]
    side = [r for r in rows if r["state"] in ("ваша правка", "отличается") and r not in todo]
    b = backup([r["dst"] for r in todo] + [VERSION], m.get("tag"))
    added = [r["dst"] for r in todo if r["cur"] is None]
    for r in todo: put(r["src"], r["dst"], r["kind"])
    newdir = os.path.join(STATE, "new", m.get("tag", "v"))   # не рядом с навыком: вторая папка навыка задвоила бы его
    for r in side: put(r["src"], os.path.join(newdir, r["name"]), r["kind"])
    files = dict(load_version().get("files", {}))
    for r in rows:
        if r in todo or r["state"] == "как есть": files[r["dst"]] = r["new"]
    os.makedirs(STATE, exist_ok=True)
    json.dump({"version": m.get("version"), "tag": m.get("tag"), "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "source": a.src or REPO, "files": files}, open(VERSION, "w"), ensure_ascii=False, indent=1)
    touched = [r["dst"] for r in todo] + [os.path.join(newdir, r["name"]) for r in side] + [VERSION]
    jlog({"event": "update", "tag": m.get("tag"), "version": m.get("version"), "yes": a.yes, "backup": b, "added": added, "touched": touched,
          "updated": [r["name"] for r in todo if r["cur"] is not None], "new_beside": [r["name"] for r in side]})
    print(json.dumps({"ok": True, "version": m.get("version"), "obnovleno": [r["name"] for r in todo if r["cur"] is not None],
                      "dobavleno": [r["name"] for r in todo if r["cur"] is None], "vasha_pravka_new_v": newdir if side else "", "backup": b}, ensure_ascii=False, indent=1))


def cmd_rollback(a):
    """Последнее обновление/установку — назад: всё, что тогда записали, убрать; что было до — распаковать из бэкапа."""
    ups = [json.loads(l) for l in open(JOURNAL)] if os.path.exists(JOURNAL) else []
    done = {u.get("backup") for u in ups if u.get("event") == "rollback"}
    ups = [u for u in ups if u.get("event") in ("update", "install-skill") and u.get("backup") not in done]
    if not ups: sys.exit(json.dumps({"error": "откатывать нечего"}, ensure_ascii=False))
    u = ups[-1]
    for p in u.get("touched", []):
        if never(p) and p != VERSION: continue
        if os.path.isdir(p) and not os.path.islink(p): shutil.rmtree(p)
        elif os.path.lexists(p): os.remove(p)
    with tarfile.open(u["backup"]) as t:
        ok = [m for m in t.getmembers() if not never("/" + m.name) or "/" + m.name == VERSION]
        t.extractall("/", members=ok, **({"filter": "tar"} if hasattr(tarfile, "tar_filter") else {}))
    jlog({"event": "rollback", "of": u.get("tag") or u.get("skill"), "backup": u["backup"]})
    print(json.dumps({"ok": True, "vernula": u.get("tag") or u.get("skill"), "iz": u["backup"]}, ensure_ascii=False))


def cmd_install_skill(a):
    d = os.path.abspath(a.dir); name = os.path.basename(d.rstrip("/"))
    if not os.path.isfile(os.path.join(d, "SKILL.md")): sys.exit(json.dumps({"error": "в папке нет SKILL.md — это не навык"}, ensure_ascii=False))
    if not a.sender: sys.exit(json.dumps({"error": "нужно --from: кто прислал (Мила-администратор)"}, ensure_ascii=False))
    for root, _, files in os.walk(d):
        for f in files:
            if SECRET.search(os.path.join(root, f)): sys.exit(json.dumps({"error": "в навыке файл с секретом: " + f}, ensure_ascii=False))
    dst = os.path.join(CLAUDE, "skills", name)
    b = backup([dst], "skill-" + name)
    existed = os.path.exists(dst)
    put(d, dst, "dir")
    jlog({"event": "install-skill", "skill": name, "from": a.sender, "yes": a.yes or "", "backup": b,
          "added": [] if existed else [dst], "touched": [dst], "sha": sha(dst)})
    print(json.dumps({"ok": True, "skill": name, "zamena": existed, "backup": b}, ensure_ascii=False))


def cmd_installed(a):
    files = load_version().get("files", {})
    sk = sorted(os.listdir(os.path.join(CLAUDE, "skills"))) if os.path.isdir(os.path.join(CLAUDE, "skills")) else []
    sk = [s for s in sk if ".bak-" not in s and ".new-" not in s]
    core = [s for s in sk if os.path.join(CLAUDE, "skills", s) in files]
    print(json.dumps({"yadro": core, "lichnye": [s for s in sk if s not in core]}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description="mila-update")
    sp = ap.add_subparsers(dest="cmd", required=True)
    for c in ("status", "check", "rollback", "installed"): sp.add_parser(c)
    for c in ("diff", "apply"):
        p = sp.add_parser(c); p.add_argument("--src"); p.add_argument("--tag"); p.add_argument("--json", action="store_true"); p.add_argument("--yes")
        p.add_argument("--take", help="через запятую: что из «отличается» взять из релиза")
        p.add_argument("--newborn-ok", action="store_true", help="обновить новорождённую до конца знакомства (только по слову администратора)")
    p = sp.add_parser("install-skill"); p.add_argument("dir"); p.add_argument("--from", dest="sender"); p.add_argument("--yes")
    a = ap.parse_args()
    {"status": cmd_status, "check": cmd_check, "diff": cmd_diff, "apply": cmd_apply, "rollback": cmd_rollback,
     "install-skill": cmd_install_skill, "installed": cmd_installed}[a.cmd.replace("_", "-")](a)


if __name__ == "__main__":
    main()
