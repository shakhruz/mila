# Mila Companion

![Mila Companion](docs/preview.png)

**Mila** is a digital personality: a kind, attentive assistant that lives in Telegram and runs on
[Claude Code](https://claude.com/claude-code) with your own Claude subscription. She talks to you
from your phone, joins your chats, keeps promises, remembers what matters, and follows a short
constitution about honesty, privacy and care for the person she serves.

This repository is the open core: skills, hooks, tools and templates needed to bring up one Mila.
Hosted version and the community: <https://milagpt.io> - you are welcome to use the service.
The Telegram plugin it runs on is a separate open repository: [shakhruz/mila-telegram](https://github.com/shakhruz/mila-telegram).

[Русская версия](README.ru.md) · [Full reference](docs/REFERENCE.md)

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

A Mila's memory (chat cards, agreements, access list, skills learned from real mistakes, spend log)
exists nowhere else, so it can be exported:

```sh
mila backup status                 # what is saved, when, what is missing
mila backup run                    # export an archive (secrets are filtered out)
mila backup run --to user@host:<archives>   # and ship a copy over ssh
```

The archive never contains bot tokens or API keys - on a new machine you install the kit, configure a
fresh token, and unpack the archive over `~/.claude` and the Telegram state directory.
A guided one-command restore is not in this repository yet - **coming soon**; today the restore is manual.

## Safety

The send-guard hook blocks messages that would leak one conversation into another or expose server
paths; if the guard itself fails, nothing is sent. See [SECURITY.md](SECURITY.md).

## Contributing, license, name

[CONTRIBUTING.md](CONTRIBUTING.md) · code under [Apache-2.0](LICENSE) ([NOTICE](NOTICE)) ·
the names "Mila", "MILAGPT" and the logo are trademarks, see [TRADEMARKS.md](TRADEMARKS.md).
