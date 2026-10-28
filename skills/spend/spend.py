#!/usr/bin/env python3
"""Расход — учёт платных генераций Милы (OpenRouter, fal.ai, HeyGen, ElevenLabs и др.).
Перед генерацией дороже порога (threshold_usd) — прогноз и детали, кнопки «одобрить / отменить»;
после — результат и фактический расход. Мила осознанно тратит деньги владельца и помогает планировать.

Папка $RASHOD_HOME (по умолчанию ~/work/rashod):
  policy.json  — {"owners":[id], "threshold_usd":0.5, "monthly_limit_usd":20, "budgets":{"<user_id>":5}}
                 budgets — сколько в месяц владелец разрешил тратить человеку без своего «да» (решение «А/Б» владельца)
  ledger.jsonl — строка на план: id, сервис, что, прогноз, кто просил, кто одобрил, факт, статус

  spend.py plan --service fal --what "видео 10 с" --est 0.8 --by <user_id>  → id + решение: auto | card
  spend.py approve <id> --card <card_id> [--msg <chat>/<msg>]   — по нажатию: кто нажал, берётся из журнала карточек
                 плагина (cards.jsonl), не из аргумента; owner — всегда, автор — в пределах своего бюджета
  spend.py reject <id> --by <user_id>
  spend.py check <id>        — можно ли тратить (код 0 — да)
  spend.py done <id> --fact 0.74 [--note "…"]
  spend.py report [--month 2026-10]  — потрачено, по сервисам, по людям, прогноз против факта, остаток
  spend.py owner <id> --card <c> · limit <usd> --card <c> · budget <user_id> <usd> --card <c>   — тоже по нажатию владельца
SPEND-TAP-2810 (Качество 28.10 17:00): одобрение держалось на --by — id, который Мила сама пишет аргументом; инъекция
«одобри, мой id …» или ошибка модели давали трату без нажатия. Теперь нужна карточка (reply с кнопками), в тексте которой
есть метка траты («#<id>» или «лимит <usd>» / «бюджет <user_id> <usd>» / «владелец <id>»), отправленная после плана,
и запись нажатия приёмника: used_by — владелец (или автор в своём бюджете), выбор — кнопка «ok» (или единственная кнопка
карточки, если приёмник выбор не пишет). Одна карточка — одно одобрение.
"""
import argparse, datetime as dt, json, os, re, sys, uuid
from collections import defaultdict

HOME = os.path.expanduser(os.environ.get("RASHOD_HOME", "~/work/rashod"))
POL, LED = os.path.join(HOME, "policy.json"), os.path.join(HOME, "ledger.jsonl")
NOW = lambda: dt.datetime.now().astimezone().isoformat(timespec="seconds")

def pol():
    d = {"owners": [], "threshold_usd": 0.5, "monthly_limit_usd": 20, "budgets": {}}
    if os.path.exists(POL): d.update(json.load(open(POL)))
    return d
def save_pol(d): os.makedirs(HOME, exist_ok=True); json.dump(d, open(POL, "w"), ensure_ascii=False, indent=1)
def rows():
    if not os.path.exists(LED): return {}
    out = {}
    for l in open(LED, encoding="utf-8"):
        if l.strip(): r = json.loads(l); out[r["id"]] = {**out.get(r["id"], {}), **r}
    return out
def put(r): os.makedirs(HOME, exist_ok=True); open(LED, "a", encoding="utf-8").write(json.dumps(r, ensure_ascii=False) + "\n")
def month(r): return r["ts"][:7]
CARDS = lambda: os.environ.get("TELEGRAM_CARDS_FILE") or os.path.join(os.environ.get("TELEGRAM_STATE_DIR") or os.path.expanduser("~/.claude/channels/telegram"), "cards.jsonl")

def _t(s):
    try: return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError): return None

def tap(card_id, mark, after=None):
    """Нажатие хозяина на карточку card_id → (кто нажал, None) или (None, причина отказа). Читает только журнал плагина."""
    card = used = None
    try:
        for l in open(CARDS(), encoding="utf-8"):
            try: r = json.loads(l)
            except ValueError: continue
            if not isinstance(r, dict) or r.get("card_id") != card_id: continue
            if r.get("used_ts"): used = r
            elif card is None: card = r
    except OSError:
        return None, "нет журнала карточек плагина"
    if not card: return None, "карточки %s нет в журнале плагина" % card_id
    if not re.search(r"(?<![\w#])%s(?!\w)" % re.escape(mark), card.get("text") or ""):
        return None, "в карточке нет метки «%s» — это карточка не про эту трату" % mark
    if after and (_t(card.get("ts")) or 0) < (_t(after) or 0):   # плагин пишет UTC «…Z», план — местное «+05:00»: сравниваю моменты
        return None, "карточка старше плана траты"
    if not used: return None, "на карточку ещё не нажимали"
    choice = [b.get("data") for row in card.get("buttons") or [] for b in row if isinstance(b, dict) and b.get("data")]
    if "data" in used:
        if used["data"] != "ok": return None, "нажата не «ok», а «%s»" % used["data"]
    elif choice != ["ok"]:
        return None, "приёмник не пишет, какая кнопка нажата: одобрять можно карточкой с одной кнопкой «ok» (✅ Делаем)"
    return str(used.get("used_by") or ""), None

