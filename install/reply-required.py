#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reply-required.py — Stop-хук Компаньона (12.09.2026, дефект клиентского компаньона).

Хозяин читает Telegram, а не терминал. Если последнее сообщение хозяина пришло
конвертом <channel …>, а с тех пор сессия ни разу не вызвала инструмент reply
плагина, ход завершать нельзя: текст без reply никуда не уходит. Хук отдаёт
decision=block с причиной — Claude продолжает ход и отправляет ответ.

Читает транскрипт по transcript_path из stdin (Claude Code даёт его хуку Stop).
Ограничитель: не блокирует второй раз подряд (stop_hook_active), чтобы не
зациклиться, если ответить действительно нечем.
"""
import json
import sys


def _incoming(r):
    """Текст входящего записи транскрипта или None.: сообщение, пришедшее посреди хода,
    Claude Code пишет отдельной записью type=attachment, attachment.type=queued_command, текст — в prompt."""
    m = r.get("message") or {}
    c = m.get("content")
    if r.get("type") == "user" and m.get("role") == "user":
        return c if isinstance(c, str) else " ".join(
            (x.get("text", "") if isinstance(x, dict) else str(x)) for x in (c or []))
    a = r.get("attachment")
    if r.get("type") == "attachment" and isinstance(a, dict) and a.get("type") == "queued_command" and isinstance(a.get("prompt"), str):
        return a["prompt"]
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("stop_hook_active"):
        return 0
    path = data.get("transcript_path") or ""
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except Exception:
        return 0
    last_channel_idx = -1
    last_reply_idx = -1
    chat_id = ""
    for i, ln in enumerate(lines):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        m = r.get("message") or {}
        c = m.get("content")
        s = _incoming(r)
        if s is not None:
            # реакция (👍, ❤) — не вопрос, ответа не требует (просьба Мила качества)
            is_reaction = "type=\"reaction\"" in s or "[реакция]" in s
            # в режиме «наблюдатель» сообщение, где бота не звали, ответа не требует
            is_observe = "observe_only=\"true\"" in s
            # тик маховика (сам велит «хозяину не пиши»), записка файловой почты, сигнал сторожа (watch-*)
            # и поручение администратора с ответом запиской (canon/CHATS-ROUTING.md) ответа в чат не требуют — иначе хук толкает
            # Милу писать хозяину про тик. Только если ТАКОВЫ ВСЕ теги записи (b, Качество: «тик + вопрос хозяина» в одной
            # записи — вопрос не теряем); message_id — атрибут своего тега, не текст.
            tags = s.split("<channel ")[1:]
            def _quiet(t):
                mid = t.split(">", 1)[0].split("message_id=\"", 1)[1].split("\"", 1)[0] if "message_id=\"" in t.split(">", 1)[0] else ""
                return mid.startswith(("tick-", "filemail-", "watch-")) or (mid.startswith("senior-") and "не сообщением в чат" in t)
            no_reply = bool(tags) and all(_quiet(t) for t in tags)
            if "<channel" in s and "source=\"telegram\"" in s and not is_reaction and not is_observe and not no_reply:
                last_channel_idx = i
                j = s.find("chat_id=\"")
                if j >= 0:
                    chat_id = s[j + 9:].split("\"", 1)[0]
        if r.get("type") == "assistant" and isinstance(c, list):
            for x in c:
                if isinstance(x, dict) and x.get("type") == "tool_use" and "telegram__reply" in str(x.get("name", "")):
                    last_reply_idx = i
    # в неутверждённый чат отправить нельзя — не требуем reply
    if chat_id:
        try:
            import os as _os
            _acc = json.load(open(_os.path.expanduser("~/.claude/channels/telegram/access.json"), encoding="utf-8"))
            _ok = {str(k) for k in (_acc.get("groups") or {}).keys()} | {str(x) for x in (_acc.get("allowFrom") or [])}
            if _ok and chat_id not in _ok:
                return 0
        except Exception:
            pass
    # сообщение с @-упоминаниями, среди которых нет
    # моего бота, адресовано другому — не требуем reply (иначе второй голос в чате, где ведёт другой).
    # И осознанная тишина: последний текст хода с меткой [[silent]] — тоже не блокируем.
    if last_channel_idx >= 0 and last_reply_idx < last_channel_idx:
        try:
            import os as _os2, re as _re2
            me = (_os2.environ.get("BOT_USERNAME") or "").lstrip("@").lower()
            last_in = lines[last_channel_idx]
            body = _incoming(json.loads(last_in)) or ""
            inner = body.split(">", 1)[1] if ">" in body else body
            mentions = {m.lower() for m in _re2.findall(r"@([A-Za-z0-9_]{5,})", inner)}
            if me and mentions and me not in mentions:
                return 0
            # метку ищем во всех текстах хода, не только в последнем —
            # после [[silent]] модель часто делает ещё шаг (запись в журнал), и последняя запись уже без метки.
            for ln in lines[last_channel_idx:]:
                try:
                    r2 = json.loads(ln)
                except Exception:
                    continue
                if r2.get("type") == "assistant":
                    c2 = (r2.get("message") or {}).get("content")
                    txt = " ".join(x.get("text", "") for x in (c2 or []) if isinstance(x, dict) and x.get("type") == "text") if isinstance(c2, list) else str(c2 or "")
                    if "[[silent]]" in txt:
                        return 0
        except Exception:
            pass
    if last_channel_idx >= 0 and last_reply_idx < last_channel_idx:
        # хук стартует на 47–49 мс раньше,
        # чем последний текст хода допишется в транскрипт, и [[silent]] не виден. Сначала смотрим
        # текст хода из входа хука (если Claude Code его даёт), потом перечитываем транскрипт.
        if "[[silent]]" in str(data.get("last_assistant_message") or ""):
            return 0
        try:
            import time as _t
            _t.sleep(0.4)
            for ln in open(path, encoding="utf-8").read().splitlines()[last_channel_idx:]:
                try:
                    r3 = json.loads(ln)
                except Exception:
                    continue
                if r3.get("type") == "assistant" and "[[silent]]" in json.dumps(
                        (r3.get("message") or {}).get("content"), ensure_ascii=False):
                    return 0
        except Exception:
            pass
        reason = ("Ответ в чат НЕ отправлен: человек читает Telegram, а не этот текст. Вызови инструмент "
                  "mcp__plugin_mila-telegram_telegram__reply с chat_id=\"%s\" и текстом ответа "
                  "(одно сообщение, до 1000 знаков). Если ответить нечем — reply с одной строкой, что делаешь. Если молчать правильно (ведёт другой исполнитель) — закончи ход текстом с меткой [[silent]]."
                  % (chat_id or "<из тега channel>"))
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
