#!/usr/bin/env python3
"""Тест сторожа отправки (send-guard.py). С onFailure: "block" (CC 2.1.295+) падение сторожа = ни одно сообщение не уходит,
поэтому сторож держим под тестом: каждый случай — exit 0 и решение «пропустить» или «deny» с причиной. Песочница: свой HOME."""
import json, os, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); G = os.path.join(H, "send-guard.py")
home = tempfile.mkdtemp(); os.makedirs(os.path.join(home, ".claude/channels/telegram"))
json.dump({"groups": {"-1001": {}}, "allowFrom": ["555"]}, open(os.path.join(home, ".claude/channels/telegram/access.json"), "w"))
env = dict(os.environ, HOME=home, OWNER_ID="111", MILA_DEV_CHAT="-1009")
ok = n = 0
def run(inp):
    r = subprocess.run([sys.executable, G], input=json.dumps(inp) if not isinstance(inp, str) else inp, capture_output=True, text=True, env=env, timeout=20)
    dec = ""
    if r.stdout.strip():
        try: dec = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]
        except Exception: dec = "?"
    return r.returncode, dec, r.stdout
def chk(name, inp, want):
    global ok, n; n += 1
    code, dec, out = run(inp); good = code == 0 and (dec == "deny") == (want == "deny")
    ok += good; print(("✅ " if good else "❌ ") + name + ("" if good else f"  (код {code}, решение {dec or 'пропуск'}: {out[:200]})"))
R = "mcp__plugin_mila-telegram_telegram__reply"
chk("хозяину обычный текст — уходит", {"tool_name": R, "tool_input": {"chat_id": "111", "text": "Квиз готов. Включить на экране?"}}, "pass")
chk("чужому чату — стоп", {"tool_name": R, "tool_input": {"chat_id": "999", "text": "привет"}}, "deny")
chk("в разрешённую группу — уходит", {"tool_name": R, "tool_input": {"chat_id": "-1001", "text": "Готово."}}, "pass")
chk("извинение хозяину — стоп (закон 7)", {"tool_name": R, "tool_input": {"chat_id": "111", "text": "Извините, я не успела"}}, "deny")
chk("ключ провайдера в тексте — стоп", {"tool_name": R, "tool_input": {"chat_id": "111", "text": "ключ " + "sk-" + "abcdefghijklmnopqrstuv"}}, "deny")   # фальшивка склеивается — сканер ядра чист
chk("серверный путь — стоп", {"tool_name": R, "tool_input": {"chat_id": "111", "text": "файл /srv/x"}}, "deny")
chk("другой инструмент — не мешает", {"tool_name": "Bash", "tool_input": {"command": "ls"}}, "pass")
chk("мусор на входе — не мешает (exit 0)", "не json", "pass")
# чаты одного дела (агентство: группа клиента Acme → рабочий чат)
ev = os.path.join(home, ".claude/channels/telegram/inbound"); os.makedirs(ev, exist_ok=True)
with open(os.path.join(ev, "events.jsonl"), "w") as f:
    for cid, title, user in (("-1001", "Agency Work", "anna_ag"), ("-1002", "Acme x Agency", "acme_travel"), ("-1003", "Другой клиент Zina", "zina_c")):
        f.write(json.dumps({"params": {"meta": {"chat_id": cid, "chat_title": title, "user": user}}}) + "\n")
json.dump({"groups": {"-1001": {}, "-1002": {}, "-1003": {}}, "allowFrom": []}, open(os.path.join(home, ".claude/channels/telegram/access.json"), "w"))
T = "Запрос из Acme: @acme_travel просит билеты Ташкент — Стамбул на 20.10, двое."
chk("без списка одного дела: название и @тег группы клиента в Agency Work — стоп (как было)", {"tool_name": R, "tool_input": {"chat_id": "-1001", "text": T}}, "deny")
os.makedirs(os.path.join(home, ".claude/hooks"), exist_ok=True)
json.dump([["-1002", "-1001"]], open(os.path.join(home, ".claude/hooks/same-case-chats.json"), "w"))
chk("со списком одного дела (Acme + Agency Work) — уходит", {"tool_name": R, "tool_input": {"chat_id": "-1001", "text": T}}, "pass")
chk("третий клиент — по-прежнему чужое дело: стоп", {"tool_name": R, "tool_input": {"chat_id": "-1001", "text": "Как у Zina дела? @zina_c писала"}}, "deny")
chk("и в обратную сторону одного дела: из Agency Work в Acme — уходит", {"tool_name": R, "tool_input": {"chat_id": "-1002", "text": "Agency Work подтвердил: билеты будут к вечеру"}}, "pass")
# без OWNER_ID адресат проверяется по access.json (allowFrom + группы); без access.json — не проверяется
env.pop("OWNER_ID", None)
json.dump({"groups": {"-1001": {}}, "allowFrom": ["555"]}, open(os.path.join(home, ".claude/channels/telegram/access.json"), "w"))
chk("без OWNER_ID: чужой чат — стоп по access.json", {"tool_name": R, "tool_input": {"chat_id": "999", "text": "привет"}}, "deny")
chk("без OWNER_ID: допущенный из allowFrom — уходит", {"tool_name": R, "tool_input": {"chat_id": "555", "text": "Готово."}}, "pass")
os.remove(os.path.join(home, ".claude/channels/telegram/access.json"))
chk("без OWNER_ID и без access.json — адресат не проверяется", {"tool_name": R, "tool_input": {"chat_id": "999", "text": "Готово."}}, "pass")
# номер карты собираем в коде (Луна), чтобы в репо не лежал «номер»
import random
def _pan(prefix="8600", L=16):
    d = [int(c) for c in prefix] + [random.randint(0, 9) for _ in range(L - len(prefix) - 1)]
    t = sum((x * 2 - 9 if x * 2 > 9 else x * 2) if i % 2 == 0 else x for i, x in enumerate(reversed(d)))
    return "".join(map(str, d)) + str((10 - t % 10) % 10)
