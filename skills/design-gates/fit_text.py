#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Влезает ли текст: одна проверка для всех визуальных навыков (слайды, рилсы, стикеры, уроки, обложки).

21.10.2026 одна и та же поломка нашлась в четырёх силах за день: длинная подпись не переносилась,
кегль ужимался до мелкого, строка уходила за край или налезала на соседний блок, а скрипт писал «ok».
Правило: перенос по словам → самый крупный кегль, при котором текст в N строк и в зону →
не влезает и на минимуме — ошибка ДО записи файла, с советом «сократите до K слов».

Из Python:
    from fit_text import fit, advise
    r = fit("Текст подписи", "/path/font.ttf", size=64, min_size=40, max_width=900, max_lines=2, max_height=None)
    if r is None: sys.exit(advise("Текст подписи", font, 64, 40, 900, 2))   # → «… сократите до K слов»
    size, lines = r

Из оболочки:
    fit_text.py --font F.ttf --size 64 --min 40 --width 900 --lines 2 [--height 300] "текст"   → JSON, код 4 если не влезает
Нужен Pillow. Узбекский ʻ (U+02BB) меряется как есть; если шрифт рисует его с отступом — подменяйте при отрисовке.
"""
import argparse, json, sys

LINE = 1.18   # межстрочный шаг по умолчанию, в долях кегля


def _measure(font_path, size, stroke=0):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(font_path, size)
    d = ImageDraw.Draw(Image.new("L", (8, 8)))
    def w(t):
        b = d.textbbox((0, 0), t, font=f, stroke_width=stroke)
        return b[2] - b[0]
    return w


def wrap(text, width_of, max_width):
    """Перенос по словам; «\\n» в тексте — жёсткий перенос."""
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split():
            t = (cur + " " + word).strip()
            if cur and width_of(t) > max_width:
                lines.append(cur); cur = word
            else:
                cur = t
        lines.append(cur)
    return lines


def fit(text, font_path, size, min_size, max_width, max_lines, max_height=None, step=2, stroke=None, line=LINE):
    """(кегль, строки) для самого крупного кегля ≤ size, где строк ≤ max_lines, каждая ≤ max_width
    и (если задано) высота ≤ max_height. Не влезает и на min_size — None."""
    s = size
    while s >= min_size:
        w = _measure(font_path, s, stroke if stroke is not None else 0)
        ls = wrap(text, w, max_width)
        if len(ls) <= max_lines and all(w(l) <= max_width for l in ls) and (max_height is None or len(ls) * s * line <= max_height):
            return s, ls
        s -= step
    return None


def advise(text, font_path, size, min_size, max_width, max_lines, max_height=None, what="текст", **kw):
    """Строка-совет для ошибки: сколько слов оставить, чтобы влезло."""
    words = str(text).split()
    keep = len(words)
    while keep > 1 and fit(" ".join(words[:keep]), font_path, size, min_size, max_width, max_lines, max_height, **kw) is None:
        keep -= 1
    return f"{what} ({len(words)} слов) не влезает в {max_lines} стр. — сократите до {keep} слов или разбейте на два кадра"


def main():
    ap = argparse.ArgumentParser(description="влезает ли текст в зону")
    ap.add_argument("text"); ap.add_argument("--font", required=True)
    ap.add_argument("--size", type=int, required=True); ap.add_argument("--min", type=int, required=True)
    ap.add_argument("--width", type=int, required=True); ap.add_argument("--lines", type=int, default=2)
    ap.add_argument("--height", type=int); ap.add_argument("--stroke", type=int, default=0)
    a = ap.parse_args()
    r = fit(a.text, a.font, a.size, a.min, a.width, a.lines, a.height, stroke=a.stroke)
    if r is None:
        print(json.dumps({"ok": False, "advice": advise(a.text, a.font, a.size, a.min, a.width, a.lines, a.height, stroke=a.stroke)}, ensure_ascii=False))
        return 4
    print(json.dumps({"ok": True, "size": r[0], "lines": r[1]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
