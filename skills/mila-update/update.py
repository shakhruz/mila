#!/usr/bin/env python3
"""update.py — навык mila-update: версия ядра Милы, сверка с релизом, обновление с бэкапом и откатом.

  update.py status                       — какая версия стоит, когда и откуда; последние записи журнала
  update.py check [--src DIR|--tag v1.1] — есть ли релиз новее; без --tag берёт последний тег репо
  update.py diff  [--src DIR|--tag v1.0] [--json] — что изменится: новое / обновится / ваша правка (не трогаю) / как есть
  update.py apply [--src DIR|--tag v1.0] --yes "<чьё да и где>" [--take a,b] — бэкап → обновление → версия и журнал;
                                         «отличается» (первая сверка) берётся только по --take, остальное — в mila-update/new/<tag>/
  update.py rollback                     — вернуть всё, как было до последнего обновления
  update.py install-skill DIR --from "<кто прислал>" [--yes "<да хозяина>"] [--allow-missing] — навык от Милы-администратора, с бэкапом
                                         и журналом; SKILL.md называет scripts/… или др. файлы, которых нет в папке — отказ со списком
  update.py installed                    — список моих навыков: ядро / личные (для рекомендации из каталога)
  update.py nightly [--dry-run] — ночной шаг: канал → есть новее (без отозванных) → сухой прогон → (auto: бэкап, крон-копия,
                                         apply, health, при провале авто-откат) или (не auto: карточка «есть обновление» хозяину)
  update.py config [--set channel=stable|canary|manual] [--set auto=true|false] [--set owner_chat=ID] — настройки (~/.claude/mila-update.json)
  update.py health                       — проверка здоровья после обновления (команда из release.json или встроенная)
  update.py slot                         — смещение ночного запуска в минутах (0–119) по имени дома, чтобы Милы не шли разом

Ядро — публичный git-репозиторий (по умолчанию github.com/shakhruz/mila; свой форк — MILA_CORE_REPO или "repo" в
~/.claude/mila-update.json). Каналы: stable — теги vX.Y.Z (без -rc, без отозванных из yanked.json), canary — ветка main.
Нет доступа — навык не падает: одна строка хозяину.
Что обновляется и что никогда — release.json релиза + неприкосновенный список ниже (он сильнее манифеста).
Пути: {claude}=~/.claude (CLAUDE_CONFIG_DIR), {work}=~/work (MILA_WORK), {home}=~. Только stdlib."""
import argparse, fnmatch, glob, hashlib, json, os, re, shutil, stat, subprocess, sys, tarfile, tempfile, time

# FLEET-1021 (пилот test20 21.10): раскатка с хоста — MILA_HOME=/srv/…/<slug>/home (дом Милы вместо ~), запуск от root,
# MILA_CHOWN=uid[:gid] — после записи всё, что тронули (и папка mila-update), отдаётся хозяину дома.
HOME = os.environ.get("MILA_HOME") or os.path.expanduser("~")
CLAUDE = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")
WORK = os.environ.get("MILA_WORK") or os.path.join(HOME, "work")
DEFAULT_REPO = "https://github.com/shakhruz/mila.git"   # открытое ядро: ключ не нужен
CONFIG = os.path.join(CLAUDE, "mila-update.json")
DEFAULT_CFG = {"channel": "stable", "auto": False, "repo": DEFAULT_REPO, "owner_chat": ""}   # auto=false: ставит только по «да» хозяина


def load_cfg():
    try: c = json.load(open(CONFIG, encoding="utf-8"))
    except FileNotFoundError: c = {}
    except Exception as e:   # журнала ещё нет (загрузка модуля) — вслух в stderr, настройки по умолчанию
        print("mila-update: mila-update.json не прочитан (%s) — беру настройки по умолчанию" % str(e)[:120], file=sys.stderr); c = {}
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


RUN_TOUCHED = set()   # FLEET-1021b: что тронул ЭТОТ запуск — только отсюда chown, журналу в доме не верим


