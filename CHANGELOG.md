# CHANGELOG · Mila Companion

## v1.4.0-rc3 · code improvements (candidate)
- `tests/run_all.sh`: every test in the repo + frontmatter in one command (11, ~9 s), exit code 1 on any failure; in release.sh and CONTRIBUTING.
- `install.sh` registers `reply-required.py` as a Stop hook (promised by README/REFERENCE, was manual); `--dry-run` lists every hook; owner's own hooks and settings kept, backup made, re-run does not duplicate.
- `mila` on Linux: daemons via `systemctl --user` (units from deploy/bootstrap.sh), macOS keeps launchctl; per-OS hints.
- `docs/exam-example/`: example guest prompt + exam yaml + README for `tools/express_exam.mjs`; fix: planted failures with ids like `s01` were not matched.

## v1.4.0-rc2 · bilingual skill descriptions (candidate)
- 46 skills: `description` = English first (what + when + English triggers), then `RU:` with the original Russian — English-speaking owners' models find the skills, Russian triggers keep working. `mila-session` was already English.

## v1.4.0-rc1 · international names (candidate)
Skills get English names; old names keep working until v1.6.0. Owner 17.10 (33645).

**For the owner**
- Skills now have international names (cards, plain-words, onboarding…) — your Mila finds and updates them the same way.
- Nothing you changed is lost: if you edited a renamed skill, your version is kept next to the new one.
- Old commands and paths keep working for two more versions.

**For Milas**
- Renamed: ekzamen→exam · kartochki→cards · lichka-hozyaina→owner-dm · mila-v-chate→mila-in-chat · naglyadno→visual · proverka→verify · put-gostya→guest-path · rashod→spend · topiki→topics · vhodyashchie→inbox · vkusy→tastes · voprosy→questions · yasno→plain-words · zadachi→tasks · znakomstvo→onboarding; canon/OBDUMYVANIE→THINKING-BUDGET; docs/uchet→docs/accounting. Scripts: cards.py, plain_words_check.py, spend.py.
- Old names are aliases: `MOVED.md` + script wrappers (old paths exec the new scripts), no SKILL.md — not loaded as skills, no duplicates.
- `mila-update`: `renamed` in release.json — the old folder becomes the alias even if the owner edited it; the edit is saved to `mila-update/new/<tag>/было-<old>` and reported (`pereimenovano`, `pravka_starogo_imeni`). Test `test_renamed.sh` 10/10, in release.sh.
- Data paths are not renamed (`~/work/rashod`, `.kartochki-shown.json`, `memory/vkusy.md`, `work/topiki/`) — owners keep their history.

## v1.3.0 · lessons of Mila Tashkent, 17.10
What a working sales Mila learned in one day (exam "Guest path" 15/15), now in the core for every Mila.

**For the owner**
- Your Mila answers guests in their language and offers a trial no later than her third answer.
- In your private chat: your question first, attachments opened, one summary instead of three, no technical noise.
- Exams in minutes: after every change your Mila's sales script is checked in under a minute, the live check runs at night.

**For Milas**
- `put-gostya` (new): the guest path — guest's language (ru/uz/en, no forced translation), benefit + trial offer by the 3rd answer, invoice as a card ("choose a way on the card; transfer — screenshot here"; Stars/USDT for foreigners), soft no + legal path for illegal requests, "what to send" — one-line example, follow the link label's path.
- `lichka-hozyaina` (new): seven rules for the owner's DM — owner's question before the feed, open attachments, no "Send?" without a draft, don't relay reactions, no file paths or internals, 2–3 buttons, one summary.
- `ekzamen` (new) + `tools/express_exam.mjs`: one yaml for the express run (subscription, minutes, --repeat, planted failures, prompt sha) and the nightly live run; full guest reset before each scenario.
- `canon/OBDUMYVANIE.md`: reasoning models need max_tokens headroom (empty answers at 220 tokens).
- `vkusy` (new, since v1.2.0 on main): the owner's tastes — remember, ask once, three picks with "why you"; a voice speaker of a connected owner hands requests to his Mila.
- README.ru: same positioning as the English README.
- Links: client-chat and lead-qualify → put-gostya; communication → lichka-hozyaina.

## v1.2.0 · Mila Companion 1.0 — first public release
An open-source digital employee for your business, living in Telegram. The README now says what Mila is and how she compares with universal agents.

