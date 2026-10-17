#!/usr/bin/env python3
"""Расход — учёт платных генераций Милы (OpenRouter, fal.ai, HeyGen, ElevenLabs и др.).
Перед генерацией дороже порога (threshold_usd) — прогноз и детали, кнопки «одобрить / отменить»;
после — результат и фактический расход. Мила осознанно тратит деньги владельца и помогает планировать.

Папка $RASHOD_HOME (по умолчанию ~/work/rashod):
  policy.json  — {"owners":[id], "threshold_usd":0.5, "monthly_limit_usd":20, "budgets":{"<user_id>":5}}
                 budgets — сколько в месяц владелец разрешил тратить человеку без своего «да» (решение «А/Б» владельца)
  ledger.jsonl — строка на план: id, сервис, что, прогноз, кто просил, кто одобрил, факт, статус

  spend.py plan --service fal --what "видео 10 с" --est 0.8 --by <user_id>  → id + решение: auto | card
  spend.py approve <id> --by <user_id> --msg <chat>/<msg>   (owner — всегда; автор — в пределах своего бюджета)
  spend.py reject <id> --by <user_id>
  spend.py check <id>        — можно ли тратить (код 0 — да)
  spend.py done <id> --fact 0.74 [--note "…"]
  spend.py report [--month 2026-10]  — потрачено, по сервисам, по людям, прогноз против факта, остаток
  spend.py owner <id> --by <owner> · limit <usd> --by <owner> · budget <user_id> <usd> --by <owner>
"""
import argparse, datetime as dt, json, os, sys, uuid
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
    for f in ("--service", "--what", "--est", "--by", "--msg", "--fact", "--note", "--month"): ap.add_argument(f)
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
        r = rs[o.x[0]]; by = str(o.by); owner = by in map(str, p["owners"])
        if cmd == "approve":
            budget = float(p["budgets"].get(by, 0)); mine = spent(rs, m, by)
            if not owner and not (by == str(r["by"]) and mine + r["est"] <= budget):
                sys.exit(f"не может одобрить: не владелец и бюджет {by} ${budget} (потрачено ${mine:.2f})")
            put({"id": r["id"], "status": "approved", "approved_by": by, "msg": o.msg, "approved_ts": NOW()})
        else: put({"id": r["id"], "status": "rejected", "by_reject": by})
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
        if p["owners"] and str(o.by) not in map(str, p["owners"]): sys.exit("меняет только владелец")
        if cmd == "owner": p["owners"] = sorted(set(map(str, p["owners"])) | {o.x[0]})
        elif cmd == "limit": p["monthly_limit_usd"] = float(o.x[0])
        else: p["budgets"][o.x[0]] = float(o.x[1])
        save_pol(p); print(json.dumps(p, ensure_ascii=False))
    else: sys.exit(__doc__)

if __name__ == "__main__": main()