def jlog(rec):
    RUN_TOUCHED.update(p for p in rec.get("touched", []) if isinstance(p, str))
    os.makedirs(STATE, exist_ok=True)
    rec = dict({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, **rec)
    open(JOURNAL, "a").write(json.dumps(rec, ensure_ascii=False) + "\n")


def soft_err(where, e):
    """Сбой, после которого идём дальше, — не молча: строка в журнал (Качество 22.10). Сам журнал не пишется — не падаем."""
    try: jlog({"event": "error", "where": where, "error": ("%s: %s" % (type(e).__name__, e))[:200]})
    except Exception: pass


def load_version():
    try: return json.load(open(VERSION))
    except FileNotFoundError: return {}
    except Exception as e: soft_err("load_version", e); return {}


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
        except Exception as e: soft_err("yanked.json", e); return set(), False
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


class ManifestRefused(Exception):
    """Манифест релиза выходит за пределы дома — отказ ВСЕГО манифеста (цепочка поставки), а не «зону молча отбросить»."""


def _inside(path, base):
    rp, rb = os.path.realpath(path), os.path.realpath(base)
    return rp == rb or rp.startswith(rb + os.sep)


def _bad_src(path, root):
    """Файл релиза: не вне папки релиза, не симлинк, не жёсткая ссылка (lstat, st_nlink == 1); у папки — то же для всего внутри."""
    if not _inside(path, root): return "вне папки релиза"
    todo = [path]
    if os.path.isdir(path) and not os.path.islink(path):
        for r, ds, fs in os.walk(path):
            todo += [os.path.join(r, n) for n in ds + fs]
    for p in todo:
        st = os.lstat(p)
        if stat.S_ISLNK(st.st_mode): return "символическая ссылка: " + os.path.relpath(p, root)
        if stat.S_ISREG(st.st_mode) and st.st_nlink != 1: return "жёсткая ссылка: " + os.path.relpath(p, root)
    return None


# Единственные места ВНЕ {claude}/{work}, куда честный релиз вправе положить файл: запускатель «mila» (точные пути; список зашит в скрипт и сильнее манифеста).
LAUNCHER_DST = ("{home}/.local/bin/mila",)   # только путь из release.json ядра (Разработка 26.10: остальные два были предположением — лишняя дверь вне дома)


def _bad_dst(dst):
    """Цель: внутри дома Милы ({claude} или {work}); ни один уровень пути от дома до файла не символическая ссылка."""
    for base in (CLAUDE, WORK):
        nd, nb = os.path.normpath(dst), os.path.normpath(base)
        if nd == nb or nd.startswith(nb + os.sep):
            cur = nb
            for part in nd[len(nb):].split(os.sep):
                if not part: continue
                cur = os.path.join(cur, part)
                if os.path.islink(cur): return "символическая ссылка на пути: " + cur
            return None
    nd = os.path.normpath(dst)
    if nd in {os.path.normpath(P(x)) for x in LAUNCHER_DST}:      # запускатель: ни один уровень от домашней папки (и сам файл) не символическая ссылка
        cur = os.path.normpath(HOME)
        for part in nd[len(cur):].split(os.sep):
            if not part: continue
            cur = os.path.join(cur, part)
            if os.path.islink(cur): return "символическая ссылка на пути запускателя: " + cur
        return None
    return "вне дома Милы: " + nd


def plan(src):
    """Пары (что, откуда, куда, вид) по манифесту релиза; запретное (список NEVER) отбрасывается; выход за дом — ManifestRefused."""
    m = json.load(open(os.path.join(src, "release.json")))
    pairs, bad = [], []
    for z in m.get("zones", []):
        if ".." in str(z.get("src", "")).split("/") or ".." in str(z.get("dst", "")).split("/"):
            bad.append("«..» в зоне «%s»" % z.get("what")); continue
        skip = z.get("skip", [])
        for s in sorted(glob.glob(os.path.join(src, z["src"]))):
            name = os.path.basename(s.rstrip("/"))
            if any(fnmatch.fnmatch(name, k) for k in skip) or name == "__pycache__": continue
            if z["kind"] == "dir" and not os.path.isdir(s): continue
            if z["kind"] == "file" and not os.path.isfile(s): continue
            dst = P(z["dst"]).replace("*", name)
            if never(dst): continue
            why = _bad_src(s, src) or _bad_dst(dst)
            if why:
                bad.append("%s → %s: %s" % (z.get("what"), name, why)); continue
            pairs.append({"what": z["what"], "name": name, "src": s, "dst": dst, "kind": z["kind"]})
    if bad: raise ManifestRefused("; ".join(bad[:20]))
    return m, pairs


def preflight():
    """Нет доступа к дому Милы — честный отказ, а не «новое» по всем навыкам (пилот 21.10: diff от mila-home видел «новое»,
    потому что не мог пройти в чужой дом)."""
    for d in (CLAUDE, os.path.dirname(CLAUDE)):
        if os.path.exists(d) and not os.access(d, os.R_OK | os.X_OK):
            sys.exit(json.dumps({"error": "нет доступа к %s — запускайте от хозяина дома или от root с MILA_CHOWN=uid" % d}, ensure_ascii=False))
    try:
        os.listdir(CLAUDE) if os.path.isdir(CLAUDE) else None
    except PermissionError:
        sys.exit(json.dumps({"error": "нет доступа к %s — запускайте от хозяина дома или от root с MILA_CHOWN=uid" % CLAUDE}, ensure_ascii=False))


def inside_home(p):
    """Путь лежит внутри дома Милы (по realpath и commonpath, не startswith: /home/mila2 не внутри /home/mila). Симлинк судим по
    месту самой ссылки, не по цели."""
    home = os.path.realpath(HOME)
    try:
        rp = os.path.join(os.path.realpath(os.path.dirname(p)), os.path.basename(p)) if os.path.islink(p) else os.path.realpath(p)
        return os.path.commonpath([rp, home]) == home and rp != home
    except (ValueError, OSError):
        return False


def fleet_chown():
    """MILA_CHOWN=uid[:gid]: тронутое последней записью журнала (и при откате — то, что вернули), папку mila-update и созданных
    по пути родителей внутри дома — хозяину. Без переменной — ничего."""
    spec = os.environ.get("MILA_CHOWN", "").strip()
    if not spec: return
    uid, _, gid = spec.partition(":"); uid = int(uid); gid = int(gid or uid)
    paths = set(RUN_TOUCHED) | {STATE}   # FLEET-1021b (Качество): только то, что тронул этот запуск, не journal.jsonl из дома
    home = os.path.realpath(HOME)
    def own(p):
        # внутри дома; жёсткая ссылка (nlink>1) — пропуск: lchown сменил бы владельца общего inode, напр. /etc/shadow
        if not inside_home(p): return
        try:
            st = os.lstat(p)
            if not os.path.islink(p) and not os.path.isdir(p) and st.st_nlink > 1: return
            os.lchown(p, uid, gid)
        except FileNotFoundError: pass
    for p in paths:
        if not os.path.lexists(p) or not inside_home(p): continue
        own(p)
        if os.path.isdir(p) and not os.path.islink(p):
            for root, dirs, files in os.walk(p):   # os.walk по симлинкам-папкам не ходит
                for x in dirs + files: own(os.path.join(root, x))
        q = os.path.dirname(os.path.realpath(p))   # созданные родители внутри дома (skills/, hooks/, work/…)
        while q != home and os.path.commonpath([q, home]) == home:
            try:
                if os.stat(q).st_uid != uid: own(q)
            except FileNotFoundError: pass
            q = os.path.dirname(q)


def compare(src):
    preflight()
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
    src = source(a)
    try: m, rows = compare(src)
    except ManifestRefused as e: sys.exit(json.dumps({"error": "манифест релиза отклонён целиком — зона вне дома или подозрительная ссылка", "detail": str(e)}, ensure_ascii=False))
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


def readable(p, deep=True):
    """PERMS-1022 (Админ: суточная копия companion-backup падала на new/<тег>/было-* с правами 600): что записал apply —
    читаемо для группы и прочих: файлы go+r, каталоги go+rx. Ссылки не трогаем, лишних прав на запись не даём."""
    def one(q):
        try:
            st = os.lstat(q)
            if stat.S_ISLNK(st.st_mode): return
            add = 0o055 if stat.S_ISDIR(st.st_mode) else 0o044
            if (st.st_mode & add) != add: os.chmod(q, stat.S_IMODE(st.st_mode) | add)
        except OSError:
            pass
    if not os.path.lexists(p): return
    one(p)
    if deep and os.path.isdir(p) and not os.path.islink(p):
        for root, dirs, files in os.walk(p):
            for n in dirs + files: one(os.path.join(root, n))


def put(src, dst, kind):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if kind == "dir":
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        shutil.copy2(src, dst)


def is_internal():
    """INTERNAL-1022: Мила самой команды (её рождает администратор по своему чек-листу, знакомство с хозяином ей не нужно) —
    "internal": true в mila-update.json или MILA_INTERNAL=1 при раскатке. Гейт новорождённой к ней не относится."""
    return "config" if CFG.get("internal") is True else "env" if os.environ.get("MILA_INTERNAL") == "1" else ""


def newborn_block(where=""):
    """новорождённая до конца знакомства (нет «знакомство: пройдено» в USER.md) живёт на малом запасе с 7 навыками —
    26 навыков ядра ей сейчас лишние и жгут топливо. Обновление — после знакомства (и подписки)."""
    u = os.path.join(WORK, "USER.md")
    if not os.path.isfile(u): return ""
    t = open(u, encoding="utf-8", errors="replace").read()
    if re.search(r"знакомство:\s*пройдено", t): return ""
    how = is_internal()
    if how:   # обход видно в журнале: администратор ловит internal у клиентской Милы (Качество 22.10)
        jlog({"event": "newborn_gate_skipped", "reason": "internal", "source": how, "where": where})
        return ""
    return "знакомство ещё не пройдено — обновление ядра после него (USER.md «знакомство: пройдено»)"


ONFAIL_MIN = (2, 1, 295)   # с этой версии Claude Code знает "onFailure" у хука (шаблон и test_send_guard: CC 2.1.295+)


def cc_version():
    """Версия Claude Code этой Милы: env MILA_CC_VERSION (раскатка с хоста от root — там свой claude), иначе `claude --version`.
    Не узнали — None (ключ не дописываем: старая CC могла бы отбросить весь хук сторожа — Качество 24.10)."""
    v = os.environ.get("MILA_CC_VERSION", "")
    if not v:
        try:
            v = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            v = ""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", v or "")
    return tuple(int(x) for x in m.groups()) if m else None


def migrate_settings(tag):
    """SG-ONFAIL-1024 (Вебмастер 24.10): у установок через install.sh хук send-guard записан без "onFailure": "block" —
    упал сторож, и сообщение уходит. Единственная правка settings.json при обновлении: дописать этот ключ хукам send-guard
    (больше ничего не трогаем; бэкап рядом; путь — только внутри дома, без симлинка). Нет правки — None."""
    p = os.path.join(CLAUDE, "settings.json")
    if os.path.islink(p) or not os.path.isfile(p) or not inside_home(p):
        return None
    ver = cc_version()
    if ver is None or ver < ONFAIL_MIN:
        jlog({"event": "migrate_skipped", "what": "send-guard onFailure=block", "why": "старая или неизвестная версия Claude Code",
              "cc": ".".join(map(str, ver)) if ver else "?"})
        return None
    try:
        raw = open(p, encoding="utf-8").read(); cfg = json.loads(raw)
    except (OSError, ValueError):
        return None
    changed = 0
    for e in ((cfg.get("hooks") or {}).get("PreToolUse") or []) if isinstance(cfg, dict) else []:
        for hk in (e.get("hooks") or []) if isinstance(e, dict) else []:
            if isinstance(hk, dict) and "send-guard.py" in str(hk.get("command", "")) and hk.get("onFailure") != "block":
                hk["onFailure"] = "block"; changed += 1
    if not changed:
        return None
    b = backup([p], tag + "-settings")
    st = os.lstat(p); tmp = p + ".new"
    try: os.unlink(tmp)                                   # хвост прошлого сбоя; unlink по ссылке не идёт
    except FileNotFoundError: pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, stat.S_IMODE(st.st_mode))
    try:
        if os.geteuid() == 0: os.fchown(fd, st.st_uid, st.st_gid)   # от root (MILA_HOME) — хозяин тот же, что у старого файла
        os.write(fd, json.dumps(cfg, ensure_ascii=False, indent=2).encode())
    finally:
        os.close(fd)
    os.replace(tmp, p)
    jlog({"event": "migrate", "what": "send-guard onFailure=block", "hooks": changed, "backup": b})
    return p


