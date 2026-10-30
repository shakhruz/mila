#!/usr/bin/env python3
"""doctor check_switches: «включено в настройке, но не работает» — гостевой контур без флага окружения, без ключа,
без handoffFile; ученики без промпта; Jev без адреса; обновления без owner_chat. Всё во временной папке."""
import importlib.util, json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(); ST = os.path.join(T, "state"); os.makedirs(ST); os.environ["TELEGRAM_STATE_DIR"] = ST
spec = importlib.util.spec_from_file_location("doctor", os.path.join(HERE, "doctor.py")); D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
key = os.path.join(T, "key"); open(key, "w").write("k"); pr = os.path.join(T, "p.md"); open(pr, "w").write("x")
def acc(cc): json.dump({"allowFrom": ["1"], "guestDm": {"enabled": True, "cc": cc}}, open(os.path.join(ST, "access.json"), "w"))
def run(env, home=T):
    r = D.Report(); D.check_switches(r, daemon_env=env, home=home); return r.rows
acc({"enabled": True, "keyFile": key, "systemPromptFile": pr, "cardToRazbor": True, "handoffFile": "/x"})
rows = run({"PATH": "/bin"})
chk("гостевой контур в access, у демона нет MILAT_GUEST_CC=1 → 🔴 с подсказкой Environment=", any(r["level"] == "bad" and "MILAT_GUEST_CC" in r["detail"] and "Environment=MILAT_GUEST_CC=1" in r["fix"] for r in rows), rows)
rows = run({"MILAT_GUEST_CC": "1"})
chk("флаг есть, ключ и промпт на месте → 🟢, без 🔴", any(r["level"] == "ok" for r in rows) and not any(r["level"] == "bad" for r in rows), rows)
rows = run(None)
chk("окружение демона не проверить → 🟡, не молча", any(r["level"] == "warn" and "проверить не удалось" in r["detail"] for r in rows), rows)
acc({"enabled": True, "keyFile": os.path.join(T, "nope"), "systemPromptFile": pr, "cardToRazbor": True})
rows = run({"MILAT_GUEST_CC": "1"})
chk("ключа нет → 🔴; cardToRazbor без handoffFile → 🔴 «только в лог»", any(r["level"] == "bad" and "ключ гостей" in r["detail"] for r in rows) and any(r["level"] == "bad" and "только в лог" in r["detail"] for r in rows), rows)
acc({"enabled": True, "keyFile": key, "systemPromptFile": pr, "students": {"knowledgeDir": "/k"}})
rows = run({"MILAT_GUEST_CC": "1"})
chk("ученики без промпта → 🟡 «выключен»", any(r["name"] == "ученики" and "выключен" in r["detail"] for r in rows), rows)
json.dump({"allowFrom": ["1"]}, open(os.path.join(ST, "access.json"), "w"))
os.makedirs(os.path.join(T, ".claude")); json.dump({"mode": "shadow", "url": ""}, open(os.path.join(T, ".claude", "jev.json"), "w"))
json.dump({"channel": "stable", "owner_chat": ""}, open(os.path.join(T, ".claude", "mila-update.json"), "w"))
rows = run({})
chk("без гостевого контура — строк о нём нет; Jev shadow без адреса и обновления без owner_chat → 🟡", not any(r["name"] == "гостевой контур" for r in rows) and any(r["name"] == "Jev" for r in rows) and any(r["name"] == "обновления" for r in rows), rows)
json.dump({"channel": "manual"}, open(os.path.join(T, ".claude", "mila-update.json"), "w"))
chk("обновления вручную (manual) — без замечания про owner_chat", not any(r["name"] == "обновления" for r in run({})))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
