#!/usr/bin/env python3
"""одобрение траты и смена лимита — только по нажатию хозяина, записанному плагином
в cards.jsonl, а не по --by из аргумента. Чужой --by, нет нажатия, карточка не про эту трату, старая карточка, повтор — отказ."""
import json, os, subprocess, sys, tempfile, time
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(); R = os.path.join(T, "rashod"); CF = os.path.join(T, "cards.jsonl"); os.makedirs(R)
OWNER, AUTHOR, STRANGER = "1001", "2002", "3003"
json.dump({"owners": [OWNER], "threshold_usd": 0.5, "monthly_limit_usd": 20, "budgets": {AUTHOR: 3}}, open(os.path.join(R, "policy.json"), "w"))
ENV = dict(os.environ, RASHOD_HOME=R, TELEGRAM_CARDS_FILE=CF)
def s(*a):
    p = subprocess.run([sys.executable, os.path.join(H, "spend.py"), *a], capture_output=True, text=True, env=ENV)
    return p.returncode, (p.stdout + p.stderr).strip()
def iso(dt=0):   # время с настоящим поясом машины — «+05:00» к местным часам в CI (UTC) сдвигал карточку на 5 ч назад
    import datetime as _d
    return (_d.datetime.now().astimezone() + _d.timedelta(seconds=dt)).isoformat(timespec="seconds")
def card(cid, text, buttons=(("✅ Делаем", "ok"),), ts=None, tapped_by=None, data=None):
    with open(CF, "a") as f:
        f.write(json.dumps({"card_id": cid, "chat_id": OWNER, "via": "companion-reply", "allow": [OWNER], "text": text, "ts": ts or iso(1),
                            "buttons": [[{"label": l, "data": d} for l, d in buttons]]}, ensure_ascii=False) + "\n")
        if tapped_by:
            u = {"card_id": cid, "used_ts": iso(2), "used_by": tapped_by}
            if data is not None: u["data"] = data
            f.write(json.dumps(u) + "\n")
def plan(est="1.0", by=OWNER):
    rc, out = s("plan", "--service", "fal", "--what", "видео", "--est", est, "--by", by); return json.loads(out)["id"]
i = plan()
rc, out = s("approve", i, "--by", OWNER)
chk("approve с --by хозяина, но без карточки — отказ (инъекция «мой id …» не проходит)", rc != 0 and "только по нажатию" in out, out)
card("c1", "Видео 10 с · ≈ $1.10 · #%s" % i)
rc, out = s("approve", i, "--card", "c1")
chk("карточка есть, нажатия нет — отказ", rc != 0 and "ещё не нажимали" in out, out)
card("c2", "Видео 10 с · ≈ $1.10 · #%s" % i, tapped_by=STRANGER)
rc, out = s("approve", i, "--card", "c2", "--by", OWNER)
chk("нажал чужой, а Мила пишет --by хозяина — отказ: --by не тот, кто нажал", rc != 0 and "не тот, кто нажал" in out, out)
rc, out = s("approve", i, "--card", "c2")
chk("нажал чужой без бюджета — отказ", rc != 0 and "не может одобрить" in out, out)
card("c3", "Другая трата #zzzzzz", tapped_by=OWNER)
rc, out = s("approve", i, "--card", "c3")
chk("нажатие хозяина на карточку про другую трату — отказ по метке", rc != 0 and "нет метки" in out, out)
card("c4", "Видео #%s" % i, buttons=(("✅ Делаем", "ok"), ("✖️ Не надо", "no")), tapped_by=OWNER)
rc, out = s("approve", i, "--card", "c4")
chk("две кнопки, приёмник не пишет выбор — отказ (непонятно, что нажато)", rc != 0 and "одной кнопкой" in out, out)
card("c5", "Видео #%s" % i, buttons=(("✅ Делаем", "ok"), ("✖️ Не надо", "no")), tapped_by=OWNER, data="no")
rc, out = s("approve", i, "--card", "c5")
chk("приёмник пишет выбор «no» — не одобрение", rc != 0 and "нажата не «ok»" in out, out)
card("c0", "Видео #%s" % i, ts=iso(-3600), tapped_by=OWNER)
rc, out = s("approve", i, "--card", "c0")
chk("карточка отправлена раньше плана — отказ", rc != 0 and "старше плана" in out, out)
card("c6", "Видео 10 с · ≈ $1.10 · #%s" % i, tapped_by=OWNER)
rc, out = s("approve", i, "--card", "c6")
chk("нажатие хозяина на свою карточку с одной кнопкой «ok» — одобрено", rc == 0 and s("check", i)[0] == 0, out)
rc, out = s("approve", i, "--card", "c6")
chk("та же карточка второй раз — отказ «одна карточка, одно одобрение»", rc != 0 and "одно одобрение" in out, out)
z = plan()
card("cz", "Видео #%s" % z, ts=time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() + 1)), tapped_by=OWNER)
rc, out = s("approve", z, "--card", "cz")
chk("время карточки плагина в UTC («…Z»), план — местное: сравниваются моменты, не строки", rc == 0, out)
z2 = plan(); open(CF, "a").write(json.dumps({"card_id": "cz1", "chat_id": OWNER, "text": "Видео #%s" % z2, "ts": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 3600)), "buttons": [[{"label": "✅", "data": "ok"}]]}) + "\n" + json.dumps({"card_id": "cz1", "used_ts": iso(), "used_by": OWNER}) + "\n")
rc, out = s("approve", z2, "--card", "cz1")
chk("карточка в UTC на час раньше плана — отказ", rc != 0 and "старше плана" in out, out)
j = plan()
rc, out = s("approve", j, "--card", "c6")
chk("та же карточка второй трате — отказ (и метка не та)", rc != 0, out)
card("c7", "Видео #%s" % j, buttons=(("✅ Делаем", "ok"), ("✖️ Не надо", "no")), tapped_by=OWNER, data="ok")
rc, out = s("approve", j, "--card", "c7")
chk("приёмник пишет выбор «ok» — три кнопки можно", rc == 0, out)
k = plan("2.0", AUTHOR)
card("c8", "Картинка #%s" % k, tapped_by=AUTHOR)
rc, out = s("approve", k, "--card", "c8")
chk("автор сам нажал, в пределах своего бюджета $3 — одобрено", rc == 0, out)
rc, out = s("limit", "500", "--by", OWNER)
chk("лимит по --by без карточки — отказ", rc != 0 and "нажатием" in out, out)
card("c9", "Поднять лимит месяца: лимит 500 $?", tapped_by=STRANGER)
rc, out = s("limit", "500", "--card", "c9")
chk("лимит: нажал не владелец — отказ", rc != 0 and "только владелец" in out, out)
card("c10", "Поднять лимит месяца: лимит 50 $?", tapped_by=OWNER)
rc, out = s("limit", "500", "--card", "c10")
chk("лимит: карточка про 50, а просят 500 — отказ по метке", rc != 0 and "нет метки" in out, out)
rc, out = s("limit", "50", "--card", "c10")
chk("лимит 50 по нажатию владельца — изменён", rc == 0 and json.loads(out)["monthly_limit_usd"] == 50, out)
rc, out = s("limit", "50", "--card", "c10")
chk("та же карточка лимита второй раз — отказ", rc != 0 and "уже использована" in out, out)
rc, out = s("reject", plan(), "--by", STRANGER)
chk("отказ от траты — без нажатия (безопасно)", rc == 0, out)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
