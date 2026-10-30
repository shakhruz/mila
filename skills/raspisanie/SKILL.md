---
name: raspisanie
description: "Use instead of CronCreate whenever a job must run on schedule (daily check, reminder, weekly report): mila-cron writes it to the Mila's home so it survives a session restart. RU: «напоминай каждый день», «по понедельникам», «через неделю проверь», расписание, кроны."
---
> **When to use (full):** Schedule that does not get lost. A job set with CronCreate lives inside the Claude Code session and dies on restart, on image rollout and by itself after 7 days. mila-cron writes the job to ~/work/schedule/jobs.json in the Mila's home; the «Барабан» service outside the session reads it once a minute and puts the due job into the plugin journal as an event — the same road rituals and flywheel ticks take, so it reaches the session after any restart. RU: Расписание, которое не теряется: вместо CronCreate — mila-cron, задача в доме Милы, срок приходит событием службы «Барабан».

# Расписание — mila-cron (не CronCreate)

```bash
M=~/.claude/skills/raspisanie/mila_cron.py
python3 $M next "0 9 * * 1" 3                      # сначала проверить выражение: ближайшие сроки
python3 $M add otchet-pn "0 9 * * 1" "Понедельник: недельный отчёт владельцу"
python3 $M add vecher "30 19 * * *" "Вечерняя проверка" --by owner --word <чат>/<сообщение>
python3 $M list                                      # следующий срок, последний запуск, итог
python3 $M done otchet-pn "отправлен, 5 строк"       # итог последнего запуска
python3 $M pause|resume|rm <id> · extend <id> ГГГГ-ММ-ДД
python3 $M import ~/work/state/crons.md              # перенести кроны из снимка сессии
```

## Правила
1. **Не CronCreate.** Любое «каждый день / по понедельникам / через неделю» — `mila-cron add`. CronCreate умирает с сессией.
2. **Сначала `next`** — увидеть сроки глазами, потом `add`. Пояс — из USER.md хозяина.
3. **Не чаще раза в 5 минут**, задач не больше 30, текст до 2000 знаков.
4. **Срок жизни** — 30 дней по умолчанию, максимум 90, у всех; истекла — придёт одно событие «продлить?» (`extend`). Задач «без срока» нет: вечная задача тратит подписку молча.
5. **Чья задача**: своя — `by mila`; с согласия владельца или администратору — `--by owner|senior --word <чат>/<сообщение>`.
6. **Пришло событие `[⏰ расписание] <id>`** — сделать дело и записать итог `done <id> "…"`. Тихие часы хозяина служба уважает сама (срок переносится на утро).

Файл задач — только этим инструментом (атомарная запись под замком). Состояние запусков ведёт служба «Барабан» вне дома.