def do_apply(src, m, rows, yes, take=(), tag=None, sha_="", channel="", src_label=""):
    """Бэкап → запись → версия и журнал. Возвращает словарь результата (печатает вызывающий)."""
    tag = tag or m.get("tag")
    if not tag: sys.exit(json.dumps({"error": "в манифесте нет tag (и не задан --tag) — не обновляюсь, бэкап не делаю"}, ensure_ascii=False))
    # RENAMED-1017 (v1.4.0, международные имена): release.json "renamed" {старое: новое}. По старому имени в релизе — алиас
    # (обёртки скриптов, без SKILL.md — навыком не грузится). Старую папку заменяем алиасом даже при правке хозяина, иначе навык задвоится;
    # его правку кладём в mila-update/new/<тег>/было-<старое> и называем в отчёте.
    ren = m.get("renamed") or {}
    kept = [r for r in rows if r["name"] in ren and r["cur"] is not None and r["state"] in ("ваша правка", "отличается")]
    for r in kept: r["state"] = "обновится"
    todo = [r for r in rows if r["state"] in ("новое", "обновится") or (r["state"] == "отличается" and r["name"] in take)]
    side = [r for r in rows if r["state"] in ("ваша правка", "отличается") and r not in todo]
    b = backup([r["dst"] for r in todo] + [VERSION], tag)
    added = [r["dst"] for r in todo if r["cur"] is None]
    newdir = os.path.join(STATE, "new", tag)   # не рядом с навыком: вторая папка навыка задвоила бы его
    for r in kept: put(r["dst"], os.path.join(newdir, "было-" + r["name"]), r["kind"])   # правка хозяина под старым именем — до замены алиасом
    for r in todo: put(r["src"], r["dst"], r["kind"])
    for r in side: put(r["src"], os.path.join(newdir, r["name"]), r["kind"])
    mig = migrate_settings(tag)   # SG-ONFAIL-1024: точечная миграция настроек (settings.json целиком не перезаписываем — он в never)
    if mig: touched_extra = [mig]
    else: touched_extra = []
    files = dict(load_version().get("files", {}))
    for r in rows:
        if r in todo or r["state"] == "как есть": files[r["dst"]] = r["new"]
    os.makedirs(STATE, exist_ok=True)
    json.dump({"version": m.get("version"), "tag": tag, "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "channel": channel or CFG["channel"],
               "sha": sha_, "source": src_label or REPO, "files": files}, open(VERSION, "w"), ensure_ascii=False, indent=1)
    touched = [r["dst"] for r in todo] + [os.path.join(newdir, r["name"]) for r in side] + [os.path.join(newdir, "было-" + r["name"]) for r in kept] + [VERSION] + touched_extra
    for q in touched: readable(q)
    if side or kept:   # путь до new/<тег> — только сами каталоги (go+rx), не всё содержимое STATE (журнал и бэкапы не открываем)
        for q in (STATE, os.path.join(STATE, "new")): readable(q, deep=False)
        readable(newdir)
    jlog({"event": "update", "tag": tag, "version": m.get("version"), "yes": yes, "backup": b, "added": added, "touched": touched,
          "updated": [r["name"] for r in todo if r["cur"] is not None], "new_beside": [r["name"] for r in side],
          "renamed": {r["name"]: ren[r["name"]] for r in rows if r["name"] in ren and r["cur"] is not None}, "renamed_kept_edit": [r["name"] for r in kept]})
    return {"ok": True, "version": m.get("version"), "obnovleno": [r["name"] for r in todo if r["cur"] is not None],
            "dobavleno": [r["name"] for r in todo if r["cur"] is None], "vasha_pravka_new_v": newdir if side or kept else "", "backup": b,
            "pereimenovano": {r["name"]: ren[r["name"]] for r in rows if r["name"] in ren and r["cur"] is not None},
            "pravka_starogo_imeni": [os.path.join(newdir, "было-" + r["name"]) for r in kept]}


