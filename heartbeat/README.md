# Heartbeat · Пульс Милы

**EN.** Mila's schedule outside the Claude Code session. Schedules made with `CronCreate` live inside the session: they are
lost on restart and expire after seven days. Heartbeat is a tiny service that runs once a minute, reads `~/work/heartbeat.yaml`
and, when a job is due, puts a message into the same inbound queue the Telegram channel uses. The session takes it like any
other message. No model is called by the service; checks are plain scripts.

**RU.** Расписание Милы вне сессии Claude Code. Кроны из `CronCreate` живут внутри сессии: пропадают при перезапуске и сами
гаснут через семь дней. Пульс — маленькая служба: раз в минуту читает `~/work/heartbeat.yaml` и, когда пришло время, кладёт
сообщение в ту же входящую очередь, что и канал Telegram. Сессия берёт его как любое другое сообщение. Модель служба не зовёт;
проверки — обычные скрипты.

## Job types · Виды заданий
| type | EN | RU |
|---|---|---|
| `beat` | a cheap check without a model; each new finding becomes one message, nothing found — nothing sent | удар: дешёвая проверка без модели; каждая новая находка — одно сообщение, нет находок — тишина |
| `think` | a scheduled thought (morning plan, evening wrap-up), skipped in quiet hours unless `quiet: false` | мысль по расписанию (утро, вечер), в тихие часы не идёт, если не `quiet: false` |
| `once` | one message at `at:`, then done | разовое: одно сообщение в `at:`, потом задание закрыто |

Fields · Поля: `id`, `type`, `cron` (5 fields, `timezone` of the file), `prompt`, `check` (beat), `at` (once), `quiet`,
`until` (end date — no seven-day limit otherwise), `enabled`, `timeout`. Example: [heartbeat.example.yaml](heartbeat.example.yaml).
Keys and tokens never go into the file — only names of env variables (`chat_id_env`, `watchdog.token_env`, `watchdog.chat_env`).

## Detector contract · Договор проверки
A `check` command prints zero or more lines: JSON `{"key": "...", "text": "..."}` or plain text. The service remembers keys,
so the same finding is not sent twice. Shipped detectors: `detectors/tg_unread.py` (new unread messages in chosen chats of the
owner's Telegram, read-only), `detectors/deadlines.py` (items due within N hours or overdue).

## Journal and watchdog · Журнал и сторож
`~/.local/state/mila-heartbeat/heartbeat.log`: time · job · type · what happened (queued / found N / nothing / skipped / error) · ms.
Watchdog: a queued message the session has not taken for `watchdog.after_min` minutes (default 15) → one Telegram message to
`MILA_ADMIN_CHAT` per incident (bot token from `BOT_TOKEN`).

## Install · Установка
Linux (systemd, user): copy this folder to `~/.claude/heartbeat/`, then
`cp mila-heartbeat.service mila-heartbeat.timer ~/.config/systemd/user/ && systemctl --user enable --now mila-heartbeat.timer`.
macOS (launchd): `cp com.mila.heartbeat.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.mila.heartbeat.plist`.
Env file for both: `~/.config/mila/heartbeat.env` (`BOT_TOKEN=…`, `MILA_OWNER_CHAT=…`, `MILA_ADMIN_CHAT=…`, mode 600).
Check: `python3 ~/.claude/heartbeat/heartbeat.py --list`, `--dry-run`.

## Glossary · Глоссарий
| EN | RU |
|---|---|
| Heartbeat | Пульс Милы |
| beat | удар (проверка без модели) |
| think | мысль (по расписанию) |
| once | разовое задание |
| quiet hours | тихие часы |
| watchdog | сторож |
| inbound queue | входящая очередь канала |
