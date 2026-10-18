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
chk("ключ провайдера в тексте — стоп", {"tool_name": R, "tool_input": {"chat_id": "111", "text": "ключ sk-abcdefghijklmnopqrstuv"}}, "deny")
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
# SELFHOST-1018: без OWNER_ID адресат проверяется по access.json (allowFrom + группы); без access.json — не проверяется
env.pop("OWNER_ID", None)
json.dump({"groups": {"-1001": {}}, "allowFrom": ["555"]}, open(os.path.join(home, ".claude/channels/telegram/access.json"), "w"))
chk("без OWNER_ID: чужой чат — стоп по access.json", {"tool_name": R, "tool_input": {"chat_id": "999", "text": "привет"}}, "deny")
chk("без OWNER_ID: допущенный из allowFrom — уходит", {"tool_name": R, "tool_input": {"chat_id": "555", "text": "Готово."}}, "pass")
os.remove(os.path.join(home, ".claude/channels/telegram/access.json"))
chk("без OWNER_ID и без access.json — адресат не проверяется", {"tool_name": R, "tool_input": {"chat_id": "999", "text": "Готово."}}, "pass")
print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
