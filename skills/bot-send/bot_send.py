#!/usr/bin/env python3
"""bot_send.py — Мила пишет человеку от СВОЕГО бота и делает рассылку (владелец 13.10).
Модуль для движка агента (factory_launch.py): инструменты bot_send, bot_broadcast (превью → «✅» владельца → отправка).
Только stdlib. Включатель — env BOT_SEND=1 (по умолчанию выключено).

Правила (не обходятся параметрами):
- Писать можно только тому, кто сам хоть раз писал боту (known(user_id) — из conversations/dialogs движка).
- Вызов — только по слову владельца в его личке (owner_gate — проверяет движок: инструмент доступен только в сессии хозяина).
- Рассылка: сначала превью «N человек, текст» владельцу с кнопкой ✅; отправка — только confirm(preview_id) после нажатия.
- Не больше 20 сообщений в секунду; заблокировавшие бота (403) и сказавшие «стоп» — в стоп-лист, им больше не пишем.
- Тихие часы 22:00–08:00 по Ташкенту: рассылка встаёт в очередь на 08:00 (личное сообщение по прямому слову владельца уходит сразу).
- Каждое отправленное — в журнал (кому, когда, message_id) и в диалог человека как исходящее (record_outgoing), чтобы dialogs видел «наш ход закрыт».
"""
import json, os, re, time, urllib.request, urllib.error, uuid
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=5))
QUIET = (22, 8)            # с 22:00 до 08:00 по Ташкенту
RATE = 20                  # сообщений в секунду, не больше
PREVIEW_TTL = 3600         # превью рассылки живёт час
RETRY_MAX = 3              # 429 одному человеку — не больше трёх повторов
PAUSE_AUTO = 3600          # c (Качество, закон 3): пауза Telegram дольше часа — остаток только по новому ✅ владельца
RETRY_CAP = 60             # и не дольше минуты ожидания за раз
# CARD-MASK-1019 (утечка 19.10): номер карты (13–19 цифр, Луна) наружу не уходит — маска ****1234
_PAN = re.compile(r"(?<![\d+])(?:\d[ -]?){12,}\d(?![\d])")


def _luhn(d):
    t = 0
    for i, ch in enumerate(reversed(d)):
        x = int(ch)
        if i % 2:
            x = x * 2 - 9 if x > 4 else x * 2
        t += x
    return t % 10 == 0


def mask_cards(text, allow=None):
    """Номер карты (13–19 цифр подряд, пробелы/дефисы между группами, Луна) → ****1234. Внутри длинной цепочки групп ищем
    окно, которое проходит Луну («карта <номер> 100 USD» — сумма после номера не мешает)."""
    allow = {re.sub(r"\D", "", str(x)) for x in (allow if allow is not None else os.environ.get("CARD_ALLOW", "").split(",")) if str(x).strip()}   # CARD-ALLOW-1019

    def rep(m):
        txt = m.group(); parts = [g.span() for g in re.finditer(r"\d+", txt)]; out, pos, i = [], 0, 0
        while i < len(parts):
            cand = []
            for j in range(len(parts) - 1, i - 1, -1):
                d = re.sub(r"\D", "", txt[parts[i][0]:parts[j][1]])
                if 13 <= len(d) <= 19 and len(set(d)) > 1 and _luhn(d) and d not in allow:
                    cand.append((j, d))
            hit = next((c for c in cand if len(c[1]) == 16), cand[0] if cand else None)   # 16 цифр — самый частый номер; иначе самое длинное окно
            if not hit:
                i += 1; continue
            out.append(txt[pos:parts[i][0]] + "****" + hit[1][-4:]); pos = parts[hit[0]][1]; i = hit[0] + 1
        return "".join(out) + txt[pos:]
    return _PAN.sub(rep, str(text or ""))


