#!/usr/bin/env python3
"""Расчёт сроков cron для «Барабана» (RASPISANIE-1025, шаг 2) — только stdlib, без croniter.

Выражение — 5 полей: минута час день-месяца месяц день-недели (0 и 7 — воскресенье).
В поле: *, N, A-B, списки через запятую, шаг /N (*/15, 10-50/10). Имена (mon, jan) не принимаю — однозначнее числами.
День месяца и день недели — как в классическом cron: заданы оба (не *) — срок, если совпало ЛЮБОЕ из двух.
Время — в поясе хозяина (zoneinfo); переход на летнее время, где он есть, считается по местным часам.

  parse(expr) → Spec (ValueError с понятной причиной)
  Spec.next_after(dt) → ближайший срок строго после dt
  Spec.last_at_or_before(dt) → последний срок ≤ dt (или None, если за 366 дней не было)
  Spec.min_step_minutes() → самый короткий шаг между сроками в сутках (для лимита «не чаще раза в 5 мин»)
"""
import datetime

FIELDS = (("минута", 0, 59), ("час", 0, 23), ("день месяца", 1, 31), ("месяц", 1, 12), ("день недели", 0, 7))
MIN_STEP = 5


def _field(text, name, lo, hi):
    out = set()
    for part in text.split(","):
        if not part:
            raise ValueError("%s: пустой элемент в «%s»" % (name, text))
        rng, _, step = part.partition("/")
        if step:
            if not step.isdigit() or int(step) < 1:
                raise ValueError("%s: шаг «/%s» — целое ≥ 1" % (name, step))
            step = int(step)
        else:
            step = 1
        if rng == "*":
            a, b = lo, hi
        elif "-" in rng:
            x, _, y = rng.partition("-")
            if not (x.isdigit() and y.isdigit()):
                raise ValueError("%s: «%s» — нужен диапазон чисел A-B" % (name, rng))
            a, b = int(x), int(y)
            if a > b:
                raise ValueError("%s: диапазон %d-%d наоборот" % (name, a, b))
        elif rng.isdigit():
            a = b = int(rng)
            if step != 1:   # «5/10» = с 5 до конца шагом 10, как в cron
                b = hi
        else:
            raise ValueError("%s: «%s» — только числа, *, A-B, /N" % (name, rng))
        if a < lo or b > hi:
            raise ValueError("%s: %s вне %d–%d" % (name, rng, lo, hi))
        out.update(range(a, b + 1, step))
    return out


class Spec:
    def __init__(self, expr, mins, hours, doms, months, dows, dom_star, dow_star):
        self.expr, self.mins, self.hours, self.doms, self.months, self.dows = expr, mins, hours, doms, months, dows
        self.dom_star, self.dow_star = dom_star, dow_star

    def _day_ok(self, d):
        if d.month not in self.months:
            return False
        dom = d.day in self.doms
        dow = (d.isoweekday() % 7) in self.dows   # Пн=1 … Вс=0
        if self.dom_star and self.dow_star:
            return True
        if self.dom_star:
            return dow
        if self.dow_star:
            return dom
        return dom or dow   # оба заданы — любое (классический cron)

    def _times(self):
        return sorted((h, m) for h in self.hours for m in self.mins)

    def next_after(self, dt):
        """Ближайший срок строго после dt (aware datetime). Ищет до 4 лет вперёд (29.02 по понедельникам)."""
        tz = dt.tzinfo
        day = dt.date()
        times = self._times()
        for i in range(366 * 4 + 1):
            d = day + datetime.timedelta(days=i)
            if not self._day_ok(d):
                continue
            for h, m in times:
                t = datetime.datetime(d.year, d.month, d.day, h, m, tzinfo=tz)
                if t > dt:
                    return t
        return None

    def last_at_or_before(self, dt):
        """Последний срок ≤ dt — Барабану: «созрел ли срок с прошлой доставки»."""
        tz = dt.tzinfo
        day = dt.date()
        times = self._times()[::-1]
        for i in range(367):
            d = day - datetime.timedelta(days=i)
            if not self._day_ok(d):
                continue
            for h, m in times:
                t = datetime.datetime(d.year, d.month, d.day, h, m, tzinfo=tz)
                if t <= dt:
                    return t
        return None

    def min_step_minutes(self):
        ts = [h * 60 + m for h, m in self._times()]
        if len(ts) == 1:
            return 24 * 60
        gaps = [b - a for a, b in zip(ts, ts[1:])] + [ts[0] + 24 * 60 - ts[-1]]
        return min(gaps)


def parse(expr, min_step=MIN_STEP):
    if not isinstance(expr, str):
        raise ValueError("cron — строка из 5 полей")
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError("cron — 5 полей «мин час день месяц день_недели», дано %d" % len(parts))
    sets = [_field(p, n, lo, hi) for p, (n, lo, hi) in zip(parts, FIELDS)]
    dows = {d % 7 for d in sets[4]}
    s = Spec(" ".join(parts), sets[0], sets[1], sets[2], sets[3], dows, parts[2] == "*", parts[4] == "*")
    if min_step and s.min_step_minutes() < min_step:
        raise ValueError("чаще раза в %d мин нельзя (шаг %d мин)" % (min_step, s.min_step_minutes()))
    if s.next_after(datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)) is None:
        raise ValueError("такого дня не бывает (например, 31 число в феврале)")
    return s
