# Contributing

Thanks for helping. Mila is a kit of skills (Markdown), hooks and small
Python/shell tools around Claude Code and a Telegram channel.

## Ground rules
- One logical change per pull request; small commits.
- No secrets, no real chat ids, no names of real customers or people in code,
  examples or tests - use placeholders (`acme_bot`, `<chat_id>`, "Anna").
- Skills: `SKILL.md` needs valid frontmatter. Check with
  `python3 tools/check_frontmatter.py skills templates`.
- JS/HTML: `python3 tools/check_comments.py <files>` (no code after `//` on one line).

## Tests
`bash tests/run_all.sh` runs every test in the repo (sandboxed `HOME`) plus the frontmatter check — all green before a
pull request. CI runs the same script, plus gitleaks on the whole history. To run one test while you work:
```sh
python3 templates/home/.claude/hooks/test_send_guard.py
bash skills/mila-update/test_update.sh
```

## Language
Skill text is mostly Russian (the author's working language); README and code
comments in English are welcome. Translations of skills are welcome as `SKILL.<lang>.md`.

## License
By contributing you agree your work is licensed under Apache-2.0 (see LICENSE).

## Releases
- Channels: `stable` = tags `vX.Y.Z` (no `-rc`), `canary` = `main`. Milas update themselves from the channel they are set to (`~/.claude/mila-update.json`).
- Before a release: add `## vX.Y.Z` to `CHANGELOG.md` with a **For the owner** block (up to 3 plain lines: it becomes the "What is new" card) and a **For Milas** block.
- `tools/release.sh X.Y.Z` runs the tests, bumps `release.json`, commits `release vX.Y.Z` and tags it (signed with `git tag -s` when `user.signingkey` is set, otherwise an unsigned annotated tag, which the script says). It never pushes.
- Withdraw a bad release: add its tag to `yanked.json` on `main` (list of tags or `{"yanked":[{"tag":"v1.2.0","reason":"..."}]}`). Milas never install a yanked tag; one that already has it gets a warning card.
- Pre-release candidates: `vX.Y.Z-rc1` (not picked up by `stable`).