class BotSend:
    def __init__(self, token, state_dir, known, record_outgoing=lambda uid, text, mid: None, api=None, now=lambda: datetime.now(TZ), sleep=time.sleep):
        """known(uid) -> bool: человек писал боту; record_outgoing — запись исходящего в диалог (движок); api(method, payload) -> dict — для тестов."""
        self.token, self.dir, self.known, self.record = token, state_dir, known, record_outgoing
        self.now, self.sleep = now, sleep
        self.api = api or self._api
        os.makedirs(state_dir, exist_ok=True)
        self.journal = os.path.join(state_dir, "bot_send.jsonl")
        self.stop_f = os.path.join(state_dir, "stoplist.json")
        self.prev_f = os.path.join(state_dir, "broadcast_previews.json")
        self.queue_f = os.path.join(state_dir, "broadcast_queue.json")

    # ── Telegram ──
    def _api(self, method, payload):
        r = urllib.request.Request(f"https://api.telegram.org/bot{self.token}/{method}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try: return json.load(urllib.request.urlopen(r, timeout=20))
        except urllib.error.HTTPError as e:
            try: return json.loads(e.read())
            except Exception: return {"ok": False, "error_code": e.code, "description": str(e)}

    # ── файлы ──
    def _rj(self, p, d):
        try: return json.load(open(p))
        except Exception: return d

    def _wj(self, p, v):
        tmp = p + ".tmp"; json.dump(v, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, p)

    def _log(self, rec):
        open(self.journal, "a").write(json.dumps(dict({"t": self.now().isoformat(timespec="seconds")}, **rec), ensure_ascii=False) + "\n")

    def stoplist(self): return set(self._rj(self.stop_f, []))

    def stop_add(self, uid, why):
        s = self.stoplist(); s.add(str(uid)); self._wj(self.stop_f, sorted(s)); self._log({"stop": str(uid), "why": why})

    def clock(self): return self.now().timestamp()   # c: одно время для сроков (превью, пауза, очередь) — тесты с подменой now двигают всё

    def quiet(self, ts=None):
        h = (datetime.fromtimestamp(ts, TZ) if ts else self.now()).hour; return h >= QUIET[0] or h < QUIET[1]

    # ── одно сообщение ──
    def _markup(self, buttons):
        if not buttons: return {}
        rows = []
        for row in buttons[:6]:
            r = []
            for b in row[:3]:
                if b.get("url", "").startswith("https://"): r.append({"text": str(b["label"])[:40], "url": b["url"]})
            if r: rows.append(r)
        return {"reply_markup": {"inline_keyboard": rows}} if rows else {}

    def send(self, user, text, buttons=None, kind="personal"):
        """bot_send: человеку, который писал боту. user — id (число) или @username (ищется движком в known)."""
        uid = str(user).strip().lstrip("@")
        text = mask_cards(str(text or "").strip())
        if not text: return {"ok": False, "error": "пустой текст"}
        if len(text) > 4096: return {"ok": False, "error": "текст длиннее 4096 знаков"}
        if not self.known(uid): return {"ok": False, "error": "этот человек не писал боту — первым писать нельзя"}
        if uid in self.stoplist(): return {"ok": False, "error": "человек отписался или заблокировал бота"}
        r = self.api("sendMessage", dict({"chat_id": uid, "text": text, "disable_web_page_preview": True}, **self._markup(buttons)))
        if r.get("ok"):
            mid = r["result"]["message_id"]; self.record(uid, text, mid); self._log({"kind": kind, "to": uid, "mid": mid})
            return {"ok": True, "message_id": mid}
        code, desc = r.get("error_code"), str(r.get("description", ""))
        # в стоп-лист — только сам человек ушёл (403: заблокировал/удалён); «chat not found» — чаще наш неверный адрес (@username), не его отказ
        if code == 403 or re.search(r"blocked|deactivated", desc, re.I): self.stop_add(uid, "403: " + desc[:80])
        if code == 429: return {"ok": False, "retry_after": (r.get("parameters") or {}).get("retry_after", 5), "error": "лимит Telegram"}
        self._log({"kind": kind, "to": uid, "error": f"{code} {desc[:120]}"})
        return {"ok": False, "error": f"{code} {desc[:120]}"}

    # ── рассылка ──
    def preview(self, user_ids, text, segment=""):
        """Шаг 1: превью владельцу. Возвращает preview_id и N (без стоп-листа и незнакомых)."""
        text = mask_cards(str(text or "").strip())
        if not text: return {"error": "пустой текст — рассылку не собираю", "n": 0}
        stop = self.stoplist()
        to = [u for u in dict.fromkeys(str(x).strip().lstrip("@") for x in user_ids) if self.known(u) and u not in stop]   # 111 и "111" — один человек
        if not to: return {"error": "некому: никто из списка не писал боту или все в стоп-листе", "n": 0}
        pid = uuid.uuid4().hex[:10]
        pv = self._rj(self.prev_f, {}); now = self.clock()
        pv = {k: v for k, v in pv.items() if now - v["t"] < PREVIEW_TTL}
        pv[pid] = {"t": now, "to": to, "text": str(text), "segment": segment}; self._wj(self.prev_f, pv)
        return {"preview_id": pid, "n": len(to), "segment": segment, "text": str(text),
                "card": f"Рассылка: {len(to)} человек{'' if not segment else ' · ' + segment}.\n\n{text}",
                "buttons": [[{"label": f"✅ Отправить {len(to)}", "choice": "bc_ok_" + pid}, {"label": "Отмена", "choice": "bc_no_" + pid}]]}

    def confirm(self, pid):
        """Шаг 2: после «✅» владельца. В тихие часы — в очередь на 08:00."""
        pv = self._rj(self.prev_f, {}); p = pv.pop(pid, None); self._wj(self.prev_f, pv)
        if p and p.get("not_before", 0) > self.clock():
            # c2: «да» владельца сейчас на этот текст и этот остаток — уйдёт в срок Telegram, сам он ничего не досылает
            q = self._rj(self.queue_f, []); q.append(dict(p, t=self.clock(), qid=pid)); self._wj(self.queue_f, q)
            self._log({"kind": "broadcast", "queued": len(p["to"]), "segment": p["segment"], "not_before": p["not_before"]})
            return {"ok": True, "queued": len(p["to"]), "note": "уйдёт после " + datetime.fromtimestamp(p["not_before"], TZ).strftime("%d.%m %H:%M") + " по Ташкенту",
                    "buttons": [[{"label": "Отменить отправку " + datetime.fromtimestamp(p["not_before"], TZ).strftime("%d.%m"), "choice": "bc_cancel_" + pid}]]}   # c3 (Качество): до срока владелец может отменить
        if not p or self.clock() - p["t"] > PREVIEW_TTL: return {"ok": False, "error": "превью нет или устарело — сделайте новое"}
        if self.quiet():
            q = self._rj(self.queue_f, []); q.append(dict(p, qid=pid)); self._wj(self.queue_f, q)   # c4: qid и ночной — отменяемо
            self._log({"kind": "broadcast", "queued": len(p["to"]), "segment": p["segment"]})
            return {"ok": True, "queued": len(p["to"]), "note": "тихие часы — уйдёт в 08:00 по Ташкенту",
                    "buttons": [[{"label": "Отменить отправку 08:00", "choice": "bc_cancel_" + pid}]]}
        return self._run(p)

    def _run(self, p):
        sent = failed = 0; t0 = time.time(); k = 0; stop = self.stoplist()
        for i, uid in enumerate(p["to"]):
            if uid in stop: continue   # b: отписался, пока рассылка ждала (очередь, пауза) — не пишем
            r = self.send(uid, p["text"], kind="broadcast")
            # b (Разработка): Telegram велит ждать дольше минуты — лимит на весь бот, дальше будет 429 каждому.
            # Останавливаю рассылку, остаток — в очередь с not_before, ушедшим второй раз не шлю.
            if r.get("retry_after") and float(r["retry_after"]) > RETRY_CAP:
                until = self.clock() + float(r["retry_after"]); left = p["to"][i:]
                when = datetime.fromtimestamp(until, TZ).strftime("%d.%m %H:%M") + " по Ташкенту"
                if float(r["retry_after"]) > PAUSE_AUTO or self.quiet(until):
                    # c: вчерашнее согласие не считается — остаток не уходит сам, владельцу новое превью на тот же текст
                    pid = uuid.uuid4().hex[:10]; pv = self._rj(self.prev_f, {})
                    pv[pid] = {"t": until, "not_before": until, "to": left, "text": p["text"], "segment": p["segment"]}; self._wj(self.prev_f, pv)
                    self._log({"kind": "broadcast", "segment": p["segment"], "sent": sent, "failed": failed, "paused_ask": len(left)})
                    return {"ok": False, "paused": True, "sent": sent, "failed": failed, "left": len(left), "n": len(left), "until": when, "preview_id": pid,
                            "card": f"Рассылка встала: ушло {sent}, осталось {len(left)}. Telegram разрешит после {when}. Отправить остаток тогда?",
                            "buttons": [[{"label": f"✅ Отправить {len(left)}", "choice": "bc_ok_" + pid}, {"label": "Отмена", "choice": "bc_no_" + pid}]]}
                q = self._rj(self.queue_f, []); q.append(dict(p, to=p["to"][i:], not_before=until)); self._wj(self.queue_f, q)
                self._log({"kind": "broadcast", "segment": p["segment"], "sent": sent, "failed": failed, "paused": len(p["to"]) - i})
                return {"ok": False, "paused": True, "sent": sent, "failed": failed, "left": len(p["to"]) - i,
                        "until": datetime.fromtimestamp(until, TZ).strftime("%d.%m %H:%M") + " по Ташкенту", "note": "Telegram ограничил рассылку — остаток уйдёт сам после срока"}
            tries = 0
            while r.get("retry_after") and tries < RETRY_MAX:
                self.sleep(min(float(r["retry_after"]), RETRY_CAP)); tries += 1; r = self.send(uid, p["text"], kind="broadcast")
            sent += bool(r.get("ok")); failed += not r.get("ok"); k += 1
            if k % RATE == 0:
                el = time.time() - t0
                if el < 1: self.sleep(1 - el)
                t0 = time.time()
        self._log({"kind": "broadcast", "segment": p["segment"], "sent": sent, "failed": failed})
        return {"ok": True, "sent": sent, "failed": failed}

    def cancel(self, qid):
        """c3: «Отменить» у отложенного остатка — до срока; после ухода — уже нечего отменять."""
        if not qid: return {"ok": False, "error": "отменять нечего — нет номера отправки"}   # c4: None/"" не снимает чужие записи
        q = self._rj(self.queue_f, []); keep = [p for p in q if p.get("qid") != qid]
        if len(keep) == len(q): return {"ok": False, "error": "отменять нечего — уже ушло или не было"}
        self._wj(self.queue_f, keep); self._log({"kind": "broadcast", "cancelled": qid})
        return {"ok": True, "cancelled": sum(len(p["to"]) for p in q if p.get("qid") == qid)}

    def flush_queue(self):
        """Вызывать кроном каждые 10 мин: вне тихих часов отправляет отложенные рассылки."""
        if self.quiet(): return {"ok": True, "waiting": len(self._rj(self.queue_f, []))}
        q = self._rj(self.queue_f, []); now = self.clock()
        due = [p for p in q if p.get("not_before", 0) <= now]; self._wj(self.queue_f, [p for p in q if p.get("not_before", 0) > now])   # b: пауза Telegram — ждёт своего срока
        return {"ok": True, "flushed": [self._run(p) for p in due]}

    def unsubscribe_text(self, uid, text):
        """Входящее «стоп / отписаться / to'xtat» — в стоп-лист (движок зовёт на каждом входящем)."""
        if re.fullmatch(r"\s*/?(стоп|stop|отписаться|отписка|to['ʻ’]?xtat|bekor)\s*[.!]?\s*", str(text or ""), re.I): self.stop_add(uid, "сам: " + text.strip()[:20]); return True
        return False
