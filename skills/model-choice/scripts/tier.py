#!/usr/bin/env python3
"""Уровень модели по пяти вопросам (воркшоп «выбор модели», 21.10.2026): трудность, цена ошибки, объём, скорость, ценность.
  tier.py [--hard] [--costly] [--rare] [--can-wait] [--valuable] [--in-name] [--irreversible]
     --hard          неясно, рассуждение в несколько шагов (иначе — устойчивый шаблон)
     --costly        ошибка заметно вредит людям или делу (иначе — легко отменить)
     --rare          делается редко (иначе — часто и повторяется)
     --can-wait      можно подождать (иначе — ответ почти мгновенно)
     --valuable      высокая ценность для клиента или дела (иначе — удобство)
     --in-name       от имени человека (письмо, пост, подпись)
     --irreversible  необратимо (деньги, удаление, отправка наружу)
Выход JSON: {tier: light|strong|strong+yes, model, score, why[]}. Правило: от имени человека и необратимое — всегда сильная + его «да»,
что бы ни сказали остальные вопросы. Цена ошибки решает: дорогая ошибка — сильная модель даже на частом шаблоне (доза, цена клиенту, срок визы);
дешёвая ошибка на сильной — переплата, дорогая на лёгкой — ущерб."""
import json, sys

MODEL = {"light": "haiku", "strong": "opus", "strong+yes": "opus"}   # алиасы Claude Code: --model / model: в субагенте


def tier(hard=False, costly=False, rare=False, can_wait=False, valuable=False, in_name=False, irreversible=False):
    why = []
    if in_name or irreversible:
        why.append("от имени человека" if in_name else "необратимо")
        return {"tier": "strong+yes", "model": MODEL["strong+yes"], "score": None,
                "why": why + ["всегда сильная модель и «да» человека на этот текст/шаг"]}
    score = hard + 2 * costly + rare + can_wait + valuable
    for flag, word in ((hard, "трудная"), (costly, "дорогая ошибка"), (rare, "редкая"), (can_wait, "можно подождать"), (valuable, "высокая ценность")):
        if flag:
            why.append(word)
    t = "strong" if costly or score >= 3 else "light"   # дорогая ошибка — всегда сильная, даже на шаблоне (Качество 21.10)
    if t == "light":
        why.append("шаблон, ошибку легко отменить, часто и быстро — лёгкая модель")
    return {"tier": t, "model": MODEL[t], "score": score, "why": why}


if __name__ == "__main__":
    a = set(sys.argv[1:])
    known = {"--hard", "--costly", "--rare", "--can-wait", "--valuable", "--in-name", "--irreversible"}
    if a - known or "-h" in a:
        sys.exit(__doc__)
    print(json.dumps(tier("--hard" in a, "--costly" in a, "--rare" in a, "--can-wait" in a, "--valuable" in a,
                          "--in-name" in a, "--irreversible" in a), ensure_ascii=False))