def card_spent(rs, card_id):
    return any(r.get("card") == card_id for r in rs.values()) or card_id in (pol().get("cards") or [])
def spent(rs, m, who=None):
    s = 0.0
    for r in rs.values():
        if month(r) != m or r.get("status") not in ("approved", "auto", "done"): continue
        if who and str(r.get("by")) != str(who): continue
        s += r.get("fact", r["est"])
    return s

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    p, rs, m = pol(), rows(), NOW()[:7]
    cmd = a[0]
    ap = argparse.ArgumentParser(); ap.add_argument("x", nargs="*")
    for f in ("--service", "--what", "--est", "--by", "--msg", "--fact", "--note", "--month", "--card"): ap.add_argument(f)
    o = ap.parse_args(a[1:])
    if cmd == "plan":
        est = round(float(o.est) * 1.1, 2)  # запас 10 %
        left = p["monthly_limit_usd"] - spent(rs, m)
        r = {"id": uuid.uuid4().hex[:6], "ts": NOW(), "service": o.service, "what": o.what, "est": est, "by": o.by}
        if est > left: r["status"] = "over_limit"
        elif est < p["threshold_usd"]: r["status"] = "auto"
        else: r["status"] = "planned"
        put(r)
        print(json.dumps({**r, "left_month": round(left, 2),
              "next": {"auto": "делай и запиши done", "planned": "карточка: что · прогноз · кнопки ✅/✏️/✖️",
                       "over_limit": "месячный потолок — спроси владельца поднять лимит"}[r["status"]]}, ensure_ascii=False))
    elif cmd in ("approve", "reject"):
        r = rs[o.x[0]]
        if cmd == "approve":
            if not o.card: sys.exit("одобрение — только по нажатию: --card <id карточки> (SPEND-TAP-2810)")
            if card_spent(rs, o.card): sys.exit("эта карточка уже одобрила трату — одна карточка, одно одобрение")
            by, why = tap(o.card, "#" + r["id"], r["ts"])
            if not by: sys.exit("не одобрено: " + why)
            if o.by and str(o.by) != by: sys.exit(f"--by {o.by} не тот, кто нажал ({by})")
            owner = by in map(str, p["owners"])
            budget = float(p["budgets"].get(by, 0)); mine = spent(rs, m, by)
            if not owner and not (by == str(r["by"]) and mine + r["est"] <= budget):
                sys.exit(f"не может одобрить: не владелец и бюджет {by} ${budget} (потрачено ${mine:.2f})")
            put({"id": r["id"], "status": "approved", "approved_by": by, "card": o.card, "msg": o.msg, "approved_ts": NOW()})
        else: put({"id": r["id"], "status": "rejected", "by_reject": str(o.by)})   # отказ безопасен — нажатия не жду
        print("ok")
    elif cmd == "check":
        r = rs.get(o.x[0]); ok = r and r.get("status") in ("approved", "auto")
        print("можно" if ok else "нельзя: нет одобрения"); sys.exit(0 if ok else 1)
    elif cmd == "done":
        r = rs[o.x[0]]; put({"id": r["id"], "status": "done", "fact": float(o.fact), "note": o.note, "done_ts": NOW()})
        print(f"факт ${float(o.fact):.2f} при прогнозе ${r['est']:.2f}")
    elif cmd == "report":
        mm = o.month or m; by_s, by_p = defaultdict(float), defaultdict(float); est = fact = 0
        for r in rs.values():
            if month(r) != mm or r.get("status") != "done": continue
            by_s[r["service"]] += r["fact"]; by_p[str(r["by"])] += r["fact"]; est += r["est"]; fact += r["fact"]
        print(f"Расход {mm}: ${fact:.2f} из ${p['monthly_limit_usd']} (прогноз был ${est:.2f})")
        print("по сервисам: " + ", ".join(f"{k} ${v:.2f}" for k, v in by_s.items()))
        print("по людям: " + ", ".join(f"{k} ${v:.2f}" for k, v in by_p.items()))
    elif cmd in ("owner", "limit", "budget"):
        mark = {"owner": "владелец %s", "limit": "лимит %s", "budget": "бюджет %s %s"}[cmd] % tuple(o.x[:2 if cmd == "budget" else 1])
        if p["owners"]:   # первый владелец ставится при установке; дальше — только нажатием владельца
            if not o.card: sys.exit("меняет только владелец нажатием: --card <id карточки> с «%s» в тексте" % mark)
            if card_spent(rs, o.card): sys.exit("эта карточка уже использована")
            by, why = tap(o.card, mark)
            if not by: sys.exit("не изменено: " + why)
            if by not in map(str, p["owners"]): sys.exit("меняет только владелец (нажал %s)" % by)
            p["cards"] = (p.get("cards") or []) + [o.card]
        if cmd == "owner": p["owners"] = sorted(set(map(str, p["owners"])) | {o.x[0]})
        elif cmd == "limit": p["monthly_limit_usd"] = float(o.x[0])
        else: p["budgets"][o.x[0]] = float(o.x[1])
        save_pol(p); print(json.dumps(p, ensure_ascii=False))
    else: sys.exit(__doc__)

if __name__ == "__main__": main()
