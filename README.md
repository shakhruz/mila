<p align="center">
  <a href="https://milaagent.com"><img src="assets/mila-face.png" alt="Mila Agent" width="120"></a>
</p>

<h1 align="center">Mila Agent</h1>

<p align="center"><b>The open-source AI employee for business.</b><br>
She answers your customers on Telegram, remembers every promise — and asks your OK before anything goes out in your name.</p>

<p align="center">
  <a href="https://milaagent.com">Website</a> ·
  <a href="https://mila.market">Mila Market</a> ·
  <a href="https://milagpt.io/akselerator/">MilaGPT Studio</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="https://github.com/shakhruz/mila-agent/discussions">Community</a>
</p>

<p align="center">
  <a href="https://github.com/shakhruz/mila-agent/stargazers"><img src="https://img.shields.io/github/stars/shakhruz/mila-agent?style=flat&logo=github" alt="GitHub stars"></a>
  <a href="https://github.com/shakhruz/mila-agent/releases/latest"><img src="https://img.shields.io/github/v/release/shakhruz/mila-agent?sort=semver&label=release" alt="Latest release"></a>
  <a href="https://github.com/shakhruz/mila-agent/actions/workflows/tests.yml"><img src="https://github.com/shakhruz/mila-agent/actions/workflows/tests.yml/badge.svg" alt="tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="Apache-2.0"></a>
  <img src="https://img.shields.io/badge/built%20on-Claude%20Code-d97757" alt="Built on Claude Code">
</p>

<p align="center"><b>English</b> · <a href="README.zh-CN.md">中文</a> · <a href="README.ru.md">Русский</a> · <a href="README.uz.md">Oʻzbekcha</a></p>

```sh
curl -fsSL https://raw.githubusercontent.com/shakhruz/mila-agent/main/install/get.sh | bash
```
<p align="center">≈ 5 minutes · macOS, Linux (Windows via WSL) · bring your own Claude plan or Anthropic API key</p>

<p align="center"><img src="docs/preview.png" alt="Mila answering a customer in Telegram" width="720"></p>

---

## Why Mila

Most open agents are universal assistants: powerful, if you tell them exactly what to do.
Mila is built the other way round — **a colleague with a job.**

- **Answers your customers on Telegram** — day and night, in the language they write in.
- **Remembers your business** — every client, conversation and promise; one short summary for you every morning.
- **Acts in your name only with your yes** — a send-guard stops leaks between chats, broadcasts and spending above your limit wait for your ✅.
- **Yours, 100%** — your files stay in your home folder; `mila export` / `mila restore` moves her to any machine.

```
Customer: Hi! Is the two-bedroom by the sea still free? Can I see it on Saturday?
Mila:     Hi! Yes, it's free 🙂 Saturday at 11:00 or 15:00 — which suits you? I'll book it and remind you an hour before.
Customer: 11, please.
Mila:     Done ✅ I'll send the address and remind you on Saturday morning.
```
*Next morning the owner gets one line: new client · viewing Saturday 11:00 · reminder set.*

## Three ways to get your Mila