def cmd_apply(a):
    if not a.yes: sys.exit(json.dumps({"error": "нужно «да» хозяина: --yes \"<кто, где, когда>\" — без него не обновляюсь"}, ensure_ascii=False))
    nb = newborn_block("apply")
    if nb and not a.newborn_ok: sys.exit(json.dumps({"error": nb, "hint": "--newborn-ok — только по слову администратора"}, ensure_ascii=False))
    src = source(a)
    try: m, rows = compare(src)
    except ManifestRefused as e: sys.exit(json.dumps({"error": "манифест релиза отклонён целиком — зона вне дома или подозрительная ссылка", "detail": str(e)}, ensure_ascii=False))
    take = set((a.take or "").split(",")) - {""}
    print(json.dumps(do_apply(src, m, rows, a.yes, take, src_label=a.src or REPO, sha_=git_sha(src)), ensure_ascii=False, indent=1))


def git_sha(d):
    try: return subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as e: soft_err("git_sha", e); return ""


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
    except FileNotFoundError: return ""
    except Exception as e: soft_err("changelog", e); return ""
    ver = re.escape((version or "").strip()); tg = re.escape(tag)
    mm = re.search(r"^##\s+(?:%s|v?%s)\b[^\n]*\n(.*?)(?=^##\s|\Z)" % (tg, ver), t, re.S | re.M) if (version or tag) else None
    if not mm: return ""
    body = mm.group(1)
    own = re.search(r"^\**(?:Для хозяина|For the owner)\**:?[ \t]*\n?(.*?)(?=^\**(?:Для Мил|For Milas)|^\*\*|\Z)", body, re.S | re.M | re.I)
    lines = [l.strip() for l in (own.group(1) if own else body).splitlines() if l.strip().startswith(("-", "·", "•"))]
    if not lines and own: lines = [l.strip() for l in own.group(1).splitlines() if l.strip()]
    return "\n".join(l.lstrip("-·• ").strip() and "· " + l.lstrip("-·• ").strip().replace("`", "") for l in lines[:3])


