#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Быстрая проверка после выкладки — первый проход, числом, без глаз.
Не заменяет Playwright-замер 360 px (mobile360.py у клиента, если есть) и
тестовую заявку через форму (lead-test.py) — это отдельный, более глубокий
шаг из SKILL.md раздела 6.

Использование:
  python3 check_deploy.py https://acme.uz/ https://acme.uz/tour-bali.html ...
  python3 check_deploy.py --file urls.txt   # по одному адресу в строке

Проверяет на каждый адрес: код ответа 200, наличие <meta viewport>,
наличие <link rel=canonical> с этим же доменом (не pages.dev), отсутствие
noindex. Печатает таблицу и код возврата 1, если хоть один адрес не прошёл.
"""
import argparse
import re
import sys
import urllib.request


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (webmaster-check)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(2_000_000).decode("utf-8", "replace")
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa
        return None, str(e)


def check_one(url):
    status, body = fetch(url)
    ok_status = status == 200
    has_viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', body, re.I)) if body else False
    has_canonical = bool(re.search(r'<link[^>]+rel=["\']canonical["\']', body, re.I)) if body else False
    has_noindex = bool(re.search(r'noindex', body, re.I)) if body else False
    canonical_domain_ok = True
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', body or "", re.I)
    if m:
        canonical_domain_ok = "pages.dev" not in m.group(1)
    passed = ok_status and has_viewport and has_canonical and canonical_domain_ok and not has_noindex
    return {
        "url": url,
        "status": status,
        "viewport": has_viewport,
        "canonical": has_canonical,
        "canonical_not_preview": canonical_domain_ok,
        "noindex": has_noindex,
        "passed": passed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--file", default=None, help="файл со списком адресов, по одному в строке")
    ap.add_argument("--allow-noindex", action="store_true", help="для превью — noindex это норма, не сбой")
    args = ap.parse_args()

    urls = list(args.urls)
    if args.file:
        urls += [l.strip() for l in open(args.file, encoding="utf-8") if l.strip()]
    if not urls:
        print("нет адресов для проверки", file=sys.stderr)
        return 2

    rows = [check_one(u) for u in urls]
    bad = 0
    for r in rows:
        ok = r["passed"] or (args.allow_noindex and r["noindex"] and r["status"] == 200
                              and r["viewport"] and r["canonical"])
        mark = "OK " if ok else "FAIL"
        print(f"{mark}  {r['status']}  viewport={r['viewport']}  canonical={r['canonical']}"
              f"  noindex={r['noindex']}  {r['url']}")
        if not ok:
            bad += 1

    print(f"\nитого: {len(rows)-bad}/{len(rows)} прошли")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
