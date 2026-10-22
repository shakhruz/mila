---
name: alisa-connect
description: "Use on «/alisa», connecting a Yandex Alice speaker, and for the hourly voice summary: 6-digit code, voice summary, speaker requests to Telegram. RU: «/alisa», «подключи Алису», «колонка», сводка для голоса."
---
> **When to use (full):** Your Mila in a Yandex Alice speaker: on «/alisa» give the owner a 6-digit code and what to say to the speaker; every hour upload a short voice summary («what's up today»); requests said to the speaker arrive in my channel — answer the owner in Telegram. Use on «/alisa», «подключи Алису», «колонка», and for the hourly summary. RU: Своя Мила в колонке Алиса: на «/alisa» — код из 6 цифр и что сказать колонке; раз в час — короткая сводка для голоса; просьбы, сказанные колонке, приходят мне в канал — отвечаю хозяину в Telegram.

# Alice speaker — connect and serve

Owner's word 17.10.2026: «the Alice skill is a service for every Mila». The skill «Моя Мила» in Yandex Alice is one for all;
which Mila answers is decided by a one-time code.

## /alisa — connect
1. `python3 ~/.claude/skills/alisa-connect/alisa.py code` → `{"code": "123456", "ttl_min": 5}`.
2. One message to the owner (plain-words card, no internals):
   «Скажите колонке: «Алиса, запусти навык Моя Мила», потом: «подключи мою Милу» — и назовите код **123 456**. Код живёт 5 минут.»
   Phone and speaker are different listeners — each one is connected with its own code.
3. Exit code 2 (no key) → «Подключу через администратора» and a request to the fleet admin; never invent a code.

## Hourly voice summary
Every hour (cron) — ≤300 characters, spoken style, no links or markdown: what happened today, who wrote, what waits for the owner's decision.
`alisa.py summary --text "…"`. Facts only from my files (NOW, inbox, tasks) — nothing for the summary is invented. Nothing private of other people (names of clients only if the owner already knows them from me today).

## Requests from the speaker
They arrive in my channel as «[голос · Алиса · …] Хозяин сказал колонке: «…»» with his private chat. I answer him there:
- a request or question → the answer in Telegram, short;
- «write to chat X» → a draft with the button «Отправить»; nothing goes out without his «да»;
- a task for another Mila → a note to her, the result to the owner.
The speaker already told him «ответ придёт в Телеграм» — so the answer must come.

## Done if
- `/alisa` → the owner got a code and one line of what to say, within a minute.
- The summary file is fresh (≤ 1 hour).
- Every speaker request has an answer in the owner's private chat.
