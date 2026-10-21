# Security policy

Mila runs an AI agent that can read and write in Telegram chats and on a
machine, so security reports are taken seriously.

## Reporting a vulnerability

Do not open a public issue. Use GitHub's "Report a vulnerability" (private security
advisory) on this repository, or write via https://milagpt.io. Please include what you
found, how to reproduce it and the impact. We aim to acknowledge within a few days.

## Scope

In scope: the hooks and tools in `install/` and `templates/`, the send-guard, the
installer and bootstrap scripts, secret handling in backups, access control and
pairing flow guidance.

Out of scope: vulnerabilities in Claude Code, Telegram or other upstream software
(report those to their vendors), and misconfiguration of your own server.

## Ground rules for everyone

- Never commit tokens, API keys or chat exports. `gitleaks` runs on this repository.
- Archives made by `mila backup` exclude secrets; still treat them as private.
- One Claude subscription login belongs to one person; do not share it.