OWNER_RU = r"Для хозяина"
OWNER_ANY = r"(?:Для хозяина|For the owner)"


def _owner_lines(body, n=3, head=OWNER_ANY):
    """Из раздела версии CHANGELOG — до n строк блока head («Для хозяина» / «For the owner»); без такого блока — первые пункты раздела."""
    own = re.search(r"^\**%s\**:?[ \t]*\n?(.*?)(?=^\**(?:Для хозяина|For the owner|Для Мил|For Milas)|^\*\*|^##\s|\Z)" % head, body, re.S | re.M | re.I)
    lines = [l.strip() for l in (own.group(1) if own else body).splitlines() if l.strip().startswith(("-", "·", "•"))]
    if not lines and own: lines = [l.strip() for l in own.group(1).splitlines() if l.strip()]
    return [l.lstrip("-·• ").strip().replace("`", "") for l in lines if l.lstrip("-·• ").strip()][:n]


def changelog_since(src, cur_tag, new_tag, per=2, total=6):
    """UPDATE-PLAN-2810 (владелец 37034): «что получит» — строки «Для хозяина» ВСЕХ версий новее стоящей до новой включительно,
    не только последней (Милы стоят на v1.5.1, а ядро ушло на две версии). Кандидаты (-rc) пропускаю."""
    try: t = open(os.path.join(src, "CHANGELOG.md"), encoding="utf-8").read()
    except OSError: return []
    out = []
    secs = list(re.finditer(r"^##\s+v?(\d+\.\d+\.\d+)(?![\w.-])([^\n]*)\n(.*?)(?=^##\s|\Z)", t, re.S | re.M))
    for mm in secs:
        v = "v" + mm.group(1)
        if cur_tag and re.match(r"^v\d", cur_tag) and vkey(v) <= vkey(cur_tag): continue
        if new_tag and re.match(r"^v\d", new_tag) and vkey(v) > vkey(new_tag): continue
        title, body = mm.group(2), mm.group(3)
        # Качество 28.10 🟡: хозяину — по-русски и простыми словами. Есть «Для хозяина» — он; нет — строка без английского текста
        if not re.search(r"^\**%s\**" % OWNER_RU, body, re.M | re.I):
            out.append((v, "%s: улучшения навыков (описания для хозяина в этой версии нет)" % v)); continue
        for l in _owner_lines(body, per, OWNER_RU):
            l = re.split(r"(?<=[.!?…])\s", l, 1)[0]   # первая фраза — карточка, а не changelog
            out.append((v, l if len(l) <= 160 else l[:157].rstrip() + "…"))
    return out[:total]


CODE_EXT = (".py", ".mjs", ".js", ".ts", ".sh")


def changed_files(r):
    """Файлы, которые реально поменяются в паре (папка — по файлам; новое — всё)."""
    s, d = r["src"], r["dst"]
    if os.path.isfile(s): return [r["name"]] if sha(s) != sha(d) else []
    out = []
    for root, dirs, files in os.walk(s):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in files:
            if f.endswith(".pyc"): continue
            fs = os.path.join(root, f); rel = os.path.relpath(fs, s); fd = os.path.join(d, rel)
            if sha(fs) != sha(fd): out.append(os.path.join(r["name"], rel))
    return out


