---
name: pult-dnya
description: "Use on every new task from the owner, when starting, waiting on someone or closing a task, and in the morning, day and evening rhythm: one pinned day board. RU: «пульт дня», новое поручение, что в работе, кто кого ждёт."
---

# Day board

One truth about my day, in one pinned message for the owner. Everything I take, wait for and close goes through the board, so the owner never has to ask "where is it?" and never waits for me while I wait for him.

Script: `python3 ~/.claude/skills/pult-dnya/scripts/day_board.py <command>`. The day file is `~/work/state/day-<date>.json`. Unfinished items carry over to the next day with the same number.

## Five rules

1. **A new task from the owner gets a line at once:**
   `add --text "…" --who owner --why "…"` → «#N queued, after #X, because …». I send that line to the owner in the same minute. I do not drop what I am doing, unless the new task is 🔴 (`--red`): then it goes straight into progress.
2. **"Waiting for you" exists only as a question asked in the same minute.** It is a message with buttons (A/B and my recommendation, checked with plain-words). Only then `wait N --on owner --asked <message link or id>`. Without `--asked` the script refuses: a passive "waiting" line in a report is not a question. *Lesson 22.10: "Mila waits for me, and I wait for her" — that is how a day is lost.*
3. **At most two things in progress.** `start N` refuses a third. 🔴 always gets in.
4. **Rhythm:**
   - Morning: `plan --pool "a; b; c"` — the day's plan plus an auto-pool of 3–5 of my own tasks, so the queue is never empty.
   - Day: after each change, `render` → `edit_message` of the pinned board. The board is edited, not reposted. `pin --chat C --message M` remembers which message is pinned.
   - **Buttons on the board** (senior's draft 29.10): one button per «waiting for you» item, at most 6, rows of 1–3, the last one «❓ Ask me the rest» when there are more. `edit_message` changes the text but not the buttons: when the set of waiting items changes, send a new board with `reply` + buttons and `pin` it; the old one stops being the pinned board. Button format — only `{label, choice|url, style}` (skill `milagpt-chat`); Bot API `{text, callback_data}` does not work.
   - `/status` in Telegram (mila-telegram plugin) shows this board to the owner on demand: `render` returns `empty` (no plan today → «Make today's plan» button) and `waiting` (items waiting on the owner — `--on owner`/`хозяин` or a name from `MILA_OWNER_NAME` → «#N — answer» buttons). `render` never changes the day file.
   - Evening: `evening` → results with conclusions, what carries over, who waits for whom.
5. **Closing needs evidence:** `done N --evidence <link, file, tool answer> --result "<conclusion in one line>"`. No evidence — not done. `drop N --why …` removes a task with a reason.

## What the owner sees

```
📋 Day board · 22.10
▶️ In progress
#7 Discord bridge · owner
⏳ Queue
#8 Day board skill · admin · after #7
🤝 Waiting for an answer
#5 Wallet for Discord · waiting: owner · asked: dev 2090
✅ Done
#3 macOS tests → rollback fixed · b29e066
```

## Don'ts

- Don't write "waiting for you" anywhere except as a question with buttons.
- Don't start a third task: close one or put it to wait with a question.
- Don't post the board as a new message every time: edit the pinned one; a new message only for the morning plan, the evening result and a changed set of «waiting» buttons.
- Name the task, not the person: not «call Ivan», but «a call to client X», and only if the chat is internal. The script masks cards (****1234), phones and e-mails anyway, on input and on output.
- A wait older than an hour turns 🔴 on the board: ask again or decide myself. `--asked` takes only a t.me/c/… link or a message number.
