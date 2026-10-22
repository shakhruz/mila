---
name: pd-vault
description: "Use when writing memory, cards, journals, reports, notes, exports, and on «what's the number of …»: personal data become labels like ⟦тел·1⟧. RU: телефоны, почта, карты, паспорта, ПИНФЛ; «какой номер у…»."
---
> **When to use (full):** Personal data vault (core layer 2a, on by default): phone numbers, e-mails, card numbers, passports, PINFL in what Mila stores or passes on become short labels like ⟦тел·1⟧; values sit encrypted in the Mila's home. Use when writing memory, cards, journals, reports, notes to other Milas, exports; when the owner asks «what's the number of …» (reveal — only to him, in his DM). RU: Хранилище личных данных (слой 2а ядра, включено по умолчанию): телефоны, почта, карты, паспорта, ПИНФЛ в том, что Мила хранит и передаёт, заменяются ярлыками; значения — зашифрованно в доме Милы. Раскрыть — только хозяину в личку.

# Personal data vault

Owner's word 17.10.2026: «store personal data privately and encrypted; outside — only a short label». On by default.

## What it does by itself
- After every write to memory, journals, chat cards, clients, NOW/USER/CLIENTS/DECISIONS — the `pd-mask` hook replaces personal data in the file with labels (`⟦тел·1⟧`, `⟦почта·2⟧`, `⟦карта·1⟧`, `⟦паспорт·1⟧`, `⟦ПИНФЛ·1⟧`). Same value — same label everywhere.
- Values go to `~/work/state/pd/vault.enc` (AES-256 + HMAC; key `~/.config/mila/pd.key`, 600). Without the key the file is unreadable; a tampered file is refused.

## What I do myself (the hook can't recognise it)
- Addresses, health and diagnoses, family matters, debts — I don't write them into memory as they are: «адрес — у клиента в карточке CRM», «по здоровью — к врачу». If they must be kept — only in the client's card, never in reports, examples, notes to other Milas.
- In notes to other Milas, reports and exams — labels only. Before sending text outside I run `pd_vault.py mask` over it.

## Reveal
`python3 ~/.claude/skills/pd-vault/pd_vault.py reveal ⟦тел·1⟧` → the value. Only when the owner asks, only in his private chat, only the one he asked for. Never to other people, never into groups, never to another Mila.

## Honest limit
The model reads an incoming message whole — otherwise Mila can't answer. The vault protects what Mila keeps and passes on, not the conversation itself. For full privacy of everything — the «Private mode» (encrypted home with the owner's key).

## Check
`pd_vault.py scan <files>` — what kinds of personal data are still in plain text (no values printed); exit 1 if found.

## Done if
- `scan` over memory/, journals and cards finds nothing.
- Reveal happened only in the owner's DM and only on his request.