| | | |
|---|---|---|
| **Build one** — free | Install Mila Agent yourself, on your computer or a server. | [Quick start ↓](#quick-start) |
| **Hire one** | Ready-made Milas for a job — moderator, manager, SMM and more. The first one is free. | [mila.market](https://mila.market) |
| **Launch your own** | MilaGPT Studio sets your Mila up with you and helps turn your expertise into a product. | [milagpt.io/akselerator](https://milagpt.io/akselerator/) |

## How Mila compares

OpenClaw, NanoClaw and Hermes Agent are excellent open agents — universal assistants for a person. Mila takes a narrower job: a digital employee for a business, on Telegram.

| | **Mila** | [OpenClaw](https://github.com/openclaw/openclaw) | [NanoClaw](https://github.com/nanocoai/nanoclaw) | [Hermes Agent](https://github.com/NousResearch/hermes-agent) |
|---|---|---|---|---|
| What it is | [digital employee for a business](#why-mila) | [universal personal agent](https://github.com/openclaw/openclaw) | [personal agent in containers](https://github.com/nanocoai/nanoclaw) | [personal agent that grows with you](https://hermes-agent.nousresearch.com/docs) |
| Engine | [Claude Code](https://code.claude.com/docs/en/overview) | [own agent loop, models as plugins](https://github.com/openclaw/openclaw) | [Claude Agent SDK](https://github.com/nanocoai/nanoclaw) | [own agent loop, any model](https://hermes-agent.nousresearch.com/docs) |
| Channels | Telegram: DMs, groups, your public bot ([mila-telegram](https://github.com/shakhruz/mila-telegram)) | [20+ (WhatsApp, Telegram, Slack...)](https://docs.openclaw.ai/channels) | [many, each added by a skill](https://github.com/nanocoai/nanoclaw) | [Telegram, Discord, Slack, WhatsApp...](https://hermes-agent.nousresearch.com/docs) |
| Business skills out of the box | [CRM of dialogs](skills/crm-dialogs/SKILL.md), [promises and tasks](skills/tasks-discipline/SKILL.md), [owner cards](skills/cards/SKILL.md), [weekly rhythm](canon/WEEK-RHYTHM.md), [mailings](skills/bot-send/SKILL.md) | [general skills (ClawHub)](https://clawhub.ai) | [general skills](https://github.com/nanocoai/nanoclaw) | [self-written skills](https://hermes-agent.nousresearch.com/docs) |
| What waits for the owner's yes | partly: [send-guard](templates/home/.claude/hooks/send-guard.py) stops messages to chats the owner didn't connect, keys and internals; broadcasts from your bot and paid work above the limit wait for the owner's ✅ ([`bot-send`](skills/bot-send/SKILL.md), [`spend`](skills/spend/SKILL.md)); ordinary replies in connected chats are not gated | [exec approvals, Team preset](https://docs.openclaw.ai/tools/exec-approvals) | [approval for credential use, self-modification and new chats; ordinary messages are not gated](https://docs.nanoclaw.dev/concepts/security) | [approval for dangerous shell commands (fail-closed); no approval step for sending messages](https://hermes-agent.nousresearch.com/docs/user-guide/security) |
| Spending limits | yes ([`spend`](skills/spend/SKILL.md): forecast, approval above the limit) | no data | no data | [per-member caps (Hermes Business)](https://portal.nousresearch.com) |
| Your Mila moves with you | [`mila export` / `mila restore`](skills/mila-export/SKILL.md) | [Markdown memory files](https://github.com/openclaw/openclaw) | [per-group folders](https://github.com/nanocoai/nanoclaw) | [own memory store](https://hermes-agent.nousresearch.com/docs) |
| License | [Apache-2.0](LICENSE) | [MIT](https://github.com/openclaw/openclaw/blob/main/LICENSE) | [MIT](https://github.com/nanocoai/nanoclaw/blob/main/LICENSE) | [MIT](https://github.com/NousResearch/hermes-agent/blob/main/LICENSE) |
| Price | free, open source; setup help — [MilaGPT Studio](https://milagpt.io/akselerator/) | [free, self-host only](https://github.com/openclaw/openclaw) | [free; enterprise on request](https://github.com/nanocoai/nanoclaw) | [free; Nous Portal $0-200/month](https://portal.nousresearch.com) |

**Mila's honest minuses.** Telegram only: no WhatsApp, Slack or Discord. It needs Claude Code, signed in with your own Claude plan
or API key — Mila herself runs only on Claude (guests on other models through OpenRouter: in the hosted version today, open core — next
release). She answers while your machine and the session run: a closed laptop means a silent Mila, so use an always-on
computer or a server. macOS and Linux; Windows only through WSL. Channels in Claude Code are a research preview, so the launcher uses a development flag for now
(see Quick start).

Facts about other projects: their READMEs and docs, checked 17.10.2026; approvals row re-checked 21.10.2026 against [NanoClaw security](https://docs.nanoclaw.dev/concepts/security) and [Hermes security](https://hermes-agent.nousresearch.com/docs/user-guide/security) -
[OpenClaw](https://github.com/openclaw/openclaw),
[NanoClaw](https://github.com/nanocoai/nanoclaw), [Hermes Agent](https://github.com/NousResearch/hermes-agent).
Something wrong or out of date? Open an issue - we fix it the same day.


## Claude — by Anthropic's rules

- Mila runs on the ordinary, unmodified Claude Code, installed as Anthropic publishes it.
- You sign in yourself, only on Anthropic's page, with your own Claude plan or your own Anthropic API key. Mila never copies or stores your login or token; don't copy an OAuth token anywhere yourself.
- Your plan is for your own use. Customers and guests who write to your bot are served through an API key, billed to the key's owner.
- A partner who sets Mila up for you does not run you on the partner's subscription, does not pay for, resell or intermediate your Claude usage, and does not collect logins.

Source: [Claude Code — legal and compliance](https://code.claude.com/docs/en/legal-and-compliance).


## Quick start


≈ 5 minutes.

**You need:**
- macOS or Linux. On Windows — inside [WSL](https://learn.microsoft.com/windows/wsl/install).
- [Claude Code](https://code.claude.com/docs/en/setup), tested on 2.1.305 (`claude --version`), signed in with your own Claude plan (Pro, Max, Team or Enterprise) or your own Anthropic API key. On Team and Enterprise your organization admin must enable channels.
- [Bun](https://bun.sh) and git.
- A Telegram bot token from `@BotFather`.
- `~/.local/bin` on your `PATH` — the `mila` launcher goes there (the installer tells you if it is missing: `export PATH="$HOME/.local/bin:$PATH"`).
- Nothing else: your Telegram id is set by `mila onboard` (step 3). Setting it by hand: `MILA_OWNER_ID=<your id> ~/mila/install/install.sh`.

One command:

```sh
curl -fsSL https://raw.githubusercontent.com/shakhruz/mila-agent/main/install/get.sh | bash
```

It checks Claude Code, Bun and git, clones the kit to `~/mila`, runs `install/install.sh` and installs the Telegram plugin `mila-telegram` (existing files are backed up as `<file>.bak-YYYYMMDD-HHMMSS`). Prefer to look first? `curl -fsSL https://raw.githubusercontent.com/shakhruz/mila-agent/main/install/get.sh | MILA_INSTALL_ARGS=--dry-run bash` — or clone and run `./install/install.sh --dry-run`: it shows exactly what will be touched.

Then three steps, each checked before the next:

```sh
mila onboard
```

1. **Bot token** — paste it (hidden), Telegram confirms it, it is saved with mode 600.
2. **Claude** — if you are not signed in, Anthropic's own sign-in opens; Mila never sees it.
3. **Pair** — you get a 6-character code, send it to your bot from Telegram; you become the owner (allowlist + `OWNER_ID`). Mila sees that code as your first message when she starts — that's normal.

Then start Mila with `mila`. `mila onboard --check` shows the three steps without changing anything; if the bot goes quiet, run
`mila doctor`. Prefer the plugin's own commands? `/mila-telegram:configure <token>` and `/mila-telegram:access pair <code>` still work.

**Why `mila` starts Claude Code with `--dangerously-load-development-channels`.** Channels are a research preview in
Claude Code: the plain `--channels` flag accepts only plugins on Anthropic's approved list, and `mila-telegram` is not on it
yet. The development flag lets this one plugin, named in the command, push messages into your session; it does not
skip permission prompts and does not load anything else. Messages still reach Mila only from people you paired or allowed.
If the plugin is accepted into Anthropic's plugin marketplace, `mila` will switch to plain `--channels`. Details:
[Claude Code — channels](https://code.claude.com/docs/en/channels#research-preview).

When it works, `mila doctor` looks like this (yellow lines are hints, not errors):

```
Channel diagnosis · ~/.claude/channels/telegram

🟢 bot                @your_mila_bot (Mila), source: ~/.claude/channels/telegram/.env
🟡 privacy mode       on — in groups only mentions and replies reach Mila
🟢 private chats      allowed 1, policy «allowlist»
🟢 daemon             running, code: …/mila-telegram/receiver.ts
🟢 permissions        telegram — 700, .env — 600, access.json — 600
🟢 channel in session plugin MCP server is running
```
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

## ⭐ Help Mila grow

If Mila saves you time, **star the repo** — it helps other business owners find her.
Built a skill or a role? **Fork it**, send a pull request, or publish your Mila on [Mila Market](https://mila.market) and earn 75% of every sale.

[![Star History Chart](https://api.star-history.com/svg?repos=shakhruz/mila-agent&type=Date)](https://star-history.com/#shakhruz/mila-agent&Date)

## Community

Questions, ideas, show what your Mila does: [GitHub Discussions](https://github.com/shakhruz/mila-agent/discussions) ·
Bugs: [Issues](https://github.com/shakhruz/mila-agent/issues) · Security: [SECURITY.md](SECURITY.md) · Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)

---

Apache-2.0 · © 2026 MILAGPT Coop, Tashkent · "Mila", "MILAGPT" and the logo are trademarks — see [TRADEMARKS.md](TRADEMARKS.md).
*Claude and Claude Code are trademarks of Anthropic, PBC. Mila is an independent open-source project, not affiliated with, endorsed or sponsored by Anthropic.*
