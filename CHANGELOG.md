# CHANGELOG · Mila

## v1.5.2 · 21.10 — English first, five questions about the model, fleet roll from the host
- English first: `communication` and `onboarding` skills in English (`SKILL.md`) with Russian beside (`SKILL.ru.md`); the owner's language can be any (LANG-ANY): Chinese, Arabic…; on «what can you do» — one benefit, not a list.
- `skills/utochnenie-zadach` (new, base skill of every Mila): understand first, then do — 2–4 questions with ready options before substantial work; answers already given — no questions; urgent — result first with assumptions.
- `skills/model-choice`: five questions → model tier (`tier.py`: light | strong | strong+yes; a costly error always goes to the strong model; in someone's name or irreversible — strong model and the person's yes).
- `skills/draft-and-check` (new): a light model drafts, the strong model checks facts, numbers and tone against sources, the person's yes on that exact text sends it.
- `mila tasks` (`install/tasks.py`): task journal — kind, outcome (done / redo / complaint), cost from the turns of the task span; weekly report per task type.
- `skills/design-gates`: `fit_text.py` — does the text fit (wrap, largest size that fits, error with advice before writing files) for every visual skill.
- CI: DejaVu font installed; a test that skipped itself (`итог 0/0`) is ⚠ locally and fails in CI; tests run with stdin closed (`ffmpeg -nostdin`).
- README: Manifesto link (`milagpt.io/en/manifest/`), site links → `milagpt.io/en/mila/`, «One Mila, two wallets» — the subscription for the owner and work chats, customers and guests on OpenRouter tokens (guest routing in the hosted version today); compare table approvals row re-checked.
- `mila-update` fleet mode: `MILA_HOME` — update a Mila's home from the host; `MILA_CHOWN=uid[:gid]` — run as root, and only what this run wrote goes back to the home's owner (in-memory list, only inside the home: realpath + commonpath, no hard links). Rollback as root does not trust the journal or backups in the home (removal and unpacking only inside the home, no hard links or devices, symlinks only to targets inside). No access to the home → a clear error. `test_fleet.py` 11/11.

## v1.5.1 · 21.10 — safe, model choice, live frames, one-command install
- One-command install: `curl -fsSL …/install/get.sh | bash` (checks Claude Code, Bun, git); CI runs `tests/run_all.sh` on every push; issue/PR templates, Code of Conduct.
- `skills/model-choice` (a partner's idea, 20.10): before any paid task (images, video, voice, transcription, translation, document analysis) Mila shows two options — budget / best quality: model, what you get, price for this job — with a recommendation, owner picks by button; `pick.py` + dated `catalog.json` (OpenRouter live, fal.ai, ElevenLabs). Test 6/6.
- Mila Safe (owner 20.10, «Да, делаем сейф»): `tools/seif` — one-time link (30 min, single use, GET does not burn it) where the business owner types passwords, keys and cards; values go straight to `work/secrets/<name>.env` (600) of the Mila's home, journal without values, note to the companion; `skills/safe-link` — never ask secrets in chat, request a safe link, read with `safe_read.py` (mask only). Tests 12/12, 6/6.
- `skills/live-frames` (new, from Mila Video, owner 20.10 «намного лучше»): explainer video from a voice track — moving background, Twemoji icons, counters, bars, arrows and pills appear on the spoken word, whoosh/pop/ticks and a ducked music bed, −14 LUFS; Pillow + numpy + ffmpeg, no paid graphics. Local word timing check (faster-whisper). Twemoji CC-BY 4.0, PT Sans OFL. Test: 3-second render with sound.
- `tools/hooks_sync.py` + template settings: mila-tasks hooks (PostToolUse reply → task-sent, SessionStart → task-open) for Milas deployed from the image (HOOKS-SYNC-1020).

## v1.5.0 · privacy and safety layer, 19.10
Personal data stays out of what Mila stores, card numbers never leave in a message, and a fresh self-hosted install comes with all its guards.

**For the owner**
- Card numbers are protected: a message with a bank card number (13–19 digits that pass the Luhn check) is never sent to a group, and in a private chat it goes out masked as ****1234. Your own payment details can be allowed in the config (`cardAllow` in access.json, `CARD_ALLOW` for bot sends).
- Personal data in Mila's memory is stored as labels, not as the data itself (pd-vault, encrypted on your machine).
- A fresh install already has every guard switched on: sending only to connected chats, no keys or internals in messages, tracking of what Mila promised you.
- New: a pack for clinics (booking and price list, with an exam).

**For Milas**
- `send-guard` (CARD-MASK): card number → deny to groups with the reason for the author, `updatedInput` with the mask in private chats; amount right after the number («… 1234 100 USD») does not hide it — the Luhn window is searched inside the digit chain, 16 digits first. `bot_send` masks in sends and broadcast previews.
- pd-vault (layer 2a): AES-256 + HMAC via openssl, labels instead of personal data; `pd-mask` PostToolUse hook; install creates the key by default.
- `install.sh` (SELFHOST): registers send-guard (PreToolUse reply/edit), task-sent and task-open (mila-tasks), `OWNER_ID` from `MILA_OWNER_ID`; send-guard falls back to access.json without OWNER_ID; installer copies every hook it registers.
- `skills/jev`: fast decider — reply / who / buttons, modes off | shadow | main, 1.2 s timeout → rules, diff log without texts.
- `mila-update`: `install-skill` refuses an incomplete skill (files named in SKILL.md missing → list, `--allow-missing` to install knowingly); `remove-skill` with backup, core skills protected.
- `packs/clinic` v0.1: clinic-booking, clinic-prices, exam (Sila's patient scenarios ×3), no condition names (diagnosis), data in `~/work/clinic/`.
- README: release badge and «which version to take» (stable — Releases, canary — main); REFERENCE licence fixed to Apache-2.0.
- Tests: `tests/run_all.sh` — ALL GREEN 17.

## v1.4.0-rc4 · fix (candidate)
- 🔴 `install.sh` (since rc3) registered `reply-required.py` as a Stop hook but did not copy the file: on a fresh install every stop failed with exit code 2, which means «don't stop» — the session would loop. Now every hook the installer registers is copied; `install/test_install_hooks.sh` checks that each hook in settings.json exists as a file. Updates via mila-update were not affected (install/*.py are copied by the release zones; settings.json is not touched).

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
