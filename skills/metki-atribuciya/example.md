# Пример: два варианта объявления MILAGPT и сайт
`metka.py --channel tgads --topic otvet3min --n 1 --bot mila_gpt_bot` → ad_tgads_otvet3min_1, https://t.me/mila_gpt_bot?start=ad_tgads_otvet3min_1
`metka.py --channel tgads --topic otvet3min --n 2 --bot mila_gpt_bot` → ad_tgads_otvet3min_2 (второй вариант теста)
`metka.py --channel post --topic katalog --n 1 --site https://milagpt.io/sily --medium post` → …?utm_source=post&utm_medium=post&utm_campaign=katalog&utm_content=ad_post_katalog_1

Таблица меток (ведёт Мила рекламы):
| метка | канал | текст | запуск | бюджет |
|---|---|---|---|---|
| ad_tgads_otvet3min_1 | Telegram Ads | «Мила отвечает клиентам за 3 минуты…» | дата | $ |

Сквозной счёт через 7 дней — по метке: показы и клики из кабинета Telegram Ads; старты, ответы, консультации, оплаты — из журналов бота по метке. Шаг без данных — «нет данных».
Живое задание (канал клиента) — свои метки ad_<канал>_<тема>_<N> на каждый из 3 текстов.
