#!/usr/bin/env python3
"""screen.py — навык «Мила Экран»: показывать на удалённом экране (ТВ/монитор) с tv.milagpt.io.
  screen.py pair КОД [имя]          — привязать экран по коду с экрана (человек прислал «экран 123456»)
  screen.py list                    — мои экраны и онлайн ли
  screen.py play URL [--loop]       — YouTube-ссылка или прямой mp4/mp3 на весь экран
  screen.py image URL [заголовок]   — картинка
  screen.py show "Заголовок" "текст" [- пункт ...] — карточка текста (прайс, расписание, итог)
  screen.py yt "запрос" [--views]   — поиск YouTube: id, просмотры, длительность, название
  screen.py top "запрос"             — самый просматриваемый ролик по запросу сразу на экран
  screen.py stop | clear            — остановить / очистить экран
  screen.py page put ПАПКА ИМЯ [--show] | show ИМЯ | list | rm ИМЯ — своя HTML-страница (игра, слайды) на свой экран
  screen.py unpair [screen]         — отвязать экран
Ключ — ~/secrets/screen.key. Ответ — JSON сервера."""
import json, os, re, sys, urllib.request, urllib.parse, urllib.error
# из контейнера внешний адрес сервера (tv.milagpt.io) не отвечает — шпилька NAT, Connection refused.
# Порядок: SCREEN_API из окружения → в контейнере (/run/.containerenv) — служба экрана на хосте напрямую → иначе публичный адрес.
API = os.environ.get("SCREEN_API") or ("http://host.containers.internal:8949/api/screen/" if os.path.exists("/run/.containerenv") else "https://tv.milagpt.io/api/screen/")
try: KEY = os.environ.get("SCREEN_KEY") or open(os.path.expanduser("~/secrets/screen.key")).read().strip()   # ключ — env SCREEN_KEY или файл, выдаёт администратор при рождении
except OSError:
    print(json.dumps({"error": "ключ экрана не выдан (~/secrets/screen.key) — экран не подключён, скажите хозяину и попросите ключ у администратору"}, ensure_ascii=False)); sys.exit(2)


def call(path, body):
    r = urllib.request.Request(API + path, data=json.dumps(body, ensure_ascii=False).encode(),
                               headers={"Content-Type": "application/json", "X-Screen-Key": KEY})
    try:
        return json.load(urllib.request.urlopen(r, timeout=20))
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:200]}


def yt(u):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})", u)
    return m.group(1) if m else None


a = sys.argv[1:] or ["list"]
# у публичной Милы (Мила Ташкент, @mila_gpt_bot) экраны личные — user = Telegram id собеседника во ВСЕХ вызовах.
USER = ""
if "--user" in a:
    i = a.index("--user"); USER = re.sub(r"\D", "", a[i + 1] if i + 1 < len(a) else ""); del a[i:i + 2]
_call = call
def call(path, body):
    if USER: body = dict(body, user=USER)
    if path == "cmd": body = dict(body, wait_ack=True)   # хаб ждёт подтверждения страницы до 6 с → shown:{ok,note}|null
    return _call(path, body)
c = a[0]
_W = {"ноль": 0, "один": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9,
      "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17,
      "восемнадцать": 18, "девятнадцать": 19, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70,
      "восемьдесят": 80, "девяносто": 90, "сто": 100, "двести": 200, "триста": 300, "четыреста": 400, "пятьсот": 500, "шестьсот": 600, "семьсот": 700,
      "восемьсот": 800, "девятьсот": 900}
def code6(words):
    """«7 3 3 4 8 9», «733 489», «семь три три…», «семьсот тридцать три четыреста восемьдесят девять» → '733489' или None."""
    import re as _re
    t = " ".join(words).lower()
    d = "".join(_re.findall(r"\d", t))
    if len(d) == 6: return d
    out, cur = [], None
    for w in _re.findall(r"\d+|[а-яё]+", t):
        if w.isdigit():
            if cur is not None: out.append(str(cur)); cur = None
            out.append(w); continue
        v = _W.get(w)
        if v is None: continue
        if cur is not None and ((v < 10 and cur % 10 == 0 and cur >= 20) or (v < 100 and cur >= 100 and cur % 100 == 0)): cur += v
        else:
            if cur is not None: out.append(str(cur))
            cur = v
    if cur is not None: out.append(str(cur))
    d = "".join(out)
    return d if len(d) == 6 else None


def split_pair(rest):
    """Код и имя экрана из слов после «pair»: первое слово из 6 цифр — код; иначе САМЫЙ ДЛИННЫЙ префикс, который кончается
    числом (цифры или число словом) и даёт ровно 6 цифр; остальное — имя. «семьсот тридцать три четыреста восемьдесят девять Кухня» → 733489, «Кухня»."""
    import re as _re
    if rest and _re.fullmatch(r"\d{6}", rest[0]):
        return rest[0], " ".join(rest[1:])
    isnum = lambda w: w.isdigit() or w.lower() in _W
    ks = [i for i in range(1, len(rest) + 1) if isnum(rest[i - 1]) and code6(rest[:i])]
    if ks:
        k = max(ks); return code6(rest[:k]), " ".join(rest[k:])
    return (rest[0] if rest else ""), " ".join(rest[1:])
