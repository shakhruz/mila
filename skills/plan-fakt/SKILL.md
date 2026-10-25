---
name: plan-fakt
description: "Use on Friday evening (or the owner's report day) for the week's plan-vs-fact: one Telegram slideshow post (square slides + sectioned text), pinned, with «❓ Questions» and «✅ Got it» buttons. RU: план-факт недели, пятничный отчёт владельцу, итог недели каруселью."
---

# Weekly plan-vs-fact — one slideshow post

Part of the week rhythm (canon/WEEK-RHYTHM.md): Monday — plan, Friday — plan-vs-fact. The owner gets one post he can swipe through, not a wall of text.

## 1. Facts — only from your files
`python3 ~/.claude/skills/plan-fakt/scripts/collect.py > ~/work/tmp/plan-fakt.json` drafts the week from:
- `~/work/WEEK.md` — the week plan (checkbox lines and 🟢🟡🔴⚪ lines);
- `~/work/state/day-<date>.json` Mon–Fri — the day boards: done with evidence, waiting, carried;
- `~/work/MONEY.md` — **only if you keep money**; no file → no money slide and no money tiles.
Missing source → «нет данных», never a guess. Every number needs evidence you can open.

## 2. Slides
Rewrite the draft in your words (cover: the week's conclusion in one phrase), keep 3–5 rows per slide, a row ≤ 60 characters. Slides: plan · done · waiting for your word (+ money if any). Then
`python3 ~/.claude/skills/plan-fakt/scripts/make_slides.py ~/work/tmp/plan-fakt.json ~/work/tmp/plan-fakt/` → s1…sN.jpg (1080×1080). Open every slide and look at it before sending. Chromium: found automatically; set `CHROME_BIN` if not.

## 3. Send — one slideshow post
- mila-telegram with slideshow support: `reply` with `slideshow: true`, `files` = the slides, `text` = the post HTML.
- otherwise: `python3 ~/.claude/skills/plan-fakt/scripts/send_slideshow.py <owner chat> post.html s1.jpg …`.
Post HTML from `post-template.html`: title · «Главное» · 📋 plan · 💰 money (only with MONEY.md) · ⏳ waiting for your word; an empty paragraph between sections; details (clients, team, lessons) inside `<details>`.
Then a reply to the post with buttons «❓ Дай вопросы (N)» and «✅ Принял», and pin the post.

## 4. After
Add «План-факт недели N» to WEEK.md (what was done, what was not and why). Monday's plan starts from it.

## Never
- 4:5 or portrait slides — the slideshow crops them. Square only.
- Several separate photos instead of one slideshow post.
- Sections without empty lines; one «more» blob.
- Numbers without evidence; another company's numbers in your template.
