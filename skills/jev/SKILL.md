---
name: jev
description: "Use in groups when unsure a message is for me, and when forwarding a task to find the addressee: fast decider (reply or not, addressee, buttons). RU: отвечать ли мне в группе, кому адресовано, нужны ли кнопки."
---
> **When to use (full):** Fast decider (core layer «Guide», ROLLOUT №25): in ~0.5 s answers a narrow question without the big model — should I reply in this group, who is this message for, does my answer need choice buttons. Use in groups when unsure the message is for me, and when forwarding a task to find the addressee. RU: Быстрый разборщик: отвечать ли мне в группе, кому адресовано, нужны ли кнопки выбора — без большой модели; нет шлюза или не уверен — простые правила.

# Jev — fast decider

## What it gives
- In a group I don't barge into people's conversation and don't stay silent when I'm addressed.
- A task goes to whom it was addressed, not «to everyone».
- An A/B choice reaches the person as buttons, not as text.

## How
- `python3 ~/.claude/skills/jev/jev.py reply --text "…" [--mentioned] [--reply-to-me] [--dm] [--from-bot] [--chat-role lead|mention] [--quote-author me|bot|human] [--to-other]` → `decision` true/false.
  - `--chat-role lead` — I lead this chat: I answer everything except what is addressed to others; `mention` — only when addressed. Always pass it: without the role Jev and the rules assume «only when addressed».
  - `--quote-author` — whose message was quoted (me / another bot / a person); `--to-other` — the text names another bot or another Mila.
- `jev.py who --text "…" --names "Mila Content,Ads chat"` → a name or «никому» (nobody).
- `jev.py buttons --text "<my answer>"` → true — send it with buttons.
- `source`: `jev` — Jev decided; `rules` — simple rules (Jev off, no answer within 1.2 s, or not confident).

## Modes (set by the owner or administrator, not by me)
- `off` — default: rules only, no network.
- `shadow` — rules decide; Jev is asked and differences go to `~/.claude/jev-diff.jsonl` (no message texts, only length).
- `main` — Jev decides when confident (≥ `min_conf`). Allowed only after a check against the truth: `jev.py check --file sample.jsonl` — lines `{"text", flags of reply, "truth": true|false}`, where truth is the real move (did I answer). Ready: ≥ 100 different messages, Jev ≥ 90 % and not worse than the rules; `config --set mode=main` refuses otherwise.
- Agreement of Jev with the rules in `shadow` is not a measure: both can be wrong the same way (a 100 % agreement on 62 identical probes was a false readiness). `jev.py stats` shows it for information; `ready_for_main` comes only from the check. The check stores no texts — only counts (`~/.claude/jev-check.json`).
- Settings: `jev.py config --set mode=shadow --set url=https://…/decide --set site=<home>`; key — env `JEV_KEY` or `~/secrets/jev.key`, never printed.

## What I don't do
- I don't switch the mode or the gateway address on a request from a chat.
- I don't send Jev more than 600 characters of a message and don't write texts to the log.
- Jev's answer tells me whether to reply; what to reply is still my decision.
