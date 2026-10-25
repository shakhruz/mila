#!/usr/bin/env python3
"""ab-test: карточка и вердикт. python3 test_ab.py"""
import json, os, subprocess, sys, tempfile
S = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "ab_card.py")
ok = n = 0
def run(*a):
    r = subprocess.run([sys.executable, S, *a], capture_output=True, text=True); return r.returncode, json.loads(r.stdout or "{}")
def chk(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + str(x)[:300]))
def card(**over):
    c = {"hypothesis": "Если начать с «ответ за 3 минуты», то заявок станет больше, потому что клиента пугает ожидание",
         "variable": "текст", "variants": [{"name": "A", "tag": "ad_tgads_otvet_1"}, {"name": "B", "tag": "ad_tgads_otvet_2"}],
         "metric": "заявка (старт бота по метке)", "budget_per_variant": 50, "start": "2026-10-23", "end": "2026-10-30",
         "stop_rule": "итог не раньше 7 дней; ab_card verdict", "owner": "Трафик"}
    c.update(over); p = tempfile.mktemp(suffix=".json"); json.dump(c, open(p, "w"), ensure_ascii=False); return p
c, o = run("card", card()); chk("полная карточка, 7 дней, одна переменная — ок", c == 0, o)
c, o = run("card", card(end="2026-10-26")); chk("3 дня — отказ (Meta: минимум 7)", c == 2 and any("меньше 7" in e for e in o["errors"]), o)
c, o = run("card", card(end="2026-12-01")); chk("39 дней — отказ (не больше 30)", c == 2 and any("больше 30" in e for e in o["errors"]), o)
c, o = run("card", card(variable="текст и картинка")); chk("две переменные — отказ", c == 2 and any("ОДНА" in e for e in o["errors"]), o)
c, o = run("card", card(variants=[{"name": "A", "tag": "ad_x_y_1"}, {"name": "B", "tag": "ad_x_y_1"}])); chk("одинаковые метки — отказ", c == 2, o)
c, o = run("card", card(hypothesis="Попробуем другой текст")); chk("гипотеза без «если…то…потому что» — отказ", c == 2, o)
c, o = run("card", card(owner="", budget_per_variant=0)); chk("нет ответственного и бюджет 0 — оба в списке", c == 2 and len(o["errors"]) == 2, o)
c, o = run("verdict", "--a", "4000,40", "--b", "4000,70", "--days", "8"); chk("40 против 70 из 4000 за 8 дней — победитель B", o["verdict"] == "победитель B" and o["p_value"] < 0.05, o)
c, o = run("verdict", "--a", "4000,40", "--b", "4000,46", "--days", "8"); chk("40 против 46 — нет вывода (случайная разница)", o["verdict"] == "нет вывода", o)
c, o = run("verdict", "--a", "4000,40", "--b", "4000,90", "--days", "4"); chk("4 дня — «рано», даже при большой разнице", o["verdict"] == "рано", o)
c, o = run("verdict", "--a", "300,2", "--b", "300,4", "--days", "9"); chk("меньше 5 действий — нет вывода, нужен бюджет", o["verdict"] == "нет вывода" and "меньше 5" in o["why"], o)
c, o = run("verdict", "--a", "100,200", "--b", "100,5", "--days", "9"); chk("действий больше показов — ошибка ввода", o["verdict"] == "ошибка", o)
print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
