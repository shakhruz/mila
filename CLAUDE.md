# CLAUDE.md — for Claude Code working in this repository

You are in **Mila Agent** — the open-source business agent for Telegram. It is a kit for Claude Code:
skills (`skills/`), hooks and tools (`install/`, `templates/home/`), working principles (`canon/`) and the
values every Mila reads first (`CONSTITUTION.md`). The Telegram channel is a separate plugin, `mila-telegram`.

## If a person asked you to install Mila for them

1. **Check what they have:** macOS or Linux (Windows only inside WSL), `claude --version`, `bun --version`, `git`.
2. **Install:** `./install/install.sh --dry-run` first and show them what it will touch, then `./install/install.sh`.
   A fresh Linux server: see [deploy/README.md](deploy/README.md).
3. **Ask the person — and only them — for:**
   - a Telegram bot token from `@BotFather` (they paste it into `mila onboard`, which hides it);
   - their own Claude sign-in: they run `claude` and sign in on Anthropic's page themselves, or give their own
     Anthropic API key. You never ask for, copy, log or store a Claude login or token;
   - pairing: `mila onboard` shows a 6-character code; they send it to their bot from Telegram.
4. **Start:** `mila`. If the bot is silent: `mila doctor`.

## What you never do here

- Never put a real token, key, phone, id, name or client data into a file, a test, a commit or an example.
  Tests use the fake values from `tests/fixtures/fake_people.py`; token-shaped strings are glued at run time.
- Never weaken the send-guard (`templates/home/.claude/hooks/send-guard.py`) or the owner's-yes rule: nothing goes
  out on the owner's behalf without the owner's explicit yes for that step.
- Never edit `CONSTITUTION.md` — its text is approved by the owner and must stay byte-equal across all Milas.
- Never rewrite `CHANGELOG.md` history or anything under `legacy/` (old names kept for updates).
- Never push, tag or publish — a maintainer does that after review.

## Changing the code

- Run the tests three ways before you call anything done:
  `bash tests/run_all.sh`, `CI=true bash tests/run_all.sh`, `bash tests/run_ci_local.sh` (clean HOME, UTC, the workflow's Python packages).
- A new test that needs a library → add it to the `pip install` line in `.github/workflows/tests.yml` the same day.
- `python3 tools/privacy_lint.py --all` (no live values) and `python3 tools/kitchen_lint.py` (no internal task codes or
  message numbers in public files) must both be clean.
- Every `SKILL.md` starts with YAML: `name` and an English `description` («Use when…», a Russian line may follow);
  `python3 tools/check_frontmatter.py skills` checks that the header parses.
- Small, reviewable changes; one idea per commit; say in the commit what a person gets from it.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
