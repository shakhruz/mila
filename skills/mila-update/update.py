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
  update.py nightly [--dry-run] — ночной шаг: канал → есть новее (без отозванных) → сухой прогон → (auto: бэкап, крон-копия,
                                         apply, health, при провале авто-откат) или (не auto: карточка «есть обновление» хозяину)
  update.py config [--set channel=stable|canary|manual] [--set auto=true|false] [--set owner_chat=ID] — настройки (~/.claude/mila-update.json)
  update.py health                       — проверка здоровья после обновления (команда из release.json или встроенная)
  update.py slot                         — смещение ночного запуска в минутах (0–119) по имени дома, чтобы Милы не шли разом

Ядро — публичный git-репозиторий (по умолчанию github.com/shakhruz/mila-companion; свой форк — MILA_CORE_REPO или "repo" в
~/.claude/mila-update.json). Каналы: stable — теги vX.Y.Z (без -rc, без отозванных из yanked.json), canary — ветка main.
Нет доступа — навык не падает: одна строка хозяину.
Что обновляется и что никогда — release.json релиза + неприкосновенный список ниже (он сильнее манифеста).
Пути: {claude}=~/.claude (CLAUDE_CONFIG_DIR), {work}=~/work (MILA_WORK), {home}=~. Только stdlib."""
import argparse, fnmatch, glob, hashlib, json, os, re, shutil, subprocess, sys, tarfile, tempfile, time

HOME = os.path.expanduser("~")
CLAUDE = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")
WORK = os.environ.get("MILA_WORK") or os.path.join(HOME, "work")
DEFAULT_REPO = "https://github.com/shakhruz/mila-companion.git"   # открытое ядро: ключ не нужен
CONFIG = os.path.join(CLAUDE, "mila-update.json")
DEFAULT_CFG = {"channel": "stable", "auto": False, "repo": DEFAULT_REPO, "owner_chat": ""}   # auto=false: ставит только по «да» хозяина


def load_cfg():
    try: c = json.load(open(CONFIG, encoding="utf-8"))
    except Exception: c = {}
    return dict(DEFAULT_CFG, **(c if isinstance(c, dict) else {}))


CFG = load_cfg()
REPO = os.environ.get("MILA_CORE_REPO") or CFG["repo"] or DEFAULT_REPO
NO_ACCESS = "Не удалось связаться с репозиторием ядра: проверьте сеть или адрес (MILA_CORE_REPO / \"repo\" в mila-update.json)."
GIT_ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0")   # закрытый репо без ключа — не спрашивать пароль, а сразу отказ
STATE = os.path.join(CLAUDE, "mila-update")
VERSION = os.path.join(STATE, "version.json")
JOURNAL = os.path.join(STATE, "journal.jsonl")
BACKUPS = os.path.join(STATE, "backups")
# Неприкосновенное: не пишется НИКОГДА, даже если манифест релиза скажет иное (защита от ошибки в релизе).
NEVER = ["{work}/NOW.md", "{work}/USER.md", "{work}/CLIENTS.md", "{work}/DECISIONS.md", "{work}/CLAUDE.md",
         "{work}/memory", "{work}/journal", "{work}/BACKLOG.md", "{work}/AUTO-POOL.md", "{work}/PERMISSIONS.md",
         "{claude}/settings.json", "{claude}/channels", "{claude}/projects", "{home}/secrets", "{work}/.env", "{work}/rituals",
         "{work}/canon/TEAM-CONTACTS.md", "{work}/state", "{claude}/.credentials.json", "{home}/.claude.json", "{claude}/mila-update.json"]
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


def vkey(t):
    n = [int(x) for x in re.findall(r"\d+", t)]
    return tuple((n + [0, 0, 0])[:max(3, len(n))])


STABLE_TAG = re.compile(r"^v\d+\.\d+(\.\d+)?$")   # v1.0, v1.1.0; v1.2.0-rc1 в stable не попадает


def tags(stable=False):
    if not REPO: no_access()
    try:
        r = subprocess.run(["git", "ls-remote", "--tags", "--refs", REPO], capture_output=True, text=True, timeout=60, env=GIT_ENV)
    except subprocess.TimeoutExpired:
        no_access("нет ответа от репо ядра")
    if r.returncode: no_access(r.stderr)
    ts = [l.split("refs/tags/")[1] for l in r.stdout.splitlines() if "refs/tags/v" in l]
    if stable: ts = [t for t in ts if STABLE_TAG.match(t)]
    return sorted(ts, key=vkey)


def head_sha(ref="main"):
    try:
        r = subprocess.run(["git", "ls-remote", REPO, "refs/heads/" + ref], capture_output=True, text=True, timeout=60, env=GIT_ENV)
    except subprocess.TimeoutExpired:
        no_access("нет ответа от репо ядра")
    if r.returncode: no_access(r.stderr)
    return r.stdout.split()[0] if r.stdout.strip() else None


def fetch(tag):
    d = tempfile.mkdtemp(prefix="mila-core-")
    if not REPO: no_access()
    r = subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", tag, REPO, d], capture_output=True, text=True, timeout=300, env=GIT_ENV)
    if r.returncode and re.search(r"Authentication|could not read Username|Repository not found|403|401|Permission denied|Could not resolve|unable to access", r.stderr, re.I): no_access(r.stderr)
    if r.returncode: sys.exit(json.dumps({"error": "релиз не скачался", "tag": tag, "detail": r.stderr[-300:]}, ensure_ascii=False))
    return d


def yanked():
    """Отозванные релизы: yanked.json в корне main — список тегов или {"yanked": [{"tag": "v1.2.0", "reason": "..."}]}.
    Нет файла или main не скачался — пусто (но nightly тогда пишет предупреждение)."""
    d = tempfile.mkdtemp(prefix="mila-yank-")
    try:
        r = subprocess.run(["git", "clone", "-q", "--depth", "1", REPO, d], capture_output=True, text=True, timeout=120, env=GIT_ENV)
        if r.returncode: return set(), False
        try: j = json.load(open(os.path.join(d, "yanked.json"), encoding="utf-8"))
        except FileNotFoundError: return set(), True
        except Exception: return set(), False
        rows = j.get("yanked", []) if isinstance(j, dict) else j
        return {(x.get("tag") if isinstance(x, dict) else x) for x in rows if x}, True
    finally:
        shutil.rmtree(d, ignore_errors=True)


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
    v = load_version(); ts = tags(stable=True); cur = v.get("tag"); ya, ok = yanked()
    ts = [t for t in ts if t not in ya]
    newer = [t for t in ts if not cur or not re.match(r"^v\d", cur) or vkey(t) > vkey(cur)]
    print(json.dumps({"installed": cur or "нет", "latest": ts[-1] if ts else None, "newer": newer, "yanked": sorted(ya),
                      "installed_yanked": cur in ya if cur else False}, ensure_ascii=False))


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


def do_apply(src, m, rows, yes, take=(), tag=None, sha_="", channel="", src_label=""):
    """Бэкап → запись → версия и журнал. Возвращает словарь результата (печатает вызывающий)."""
    tag = tag or m.get("tag")
    todo = [r for r in rows if r["state"] in ("новое", "обновится") or (r["state"] == "отличается" and r["name"] in take)]
    side = [r for r in rows if r["state"] in ("ваша правка", "отличается") and r not in todo]
    b = backup([r["dst"] for r in todo] + [VERSION], tag)
    added = [r["dst"] for r in todo if r["cur"] is None]
    for r in todo: put(r["src"], r["dst"], r["kind"])
    newdir = os.path.join(STATE, "new", tag)   # не рядом с навыком: вторая папка навыка задвоила бы его
    for r in side: put(r["src"], os.path.join(newdir, r["name"]), r["kind"])
    files = dict(load_version().get("files", {}))
    for r in rows:
        if r in todo or r["state"] == "как есть": files[r["dst"]] = r["new"]
    os.makedirs(STATE, exist_ok=True)
    json.dump({"version": m.get("version"), "tag": tag, "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "channel": channel or CFG["channel"],
               "sha": sha_, "source": src_label or REPO, "files": files}, open(VERSION, "w"), ensure_ascii=False, indent=1)
    touched = [r["dst"] for r in todo] + [os.path.join(newdir, r["name"]) for r in side] + [VERSION]
    jlog({"event": "update", "tag": tag, "version": m.get("version"), "yes": yes, "backup": b, "added": added, "touched": touched,
          "updated": [r["name"] for r in todo if r["cur"] is not None], "new_beside": [r["name"] for r in side]})
    return {"ok": True, "version": m.get("version"), "obnovleno": [r["name"] for r in todo if r["cur"] is not None],
            "dobavleno": [r["name"] for r in todo if r["cur"] is None], "vasha_pravka_new_v": newdir if side else "", "backup": b}


def cmd_apply(a):
    if not a.yes: sys.exit(json.dumps({"error": "нужно «да» хозяина: --yes \"<кто, где, когда>\" — без него не обновляюсь"}, ensure_ascii=False))
    nb = newborn_block()
    if nb and not a.newborn_ok: sys.exit(json.dumps({"error": nb, "hint": "--newborn-ok — только по слову администратора"}, ensure_ascii=False))
    src = source(a); m, rows = compare(src)
    take = set((a.take or "").split(",")) - {""}
    print(json.dumps(do_apply(src, m, rows, a.yes, take, src_label=a.src or REPO, sha_=git_sha(src)), ensure_ascii=False, indent=1))


def git_sha(d):
    try: return subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception: return ""


# ── ночной шаг: каналы, сухой прогон, health, авто-откат, карточка ───────────────────────────
def fm_check(path):
    """Заголовок SKILL.md: есть name и description, разбирается. yaml нет (macOS без pyyaml) — проверка «: » без кавычек."""
    try: t = open(path, encoding="utf-8").read()
    except Exception as e: return str(e)
    mm = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*(\n|$)", t, re.S)
    if not mm: return "нет заголовка --- … ---"
    try:
        import yaml
        d = yaml.safe_load(mm.group(1))
        if not isinstance(d, dict): return "заголовок не словарь"
        return "" if d.get("name") and d.get("description") else "нет name или description"
    except ImportError:
        keys = {}
        for line in mm.group(1).split("\n"):
            k = re.match(r"^([A-Za-z][\w-]*):[ \t]*(.*)$", line)
            if not k: continue
            v = k.group(2).strip(); keys[k.group(1)] = v
            if v[:1] not in "\"'|>[{" and (": " in v or v.endswith(":")): return "значение с «: » без кавычек: " + k.group(1)
        return "" if keys.get("name") and keys.get("description") else "нет name или description"
    except Exception as e:
        return str(e).split("\n")[0][:160]


def validate_release(src, m, rows):
    """Сухая проверка того, что собираемся ставить: manifest, навыки парсятся, хуки компилируются. Список ошибок."""
    err = []
    if not m.get("version") or not m.get("zones"): err.append("release.json: нет version или zones")
    for r in rows:
        if r["kind"] == "dir" and os.path.isfile(os.path.join(r["src"], "SKILL.md")):
            e = fm_check(os.path.join(r["src"], "SKILL.md"))
            if e: err.append("навык %s: %s" % (r["name"], e))
        if r["kind"] == "file" and r["src"].endswith(".py"):
            try: compile(open(r["src"], encoding="utf-8").read(), r["src"], "exec")
            except SyntaxError as e: err.append("хук %s: %s" % (r["name"], e))
    return err


def run_health(m, tag):
    """release.json {"health": ["cmd", "arg"…]} — команда релиза (код 0 = здорова); нет — встроенная проверка:
    ключевые файлы на месте, навыки разбираются, хуки компилируются, версия в version.json = целевая."""
    v = load_version(); problems = []
    if v.get("tag") != tag: problems.append("version.json: %s вместо %s" % (v.get("tag"), tag))
    for dst in v.get("files", {}):
        if never(dst): continue
        if not os.path.exists(dst): problems.append("нет файла " + dst)
        elif os.path.isdir(dst) and os.path.isfile(os.path.join(dst, "SKILL.md")):
            e = fm_check(os.path.join(dst, "SKILL.md"))
            if e: problems.append("навык %s: %s" % (os.path.basename(dst), e))
        elif dst.endswith(".py"):
            try: compile(open(dst, encoding="utf-8").read(), dst, "exec")
            except SyntaxError as e: problems.append("хук %s: %s" % (os.path.basename(dst), e))
    cmd = m.get("health")
    if cmd:
        if isinstance(cmd, str): cmd = cmd.split()
        env = dict(os.environ, MILA_CLAUDE=CLAUDE, MILA_WORK=WORK)
        try:
            r = subprocess.run([P(c) for c in cmd], capture_output=True, text=True, timeout=120, env=env)
            if r.returncode: problems.append("health-команда релиза: код %d %s" % (r.returncode, (r.stderr or r.stdout)[-160:]))
        except Exception as e: problems.append("health-команда релиза: %s" % e)
    return problems


def cmd_health(a):
    v = load_version(); p = run_health({}, v.get("tag"))
    print(json.dumps({"ok": not p, "problems": p}, ensure_ascii=False)); sys.exit(1 if p else 0)


def changelog_card(src, tag, version):
    """Раздел версии из CHANGELOG.md → до 3 строк «Для хозяина»; без такого блока — первые пункты раздела."""
    try: t = open(os.path.join(src, "CHANGELOG.md"), encoding="utf-8").read()
    except Exception: return ""
    ver = re.escape((version or "").strip()); tg = re.escape(tag)
    mm = re.search(r"^##\s+(?:%s|v?%s)\b[^\n]*\n(.*?)(?=^##\s|\Z)" % (tg, ver), t, re.S | re.M) if (version or tag) else None
    if not mm: return ""
    body = mm.group(1)
    own = re.search(r"^\**(?:Для хозяина|For the owner)\**:?[ \t]*\n?(.*?)(?=^\**(?:Для Мил|For Milas)|^\*\*|\Z)", body, re.S | re.M | re.I)
    lines = [l.strip() for l in (own.group(1) if own else body).splitlines() if l.strip().startswith(("-", "·", "•"))]
    if not lines and own: lines = [l.strip() for l in own.group(1).splitlines() if l.strip()]
    return "\n".join(l.lstrip("-·• ").strip() and "· " + l.lstrip("-·• ").strip().replace("`", "") for l in lines[:3])


def card(kind, tag, version, text="", extra=""):
    """Карточка хозяину: простыми словами. kind: offer | done | failed | yanked."""
    if kind == "offer":
        body = "Есть обновление: версия %s.\n%s\nНе тронется: ваши файлы, память, настройки. Отменить можно.%s" % (version or tag, text, extra)
        buttons = [[{"label": "✅ Обновиться", "data": "mila-update:apply:" + tag}, {"label": "⏸ Не сейчас", "data": "mila-update:later:" + tag}]]
    elif kind == "done":
        body = "Я обновилась до версии %s.\n%s" % (version or tag, text); buttons = []
    elif kind == "failed":
        body = "Обновление до версии %s не прошло проверку — вернула всё, как было. Работаю по-прежнему.%s" % (version or tag, extra); buttons = []
    else:
        body = "Версия %s отозвана разработчиками.%s" % (version or tag, extra); buttons = []
    return {"text": body[:900], "buttons": buttons}


def deliver_card(c, kind, tag):
    """Файл для хозяина: outbox sender-демона (если задан owner_chat), иначе файл-карточка в mila-update/cards/. Всегда печатается."""
    os.makedirs(os.path.join(STATE, "cards"), exist_ok=True)
    path = os.path.join(STATE, "cards", "%s-%s.json" % (kind, re.sub(r"\W", "_", tag)))
    json.dump(c, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    chat = os.environ.get("MILA_OWNER_CHAT") or CFG.get("owner_chat")
    out = os.environ.get("MILA_OUTBOX") or os.path.join(os.environ.get("TELEGRAM_STATE_DIR") or os.path.join(CLAUDE, "channels", "telegram"), "outbox")
    if chat and str(chat).lstrip("-").isdigit() and os.path.isdir(os.path.dirname(out)):
        os.makedirs(out, mode=0o700, exist_ok=True)
        job = {"chat_id": int(chat), "text": c["text"]}
        if c["buttons"]: job["buttons"] = c["buttons"]
        name = "update-%d-%d.json" % (int(time.time() * 1000), os.getpid())
        json.dump(job, open(os.path.join(out, name + ".tmp"), "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(os.path.join(out, name + ".tmp"), os.path.join(out, name))
        return {"card_file": path, "outbox": os.path.join(out, name)}
    return {"card_file": path, "outbox": ""}


def save_crons():
    """Кроны сессии (crons-keeper: state/crons.json, или crons.md): копия в mila-update/crons-<ts>/. Apply их и так не трогает (state — в NEVER)."""
    kept = []; d = os.path.join(STATE, "crons-" + time.strftime("%Y%m%d-%H%M%S"))
    for n in ("crons.json", "crons.md"):
        f = os.path.join(WORK, "state", n)
        if os.path.isfile(f):
            os.makedirs(d, exist_ok=True); shutil.copy2(f, d); kept.append(os.path.join(d, n))
    return kept


def candidate():
    """Что предложить по каналу. → (ref, tag_для_записи, sha, пометка) или None."""
    ch = CFG["channel"]; v = load_version()
    if ch == "canary":
        h = head_sha("main")
        if not h or v.get("sha") == h: return None, {}
        return "main", {"tag": "main@" + h[:7], "sha": h}
    ts = tags(stable=True); ya, ok = yanked()
    ts = [t for t in ts if t not in ya]; cur = v.get("tag")
    newer = [t for t in ts if not (cur and re.match(r"^v\d", cur)) or vkey(t) > vkey(cur)]
    info = {"yanked": sorted(ya), "yanked_list_ok": ok, "installed_yanked": bool(cur and cur in ya)}
    return (newer[-1], dict(info, tag=newer[-1])) if newer else (None, info)


def cmd_nightly(a):
    ch = CFG["channel"]; auto = bool(CFG["auto"])
    res = {"channel": ch, "auto": auto, "dry_run": a.dry_run}
    if ch == "manual": print(json.dumps(dict(res, status="manual: сама не проверяю"), ensure_ascii=False)); return
    nb = newborn_block()
    if nb: print(json.dumps(dict(res, status="skip", reason=nb), ensure_ascii=False)); return
    ref, info = candidate(); res.update({k: info[k] for k in ("yanked", "installed_yanked") if k in info})
    if res.get("installed_yanked"):
        res["warning"] = "стоящая версия отозвана — нужен откат на прежнюю (update.py rollback) или новая версия"
        if not a.dry_run:
            res["card"] = deliver_card(card("yanked", load_version().get("tag", ""), load_version().get("version")), "yanked", load_version().get("tag", ""))
            jlog({"event": "nightly", "result": "installed-yanked", "tag": load_version().get("tag")})
    if not ref:
        print(json.dumps(dict(res, status="up-to-date", installed=load_version().get("tag")), ensure_ascii=False)); return
    src = fetch(ref)
    try:
        sha_ = git_sha(src); tag = info["tag"]
        if CFG.get("require_signed") and ch == "stable":
            if subprocess.run(["git", "-C", src, "verify-tag", ref], capture_output=True).returncode:
                print(json.dumps(dict(res, status="rejected", tag=tag, reason="подпись тега не проверилась"), ensure_ascii=False)); return
        m, rows = compare(src); errs = validate_release(src, m, rows)
        res.update({"tag": tag, "version": m.get("version"), "dry_run_summary": {k: v for k, v in summary(rows).items()}, "errors": errs})
        if errs:
            jlog({"event": "nightly", "result": "rejected", "tag": tag, "errors": errs})
            print(json.dumps(dict(res, status="rejected"), ensure_ascii=False)); return
        if a.dry_run:
            print(json.dumps(dict(res, status="dry-run: ничего не записано"), ensure_ascii=False, indent=1)); return
        text = changelog_card(src, tag, m.get("version")) if ch == "stable" else ""
        if not auto:
            if load_version().get("offered") == tag:
                print(json.dumps(dict(res, status="offered-already"), ensure_ascii=False)); return
            res["card"] = deliver_card(card("offer", tag, m.get("version"), text), "offer", tag)
            v = load_version(); v["offered"] = tag; os.makedirs(STATE, exist_ok=True); json.dump(v, open(VERSION, "w"), ensure_ascii=False, indent=1)
            jlog({"event": "nightly", "result": "offered", "tag": tag})
            print(json.dumps(dict(res, status="offered: жду «да» хозяина"), ensure_ascii=False, indent=1)); return
        res["crons_saved"] = save_crons() or "кронов в state/ нет — сохранять нечего"
        yes = "auto: хозяин включил auto в mila-update.json · канал " + ch
        out = do_apply(src, m, rows, yes, tag=tag, sha_=sha_, channel=ch, src_label=REPO)
        probs = run_health(m, tag)
        if probs:
            rb = subprocess.run([sys.executable, os.path.abspath(__file__), "rollback"], capture_output=True, text=True)
            jlog({"event": "nightly", "result": "health-failed-rolled-back", "tag": tag, "problems": probs, "rollback_ok": rb.returncode == 0})
            res["card"] = deliver_card(card("failed", tag, m.get("version")), "failed", tag)
            print(json.dumps(dict(res, status="rolled-back", problems=probs, rollback_ok=rb.returncode == 0), ensure_ascii=False, indent=1)); sys.exit(1)
        jlog({"event": "nightly", "result": "ok", "tag": tag, "health": "ok"})
        res["card"] = deliver_card(card("done", tag, m.get("version"), text), "done", tag)
        print(json.dumps(dict(res, status="updated", **{k: out[k] for k in ("obnovleno", "dobavleno", "backup")}), ensure_ascii=False, indent=1))
    finally:
        shutil.rmtree(src, ignore_errors=True)


def cmd_config(a):
    global CFG
    c = dict(DEFAULT_CFG); c.update(json.load(open(CONFIG)) if os.path.exists(CONFIG) else {})
    for kv in a.set or []:
        k, _, v = kv.partition("=")
        if k == "channel" and v in ("stable", "canary", "manual"): c[k] = v
        elif k == "auto" and v in ("true", "false"): c[k] = v == "true"
        elif k in ("repo", "owner_chat", "require_signed"): c[k] = (v == "true") if k == "require_signed" else v
        else: sys.exit(json.dumps({"error": "неверная настройка: " + kv}, ensure_ascii=False))
    if a.set:
        os.makedirs(CLAUDE, exist_ok=True); json.dump(c, open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        jlog({"event": "config", "set": a.set})
    print(json.dumps(c, ensure_ascii=False, indent=1))


def cmd_slot(a):
    print(int(hashlib.sha256(HOME.encode()).hexdigest(), 16) % 120)


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
    for c in ("status", "check", "rollback", "installed", "health", "slot"): sp.add_parser(c)
    p = sp.add_parser("nightly"); p.add_argument("--dry-run", action="store_true")
    p = sp.add_parser("config"); p.add_argument("--set", action="append")
    for c in ("diff", "apply"):
        p = sp.add_parser(c); p.add_argument("--src"); p.add_argument("--tag"); p.add_argument("--json", action="store_true"); p.add_argument("--yes")
        p.add_argument("--take", help="через запятую: что из «отличается» взять из релиза")
        p.add_argument("--newborn-ok", action="store_true", help="обновить новорождённую до конца знакомства (только по слову администратора)")
    p = sp.add_parser("install-skill"); p.add_argument("dir"); p.add_argument("--from", dest="sender"); p.add_argument("--yes")
    a = ap.parse_args()
    {"status": cmd_status, "check": cmd_check, "diff": cmd_diff, "apply": cmd_apply, "rollback": cmd_rollback,
     "install-skill": cmd_install_skill, "installed": cmd_installed, "nightly": cmd_nightly,
     "config": cmd_config, "health": cmd_health, "slot": cmd_slot}[a.cmd.replace("_", "-")](a)


if __name__ == "__main__":
    main()