def risk_of(rows, m):
    """Риск обновления простыми словами: низкий — только тексты навыков; средний — код навыков; высокий — хуки, запускатель,
    настройки (миграция settings), плагин. → (уровень, почему)."""
    why_hi, why_mid, any_ch, word = [], [], False, []
    for r in rows:
        if r["state"] not in ("обновится", "новое"): continue
        files = changed_files(r)
        if not files: continue
        any_ch = True
        if os.path.basename(r["dst"]) == "CONSTITUTION.md" or "/canon/" in r["dst"] + "/":   # слово владельца — не ниже среднего
            word.append(r["name"])
        if "/hooks/" in r["dst"] or r["dst"].endswith("/.local/bin/mila") or "plugin" in r["dst"] or "settings" in os.path.basename(r["dst"]):
            why_hi.append(r["name"]); continue
        if any(f.endswith(CODE_EXT) for f in files): why_mid.append(r["name"])
    if m.get("migrations") or why_hi:
        return "высокий", "меняются хуки, запускатель или настройки" + (": " + ", ".join(sorted(set(why_hi))[:5]) if why_hi else " (миграция настроек)")
    if why_mid or word:
        return "средний", "; ".join(x for x in ("меняется код навыков: " + ", ".join(sorted(set(why_mid))[:5]) if why_mid else "",
                                                 "меняются конституция или каноны" if word else "") if x)
    if not any_ch and not m.get("migrations"):
        return "нет", "файлы не меняются"
    return "низкий", "меняются только тексты навыков и правил"


def plan_text(src, m, rows, cur_tag, tag):
    """Читаемый план хозяину (UPDATE-PLAN-2810): что получит, что изменится, что не тронется, риск. → (текст ≤ 900, словарь)."""
    get = changelog_since(src, cur_tag, tag)
    ch, keep = {}, {}
    for r in rows:
        if r["state"] in ("обновится", "новое"): ch.setdefault(r["what"], []).append(r["name"])
        elif r["state"] in ("ваша правка", "отличается"): keep.setdefault(r["state"], []).append(r["name"])
    lvl, why = risk_of(rows, m)
    head = ["Обновление %s → %s." % (cur_tag or "—", m.get("version") or tag)]
    lines = []
    if ch:
        lines.append("Что изменится:"); lines += ["· %s: %d (%s)" % (w, len(n), ", ".join(n[:4]) + (" …" if len(n) > 4 else "")) for w, n in ch.items()]
    else:
        lines.append("Что изменится: ничего — у вас уже всё из этой версии.")
    kept = keep.get("ваша правка", []) + keep.get("отличается", [])
    lines.append("Не тронется: ваша память, настройки, ключи, личные навыки" + ("; ваши правки — %s" % ", ".join(kept[:4]) if kept else "") + ".")
    word = [r["name"] for r in rows if r["state"] in ("обновится", "новое") and (os.path.basename(r["dst"]) == "CONSTITUTION.md" or "/canon/" in r["dst"] + "/") and changed_files(r)]
    if word: lines.append("Меняется конституция или канон (%s) — прочитайте до «Обновиться»." % ", ".join(word[:3]))
    lines.append("Риск: %s — %s. Отменить можно." % (lvl, why))
    # «что получите» — сколько влезет в 900 знаков; изменения, «не тронется» и риск — всегда
    room = 900 - len("\n".join(head + lines)) - len("\nЧто получите:")
    got = []
    for v, l in get:
        if len("\n".join(got + ["· " + l])) + 1 > room: break
        got.append("· " + l)
    text = "\n".join(head + (["Что получите:"] + got if got else []) + lines)
    d = {"from": cur_tag, "to": tag, "get": [l for v, l in get], "change": ch, "keep": keep, "risk": lvl, "risk_why": why}
    return text[:900], d


def cmd_plan(a):
    """update.py plan [--src|--tag] [--json] — читаемый план обновления для хозяина (ничего не пишет)."""
    src = source(a)
    try: m, rows = compare(src)
    except ManifestRefused as e: sys.exit(json.dumps({"error": "манифест релиза отклонён целиком", "detail": str(e)}, ensure_ascii=False))
    txt, d = plan_text(src, m, rows, load_version().get("tag"), m.get("tag") or getattr(a, "tag", None))
    print(json.dumps(d, ensure_ascii=False, indent=1) if a.json else txt)


