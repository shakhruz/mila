# Roadmap — repo to stars (21.10.2026, owner: «English first»)

Positioning: **Open-source digital employee in Telegram — runs on your Claude subscription.**
Closest by name: markfulton/ai-employees (scheduled roles on Claude Code), OpenBMB/StaffDeck (enterprise), lemonclaw. Our difference: lives in Telegram, runs on the owner's subscription, remembers the business, and acts on the owner's behalf only with consent — every such action in a journal.

Product manager: Mila Companion (leads and accepts). Build: Mila Development. Review before every push: Quality.

| # | What | Done when | Date |
|---|---|---|---|
| 1 | CI (`tests/run_all.sh`), one-command install, issue/PR templates, Code of Conduct | merged, CI green on GitHub | 21.10 (v1.5.1, accepted) |
| 2 | README: positioning first screen, English first, links to README.ru / README.uz, language card with an English dialogue | merged | 21.10 |
| 3 | Core skills English-first: `SKILL.md` English, `SKILL.ru.md` beside it; order — communication, onboarding | both merged, frontmatter check 0 errors | 21.10–22.10 |
| 4 | Next: mila-path, docs/accounting, install/doctor.py (messages EN with RU), packs/webmaster | merged | 23.10–24.10 |
| 5 | The rest — ≈ 190 files with Cyrillic outside `*.ru.*`, ~25 files a day, biggest first | 0 files with Cyrillic outside `*.ru.*`, `RU:` descriptions, `locales/` and sample replies | by 31.10 |
| 6 | `locales/<code>/` — one folder per language for customer-facing templates (greetings, card texts); ru and uz moved there, en default | add a language = add one folder | 27.10 |
| 7 | Duplicates inbox/vhodyashchie, tasks/zadachi, topics/topiki, questions/voprosy, tastes/vkusy — decision of Mila Companion (remove aliases in v1.6.0 or hide in `skills/_aliases/`) | catalog without duplicates | the day after the decision |
| 8 | Demo GIF in English (Content + Mila Video): a customer writes at night → Mila answers → morning summary | in README first screen | 24.10 |

**Before rolling English-first skills to the fleet:** exams for onboarding and communication in ru and uz on the stand — reply language, «знакомство: пройдено» marker, buttons (Quality, 21.10). Until they pass, English-first skills stay out of the nightly roll.

Each step: branch → Quality (secrets, our hosts, client and people names in history = 0; run_all green) → push by Admin.
