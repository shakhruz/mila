# Contributing

Thanks for helping. Mila Companion is a kit of skills (Markdown), hooks and small
Python/shell tools around Claude Code and a Telegram channel.

## Ground rules
- One logical change per pull request; small commits.
- No secrets, no real chat ids, no names of real customers or people in code,
  examples or tests - use placeholders (`acme_bot`, `<chat_id>`, "Anna").
- Skills: `SKILL.md` needs valid frontmatter. Check with
  `python tools/check_frontmatter.py skills templates`.
- JS/HTML: `python tools/check_comments.py <files>` (no code after `//` on one line).

## Tests
```sh
python3 templates/home/.claude/hooks/test_send_guard.py
python3 install/test_records.py
python3 install/test_team_hearing.py
python3 skills/bot-send/test_bot_send.py
python3 skills/kartochki/test_kartochki.py
bash skills/yasno/test_yasno.sh
bash skills/mila-update/test_update.sh
```
Run them before opening a PR; CI runs the frontmatter, send-guard and comment checks.

## Language
Skill text is mostly Russian (the author's working language); README and code
comments in English are welcome. Translations of skills are welcome as `SKILL.<lang>.md`.

## License
By contributing you agree your work is licensed under Apache-2.0 (see LICENSE).