def card(kind, tag, version, text="", extra=""):
    """Карточка хозяину: простыми словами. kind: offer | done | failed | yanked."""
    if kind == "offer":
        body = ("%s%s" % (text, extra)) if text.startswith("Обновление ") else "Есть обновление: версия %s.\n%s\nНе тронется: ваши файлы, память, настройки. Отменить можно.%s" % (version or tag, text, extra)
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
    nb = newborn_block("nightly")
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
        try: m, rows = compare(src)
        except ManifestRefused as e:
            jlog({"event": "nightly", "result": "rejected", "tag": tag, "errors": ["манифест отклонён: " + str(e)]})
            print(json.dumps(dict(res, status="rejected", tag=tag, reason="манифест отклонён целиком: " + str(e)), ensure_ascii=False)); return
        errs = validate_release(src, m, rows)
        res.update({"tag": tag, "version": m.get("version"), "dry_run_summary": {k: v for k, v in summary(rows).items()}, "errors": errs})
        if errs:
            jlog({"event": "nightly", "result": "rejected", "tag": tag, "errors": errs})
            print(json.dumps(dict(res, status="rejected"), ensure_ascii=False)); return
        if a.dry_run:
            print(json.dumps(dict(res, status="dry-run: ничего не записано"), ensure_ascii=False, indent=1)); return
        text = changelog_card(src, tag, m.get("version")) if ch == "stable" else ""
        plan_txt, plan_d = plan_text(src, m, rows, load_version().get("tag"), tag)   # UPDATE-PLAN-2810: в карточке — читаемый план
        res["plan"] = plan_d
        if not auto:
            if load_version().get("offered") == tag:
                print(json.dumps(dict(res, status="offered-already"), ensure_ascii=False)); return
            res["card"] = deliver_card(card("offer", tag, m.get("version"), plan_txt), "offer", tag)
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
        elif k == "internal" and v in ("true", "false"): c[k] = v == "true"   # только администратор флота
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
    # FLEET-1021b: журнал и бэкап лежат в доме Милы — при запуске от root им не верим: удаляем и распаковываем только внутри дома,
    # из архива — только обычные файлы и папки (и симлинки, чья цель внутри дома); жёсткие ссылки и устройства — нет
    if not inside_home(u.get("backup", "")): sys.exit(json.dumps({"error": "бэкап вне дома — откат отклонён"}, ensure_ascii=False))
    home = os.path.realpath(HOME)
    def in_home_lex(path):
        # MACOS-1022: родителей сводим через realpath, как и сам дом. Иначе на macOS дом /var/folders/… (ссылка на /private/var/…)
        # не совпадал с путями из архива, и откат пропускал всё. Родитель-ссылка наружу теперь тоже отсекается.
        q = os.path.normpath(path)
        q = os.path.join(os.path.realpath(os.path.dirname(q)), os.path.basename(q))
        try: return os.path.commonpath([q, home]) == home and q != home
        except ValueError: return False
    for p in u.get("touched", []):
        if not isinstance(p, str) or not inside_home(p): continue
        RUN_TOUCHED.add(p)
        if never(p) and p != VERSION: continue
        if os.path.isdir(p) and not os.path.islink(p): shutil.rmtree(p)
        elif os.path.lexists(p): os.remove(p)
    skipped = []
    # CHAIN-1022 (Качество): распаковка в сам дом (dest = realpath(home)), по одному члену, с фильтром «data». Фильтр смотрит
    # каждый член уже ПОСЛЕ распаковки предыдущих, поэтому цепочка ссылок (a → c, где c — давняя ссылка из дома наружу) и файл
    # a/x отсекаются: LinkOutsideDestinationError, снаружи ничего. Имена в архиве — от корня; переводим их в путь от дома.
    homes = {os.path.normpath(os.path.abspath(HOME)), home}
    def rel_to_home(full):
        for h in homes:
            if full.startswith(h + os.sep): return full[len(h) + 1:]
        return None
    has_data = hasattr(tarfile, "data_filter")
    if not has_data and (os.geteuid() == 0 or os.environ.get("MILA_CHOWN")):   # флот от root без фильтра — закрыто (Качество 22.10)
        sys.exit(json.dumps({"error": "откат от root нужен python с tarfile.data_filter (3.12+, или 3.8.17/3.9.17/3.10.12/3.11.4+)"}, ensure_ascii=False))
    def lands_inside(rel):
        """Без фильтра «data» (python до 3.12 без бэкпорта): перед записью члена — его родитель по realpath, с учётом уже
        распакованных ссылок, внутри дома."""
        q = os.path.realpath(os.path.join(home, os.path.dirname(rel)))
        try: return os.path.commonpath([q, home]) == home
        except ValueError: return False
    with tarfile.open(u["backup"]) as t:
        for m in t.getmembers():
            name = "/" + m.name.lstrip("/")
            if not in_home_lex(name) or (never(name) and name != VERSION): continue
            if m.issym() and not in_home_lex(os.path.join(os.path.dirname(name), m.linkname)): continue
            if not (m.isfile() or m.isdir() or m.issym()): continue
            rel = rel_to_home(os.path.normpath(name))
            if not rel: skipped.append(name); continue
            m.name = rel
            if m.issym() and os.path.isabs(m.linkname):   # абсолютная цель внутри дома → относительная (фильтр «data» не пускает абсолютные)
                tgt = rel_to_home(os.path.normpath(m.linkname))
                if tgt is None: skipped.append(name); continue
                m.linkname = os.path.relpath(tgt, os.path.dirname(rel) or ".")
            if not has_data:
                tgt = os.path.realpath(os.path.join(home, os.path.dirname(rel), m.linkname)) if m.issym() else ""
                if not lands_inside(rel) or (tgt and os.path.commonpath([tgt, home]) != home) or m.mode & 0o6000:
                    skipped.append(name); continue
            dst = os.path.join(home, rel)
            if os.path.islink(dst) and not m.issym():   # давняя ссылка на месте обычного файла: пишем файл, не по ссылке наружу
                os.unlink(dst)
            try:
                if has_data: t.extract(m, home, filter="data")
                else: t.extract(m, home)
                RUN_TOUCHED.add(name)
            except (tarfile.FilterError if has_data else tarfile.TarError, OSError) as e:
                skipped.append(name); soft_err("rollback filter " + name, e)
    jlog({"event": "rollback", "of": u.get("tag") or u.get("skill"), "backup": u["backup"], "skipped": skipped})
    print(json.dumps(dict({"ok": True, "vernula": u.get("tag") or u.get("skill"), "iz": u["backup"]}, **({"propushcheno": skipped} if skipped else {})), ensure_ascii=False))