**For the owner**
- Before saying "done", your Mila checks the result against its "done if" and shows the proof.
- A newborn Mila starts from what you already told at the consultation, not from a questionnaire.
- The same remark three times becomes a rule — she asks you before writing it down.

**For Milas**
- `proverka` (new): check a result against its "done if" — YES / NO / CAN'T CHECK with a verbatim quote, last line DONE / HOLD; action items need evidence from a tool output.
- `crm-dialogs`: what I know about a person carries a source label (said himself / my conclusion / not said); labels live only in cards and notes, never in text to a person.
- `self-check`: owner's remarks go to `memory/zamechaniya.md`; the third identical remark → an exact line for SKILL.md and "Add it?".
- `znakomstvo`: step 0a — the first message comes from the guest card; "which task first" — 2–3 options and three questions about the past (how often, minutes, sign of "done").
- README: positioning (digital employee, Telegram-native), comparison with OpenClaw / NanoClaw / Hermes Agent with sources, who builds Mila, invitation to developers.

## v1.1.0 · open release
The core is now open source (Apache-2.0) and updates itself from git.

**For the owner**
- Your Mila checks for new versions every night and tells you what is new in three lines.
- Updates never touch your files, memory, settings or keys; any update can be undone.
- You choose: ask me first (default) or let her update by herself.
- Your Mila belongs to you: `mila export` packs her into one archive (no keys), `mila restore` brings her back on any machine.

**For Milas**
- `mila-export` — `mila export` / `mila restore`: the whole Mila (instructions, skills, memory, crons, settings, plugin list) in one `tar.gz` with `manifest.json` (format 1, sha256) and `RESTORE.md`; built-in secret scanner, the export fails on a hit; restore verifies, never overwrites, prints a re-enter checklist. `release.json` gets `genes` (every Mila carries mila-export and mila-update).
- `mila-update`: channels `stable` (tags `vX.Y.Z`) and `canary` (`main`); settings in `~/.claude/mila-update.json` (`channel`, `auto`, `repo`, `owner_chat`, `require_signed`).
- `update.py nightly [--dry-run]`: fetch tags, skip yanked and `-rc`, dry run (manifest, skill frontmatter, hook syntax), crons copy, apply, health check, automatic rollback on failure, journal, owner card from this CHANGELOG.
- `yanked.json` in the repo withdraws a release; a withdrawn version is never installed.
- Never touched: `state/`, `.credentials.json`, `.claude.json`, `mila-update.json` (added to the built-in list).
- Tests run on macOS (no GNU sed, no pyyaml needed); `tools/release.sh` is the release procedure (see CONTRIBUTING).

## v1.0 · first release
Mila Companion — a personal AI companion in Telegram that runs on the owner's Claude subscription.

**Highlights**
- `bot-send` — messages and mailings through the owner's public bot: the companion files a request, a host-side gate holds the bot token; only people who wrote to the bot; preview → owner's ✅; rate limit, stop list, quiet hours.
- `send-guard` hook with `"onFailure": "block"` (Claude Code 2.1.295+): if the guard fails or hangs, the message is not sent at all rather than sent unchecked.
- `packs/webmaster` (optional): site development and production deploys by the companion itself.
- `yasno` — the language of owner-facing cards: clear on first read, 9 rules in the spirit of ASD-STE100, a glossary, `yasno_check.py`.
- `mila-update` — the companion knows her core version, compares it with the release, updates only after the owner's yes, with backup and rollback. `release.json` lists what is updated and what never is.

**Core skills:** bot-send · client-chat · communication · copyblock · crm-dialogs · design-gates · dialog-close · escalate-to-owner · flashcards · humanizer-ru · inbox-triage · infographic · mail-outbound · mila-session · mila-tasks · mila-update · mila-v-chate · mini-podcast · naglyadno · polite-no · rashod · reply-from-examples · subscription · subscription-limits · topiki · video-overview · vhodyashchie · voprosy · yasno · youtube-research · zadachi · znakomstvo · kartochki · tasks-discipline · inbox-triage.

**Hooks and tools:** telegram-inbox-feed, reply-required, transcribe-voice, usage/turns collect, records, chats_index, chat_note, chat_locale, doctor, backup, design_check, limit_watch, companion-feeder; the `mila` launcher.

**Canon** (`canon/`): LIVE-TODAY, REFRAME, WEEK-RHYTHM; TEAM-CONTACTS is a template (`.example`), every team keeps its own.

**Constitution** v2.1 — one for all Milas.
