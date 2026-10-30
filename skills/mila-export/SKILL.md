---
name: mila-export
description: "Use on \"make a copy of Mila\", \"export yourself\", \"move Mila to another machine\", \"restore Mila from archive\": archive without secrets. RU: «сделай копию Милы», «выгрузи себя», «перенеси Милу», «восстанови Милу»."
---
> **When to use (full):** Export Mila to an archive and revive her from it. No passwords or keys (secret scanner), manifest and sha256; restore never overwrites. Mila belongs 100% to the owner. Triggers: "make a copy of Mila", "export yourself", "move Mila to another machine", "restore Mila from archive". RU: Выгрузка Милы в архив и возрождение из него — «сделай копию Милы», «выгрузи себя», «перенеси Милу на другую машину», «восстанови Милу из архива». Архив без паролей и ключей (сканер секретов), с манифестом и sha256; восстановление не перезаписывает существующее. Мила принадлежит владельцу на 100%.

# mila-export — Мила принадлежит владельцу

Всё, чему владелец научил Милу, — инструкции, навыки, память, кроны, настройки — выгружается в один архив.
Открытое ядро (shakhruz/mila-agent) + этот архив = та же Мила на любой машине. Секретов в архиве нет по замыслу.

## Команды
```
mila export [--name NAME] [--out DIR]          # выгрузка → <DIR>/mila-export-<name>-<дата>.tar.gz
mila export --dry-run                          # сколько файлов и байт, архив не пишет
mila export --with-history                     # + транскрипты сессий и карточки чатов (данные других людей!)
mila export --no-people                        # без папок students/, clients/, people/, contacts/
mila export --allow 'work/путь/*'              # ложное срабатывание сканера — явное исключение
mila export verify <архив>                     # манифест, формат, sha256, повторный скан
mila restore <архив> [--dry-run] [--overwrite] # раскладка в ~/.claude и ~/work
mila export scan <папка>                       # только сканер секретов
```
Без `mila`-запускателя: `python3 ~/.claude/skills/mila-export/mila_export.py export|restore|verify|scan …`.
Пути: `--home DIR` (дом с `.claude/` и `work/`) или `--claude DIR --work DIR`; по умолчанию `~/.claude` и `~/work`
(`CLAUDE_CONFIG_DIR`, `MILA_WORK`). Только стандартная библиотека, Python 3.10+.

## Что внутри
`work/` — CLAUDE.md, CONSTITUTION, canon/, память (memory/), дневник (journal/), ритуалы, `state/crons.*`, знания, документы;
`claude/` — навыки (ядра и личные), хуки, команды, `settings.json` без секретов, список плагинов и версии,
шаблон `channels/telegram/access.template.json` (без id людей), `mila-update/version.json`.
`manifest.json` — формат (`format=1`), дата, версия ядра, каждый файл с sha256, что не вошло и почему.
`RESTORE.md` — что ввести заново: токен бота, вход в Claude, имена ключей сервисов, MCP-серверы.

## Чего не берём
`.env*`, имена с token/key/secret/credential/passw, `.pem`, `secrets/`, `.ssh/`, симлинки, файлы > 5 МБ, медиа и архивы
(`--with-media`), `inbox/`, `outbox/`, `channels/*/inbound`. Транскрипты сессий и карточки чатов — только
по `--with-history`: в них другие люди. `journal/` (дневник — память самой Милы) берётся по умолчанию.
**Внимание: архив содержит записи о ваших людях (карточки в навыках и памяти) — не передавайте его третьим лицам**; `--no-people` исключает такие папки.
Сканер читает **каждый** взятый файл: `sk-…`, `sk-ant-…`, токен бота `\d{8,10}:AA…`, `ghp_`, `AKIA`, `re_`,
блок закрытого ключа (PEM), присвоения пароля и ключей. Находка → export падает со списком файлов
(значения не печатаются), архив не создаётся.

## Как действую
1. Просьба владельца «сделай копию» — это его же данные: делаю `mila export --out <папка>`, сообщаю путь, размер, число файлов.
2. Падение сканера — не обхожу: показываю владельцу файлы, секрет убираем из файла; `--allow` — только с его «да».
3. Архив наружу (не владельцу) не отправляю. С `--with-history` — предупреждаю о чужих данных.
4. Раз в месяц и перед обновлением ядра — предложить копию; обновление (`mila-update`) делает своё резервирование отдельно.

## Восстановление
Чистая машина: ядро (`install/install.sh` или `deploy/bootstrap.sh`) → `mila export verify <архив>` → `mila restore <архив>`.
Существующие файлы не перезаписываются: версии из архива — в `~/.claude/mila-restore/<время>/conflicts/`;
`--overwrite` заменяет, оставляя копию в `replaced/`. `settings.json` на новом пути получает свой домашний каталог.
В конце — чек-лист «введите заново». Затем `mila doctor`.

## English, short
`mila export` writes a `tar.gz` of everything the owner taught this Mila (instructions, skills, memory, crons, settings) with
`manifest.json` (format 1, sha256 per file) and `RESTORE.md`. No secrets: secret-like files are skipped, every file goes through
a secret scanner and the export fails on a hit. `mila restore <archive>` verifies the manifest, lays files out, never overwrites
existing ones, and prints what to re-enter (bot token, Claude login, service keys). Transcripts/history only with `--with-history`.
Tests: `bash skills/mila-export/test_export.sh`.
