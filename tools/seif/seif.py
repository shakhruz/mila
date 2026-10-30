#!/usr/bin/env python3
"""Сейф Милы (задача №1 владельца 20.10, «Да, делаем сейф»): одноразовая ссылка, по которой ВЛАДЕЛЕЦ БИЗНЕСА сам вводит
пароли, ключи и карты для своей Милы. Значения идут прямо в закрытый файл её дома — мимо чата, почты и Милы Админ.
  seif.py link <slug> <ПОЛЕ>[,<ПОЛЕ>…] [--name acme] [--to <tg_id>] [--ttl 30]   → ссылка (одна на раз, живёт 30 мин)
  seif.py serve [--port 7692]                                                       → страница сейфа на 127.0.0.1 (Caddy: /v/<token>/)
Запись: $SEIF_HOMES/<slug>/home/work/secrets/<name>.env (папка 700, файл 600, хозяин SEIF_UID), прежние ключи файла сохраняются.
Настройка — только окружением: SEIF_BASE (адрес ссылок, обязателен), SEIF_HOMES (папка домов Мил, обязательна), SEIF_DIR, SEIF_UID.
Журнал SEIF_DIR/journal.jsonl: кто (tg из --to), когда, slug, файл, какие поля — БЕЗ значений. Компаньону — записка в его
work/inbox/senior.jsonl «в сейфе появились: …». Токен хранится только хешем; GET не тратит ссылку (превью Telegram открывает GET),
тратит только «Сохранить» (POST). Значения нигде не печатаются и не логируются. Только stdlib."""
import hashlib, html, json, os, re, secrets, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

SEIF_DIR = os.path.expanduser(os.environ.get("SEIF_DIR", "~/.local/share/mila-seif"))
HOMES = os.environ.get("SEIF_HOMES", "")
BASE = os.environ.get("SEIF_BASE", "")
UID = int(os.environ.get("SEIF_UID", str(os.getuid())))
LABELS = {"SITE_LOGIN": "Логин сайта (телефон или почта)", "SITE_PASSWORD": "Пароль сайта", "API_KEY": "API-ключ",
          "CARD_NUMBER": "Номер карты (16 цифр)", "CARD_EXPIRY": "Срок карты (ММ/ГГ)"}
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
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(path + ".tmp", path)


def chown(path):
    try:
        os.chown(path, UID, UID)
    except OSError:
        pass


def mkdir_owned(base, *parts, mode=0o700):
    """Создать base/parts… по шагу и каждой НОВОЙ папке отдать хозяина (SEIF_UID): сервис идёт от root, иначе work/inbox
    и work/secrets остаются root — компаньон не может в них писать (поймал Хранитель в canary 20.10)."""
    p = base
    for part in parts:
        p = os.path.join(p, part)
        if not os.path.isdir(p):
            os.mkdir(p, mode)
            chown(p)
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
        return None, "пусто"
    if "\n" in v or "\r" in v or len(v) > 512:
        return None, "одна строка, до 512 знаков"
    if field == "CARD_NUMBER":
        d = re.sub(r"[ -]", "", v)
        if not d.isdigit() or not 13 <= len(d) <= 19 or not luhn(d):
            return None, "проверьте номер карты"
        return d, None
    if field == "CARD_EXPIRY":
        m = re.fullmatch(r"(0[1-9]|1[0-2])\s*[/.\-]?\s*(\d{2})", v)
        if not m:
            return None, "срок — ММ/ГГ, например 08/28"
        return m.group(1) + m.group(2), None
    return v, None


def env_quote(v):
    return "'" + v.replace("'", "'\\''") + "'"


def read_env(path):
    out = {}
    try:
        for ln in open(path, encoding="utf-8"):
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


