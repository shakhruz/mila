#!/bin/bash
# Сейф Милы: одноразовая ссылка для владельца бизнеса. vault-link.sh <slug> <ПОЛЕ>[,<ПОЛЕ>…] [--name имя] [--to tg_id] [--ttl 30]
# пример: vault-link.sh acme SITE_LOGIN,SITE_PASSWORD,CARD_NUMBER,CARD_EXPIRY --name acme --to 123456
exec python3 "$(dirname "$(readlink -f "$0")")/seif.py" link "$@"