if c == "pair":
    import re as _re2
    code, name = split_pair(a[1:])
    if not _re2.fullmatch(r"\d{6}", code or ""):
        sys.exit("pair: нужен код из 6 цифр (можно словами или через пробел)")
    out = call("pair", {"code": code, "name": name or "Экран"})
elif c == "list":
    out = call("list", {})
elif c == "play":
    u = a[1]; v = yt(u)
    out = call("cmd", dict({"action": "play", "loop": "--loop" in a}, **({"youtube": v} if v else {"src": u})))
elif c == "image":
    out = call("cmd", {"action": "image", "url": a[1], "title": " ".join(a[2:])})
elif c == "show":
    items = [x[2:] if x.startswith("- ") else x for x in a[3:]]
    out = call("cmd", {"action": "show", "title": a[1], "text": a[2] if len(a) > 2 else "", "items": items})
elif c == "yt":  # поиск YouTube с просмотрами: screen.py yt "запрос" [--views]
    out = call("yt", {"q": " ".join(x for x in a[1:] if x != "--views"), "sort": "views" if "--views" in a else ""})
elif c == "top":  # самый просматриваемый ролик по запросу — сразу на экран
    r = call("yt", {"q": " ".join(a[1:]), "sort": "views"}).get("results") or []
    out = {"error": "ничего не нашла"} if not r else dict(call("cmd", {"action": "play", "youtube": r[0]["youtube"], "title": r[0]["title"], "alt": [x["youtube"] for x in r[1:6]]}), picked=r[0])
elif c in ("stop", "clear", "pause", "resume", "repeat", "next", "prev", "mute", "unmute"):
    # управление тем, что играет, и плейлистом
    out = call("cmd", {"action": c})
elif c == "seek":  # seek 600 — на 10-ю минуту; seek +30 / seek -30 — вперёд/назад
    v = a[1]
    out = call("cmd", {"action": "seek", "delta": int(v)} if v[:1] in "+-" else {"action": "seek", "sec": int(v)})
elif c == "volume":  # volume 0..100
    out = call("cmd", {"action": "volume", "level": max(0, min(100, int(a[1])))})
elif c == "audio":  # audio URL "Название"
    out = call("cmd", {"action": "audio", "src": a[1], "title": " ".join(a[2:])})
elif c == "playlist":  # playlist [--loop] [--shuffle] URL|ID … — ролики YouTube и наши файлы по очереди
    items = []
    for u in a[1:]:
        if u.startswith("--"): continue
        v = yt(u) or (u if re.fullmatch(r"[\w-]{11}", u) else None)
        items.append({"youtube": v} if v else {"src": u})
    out = call("cmd", {"action": "playlist", "items": items, "loop": "--loop" in a, "shuffle": "--shuffle" in a})
elif c == "slides":  # slides [--loop] [--sec 10] IMG_URL … — картинки по таймеру
    sec = 10
    if "--sec" in a: sec = int(a[a.index("--sec") + 1])
    imgs = [u for i, u in enumerate(a[1:], 1) if not u.startswith("--") and a[i - 1] != "--sec"]
    out = call("cmd", {"action": "loop" if "--loop" in a else "slides", "sec": sec, "items": [{"action": "image", "url": u, "src": u} for u in imgs]})
elif c == "upload":  # upload FILE [--loop] [--play] — свой ролик/картинку на наш сервер; --play — сразу на экран (по кругу с --loop)
    f = a[1]; name = re.sub(r"[^\w.-]", "_", os.path.basename(f))[:80]
    q = "upload?name=" + urllib.parse.quote(name) + ("&user=" + USER if USER else "")
    with open(f, "rb") as fh:
        r = urllib.request.Request(API + q, data=fh.read(), headers={"Content-Type": "application/octet-stream", "X-Screen-Key": KEY})
    try:
        out = json.load(urllib.request.urlopen(r, timeout=120))
    except urllib.error.HTTPError as e:
        out = {"error": e.code, "detail": e.read().decode()[:200]}
    if out.get("src") and "--play" in a:
        kind = "audio" if re.search(r"\.(mp3|m4a|ogg|wav)$", name, re.I) else "image" if re.search(r"\.(png|jpe?g|webp|gif)$", name, re.I) else "play"
        body = {"action": kind, "loop": "--loop" in a}
        body.update({"url": out["src"]} if kind == "image" else {"src": out["src"]})
        out["shown"] = call("cmd", body)
