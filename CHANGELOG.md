# CHANGELOG · Mila Companion

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
