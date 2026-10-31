# Consent proxy · Согласие без терминала

**EN.** An outside action (publishing through Zernio, uploading to someone's Drive, sending mail) runs only after the owner said
«yes» in Telegram to that exact action. Cloud Milas have no terminal, so the usual «yes» in Claude Code is out of reach.
A hook alone is not enough: if the session holds the service key, it can repeat the call with curl. So the keys live only with
this proxy, run as a separate OS user (`mila-io`); the session asks, the proxy draws the card, and executes only with a fresh,
single-use consent for the hash of the exact payload.

**RU.** Внешнее действие (публикация через Zernio, загрузка в чужой Drive, письмо) выполняется только после «да» владельца в
Telegram на ЭТО действие. У облачных Мил терминала нет. Одного хука мало: если ключ сервиса у сессии, она повторит вызов curl'ом.
Поэтому ключи — только у прокси под отдельным пользователем `mila-io`; сессия просит, прокси рисует карточку и исполняет только
при свежем одноразовом согласии на hash именно этого payload.

## Flow · Как идёт
1. `consent_client.py publish_zernio < payload.json` → `asked`: the owner gets a card (targets in full, text length, head and tail,
   time, attachments with size; invisible and bidi characters stripped). / владельцу ушла карточка.
2. The owner taps «Да, это» → the Telegram receiver (as `mila-io`) forwards `consent:<id>.<sig>.y` to the io socket → `granted`.
3. The session sends the SAME payload again → `done`. A changed text or a replaced attachment is another hash → a new card.
   Consent lives 15 minutes and is used once. «Нет» → declined. / Согласие живёт 15 минут и тратится один раз.

## Boundaries · Границы
- Only the owner, only in a private chat, only a button the proxy signed (HMAC, key 600 at `mila-io`); the session cannot draw it.
- Attachments: only files inside the Mila's home — no symlink on the path, regular file, size limit; the executor gets checked copies.
- Fail closed: no proxy, no answer, garbage — denied; nothing is published.
- Categories (`publish_zernio`, …) are switched by the owner only (io socket), every switch is journalled.
- Journal `consents.jsonl`: asked · granted · declined · used · executed · denied · category — no post text.

## Install (server) · Установка
User `mila-io` owns `state_dir`, the io socket (600), the service keys (`ZERNIO_API_KEY`) and runs the Telegram receiver;
the session user is in the group of the session socket (660). `~/.claude/settings.json` and hooks are root-owned and managed
(`allowManagedHooksOnly`) so the session cannot switch them off. Config: `consent.example.json`.
Receiver side (mila-telegram plugin, separate change): forward `callback_data` starting with `consent:` to the io socket;
refuse `reply` buttons whose `choice` starts with `consent:`.
