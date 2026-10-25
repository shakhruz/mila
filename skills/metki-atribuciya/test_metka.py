#!/usr/bin/env python3
"""metki-atribuciya: метка и ссылки. python3 test_metka.py"""
import json, os, subprocess, sys
S = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "metka.py")
ok = n = 0
def run(*a):
    r = subprocess.run([sys.executable, S, *a], capture_output=True, text=True); return r.returncode, json.loads(r.stdout or "{}")
def chk(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + str(x)[:300]))
c, o = run("--channel", "tgads", "--topic", "otvet3min", "--n", "2", "--bot", "mila_gpt_bot", "--site", "https://milagpt.io/x?lang=ru")
chk("метка ad_tgads_otvet3min_2 и ссылка на бота ?start=", c == 0 and o["tag"] == "ad_tgads_otvet3min_2" and o["bot_link"] == "https://t.me/mila_gpt_bot?start=ad_tgads_otvet3min_2", o)
chk("сайт: utm_source/medium/campaign + utm_content=метка, старый параметр сохранён", "lang=ru&utm_source=tgads&utm_medium=cpc&utm_campaign=otvet3min&utm_content=ad_tgads_otvet3min_2" in o.get("site_link", ""), o)
c, o = run("--channel", "TG Ads", "--topic", "otvet_3min", "--n", "0")
chk("пробел, _ в теме, N=0 — отказ со всеми тремя причинами", c == 2 and len(o["errors"]) == 3, o)
c, o = run("--channel", "tgads", "--topic", "x1", "--n", "1", "--bot", "@evil.com/x")
chk("кривое имя бота — отказ", c == 2, o)
c, o = run("--check", "ad_tgads_otvet3min_2"); chk("--check годной метки", c == 0 and o["ok"])
c, o = run("--check", "p_helen"); chk("--check метки партнёра", c == 0)
c, o = run("--check", "ad_" + "a" * 70); chk("--check: длиннее 64 — отказ", c == 2 and any("64" in e for e in o["errors"]), o)
c, o = run("--check", "реклама_1"); chk("--check: кириллица — отказ", c == 2)
print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
