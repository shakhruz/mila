---
name: draft-and-check
description: "Use for any text going out in a person's name (email, post, client reply, proposal): light model drafts, strong model checks facts and tone; send only on \"yes\". RU: черновик письма, поста, ответа клиенту — проверка."
---
> **When to use (full):** Light model drafts, strong model checks: for any text that goes out in a person's name (email, post, reply to a client, proposal) — a subagent on a light model writes the draft, I (the strong model) check facts, numbers and tone against the sources, fix, and only the person's "yes" on this exact text sends it. Saves the expensive model for judgement, not typing. RU: Лёгкая пишет — сильная проверяет: текст от имени человека — черновик пишет субагент на лёгкой модели, я сверяю факты, цифры и тон с источниками, правлю, наружу — только по «да» человека на этот текст.

# Light model drafts, strong model checks

## What it gives
- Texts in a person's name cost less: the long typing is done by a light model.
- The risky part — facts, numbers, promises, tone — is checked by the strong model against the sources.
- Nothing goes out without the person's "yes" on this exact text.

## When
A text that goes out in someone's name: an email, a post, a reply to a client, a proposal, a comment.
Not for: a short chat reply (write it yourself), money, signatures or anything irreversible (strong model only, see `model-choice`).

## How
1. **Brief.** Collect what the text must say: facts and numbers with their source (file, message, tool answer), audience, tone, length, a sample if there is one. Missing facts — ask first (`utochnenie-zadach`), do not let the draft guess.
2. **Draft on a light model.** Start a subagent with `model: haiku` (Agent tool, model parameter) and give it only the brief: "Write <kind> for <audience>, tone <…>, length <…>. Use only these facts: <list with sources>. Mark anything you are unsure about with [?]. No new numbers, names, dates or promises."
3. **Check on the strong model (me).** Go through the draft line by line:
   - every number, name, date, price and promise is in the brief's sources — otherwise remove or ask;
   - every [?] is resolved or turned into a question to the person;
   - tone and length match the person and the audience;
   - nothing the person did not agree to (discounts, deadlines, commitments).
   Fix it myself. If more than half had to be rewritten, say so in the journal: the brief was weak.
4. **Show the person the final text** and one line of what I checked ("numbers from the price list of 20.10, the date from your message"). Buttons: [✅ Send] [✏️ Edit] [✖️ Don't send].
5. **Send only after "✅ Send" on this text.** Yesterday's "yes", a reaction or "ok" on a different version does not count. Record the "yes" in the consent journal.
6. **Journal line:** task, draft model, check model, what was fixed (facts / tone / nothing), outcome (sent / edited / not sent). This feeds the weekly cost-per-task report.

## What I don't do
- I don't send the light model's draft unchecked, even if it looks fine.
- I don't give the subagent private data it does not need for the text.
- I don't let the draft add facts: a fact without a source is removed, not kept.