elif c == "app":  # app NAME [k=v …] — наше живое приложение на экране (tashkent-today rayon=Чиланзар sec=10)
    pr = {}
    for kv in a[2:]:
        if "=" in kv:
            k, v = kv.split("=", 1); pr[k] = int(v) if v.isdigit() else v[:200]
    out = None
    if a[1] == "milatv" and isinstance(pr.get("n"), int):   # номер канала сверяю со списком эфира — «Канала 25 нет — всего 18» человеку, не молча
        try:
            idx = json.load(urllib.request.urlopen(re.sub(r"/api/screen/?$", "/", API) + "channels/index.json", timeout=10))
            total = len(idx.get("channels") or []) + (1 if pr.get("c") else 0)   # свой канал человека — первым номером
            if total and not 1 <= pr["n"] <= total: out = {"ok": False, "error": "Канала %d нет — всего %d" % (pr["n"], total), "kanalov": total}
        except Exception: pass   # список недоступен — плеер на экране сам скажет «Канала N нет»
    if out is None: out = call("cmd", {"action": "app", "app": a[1], "params": pr})
elif c == "site":  # site https://… — живая страница на экране (только хозяин экрана, только https)
    u = a[1] if len(a) > 1 else ""
    out = {"error": "только https-адрес"} if not re.match(r"^https://[^\s\"'<>]+$", u) else call("cmd", {"action": "site", "url": u})
elif c == "snapshot":  # snapshot https://… [--every 300] — снимок страницы картинкой (рендер на сервере)
    u = a[1] if len(a) > 1 else ""; ev = int(a[a.index("--every") + 1]) if "--every" in a else 300
    out = {"error": "только https-адрес"} if not re.match(r"^https://[^\s\"'<>]+$", u) else call("cmd", {"action": "snapshot", "url": u, "every": max(60, ev)})
elif c == "page":  #: своя HTML-страница (игра, слайды) — page put ПАПКА ИМЯ | show ИМЯ | list | rm ИМЯ
    sub = a[1] if len(a) > 1 else ""
    if sub == "put":
        import io, tarfile
        src, nm = (a[2] if len(a) > 2 else ""), (a[3] if len(a) > 3 else "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", nm) or not os.path.isfile(os.path.join(src, "index.html")):
            out = {"error": "page put ПАПКА ИМЯ: в папке нужен index.html, имя — a-z, 0-9, дефис"}
        else:
            buf = io.BytesIO(); bad = []
            with tarfile.open(fileobj=buf, mode="w:gz") as tf:
                for dp, dn, fn in os.walk(src):
                    dn[:] = sorted(d for d in dn if not d.startswith(".") and not os.path.islink(os.path.join(dp, d)))
                    for f in sorted(fn):
                        full = os.path.join(dp, f)
                        if f.startswith("."): continue
                        if os.path.islink(full) or not os.path.isfile(full): bad.append(f); continue
                        tf.add(full, arcname=os.path.relpath(full, src), recursive=False)
            if bad:
                out = {"error": "в папке ссылки или не файлы — уберите: " + ", ".join(bad[:5])}
            else:
                r = urllib.request.Request(API + "page?name=" + nm, data=buf.getvalue(), headers={"Content-Type": "application/gzip", "X-Screen-Key": KEY})
                try: out = json.load(urllib.request.urlopen(r, timeout=120))
                except urllib.error.HTTPError as e: out = {"error": e.code, "detail": e.read().decode()[:300]}
                if out.get("ok") and "--show" in a: out["shown"] = call("cmd", {"action": "page", "name": nm})
    elif sub == "show":
        out = call("cmd", {"action": "page", "name": a[2] if len(a) > 2 else ""})
    elif sub == "list":
        out = call("page-list", {})
    elif sub == "rm":
        out = call("page-rm", {"name": a[2] if len(a) > 2 else ""})
    else:
        out = {"error": "page put ПАПКА ИМЯ [--show] | page show ИМЯ | page list | page rm ИМЯ"}
elif c == "deck":  # deck FILE.json [--i 1] — колода Милы Сцены на экран: {title, slides:[{title,sub,points,big,bars,image,notes}]}
    d = json.load(open(a[1])); i0 = int(a[a.index("--i") + 1]) - 1 if "--i" in a else 0
    sl = [{k: v for k, v in x.items() if k != "notes"} for x in (d.get("slides") or [])][:20]   # заметки — пульту, не экрану
    out = call("cmd", {"action": "app", "app": "deck", "params": {"title": str(d.get("title", ""))[:80], "slides": sl, "i": max(0, i0)}})
elif c == "goto":  # goto 3 — на слайд 3
    out = call("cmd", {"action": "goto", "i": int(a[1])})
elif c == "unpair":
    out = call("unpair", {"screen": a[1]} if len(a) > 1 else {})
else:
    out = {"error": "команда: pair|list|play|top|yt|image|audio|show|upload|page|playlist|slides|app|pause|resume|repeat|seek|volume|mute|unmute|next|prev|stop|clear|app|unpair"}
print(json.dumps(out, ensure_ascii=False))
