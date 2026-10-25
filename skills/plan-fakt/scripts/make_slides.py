#!/usr/bin/env python3
"""plan-fakt · data.json → square slides 1080×1080 (PNG, plus JPG when Pillow is present) for a Telegram slideshow post.

  make_slides.py data.json out_dir

Chromium: env CHROME_BIN, else the first found of chromium / chromium-browser / google-chrome / chrome-headless-shell
(also Playwright's cache ~/.cache/ms-playwright) / Google Chrome.app on macOS. Not found → exit 2 with a clear line.
Square only: a slideshow crops 4:5 at the top and bottom (owner's lesson 23.10).
data.json — see data-example.json: week, dates, day, brand, author, cover{title, lead, tiles[[value, note, "sand"|""]]},
slides[{kicker, title, rows[[mark, text]]}]. title fields may hold <br> and <em> (accent); everything else is escaped.
"""
import glob, html, json, os, re, shutil, subprocess, sys

CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1080px;background:radial-gradient(circle at 85% 8%,#1f6f66 0,#0b2f2c 58%);font-family:"PT Sans",-apple-system,"Helvetica Neue",Arial,sans-serif;color:#eefaf6;padding:70px 76px 96px;display:flex;flex-direction:column;position:relative}
.top{display:flex;justify-content:space-between;font-size:24px;letter-spacing:4px;color:#99f6e4;font-weight:700;padding-bottom:26px;border-bottom:1px solid rgba(153,246,228,.22)}
.top span:last-child{color:#f2c98a}
.main{flex:1;display:flex;flex-direction:column;justify-content:center;padding:44px 0 36px}
h1{font-size:80px;line-height:1.02;font-weight:800;margin-bottom:26px}
h1 em,h2 em{color:#5eead4;font-style:normal}
h2{font-size:76px;line-height:1.05;font-weight:800;margin-bottom:18px}
.lead{font-size:30px;line-height:1.35;color:#cfe9e3}
.grid{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:18px;margin:34px 0 0}
.t{background:rgba(255,255,255,.07);border:1px solid rgba(153,246,228,.25);border-radius:28px;padding:30px 26px}
.t b{display:block;font-size:54px;font-weight:800;white-space:nowrap}
.t small{display:block;font-size:23px;color:#a7d8cf;margin-top:8px;line-height:1.3}
.t.sand b{color:#f2c98a}
.k{font-size:26px;letter-spacing:3px;color:#99f6e4;margin:0 0 22px;font-weight:700}
.card{display:flex;gap:22px;align-items:center;background:rgba(255,255,255,.06);border:1px solid rgba(153,246,228,.18);border-radius:24px;padding:22px 28px;margin-bottom:16px;font-size:33px;line-height:1.28}
.card .dot{font-size:40px;width:52px;flex:none;text-align:center}
.foot{position:absolute;left:76px;right:76px;bottom:44px;display:flex;justify-content:space-between;font-size:23px;color:#7fbfb4}"""

SAFE_TITLE = re.compile(r"</?(br|em)\s*/?>", re.I)


def title_html(t):
    """Only <br> and <em> survive in titles; everything else is escaped."""
    parts, pos = [], 0
    for m in SAFE_TITLE.finditer(str(t or "")):
        parts.append(html.escape(t[pos:m.start()])); parts.append(m.group(0).lower()); pos = m.end()
    parts.append(html.escape(str(t or "")[pos:]))
    return "".join(parts)


def find_chrome():
    c = os.environ.get("CHROME_BIN")
    if c:
        return c if os.path.exists(c) or shutil.which(c) else None
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome-headless-shell"):
        p = shutil.which(name)
        if p:
            return p
    pw = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))
                + glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome")))
    if pw:
        return pw[-1]
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return mac if os.path.exists(mac) else None


def page(body, d, i, n):
    brand = html.escape(d.get("brand") or "ПЛАН-ФАКТ")
    right = html.escape("НЕДЕЛЯ %s · %s" % (d.get("week", ""), d.get("dates", "")))
    foot = html.escape(" · ".join(x for x in (d.get("author", ""), d.get("day", "")) if x))
    return ('<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>%s</style></head><body>'
            '<div class="top"><span>%s</span><span>%s</span></div><div class="main">%s</div>'
            '<div class="foot"><span>%s</span><span>%d / %d</span></div></body></html>') % (CSS, brand, right, body, foot, i, n)


def rows(rs):
    return "".join('<div class="card"><span class="dot">%s</span><span>%s</span></div>' % (html.escape(str(a)), html.escape(str(b)))
                   for a, b in rs)


def build(d):
    c = d.get("cover") or {}
    slides = d.get("slides") or []
    n = 1 + len(slides)
    tiles = c.get("tiles") or []
    tiles_html = "".join('<div class="t %s"><b>%s</b><small>%s</small></div>' % ("sand" if cls == "sand" else "", html.escape(str(v)),
                                                                                    title_html(s)) for v, s, cls in tiles)
    grid = ('<div class="grid" style="--n:%d">%s</div>' % (max(1, len(tiles)), tiles_html)) if tiles else ""
    pages = [page('<h1>%s</h1><p class="lead">%s</p>%s' % (title_html(c.get("title")), html.escape(c.get("lead", "")), grid), d, 1, n)]
    for i, s in enumerate(slides, 2):
        pages.append(page('<h2>%s</h2><div class="k">%s</div>%s' % (title_html(s.get("title")), html.escape(s.get("kicker", "")),
                                                                   rows(s.get("rows") or [])), d, i, n))
    return pages


def main():
    if len(sys.argv) != 3:
        print("make_slides.py data.json out_dir"); return 2
    try:
        d = json.load(open(sys.argv[1], encoding="utf-8"))
    except (OSError, ValueError) as e:
        print("data.json не читается: %s" % type(e).__name__); return 2
    if not (d.get("cover") and isinstance(d.get("slides"), list) and 1 <= len(d["slides"]) <= 9):
        print("в data.json нужны cover и slides (1–9 слайдов): слайдов в посте 2–10"); return 2
    ch = find_chrome()
    if not ch:
        print("Chromium не найден — задайте CHROME_BIN (путь к chromium / chrome-headless-shell)"); return 2
    out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    made = []
    for i, p in enumerate(build(d), 1):
        h = os.path.join(out, "s%d.html" % i); open(h, "w", encoding="utf-8").write(p)
        png = os.path.join(out, "s%d.png" % i)
        subprocess.run([ch, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--window-size=1080,1080",
                        "--virtual-time-budget=3000", "--screenshot=" + png, "file://" + os.path.abspath(h)], capture_output=True, timeout=90)
        if not os.path.isfile(png) or os.path.getsize(png) == 0:
            print("слайд %d не отрисовался (%s)" % (i, ch)); return 1
        try:
            from PIL import Image
            jpg = png[:-4] + ".jpg"
            Image.open(png).convert("RGB").save(jpg, quality=90); made.append(jpg)
        except Exception:
            made.append(png)
    print(json.dumps({"ok": True, "slides": made}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
