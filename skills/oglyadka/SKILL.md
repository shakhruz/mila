---
name: oglyadka
description: "Use after a stream of 5+ assignments, at midday and in the evening before quiet hours, and before saying «everything is closed»: reread the day's dialogs (not memory), match every assignment and promise against tasks and proof, find what was lost and move it. RU: оглядка — «что я упустила?», перечитать диалоги, найти забытое."
---
> **When to use (full):** Look-back (owner's word 28.10): Mila remembers what she might have forgotten — rereads the day's dialogs, checks every assignment and promise against her tasks and proof, finds what was lost and moves it, like a person who sits down and thinks «so, what did I miss?». Morning, after a stream of assignments, evening before quiet hours. RU: Оглядка — Мила сама вспоминает, что могла забыть: перечитывает диалоги дня, сверяет каждое поручение и обещание с задачами и уликой, находит потерянное и двигает. Утром, днём после потока поручений, вечером до тихих часов.

# Оглядка
«Как человек вспоминает: сиди, так, чего я забыла? Возвращаешься к диалогам, перепроверяешь себя — что могла упустить».

## Когда
- после потока из 5+ поручений подряд;
- в полдень и вечером до тихих часов;
- перед «у меня всё закрыто».

## Шаги
1. **Перечитать, а не вспоминать.** Источник — журнал разговоров и задач, не моя память:
   - `python3 ~/.claude/skills/oglyadka/oglyadka.py --hours 12` — поручения хозяина за окно, у которых нет задачи;
   - `task.py scan-sent --hours 12` (навык `mila-tasks`) — мои обещания в отправленном, у которых нет карточки.
2. **Каждое поручение и обещание** («сделай», «запомни», «напомни», мои «беру», «напишу», «проверю») сверить:
   нет задачи → завести сейчас; нет улики «сделано» → это хвост; сделала, но человеку не сказала → сказать.
3. **Чужие ответы:** кто мне ответил, а я не прочла — записки других Мил, кнопки хозяина, ответы клиентов.
4. **Мои слова, которые могли быть неправдой:** цифра без источника, «сделала» до результата → перепроверить инструментом
   и поправить первой.
5. **Итог:** найденное — сразу в работу по навыку `zhonglyor`. Хозяину — одна строка, только если нашла его дело:
   «Оглянулась: нашла N забытых, M уже двинула, ждёт вас — кнопкой». Ничего не нашла — молчу.

## Нельзя
- «Вроде всё сделано» без перечитывания.
- Закрывать хвост словом, без улики.