SKILL_REF = re.compile(r"(?:~/\.claude/skills/([A-Za-z0-9._-]+)/|(?<![\w./-]))((?:scripts|templates|examples|knowledge|assets|fonts|data)/[^\s`'\"()<>*?{}\[\],;]+)")


def missing_refs(d):
    """SHELF-CHECK-1018 (Сила: у сил коробок 2–5 на полке был только SKILL.md): файлы своей папки, которые называет SKILL.md
    (scripts/…, templates/…, examples/…, knowledge/…, assets/…, fonts/…, data/…), должны лежать в папке навыка."""
    name = os.path.basename(d.rstrip("/"))
    txt = open(os.path.join(d, "SKILL.md"), encoding="utf-8", errors="replace").read()
    miss = []
    for m in SKILL_REF.finditer(txt):
        if m.group(1) and m.group(1) != name:
            continue                                   # файл чужого навыка — не наш вопрос
        rel = m.group(2).rstrip(".:!»…")
        if rel not in miss and not os.path.exists(os.path.join(d, rel)):
            miss.append(rel)
    return miss


def cmd_install_skill(a):
    d = os.path.abspath(a.dir); name = os.path.basename(d.rstrip("/"))
    if not os.path.isfile(os.path.join(d, "SKILL.md")): sys.exit(json.dumps({"error": "в папке нет SKILL.md — это не навык"}, ensure_ascii=False))
    miss = missing_refs(d)
    if miss and not a.allow_missing:
        sys.exit(json.dumps({"error": "навык неполный: SKILL.md называет файлы, которых нет в папке — попросить у приславшего целую папку",
                             "missing": miss[:30]}, ensure_ascii=False))
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
    print(json.dumps(dict({"ok": True, "skill": name, "zamena": existed, "backup": b}, **({"missing": miss} if miss else {})), ensure_ascii=False))


def cmd_remove_skill(a):
    """REMOVE-SKILL-1017 (Сила, пакеты коробок): снять навык, поставленный install-skill. Навыки ядра не снимает (их ведёт обновление);
    перед удалением — бэкап (вернуть: rollback или распаковать бэкап). Нужно «--from» (кто велел) и «--yes» (слово хозяина)."""
    name = os.path.basename(a.name.rstrip("/"))
    dst = os.path.join(CLAUDE, "skills", name)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or not os.path.isdir(dst): sys.exit(json.dumps({"error": "нет такого навыка: " + name}, ensure_ascii=False))
    if dst in load_version().get("files", {}): sys.exit(json.dumps({"error": "это навык ядра — его ведёт mila-update, снимать нельзя"}, ensure_ascii=False))
    if not a.sender or not a.yes: sys.exit(json.dumps({"error": "нужно --from (кто велел) и --yes (слово хозяина)"}, ensure_ascii=False))
    b = backup([dst], "remove-" + name)
    shutil.rmtree(dst)
    jlog({"event": "remove-skill", "skill": name, "from": a.sender, "yes": a.yes, "backup": b, "touched": [dst]})
    print(json.dumps({"ok": True, "skill": name, "backup": b}, ensure_ascii=False))


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
    for c in ("diff", "apply", "plan"):
        p = sp.add_parser(c); p.add_argument("--src"); p.add_argument("--tag"); p.add_argument("--json", action="store_true"); p.add_argument("--yes")
        p.add_argument("--take", help="через запятую: что из «отличается» взять из релиза")
        p.add_argument("--newborn-ok", action="store_true", help="обновить новорождённую до конца знакомства (только по слову администратора)")
    p = sp.add_parser("install-skill"); p.add_argument("dir"); p.add_argument("--from", dest="sender"); p.add_argument("--yes")
    p.add_argument("--allow-missing", action="store_true")   # поставить неполный навык осознанно (ответ покажет missing)
    p = sp.add_parser("remove-skill"); p.add_argument("name"); p.add_argument("--from", dest="sender"); p.add_argument("--yes")
    a = ap.parse_args()
    try:
        {"status": cmd_status, "check": cmd_check, "diff": cmd_diff, "apply": cmd_apply, "plan": cmd_plan, "rollback": cmd_rollback,
         "install-skill": cmd_install_skill, "remove-skill": cmd_remove_skill, "installed": cmd_installed, "nightly": cmd_nightly,
         "config": cmd_config, "health": cmd_health, "slot": cmd_slot}[a.cmd.replace("_", "-")](a)
    finally:   # и при sys.exit внутри команды: что записали — хозяину дома (MILA_CHOWN)
        if a.cmd in ("apply", "rollback", "install-skill", "remove-skill", "nightly"):
            fleet_chown()


if __name__ == "__main__":
    main()
