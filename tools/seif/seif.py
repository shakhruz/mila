#!/usr/bin/env python3
"""Сейф Милы (задача №1 владельца 20.10, «Да, делаем сейф»): одноразовая ссылка, по которой ВЛАДЕЛЕЦ БИЗНЕСА сам вводит
пароли, ключи и карты для своей Милы. Значения идут прямо в закрытый файл её дома — мимо чата, почты и Милы Админ.
  seif.py link <slug> <ПОЛЕ>[,<ПОЛЕ>…] [--name acme] [--to <tg_id>] [--ttl 30]   → ссылка (одна на раз, живёт 30 мин)
  seif.py serve [--port 7692]                                                       → страница сейфа на 127.0.0.1 (Caddy: /v/<token>/)
Запись: $SEIF_HOMES/<slug>/home/work/secrets/<name>.env (папка 700, файл 600, хозяин SEIF_UID), прежние ключи файла сохраняются.
Настройка — только окружением: SEIF_BASE (адрес ссылок, обязателен), SEIF_HOMES (папка домов Мил, обязательна), SEIF_DIR, SEIF_UID.
Журнал SEIF_DIR/journal.jsonl: кто (tg из --to), когда, slug, файл, какие поля — БЕЗ значений. Компаньону — записка в его
work/inbox/senior.jsonl «в сейфе появились: …». Токен хранится только хешем; GET не тратит ссылку (превью Telegram открывает GET),
тратит только «Сохранить» (POST). Значения нигде не печатаются и не логируются. Только stdlib.
Язык страницы (31.10, «Мила международная»): ?lang= → язык ссылки (--lang или "lang" из work/owner.json дома) → Accept-Language → en.
Строки — locales/<код>.json рядом (SEIF_LOCALES), новый язык = один файл; недостающая строка — из en.json."""
import hashlib, html, json, os, re, secrets, stat, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mila_i18n

SEIF_DIR = os.path.expanduser(os.environ.get("SEIF_DIR", "~/.local/share/mila-seif"))
HOMES = os.environ.get("SEIF_HOMES", "")
BASE = os.environ.get("SEIF_BASE", "")
UID = int(os.environ.get("SEIF_UID", str(os.getuid())))
LOC = mila_i18n.load(os.environ.get("SEIF_LOCALES") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales"))
SECRETISH = re.compile(r"PASS|SECRET|TOKEN|KEY|CARD_NUMBER|PIN", re.I)
NAME_RE, FIELD_RE, SLUG_RE = re.compile(r"^[a-z0-9_-]{1,40}$"), re.compile(r"^[A-Z][A-Z0-9_]{1,40}$"), re.compile(r"^[a-z0-9_-]{2,40}$")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def h(tok):
    return hashlib.sha256(tok.encode()).hexdigest()


def tok_path(tok):
    return os.path.join(SEIF_DIR, "tokens", h(tok) + ".json")


def wfile(path, data, mode=0o600):
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    if os.path.lexists(path + ".tmp"):   # подложенный .tmp (симлинк) — убрать, не идти по нему
        os.unlink(path + ".tmp")
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(path + ".tmp", path)


def chown(path):
    try:
        os.chown(path, UID, UID, follow_symlinks=False)
    except OSError:
        pass


def mkdir_owned(base, *parts, mode=0o700):
    """Создать base/parts… по шагу и каждой НОВОЙ папке отдать хозяина (SEIF_UID): сервис идёт от root, иначе work/inbox
    и work/secrets остаются root — компаньон не может в них писать (поймал Хранитель в canary 20.10).
    31.10: сервис идёт от root, а дом пишет Мила — ни одна папка пути не симлинк, путь внутри дома, иначе OSError (ничего не пишем)."""
    p = base = os.path.realpath(base)
    for part in parts:
        p = os.path.join(p, part)
        if os.path.islink(p):
            raise OSError("seif: %s — симлинк" % part)
        if not os.path.exists(p):
            os.mkdir(p, mode)
            chown(p)
        elif not os.path.isdir(p):
            raise OSError("seif: %s — не папка" % part)
    if os.path.commonpath([os.path.realpath(p), base]) != base:
        raise OSError("seif: путь вне дома")
    return p


def journal(row):
    p = os.path.join(SEIF_DIR, "journal.jsonl"); os.makedirs(SEIF_DIR, mode=0o700, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now_iso(), **row}, ensure_ascii=False) + "\n")


