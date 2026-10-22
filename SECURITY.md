# Security policy

Mila runs an AI agent that can read and write in Telegram chats and on a
machine, so security reports are taken seriously.

## Reporting a vulnerability

Do not open a public issue. Use GitHub's "Report a vulnerability" (private security
advisory) on this repository, or e-mail hello@milagpt.io with "security" in the subject.
Please include what you found, how to reproduce it and the impact.
We acknowledge every report within 5 business days.

## Scope

In scope: the hooks and tools in `install/` and `templates/`, the send-guard, the
installer and bootstrap scripts, secret handling in backups, access control and
pairing flow guidance.

Out of scope: vulnerabilities in Claude Code, Telegram or other upstream software
(report those to their vendors), and misconfiguration of your own server.

## The development-channels flag

`mila` starts Claude Code with `--dangerously-load-development-channels plugin:mila-telegram@<marketplace>`.
While channels are a research preview, plain `--channels` accepts only plugins on Anthropic's approved list, and
`mila-telegram` is not on it. The flag applies only to the plugin named after it: it does not bypass permission
prompts or load other channels. Who can write to the session is limited by the plugin's pairing and allowlist
(`/mila-telegram:access`). Once the plugin is accepted into Anthropic's marketplace, the launcher moves to `--channels`.

## Ground rules for everyone

- Never commit tokens, API keys or chat exports. `gitleaks` scans the whole history on every push and pull request (`.github/workflows/gitleaks.yml`).
- Archives made by `mila backup` exclude secrets; still treat them as private.
- One Claude subscription login belongs to one person; do not share it.
