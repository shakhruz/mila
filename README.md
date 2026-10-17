# Mila Companion

![Mila Companion](docs/preview.png)

**Mila Companion is an open-source digital employee for your business. She lives in Telegram.**

Most open agents are universal: a powerful assistant that can do anything, if you tell it how.
Mila is built the other way round - as a colleague with a job. She answers your clients, keeps your promises,
remembers every conversation, writes the posts, reminds about meetings and tells you every morning what is
on fire. You talk to her from your phone, by text or voice, like to a person on your team.

- **A digital employee, not a universal agent.** Business skills out of the box: client chats, CRM of dialogs,
  promises and tasks, owner approval cards, weekly rhythm (plan in the morning, results in the evening),
  spending limits, mailings with your yes.
- **Telegram-native.** Your chats, your groups, your clients - Mila works where your business already talks.
  No new app to install.
- **Runs on your own Claude subscription** through [Claude Code](https://claude.com/claude-code). Your data stays
  in your home folder; Mila belongs to you 100% and moves with you (`mila export` / `mila restore`).
- **Safe by default.** Nothing goes out on your behalf without your yes; a send-guard blocks messages that would
  leak one conversation into another; spending above the limit needs your approval.
- **Open core, Apache-2.0.** Skills, hooks, tools and templates are here. Fork it, teach it, send a pull request.

Don't want to set it up yourself? Talk to [Mila Tashkent](https://t.me/mila_tashkent_bot): she will start your own
Mila in one conversation - 3 days for $5, then $50/month. Hosted version and the community: <https://milagpt.io>.
The Telegram plugin is a separate open repository: [shakhruz/mila-telegram](https://github.com/shakhruz/mila-telegram).

[Русская версия](README.ru.md) · [Full reference](docs/REFERENCE.md)

## How Mila compares

OpenClaw, NanoClaw and Hermes Agent are excellent open agents - universal assistants for a person.
Mila Companion takes a narrower job: a digital employee for a business, in Telegram.

| | **Mila Companion** | OpenClaw | NanoClaw | Hermes Agent |
|---|---|---|---|---|
| What it is | digital employee for a business | universal personal agent | personal agent in containers | personal agent that grows with you |
| Engine | Claude Code | own agent loop, models as plugins | Claude Agent SDK | own agent loop, any model |
| Runs on your Claude subscription | yes (Claude Code) | no, since 04.04.2026 extra usage or API key | no data | no data |
| Channels | Telegram: DMs, groups, your public bot | 20+ (WhatsApp, Telegram, Slack...) | many, each added by a skill | Telegram, Discord, Slack, WhatsApp... |
| Business skills out of the box | CRM of dialogs, promises and tasks, owner cards, weekly rhythm, mailings | general skills (ClawHub) | general skills | self-written skills |
| Nothing goes out without the owner's yes | yes, by design (constitution + send-guard) | exec approvals, Team preset | enterprise version | no data |
| Spending limits | yes (`rashod` skill: forecast, approval above the limit) | no data | no data | per-employee limit (Business plan) |
| Your Mila moves with you | `mila export` / `mila restore` | Markdown memory files | per-group folders | own memory store |
| License | Apache-2.0 | MIT | MIT | MIT |
| Price | free to self-host; hosted from $50/month | free, self-host only | free; enterprise on request | free; Nous Portal $0-200/month |

Facts about other projects: their READMEs and docs, checked 17.10.2026 -
[OpenClaw](https://github.com/openclaw/openclaw) ([Claude subscription change](https://techcrunch.com/2026/04/04/anthropic-says-claude-code-subscribers-will-need-to-pay-extra-for-openclaw-support/)),
[NanoClaw](https://github.com/nanocoai/nanoclaw), [Hermes Agent](https://github.com/NousResearch/hermes-agent).
Something wrong or out of date? Open an issue - we fix it the same day.

## What is inside

| Path | What |
|---|---|
| `skills/` | The abilities: communication, tasks, CRM of dialogs, cards for the owner, group behaviour, mailings, spending control, flashcards, infographics, video/podcast overviews, updates. |
| `install/` | Installer, the `mila` launcher, hooks (inbox feed, reply-required), usage/limit tools, `doctor`, `backup`. |
| `templates/home/` | Hooks and settings for a Mila home directory: the send-guard hook, session-start hook. |
| `canon/` | Working principles (live today, reframe, weekly rhythm). |
| `deploy/` | Bootstrap script for a fresh Linux server. |
| `packs/webmaster/` | Optional: build and deploy a website by the companion itself. |
| `CONSTITUTION.md` | The values every Mila is read to first. |

## Quick start

Requirements: Claude Code, a Claude subscription, [Bun](https://bun.sh), a Telegram bot token from `@BotFather`.

```sh
git clone <this repository> mila-companion
cd mila-companion
./install/install.sh --dry-run   # shows exactly what will be touched
./install/install.sh             # existing files are backed up as <file>.bak-YYYYMMDD-HHMMSS
```

Then, inside a Claude Code session:

```
/plugin marketplace add shakhruz/mila-telegram
/plugin install mila-telegram@mila
/telegram:configure <bot token from @BotFather>
```

Restart with `mila`, message your bot, pair (`/telegram:access pair <code>`), then lock it down with
`/telegram:access policy allowlist`. If the bot goes quiet, run `mila doctor`.
Server install: see [deploy/README.md](deploy/README.md).

## Revive your Mila from an archive

A Mila belongs to her owner, 100%. Everything you taught her - instructions, skills, memory, crons, settings - exports to one
archive, and this open core plus that archive brings her back on any machine.

```sh
mila export --out ~/mila-backups     # archive without passwords and keys (a secret scanner runs on every file)
mila export verify <archive>         # manifest + sha256 check
# on a clean machine, after install/install.sh or deploy/bootstrap.sh:
mila restore <archive> --dry-run     # see what goes where
mila restore <archive>               # existing files are never overwritten; differences go to ~/.claude/mila-restore/
```

The archive has `manifest.json` (format 1, sha256 of each file, core version) and `RESTORE.md`; secrets are never in it.
After the restore you re-enter by hand: the bot token, your Claude login, service keys (the checklist is printed).
Chat history and transcripts are exported only with `--with-history` (other people's data - keep it closed).
Details: [skills/mila-export](skills/mila-export/SKILL.md). To save the memory on a schedule, use `mila backup` (see above in the reference).

## Safety

The send-guard hook blocks messages that would leak one conversation into another or expose server
paths; if the guard itself fails, nothing is sent. See [SECURITY.md](SECURITY.md).

## Who builds Mila

MILAGPT is a small team led by **Shakhruz Ashot Ashirov** - founder of MILAGPT and AshotAI, 40 years in software,
28 of them in commercial development and online marketing (Disney, Apple, AT&T), and **Farangiz Sharapova** -
co-founder of MILAGPT. A fleet of Milas works next to us every day: development, quality, content, clients -
this repository is the core they run on.

**Developers, join us.** Build a skill, fix a hook, translate a skill to your language, tell us what broke.
Every pull request is read by a person and by Mila Quality. Good contributors are invited to the core team.
Start with [CONTRIBUTING.md](CONTRIBUTING.md).

## Contributing, license, name

[CONTRIBUTING.md](CONTRIBUTING.md) · code under [Apache-2.0](LICENSE) ([NOTICE](NOTICE)) ·
the names "Mila", "MILAGPT" and the logo are trademarks, see [TRADEMARKS.md](TRADEMARKS.md).