def luhn(d):
    t = 0
    for i, ch in enumerate(reversed(d)):
        x = int(ch)
        if i % 2:
            x = x * 2 - 9 if x > 4 else x * 2
        t += x
    return t % 10 == 0


def check_value(field, v):
    """→ (значение, ошибка). Карта: 13–19 цифр с Луной; срок ММ/ГГ → ММГГ. Остальное — одна строка до 512 знаков."""
    v = (v or "").strip()
    if not v:
        return None, "seif.err.empty"
    if "\n" in v or "\r" in v or len(v) > 512:
        return None, "seif.err.line"
    if field == "CARD_NUMBER":
        d = re.sub(r"[ -]", "", v)
        if not d.isdigit() or not 13 <= len(d) <= 19 or not luhn(d):
            return None, "seif.err.card"
        return d, None
    if field == "CARD_EXPIRY":
        m = re.fullmatch(r"(0[1-9]|1[0-2])\s*[/.\-]?\s*(\d{2})", v)
        if not m:
            return None, "seif.err.expiry"
        return m.group(1) + m.group(2), None
    return v, None


def env_quote(v):
    return "'" + v.replace("'", "'\\''") + "'"


def read_env(path):
    out = {}
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), encoding="utf-8") as f:   # симлинк — ELOOP, FIFO — не ждём
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                raise OSError("seif: .env — не обычный файл")
            for ln in f:
                m = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", ln.rstrip("\n"))
                if m:
                    v = m.group(2)
                    if len(v) >= 2 and v[0] == v[-1] == "'":
                        v = v[1:-1].replace("'\\''", "'")
                    out[m.group(1)] = v
    except FileNotFoundError:
        pass
    return out


def need_env():
    miss = [k for k, v in (("SEIF_BASE", BASE), ("SEIF_HOMES", HOMES)) if not v]
    if miss:
        sys.exit("ERROR: задайте окружение " + ", ".join(miss) + " (адрес ссылок и папку домов Мил)")


def owner_lang(slug):
    """"lang" из work/owner.json дома Милы — только внутри дома, без симлинков, до 4 КБ, код из словарей (mila_i18n.owner_lang)."""
    return mila_i18n.owner_lang(LOC, os.path.join(HOMES, slug, "home"))


def cmd_link(a):
    need_env()
    slug, fields = a[0], [f.strip() for f in a[1].split(",") if f.strip()]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    name, to, ttl, lang = opt("--name", slug), opt("--to", ""), int(opt("--ttl", "30")), opt("--lang")
    if not SLUG_RE.match(slug) or not NAME_RE.match(name) or not fields or not all(FIELD_RE.match(f) for f in fields):
        sys.exit("ERROR: slug a-z0-9_- ; поля — ЗАГЛАВНЫЕ_С_ПОДЧЁРКИВАНИЕМ; name a-z0-9_-")
    if not os.path.isdir(os.path.join(HOMES, slug, "home")):
        sys.exit("ERROR: нет дома %s/%s/home" % (HOMES, slug))
    if lang is not None and not mila_i18n.norm(LOC, lang):
        sys.exit("ERROR: --lang — один из: %s" % ", ".join(sorted(LOC)))
    lang = mila_i18n.norm(LOC, lang) if lang else owner_lang(slug)
    tok = secrets.token_urlsafe(24)
    rec = {"slug": slug, "name": name, "fields": fields, "to": str(to), "exp": time.time() + ttl * 60, "made": now_iso(), "ttl": ttl}
    if lang:
        rec["lang"] = lang
    wfile(tok_path(tok), json.dumps(rec, ensure_ascii=False))
    journal({"ev": "link", "slug": slug, "name": name, "fields": fields, "to": str(to), "ttl_min": ttl, "lang": lang or ""})
    print(json.dumps({"ok": True, "url": BASE + tok + "/" + ("?lang=" + lang if lang else ""), "expires_min": ttl, "fields": fields, "lang": lang or mila_i18n.FALLBACK}, ensure_ascii=False))