env["OWNER_ID"] = "111"
json.dump({"groups": {"-1001": {}}, "allowFrom": ["555"]}, open(os.path.join(home, ".claude/channels/telegram/access.json"), "w"))
P19 = _pan("4", 19); P = _pan(); PS = " ".join(P[i:i + 4] for i in range(0, 16, 4)); PD = "-".join(P[i:i + 4] for i in range(0, 16, 4))
chk("карта в группу (с пробелами) — стоп", {"tool_name": R, "tool_input": {"chat_id": "-1001", "text": "Новые за сутки: письмо — карта " + PS}}, "deny")
chk("карта в группу (с дефисами, 19 цифр) — стоп", {"tool_name": R, "tool_input": {"chat_id": "-1001", "text": "карта " + "-".join(P19[i:i + 4] for i in range(0, 19, 4))}}, "deny")
n += 1; code, dec, out = run({"tool_name": R, "tool_input": {"chat_id": "111", "text": "Оплата с карты " + PD + " прошла", "reply_to": 7}})
ti = (json.loads(out)["hookSpecificOutput"].get("updatedInput") or {}) if out.strip() else {}
good = dec == "allow" and ti.get("text") == "Оплата с карты ****" + P[-4:] + " прошла" and ti.get("reply_to") == 7 and P not in out
ok += good; print(("✅ " if good else "❌ ") + "карта хозяину — уходит с маской ****1234, остальные поля целы" + ("" if good else "  " + out[:200]))
bad = P[:-1] + str((int(P[-1]) + 1) % 10)
chk("16 цифр без Луны (номер заказа) — уходит как есть", {"tool_name": R, "tool_input": {"chat_id": "-1001", "text": "заказ " + bad}}, "pass")
chk("телефон +998 90 123 45 67 и 12 цифр — не карта", {"tool_name": R, "tool_input": {"chat_id": "-1001", "text": "звоните +998 90 123 45 67, ИНН 123456789012"}}, "pass")
chk("карта + другая причина хозяину — стоп (маска не прячет ошибку)", {"tool_name": R, "tool_input": {"chat_id": "111", "text": "карта " + P + " и файл /srv/x"}}, "deny")
OUR = _pan("9860")
json.dump({"groups": {"-1001": {}}, "allowFrom": ["555"], "cardAllow": [OUR]}, open(os.path.join(home, ".claude/channels/telegram/access.json"), "w"))
chk("CARD-ALLOW: наши реквизиты (access.json cardAllow) в группу — уходят", {"tool_name": R, "tool_input": {"chat_id": "-1001", "text": "Перевод на карту " + " ".join(OUR[i:i + 4] for i in range(0, 16, 4))}}, "pass")
chk("CARD-ALLOW: чужая карта при заданном cardAllow — всё равно стоп", {"tool_name": R, "tool_input": {"chat_id": "-1001", "text": "карта " + P}}, "deny")
n += 1; code, dec, out = run({"tool_name": R, "tool_input": {"chat_id": "111", "text": "Карта " + PS + " 100 USD"}})
good = dec == "allow" and (json.loads(out)["hookSpecificOutput"]["updatedInput"]["text"] == "Карта ****" + P[-4:] + " 100 USD")
ok += good; print(("✅ " if good else "❌ ") + "сумма сразу после номера («… 100 USD») — номер всё равно маской" + ("" if good else "  " + out[:200]))
# подпись к фото (caption) проверяется так же, как текст; маска — в своём поле, текст не смешивается
chk("ключ провайдера в caption — стоп", {"tool_name": R, "tool_input": {"chat_id": "111", "text": "Готово", "caption": "ключ " + "sk-" + "abcdefghijklmnopqrstuv"}}, "deny")
chk("серверный путь в caption — стоп", {"tool_name": R, "tool_input": {"chat_id": "111", "text": "Альбом", "caption": "файлы в " + "/srv/" + "mila/x"}}, "deny")
n += 1; code, dec, out = run({"tool_name": R, "tool_input": {"chat_id": "111", "text": "Альбом", "caption": "Карта " + PS + " к оплате", "files": ["/tmp/a.png", "/tmp/b.png"]}})
u = json.loads(out)["hookSpecificOutput"].get("updatedInput", {}) if dec == "allow" else {}
good = dec == "allow" and u.get("text") == "Альбом" and u.get("caption") == "Карта ****" + P[-4:] + " к оплате" and u.get("files") == ["/tmp/a.png", "/tmp/b.png"]
ok += good; print(("✅ " if good else "❌ ") + "карта в caption хозяину — маска в caption, текст и файлы как были")
print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
