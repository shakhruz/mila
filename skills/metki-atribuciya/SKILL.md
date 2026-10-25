---
name: metki-atribuciya
description: "Use when launching any ad, post with a link or partner link: \"make a tag\", \"where did leads come from\", \"/metka\" — one key per ad (ad_<channel>_<topic>_<N>), carried from click to payment. RU: метка на каждое объявление, сквозной счёт до оплаты, «откуда заявки»."
metadata: {"nanobot":{"emoji":"🏷"}}
---
> **When to use (full):** Before an ad, a post with a link, a partner link or a QR goes out — and when the owner asks «откуда заявки» or «какое объявление окупилось». One key per ad, the same key in the bot start, on the site and in the payment record. RU: Метка на каждое объявление, сквозной счёт до оплаты.

# 🏷 Метки и сквозной счёт

## Зачем
Хопкинс (Scientific Advertising, 1923, гл. 1): принципы рекламы проверяются «through keyed advertising, by traced returns» — каждое объявление с ключом, и «Never be guided in any way by ads which are untraced». Метка — наш ключ: без неё объявление нельзя ни сравнить, ни выключить по делу.

## Формат метки
`ad_<канал>_<тема>_<N>` — латиница, цифры, `_`, до 64 знаков (так требует Telegram для `?start=`: https://core.telegram.org/bots/features#deep-linking).
- **канал** — где показано: `tgads`, `meta`, `ig`, `post`, `blogger`, `site`, `qr`…
- **тема** — одна мысль объявления латиницей: `otvet3min`, `turstambul`.
- **N** — номер варианта; в A/B у вариантов один канал и тема, разный N.
- Партнёр — своя метка `p_<партнёр>` (не смешиваем с рекламой).

Собрать и проверить: `python3 scripts/metka.py --channel tgads --topic otvet3min --n 2 --bot mila_gpt_bot [--site https://milagpt.io/x]`.

## Куда ставится
- **Telegram-бот:** ссылка `https://t.me/<бот>?start=<метка>` — бот записывает метку при первом старте.
- **Сайт:** `utm_source=<канал>&utm_medium=<тип: cpc, post, partner>&utm_campaign=<тема>&utm_content=<метка>` — три первых обязательны (Google Analytics: https://support.google.com/analytics/answer/10917952). Внутренние ссылки сайта метками не размечаем — это сбивает счёт.
- **Оплата:** метка гостя переносится в счёт и в запись оплаты (касса) — иначе цепочка рвётся на самом важном шаге.

## Сквозной счёт (по метке)
показ → клик → старт или заявка → ответ → консультация → оплата. Цифры показов и кликов — из кабинета площадки, остальное — из журналов Милы по метке. Пишу только посчитанное; шага без данных — «нет данных», не оценка.

## Правила
- Одна метка — одно объявление. Новый текст = новый N.
- Метки не переиспользуем для другого смысла; старую — в архив, не переименовываем.
- Таблица меток — у Милы, которая ведёт рекламу: метка · канал · текст · дата запуска · бюджет.

Пример на живом задании — `example.md`.