def load_tok(tok):
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,64}", tok or ""):
        return None
    try:
        rec = json.load(open(tok_path(tok)))
    except Exception:
        return None
    if rec.get("exp", 0) < time.time():
        try: os.remove(tok_path(tok))
        except OSError: pass
        return None
    return rec


CSS = """body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:linear-gradient(#eaf5f0,#fbf6ee);color:#15524a;margin:0;padding:24px}
.c{max-width:460px;margin:0 auto;background:#fff;border-radius:18px;padding:24px;box-shadow:0 6px 24px rgba(0,0,0,.06)}
h1{font-size:22px;margin:0 0 6px}p{color:#5f6e6c;font-size:15px;line-height:1.4}label{display:block;margin:14px 0 6px;font-weight:600;font-size:14px}
input{width:100%;box-sizing:border-box;padding:12px;border:1px solid #cfe0da;border-radius:10px;font-size:16px}
button{margin-top:20px;width:100%;padding:14px;border:0;border-radius:24px;background:#168a7a;color:#fff;font-size:16px;font-weight:600}
.e{color:#b44;font-size:13px;margin-top:4px}.ok{font-size:40px;text-align:center}
.lang{text-align:right;font-size:13px;margin:-8px 0 8px}.lang a{color:#168a7a;text-decoration:none;margin-left:10px}.lang b{margin-left:10px}"""


def T(lang, key, **kw):
    return html.escape(mila_i18n.t(LOC, lang, key, **kw))


def switcher(lang):
    """Переключатель языков из словарей: ссылки ?lang= (GET ничего не тратит и не меняет)."""
    return "<div class=lang>%s</div>" % "".join(("<b>%s</b>" if c == lang else "<a href='?lang=%s' hreflang=%s>%%s</a>" % (c, c)) % html.escape(n)
                                               for c, n in mila_i18n.names(LOC))


def page(body, lang):
    return ("<!doctype html><html lang=%s><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=robots content=noindex><title>%s</title><style>%s</style></head><body><div class=c>%s%s</div></body></html>"
            % (lang, T(lang, "seif.title"), CSS, switcher(lang), body)).encode()


def form(rec, lang, errs=None):
    errs = errs or {}
    rows = []
    for f in rec["fields"]:
        k = "seif.f." + f
        lab = T(lang, k) if k in LOC[lang] or k in LOC[mila_i18n.FALLBACK] else html.escape(f.replace("_", " ").capitalize())
        typ = "password" if SECRETISH.search(f) else "text"
        im = " inputmode=numeric" if f in ("CARD_NUMBER", "CARD_EXPIRY") else ""
        e = ("<div class=e>%s</div>" % T(lang, errs[f])) if f in errs else ""
        rows.append("<label for=%s>%s</label><input id=%s name=%s type=%s autocomplete=off%s required>%s" % (f, lab, f, f, typ, im, e))
    return page("<h1>%s</h1><p>%s</p><form method=post action='?lang=%s'>%s<button type=submit>%s</button></form><p style='font-size:12px'>%s</p>"
                % (T(lang, "seif.h1"), T(lang, "seif.intro"), lang, "".join(rows), T(lang, "seif.save"), T(lang, "seif.once", min=int(rec.get("ttl", 30)))), lang)


