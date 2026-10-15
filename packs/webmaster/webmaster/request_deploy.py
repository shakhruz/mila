#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Заявка на выкладку партии — кладёт JSON в свой work/outbox/deploy/.
Дальше заявку читает хост-служба webmaster-deploy (см. SKILL.md раздел 7).
Компаньон НЕ вызывает wrangler сам — токена с правом Pages у него нет и не
должно быть.

Использование:
  python3 request_deploy.py --client acme --kind prod --head 93dcc88 \
      --what "Мальдивы/Хайнань" \
      --yes-who "Анна" --yes- \
      [--excluded-reviewed] [--note "текст для журнала"]

  python3 request_deploy.py --client acme --kind preview --head 93dcc88 \
      --what "черновик страницы услуг"

kind=prod требует --yes-who и (--yes-msg или --yes-quote) — без этого заявка
не пишется (проверка тут же, на месте, а не только на хосте).
"""
import argparse
import json
import os
import sys
import time
import pathlib

HOME = pathlib.Path(os.environ.get("HOME", os.path.expanduser("~")))
OUTBOX = HOME / "work" / "outbox" / "deploy"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True, help="ключ клиента из таблицы хоста, напр. acme")
    ap.add_argument("--kind", required=True, choices=["prod", "preview"])
    ap.add_argument("--head", required=True, help="короткий git-хеш сборки")
    ap.add_argument("--what", required=True, help="что уходит, по-человечески")
    ap.add_argument("--yes-who", default=None, help="кто из клиента сказал «да» (только для prod)")
    ap.add_argument("--yes-msg", default=None, help="id сообщения с «да» в рабочем чате")
    ap.add_argument("--yes-quote", default=None, help="точная цитата «да», если id сообщения нет (голосовое)")
    ap.add_argument("--excluded-reviewed", action="store_true",
                     help="файл из раздела 3 SKILL.md (юр. страница/чужое фото/цена без источника) в этой сборке проверен человеком")
    ap.add_argument("--reviewer", default=None, help="кто проверил исключённый файл, если --excluded-reviewed")
    ap.add_argument("--note", default="", help="свободная строка в журнал")
    args = ap.parse_args()

    if args.kind == "prod":
        if not args.yes_who or not (args.yes_msg or args.yes_quote):
            print("СТОП: для kind=prod нужны --yes-who и (--yes-msg или --yes-quote) — "
                  "прод только по явному «да» клиента на эту партию (SKILL.md раздел 1).",
                  file=sys.stderr)
            return 1
    if args.excluded_reviewed and not args.reviewer:
        print("СТОП: --excluded-reviewed без --reviewer — кто проверил, должно быть названо.",
              file=sys.stderr)
        return 1

    OUTBOX.mkdir(parents=True, exist_ok=True)
    ts_id = time.strftime("%Y%m%d-%H%M", time.localtime())
    req_id = f"{ts_id}-{args.client}-{args.kind}"
    path = OUTBOX / f"{req_id}.json"
    if path.exists():
        req_id = f"{req_id}-{int(time.time())}"
        path = OUTBOX / f"{req_id}.json"

    data = {
        "id": req_id,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "client_key": args.client,
        "kind": args.kind,
        "head": args.head,
        "what": args.what,
        "note": args.note,
        "excluded_files_reviewed": bool(args.excluded_reviewed),
        "reviewer": args.reviewer,
        "status": "open",
    }
    if args.kind == "prod":
        data["client_yes"] = {
            "who": args.yes_who,
            "msg_id": args.yes_msg,
            "quote": args.yes_quote,
        }

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"заявка записана: {path}")
    print("результат появится рядом файлом "
          f"{req_id}.result.json — хост-служба webmaster-deploy читает outbox по расписанию.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