def cmd_link(a):
    need_env()
    slug, fields = a[0], [f.strip() for f in a[1].split(",") if f.strip()]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    name, to, ttl = opt("--name", slug), opt("--to", ""), int(opt("--ttl", "30"))
    if not SLUG_RE.match(slug) or not NAME_RE.match(name) or not fields or not all(FIELD_RE.match(f) for f in fields):
        sys.exit("ERROR: slug a-z0-9_- ; поля — ЗАГЛАВНЫЕ_С_ПОДЧЁРКИВАНИЕМ; name a-z0-9_-")
    if not os.path.isdir(os.path.join(HOMES, slug, "home")):
        sys.exit("ERROR: нет дома %s/%s/home" % (HOMES, slug))
    tok = secrets.token_urlsafe(24)
    rec = {"slug": slug, "name": name, "fields": fields, "to": str(to), "exp": time.time() + ttl * 60, "made": now_iso()}
    wfile(tok_path(tok), json.dumps(rec, ensure_ascii=False))
    journal({"ev": "link", "slug": slug, "name": name, "fields": fields, "to": str(to), "ttl_min": ttl})
    print(json.dumps({"ok": True, "url": BASE + tok + "/", "expires_min": ttl, "fields": fields}, ensure_ascii=False))


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
.e{color:#b44;font-size:13px;margin-top:4px}.ok{font-size:40px;text-align:center}"""


def page(body, title="Сейф Милы"):
    return ("<!doctype html><html lang=ru><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=robots content=noindex><title>%s</title><style>%s</style></head><body><div class=c>%s</div></body></html>" % (title, CSS, body)).encode()


def form(rec, errs=None):
    errs = errs or {}
    rows = []
    for f in rec["fields"]:
        lab = html.escape(LABELS.get(f, f.replace("_", " ").capitalize()))
        typ = "password" if SECRETISH.search(f) else "text"
        im = " inputmode=numeric" if f in ("CARD_NUMBER", "CARD_EXPIRY") else ""
        e = ("<div class=e>%s</div>" % html.escape(errs[f])) if f in errs else ""
        rows.append("<label for=%s>%s</label><input id=%s name=%s type=%s autocomplete=off%s required>%s" % (f, lab, f, f, typ, im, e))
    return page("<h1>🔒 Сейф Милы</h1><p>Введите данные для вашей Милы. Они попадут прямо в её закрытый файл — мимо чата и почты. "
                "Никто из людей их не увидит, Мила использует их только своим инструментом в момент действия.</p>"
                "<form method=post>%s<button type=submit>Сохранить</button></form>"
                "<p style='font-size:12px'>Ссылка одноразовая и живёт 30 минут.</p>" % "".join(rows))


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

    def gone(self):
        self.send(410, page("<h1>Ссылка уже не действует</h1><p>Она одноразовая и живёт 30 минут. Попросите у Милы новую.</p>"))

    def do_GET(self):
        t = self.tok(); rec = load_tok(t) if t else None
        return self.send(200, form(rec)) if rec else self.gone()

    def do_POST(self):
        t = self.tok(); rec = load_tok(t) if t else None
        if not rec:
            return self.gone()
        n = int(self.headers.get("Content-Length") or 0)
        if n > 16384:
            return self.send(413, page("<h1>Слишком много данных</h1>"))
        q = parse_qs(self.rfile.read(n).decode("utf-8", "replace"), keep_blank_values=True)
        vals, errs = {}, {}
        for f in rec["fields"]:
            v, e = check_value(f, (q.get(f) or [""])[0])
            if e:
                errs[f] = e
            else:
                vals[f] = v
        if errs:
            return self.send(200, form(rec, errs))   # ссылка не тратится, введённое назад не выводится
        try:
            os.remove(tok_path(t))   # одноразовость: сначала гасим ссылку
        except OSError:
            return self.gone()
        home = os.path.join(HOMES, rec["slug"], "home")
        sdir = mkdir_owned(home, "work", "secrets"); chown(sdir); envp = os.path.join(sdir, rec["name"] + ".env")
        cur = read_env(envp); cur.update(vals)
        wfile(envp, "".join("%s=%s\n" % (k, env_quote(v)) for k, v in cur.items())); chown(envp)
        journal({"ev": "saved", "slug": rec["slug"], "file": "work/secrets/%s.env" % rec["name"], "fields": sorted(vals), "to": rec.get("to", "")})
        try:
            ib = os.path.join(mkdir_owned(home, "work", "inbox"), "senior.jsonl")
            note = {"id": "seif-" + str(int(time.time())), "ts": now_iso(), "kind": "note", "from": "seif",
                    "text": "В сейфе появились: %s (файл work/secrets/%s.env). Значения читай только своим инструментом в момент действия, в чат — только маска ****1234." % (", ".join(sorted(vals)), rec["name"])}
            with open(ib, "a", encoding="utf-8") as f:
                f.write(json.dumps(note, ensure_ascii=False) + "\n")
            chown(ib)
        except OSError:
            pass
        self.send(200, page("<div class=ok>✅</div><h1 style='text-align:center'>Сохранено</h1><p style='text-align:center'>Можно закрыть страницу. Мила уже знает, что данные на месте.</p>"))


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
