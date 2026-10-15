#!/usr/bin/env python3
"""request_send.py — заявка «написать через оператора» (навык bot-send). Пишет work/outbox/bot-send/<id>.json; отправляет хост-служба
bot-send-gate (токен бота оператора живёт на хосте, не у меня). Без нажатия ✅ хозяина заявку не пишет.
  request_send.py personal --operator <slug> --to <id|@username> --text "…" --card <card_id> --choice <choice>
  request_send.py broadcast --operator <slug> --segment "<сегмент>" | --to id1,id2 --text "…" --card <card_id> --choice <choice>
  request_send.py status <id>                 — что ответила служба (<id>.result.json)
card/choice — карточка, на которой хозяин нажал ✅ (из входящего «[кнопка] …» и cards.jsonl плагина); служба сверит её сама."""
import argparse, json, os, re, sys, time, uuid

OUT = os.path.join(os.environ.get("MILA_WORK") or os.path.expanduser("~/work"), "outbox", "bot-send")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    for k in ("personal", "broadcast"):
        p = sp.add_parser(k); p.add_argument("--operator", required=True); p.add_argument("--text", required=True)
        p.add_argument("--to", default=""); p.add_argument("--card", required=True); p.add_argument("--choice", required=True)
        p.add_argument("--buttons", default="", help='JSON: [[{"label":"Сайт","url":"https://…"}]] — только https')
        if k == "broadcast": p.add_argument("--segment", default="")
    s = sp.add_parser("status"); s.add_argument("id")
    a = ap.parse_args()
    if a.cmd == "status":
        r = os.path.join(OUT, a.id + ".result.json")
        print(open(r).read() if os.path.exists(r) else json.dumps({"status": "ждёт службу", "id": a.id}, ensure_ascii=False)); return
    text = a.text.strip()
    if not text or len(text) > 4096: sys.exit(json.dumps({"error": "текст пустой или длиннее 4096"}, ensure_ascii=False))
    if not re.fullmatch(r"[a-z0-9-]{2,40}", a.operator): sys.exit(json.dumps({"error": "operator — slug оператора"}, ensure_ascii=False))
    to = [x.strip().lstrip("@") for x in a.to.split(",") if x.strip()]
    if a.cmd == "personal" and len(to) != 1: sys.exit(json.dumps({"error": "personal — ровно один получатель"}, ensure_ascii=False))
    if a.cmd == "broadcast" and not (to or a.segment): sys.exit(json.dumps({"error": "broadcast — --segment или --to"}, ensure_ascii=False))
    if not re.search(r"ok|✅|yes|send|da", a.choice, re.I): sys.exit(json.dumps({"error": "нет ✅ хозяина — заявку не пишу"}, ensure_ascii=False))
    buttons = json.loads(a.buttons) if a.buttons else []
    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    req = {"id": rid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": a.cmd, "operator": a.operator, "to": to,
           "segment": getattr(a, "segment", ""), "text": text, "buttons": buttons, "owner_yes": {"card_id": a.card, "choice": a.choice}}
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(OUT, rid + ".json.tmp"); json.dump(req, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, os.path.join(OUT, rid + ".json"))
    print(json.dumps({"ok": True, "id": rid, "note": "служба отправит в течение пары минут; итог — request_send.py status " + rid}, ensure_ascii=False))


if __name__ == "__main__":
    main()
