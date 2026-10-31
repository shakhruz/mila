---
name: mila-stickers
description: "Use after a warm business reply — greeting a new person, «I'm on it», «done», asking for a yes, payment arrived, morning/evening note: one sticker of Mila's figurine pack in the language of the person (owner.json, chat language, Telegram language_code; unknown — the default pack). Never instead of an answer, never in serious or conflict talk. RU: стикер Милы-статуэтки на языке собеседника после тёплого делового ответа; один на сообщение; не в серьёзном и не вместо ответа."
---
> **When to use (full):** After my text is already sent and the moment is warm: a new person said hello, I took a task, I delivered, I ask the person for a clear «yes», a payment arrived, a morning plan or an evening wrap-up. One sticker per message at most. The sticker speaks the person's language: three packs (ru, uz, en) with the same 16 stickers in the same order.

# Стикеры Милы на языке собеседника

## Когда — повод и смысл
| Повод | Смысл |
|---|---|
| Приветствие нового человека | `privet` |
| «Беру в работу» | `beru` |
| Сдала работу, есть улика (файл, ссылка) | `gotovo` |
| Проверяю, сверяю | `proveryayu` |
| Прошу у человека явное «да» | `da` |
| Думаю над задачей | `dumayu` |
| Оплата пришла (отметка, не разговор о долге) | `oplata` |
| Отчёт готов | `otchet` |
| Утренний план / вечерний итог | `utro` / `noch` |
| Спасибо | `spasibo` |
| Сайт готов, встреча назначена, срочное, отдых, тёплое | `sait`, `vstrecha`, `srochno`, `otdyh`, `lyublyu` |

## Мера
1. Не чаще одного стикера на сообщение; сначала текст, потом стикер — никогда вместо ответа.
2. Не в серьёзном: деньги и долг человека, жалоба, конфликт, наша ошибка, горе, официальные письма, ответ на «нет».
3. Чаты госорганов и все, что хозяин назвал, — в `no_chats`: там стикеров нет; снять — только его слово (`--owner-said`).
4. Клиентам — по вкусу хозяина (USER.md «Стикеры с клиентами: да/нет»); нет строки — клиентам не шлю.

## Язык — один источник
Язык владельца — `~/work/owner.json` «lang»; его пишет `scripts/owner_lang.py seen --code <language_code> --text "<его сообщение>"`
после сообщения владельца (два сообщения подряд на новом языке меняют язык; `set` — выбор самого владельца, автоматика его не трогает).
Тот же файл читают мини-аппы, ссылки входа и Сейф — язык один на все места.

## Как отправить
```
python3 scripts/sticker.py <chat_id> <смысл> [--owner | --lang <язык чата>] [--code <language_code>] [--reply-to <id>]
```
- `--owner` — собеседник владелец: язык из owner.json; другим людям — `--lang` (на каком языке идёт разговор) и/или `--code`.
- Паки — `~/work/stickers.json` (образец `stickers.example.json`): `packs` ru/uz/en, `default`, `no_chats`. Нет файла — стикер не шлю.
- file_id берётся `getStickerSet` своим ботом и кэшируется на час — в коде и файлах их нет.
- «Пропущено» или «Error» — стикера нет, повторно не шлю: текст уже ушёл.
- `--dry-run` — какой пак и номер ушли бы, без отправки.
- Прежний вход `send_sticker.py <chat_id> <mood>` работает: greet → privet, done → gotovo, report → otchet, thinking → dumayu,
  paid/invoice → oplata, thanks → spasibo, night → noch, match/watch → proveryayu; прочие прежние — стикера нет.