class H(BaseHTTPRequestHandler):
    server_version = "seif"

    def log_message(self, *a):   # без логов запросов (в пути — токен)
        pass

    def send(self, code, body):
        self.send_response(code)
        for k, v in (("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store"), ("Referrer-Policy", "no-referrer"),
                     ("X-Frame-Options", "DENY"), ("X-Content-Type-Options", "nosniff"),
                     ("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'"), ("Content-Length", str(len(body)))):
            self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def tok(self):
        m = re.fullmatch(r"/v/([A-Za-z0-9_-]{20,64})/?", self.path.split("?")[0])
        return m.group(1) if m else None

    def lang(self, rec=None):
        q = parse_qs(urlsplit(self.path).query).get("lang") or [None]
        return mila_i18n.pick(LOC, q[0], (rec or {}).get("lang"), mila_i18n.accept_language(self.headers.get("Accept-Language")))

    def gone(self, lang=None):
        lang = lang or self.lang()
        self.send(410, page("<h1>%s</h1><p>%s</p>" % (T(lang, "seif.gone.h1"), T(lang, "seif.gone.p")), lang))

    def do_GET(self):
        t = self.tok(); rec = load_tok(t) if t else None
        return self.send(200, form(rec, self.lang(rec))) if rec else self.gone()

    def do_POST(self):
        t = self.tok(); rec = load_tok(t) if t else None
        if not rec:
            return self.gone()
        lang = self.lang(rec)
        n = int(self.headers.get("Content-Length") or 0)
        if n > 16384:
            return self.send(413, page("<h1>%s</h1>" % T(lang, "seif.toobig"), lang))
        q = parse_qs(self.rfile.read(n).decode("utf-8", "replace"), keep_blank_values=True)
        vals, errs = {}, {}
        for f in rec["fields"]:
            v, e = check_value(f, (q.get(f) or [""])[0])
            if e:
                errs[f] = e
            else:
                vals[f] = v
        if errs:
            return self.send(200, form(rec, lang, errs))   # ссылка не тратится, введённое назад не выводится
        home = os.path.join(HOMES, rec["slug"], "home")
        try:   # путь проверяем до траты ссылки: подлог в доме — ничего не пишем, ссылка цела
            sdir = mkdir_owned(home, "work", "secrets"); envp = os.path.join(sdir, rec["name"] + ".env")
            cur = read_env(envp)
        except OSError:
            journal({"ev": "refused", "slug": rec["slug"], "why": "path"})
            return self.send(409, page("<h1>%s</h1><p>%s</p>" % (T(lang, "seif.bad.h1"), T(lang, "seif.bad.p")), lang))
        try:
            os.remove(tok_path(t))   # одноразовость: сначала гасим ссылку
        except OSError:
            return self.gone(lang)
        cur.update(vals)
        wfile(envp, "".join("%s=%s\n" % (k, env_quote(v)) for k, v in cur.items())); chown(envp)
        journal({"ev": "saved", "slug": rec["slug"], "file": "work/secrets/%s.env" % rec["name"], "fields": sorted(vals), "to": rec.get("to", "")})
        try:
            ib = os.path.join(mkdir_owned(home, "work", "inbox"), "senior.jsonl")
            note = {"id": "seif-" + str(int(time.time())), "ts": now_iso(), "kind": "note", "from": "seif",
                    "text": "В сейфе появились: %s (файл work/secrets/%s.env). Значения читай только своим инструментом в момент действия, в чат — только маска ****1234." % (", ".join(sorted(vals)), rec["name"])}
            with os.fdopen(os.open(ib, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600), "a", encoding="utf-8") as f:
                f.write(json.dumps(note, ensure_ascii=False) + "\n")
            chown(ib)
        except OSError:
            pass
        self.send(200, page("<div class=ok>✅</div><h1 style='text-align:center'>%s</h1><p style='text-align:center'>%s</p>"
                            % (T(lang, "seif.saved.h1"), T(lang, "seif.saved.p")), lang))


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "link" and len(a) >= 3:
        return cmd_link(a[1:])
    if a[0] == "serve":
        need_env()
        port = int(a[a.index("--port") + 1]) if "--port" in a else 7692
        ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
