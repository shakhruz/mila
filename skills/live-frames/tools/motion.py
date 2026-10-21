#!/usr/bin/env python3
"""Движок «живых» кадров для выпусков Милы Видео: живой фон, элементы появляются по словам голоса, переходы со вспышкой,
звуки (вжух, поп, тики счётчика, удар), тихая музыкальная подложка с приглушением под голос. Только Pillow + numpy + ffmpeg.
  motion.py SPEC.py OUT.mp4            SPEC.py задаёт VOICE (путь), SCENES (список), W/H по желанию (1920×1080 или 1080×1920)
Сцена: {"t": начало, "bg": "dark"|"warm"|"blue", "els": [элементы]}; конец сцены — начало следующей (последняя — до конца голоса).
Элементы (at — с какого момента, секунды от начала ролика):
  ("text", txt, x, y, size, at, {"color":..., "anchor":"mm", "anim":"rise"|"pop"|"type", "w": ширина-переноса})
  ("icon", name, x, y, size, at)                — эмодзи Twemoji из tools/emoji, «прыжок» с перелётом
  ("glass", x0, y0, x1, y1, at)                 — стеклянная карточка
  ("pill", txt, x, y, size, at, {"color":...})  — пилюля-подпись
  ("count", a, b, fmt, x, y, size, at, dur, {"color":...}) — счётчик с тиками
  ("bar", x0, y, x1, frac, at, dur, {"color":..., "label":...}) — полоса заполняется до доли
  ("arrow", x0, y0, x1, y1, at, dur, {"color":...}) — стрелка рисуется
  ("ring", x, y, r, frac, at, dur, {"color":...}) — кольцо-прогресс
  ("strike", x0, y, x1, at, dur)                — зачёркивание
Звуки ставятся сами: вжух на смене сцены, поп на иконке/пилюле, тики на счётчике, удар на конце счётчика."""
import importlib.util, json, math, os, random, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "PTSans-Bold.ttf")
EMO = os.path.join(HERE, "emoji")
FPS = 30
PAL = {"dark": [(40, 46, 90), (90, 40, 110), (20, 70, 110)], "warm": [(235, 120, 60), (180, 50, 120), (240, 170, 70)],
       "blue": [(20, 90, 170), (30, 40, 120), (60, 160, 200)]}
ACC, WHITE, MUTED, RED, GREEN = (255, 216, 77), (255, 255, 255), (170, 178, 200), (255, 95, 95), (110, 220, 140)
_fc, _ic = {}, {}

def font(s):
    if s not in _fc: _fc[s] = ImageFont.truetype(FONT, s)
    return _fc[s]

def icon(name, s):
    k = (name, s)
    if k not in _ic: _ic[k] = Image.open(os.path.join(EMO, name + ".png")).convert("RGBA").resize((s, s), Image.LANCZOS)
    return _ic[k]

def clamp(x): return max(0.0, min(1.0, x))
def out_cubic(p): return 1 - (1 - p) ** 3
def out_back(p, s=1.7): p -= 1; return 1 + (s + 1) * p ** 3 + s * p ** 2

class BG:
    """Живой фон: размытые цветные пятна медленно плывут + точечная сетка с параллаксом."""
    def __init__(self, W, H, seed=3):
        r = random.Random(seed); self.W, self.H = W, H; self.w, self.h = W // 5, H // 5
        self.blobs = [(r.random(), r.random(), r.uniform(0.18, 0.35), r.uniform(0, 6.28), r.uniform(0.03, 0.07), k % 3) for k in range(6)]
        yy, xx = np.mgrid[0:self.h, 0:self.w]; self.xx, self.yy = xx / self.w, yy / self.h * (self.h / self.w)
        grid = Image.new("RGBA", (W + 120, H + 120), (0, 0, 0, 0)); d = ImageDraw.Draw(grid)
        for y in range(0, H + 120, 40):
            for x in range(0, W + 120, 40): d.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(255, 255, 255, 22))
        self.grid = grid
    def frame(self, t, pal):
        img = np.zeros((self.h, self.w, 3), np.float32) + np.array([9, 10, 16], np.float32)
        for (x0, y0, r, ph, sp, c) in self.blobs:
            cx = x0 + 0.12 * math.sin(ph + t * sp * 6); cy = (y0 + 0.10 * math.cos(ph + t * sp * 5)) * (self.h / self.w)
            g = np.exp(-((self.xx - cx) ** 2 + (self.yy - cy) ** 2) / (2 * (r * 0.6) ** 2))[..., None]
            img += g * np.array(PAL[pal][c], np.float32) * 0.55
        im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((self.W, self.H), Image.BICUBIC).convert("RGBA")
        ox, oy = int(60 + 40 * math.sin(t * 0.15)), int(60 + 30 * math.cos(t * 0.11))
        im.alpha_composite(self.grid.crop((ox, oy, ox + self.W, oy + self.H)))
        return im

def draw_el(L, d, e, t, ev):
    k = e[0]
    if k == "text":
        _, txt, x, y, s, at, *o = e; o = o[0] if o else {}
        p = clamp((t - at) / 0.35)
        if p <= 0: return
        col = o.get("color", WHITE); anim = o.get("anim", "rise"); f = font(s)
        lines = [txt]
        if o.get("w"):
            lines, cur = [], ""
            for wd in txt.split():
                if d.textlength((cur + " " + wd).strip(), font=f) > o["w"]: lines.append(cur); cur = wd
                else: cur = (cur + " " + wd).strip()
            lines.append(cur)
        if anim == "type":
            n = int(len(txt) * clamp((t - at) / max(0.3, len(txt) * 0.035))); lines = [txt[:n]]; p = 1
        dy = (1 - out_cubic(p)) * 40 if anim == "rise" else 0
        sc = out_back(p) if anim == "pop" else 1
        a = int(255 * out_cubic(p)); lh = int(s * 1.18); y0 = y - (len(lines) - 1) * lh / 2
        for i, ln in enumerate(lines):
            if sc != 1:
                fs = font(max(8, int(s * sc))); d.text((x, y0 + i * lh + dy), ln, font=fs, fill=col + (a,), anchor=o.get("anchor", "mm"))
            else:
                d.text((x, y0 + i * lh + dy), ln, font=f, fill=col + (a,), anchor=o.get("anchor", "mm"))
    elif k == "icon":
        _, name, x, y, s, at = e; p = clamp((t - at) / 0.45)
        if p <= 0: return
        sc = max(0.05, out_back(p, 2.2)); sz = max(4, int(s * sc)); bob = 8 * math.sin((t - at) * 2.2)
        L.alpha_composite(icon(name, sz), (int(x - sz / 2), int(y - sz / 2 + bob)))
    elif k == "glass":
        _, x0, y0, x1, y1, at = e; p = clamp((t - at) / 0.4)
        if p <= 0: return
        a = out_cubic(p); dy = (1 - a) * 30
        d.rounded_rectangle((x0, y0 + dy, x1, y1 + dy), 28, fill=(255, 255, 255, int(28 * a)), outline=(255, 255, 255, int(70 * a)), width=2)
    elif k == "pill":
        _, txt, x, y, s, at, *o = e; o = o[0] if o else {}; p = clamp((t - at) / 0.35)
        if p <= 0: return
        f = font(s); tw = d.textlength(txt, font=f); sc = out_back(p); a = int(255 * out_cubic(p))
        w2, h2 = (tw / 2 + s * 0.7) * sc, s * 0.95 * sc
        d.rounded_rectangle((x - w2, y - h2, x + w2, y + h2), int(h2), fill=o.get("color", (255, 255, 255)) + (int(a * 0.16),), outline=o.get("color", (255, 255, 255)) + (int(a * 0.6),), width=2)
        d.text((x, y), txt, font=f, fill=o.get("tcolor", WHITE) + (a,), anchor="mm")
    elif k == "count":
        _, a0, b0, fmt, x, y, s, at, dur, *o = e; o = o[0] if o else {}; p = clamp((t - at) / dur)
        if t < at: return
        v = a0 + (b0 - a0) * out_cubic(p); txt = fmt.format(v).replace(".", ",")
        pulse = 1 + 0.08 * max(0, 1 - (t - at - dur) / 0.25) if t > at + dur else 1
        d.text((x, y), txt, font=font(int(s * pulse)), fill=o.get("color", ACC) + (255,), anchor="mm")
    elif k == "bar":
        _, x0, y, x1, frac, at, dur, *o = e; o = o[0] if o else {}; p = clamp((t - at) / dur)
        if t < at: return
        h = o.get("h", 56); col = o.get("color", RED)
        d.rounded_rectangle((x0, y - h / 2, x1, y + h / 2), h // 2, fill=(255, 255, 255, 30))
        xe = x0 + (x1 - x0) * frac * out_cubic(p)
        if xe > x0 + h: d.rounded_rectangle((x0, y - h / 2, xe, y + h / 2), h // 2, fill=col + (235,))
    elif k == "arrow":
        _, x0, y0, x1, y1, at, dur, *o = e; o = o[0] if o else {}; p = clamp((t - at) / dur)
        if p <= 0: return
        col = o.get("color", ACC) + (255,); xe, ye = x0 + (x1 - x0) * out_cubic(p), y0 + (y1 - y0) * out_cubic(p)
        d.line((x0, y0, xe, ye), fill=col, width=7)
        if p > 0.6:
            ang = math.atan2(y1 - y0, x1 - x0); s = 26
            d.polygon([(xe, ye), (xe - s * math.cos(ang - 0.5), ye - s * math.sin(ang - 0.5)), (xe - s * math.cos(ang + 0.5), ye - s * math.sin(ang + 0.5))], fill=col)
    elif k == "ring":
        _, x, y, r, frac, at, dur, *o = e; o = o[0] if o else {}; p = clamp((t - at) / dur)
        if t < at: return
        d.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, 40), width=18)
        d.arc((x - r, y - r, x + r, y + r), -90, -90 + 360 * frac * out_cubic(p), fill=o.get("color", ACC) + (255,), width=18)
    elif k == "strike":
        _, x0, y, x1, at, dur = e; p = clamp((t - at) / dur)
        if p > 0: d.line((x0, y, x0 + (x1 - x0) * out_cubic(p), y), fill=RED + (255,), width=10)

def sfx_events(scenes, total):
    ev = []
    for i, sc in enumerate(scenes):
        if i: ev.append(("whoosh", sc["t"] - 0.18, 0.9))
        for e in sc["els"]:
            if e[0] in ("icon", "pill"): ev.append(("pop", e[5] if e[0] == "icon" else e[5], 0.8))
            if e[0] == "count":
                at, dur = e[7], e[8]
                for q in range(10): ev.append(("tick", at + dur * (1 - (1 - q / 10) ** 0.5), 0.5))
                ev.append(("impact", at + dur, 1.0)); ev.append(("riser", at - 0.9, 0.6))
            if e[0] == "strike": ev.append(("swipe", e[4], 0.7))
    return [x for x in ev if 0 <= x[1] < total]

def synth(name, sr=48000):
    rng = np.random.default_rng(1)
    if name == "whoosh":
        n = int(0.55 * sr); x = rng.standard_normal(n); env = np.sin(np.linspace(0, np.pi, n)) ** 2
        f = np.linspace(400, 5000, n); y = np.zeros(n); a = 0
        for i in range(n): a += (x[i] - a) * min(1, f[i] / sr * 6.28); y[i] = a     # бегущий фильтр
        return y * env * 0.5
    if name == "swipe":
        n = int(0.3 * sr); x = rng.standard_normal(n); return x * np.exp(-np.linspace(0, 6, n)) * 0.15
    if name == "pop":
        n = int(0.14 * sr); t = np.arange(n) / sr; f = 900 * np.exp(-t * 18) + 400
        return np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 30) * 0.45
    if name == "tick":
        n = int(0.02 * sr); return rng.standard_normal(n) * np.exp(-np.linspace(0, 8, n)) * 0.25
    if name == "impact":
        n = int(0.7 * sr); t = np.arange(n) / sr
        return (np.sin(2 * np.pi * 55 * t) * np.exp(-t * 6) * 0.8 + rng.standard_normal(n) * np.exp(-t * 25) * 0.25)
    if name == "riser":
        n = int(0.9 * sr); t = np.arange(n) / sr; return np.sin(2 * np.pi * (300 + 600 * t / 0.9) * t) * (t / 0.9) ** 2 * 0.12

def music(total, sr=48000):
    """Тихая подложка: Am–F–C–G по 4 с, мягкие синусы с медленной атакой."""
    chords = [[220, 261.6, 329.6], [174.6, 220, 261.6], [130.8, 196, 261.6], [196, 246.9, 293.7]]
    n = int(total * sr); y = np.zeros(n); t = np.arange(int(4 * sr)) / sr
    env = np.minimum(1, t / 1.2) * np.minimum(1, (4 - t) / 1.2)
    for k in range(int(total // 4) + 1):
        ch = chords[k % 4]; s = sum(np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t) for f in ch) + 0.6 * np.sin(np.pi * ch[0] * t)
        a = k * len(t); b = min(n, a + len(t))
        if a < n: y[a:b] += (s * env)[: b - a]
    return y / np.abs(y).max() * 0.25

def main():
    spec_p, out = sys.argv[1], sys.argv[2]
    sp = importlib.util.spec_from_file_location("spec", spec_p); S = importlib.util.module_from_spec(sp); sp.loader.exec_module(S)
    W, H = getattr(S, "W", 1920), getattr(S, "H", 1080)
    total = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", S.VOICE])) + getattr(S, "TAIL", 1.0)
    scenes = S.SCENES; bg = BG(W, H); tmp = tempfile.mkdtemp(prefix="motion-")
    vid = os.path.join(tmp, "v.mp4")
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-threads", "4", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", vid], stdin=subprocess.PIPE)
    starts = [s["t"] for s in scenes] + [total]
    for fi in range(int(total * FPS)):
        t = fi / FPS; si = max(i for i in range(len(scenes)) if scenes[i]["t"] <= t) if t >= scenes[0]["t"] else 0
        sc = scenes[si]; im = bg.frame(t, sc.get("bg", "dark"))
        L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
        for e in sc["els"]: draw_el(L, d, e, t, None)
        # медленный наезд камеры на слой с элементами
        ps = (t - sc["t"]) / max(0.1, starts[si + 1] - sc["t"]); z = 1 + 0.035 * ps
        if z > 1.001:
            L = L.resize((int(W * z), int(H * z)), Image.BILINEAR); ox, oy = (L.width - W) // 2, (L.height - H) // 2; L = L.crop((ox, oy, ox + W, oy + H))
        im.alpha_composite(L)
        # переход: вспышка и «въезд» первые 0,25 с сцены
        q = (t - sc["t"]) / 0.2
        if si and 0 <= q < 1:
            z2 = 1 + 0.08 * (1 - out_cubic(q)); im = im.resize((int(W * z2), int(H * z2)), Image.BILINEAR)
            ox, oy = (im.width - W) // 2, (im.height - H) // 2; im = im.crop((ox, oy, ox + W, oy + H))
            im = Image.blend(im, Image.new("RGBA", (W, H), (255, 255, 255, 255)), 0.35 * (1 - q) ** 3)
        ff.stdin.write(im.convert("RGB").tobytes())
    ff.stdin.close(); ff.wait()
    # звук: голос + подложка (приглушается под голос) + эффекты
    sr = 48000; n = int(total * sr); fx = np.zeros(n)
    for name, at, g in sfx_events(scenes, total):
        s = synth(name); a = int(at * sr); b = min(n, a + len(s)); fx[a:b] += s[: b - a] * g
    np.clip(fx, -1, 1, out=fx)
    for nm, arr in (("fx", fx), ("mus", music(total))):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f64le", "-ar", str(sr), "-ac", "1", "-i", "-", os.path.join(tmp, nm + ".wav")], input=arr.astype(np.float64).tobytes(), check=True)
    mus_db = getattr(S, "MUSIC_DB", -14)
    fc = (f"[1:a]aresample={sr},aformat=channel_layouts=stereo,adelay={int(getattr(S, 'VOICE_AT', 0.0) * 1000)}:all=1,apad[v];[v]asplit[v1][v2];"
          f"[3:a]aformat=channel_layouts=stereo,volume={mus_db}dB[m];[m][v2]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=400[md];"
          f"[2:a]aformat=channel_layouts=stereo,volume=-6dB[f];[v1][md][f]amix=inputs=3:normalize=0:duration=longest,atrim=0:{total:.2f},loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", vid, "-i", S.VOICE, "-i", os.path.join(tmp, "fx.wav"), "-i", os.path.join(tmp, "mus.wav"),
                    "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True)
    print(json.dumps({"out": out, "sec": round(total, 1), "scenes": len(scenes), "sfx": len(sfx_events(scenes, total))}, ensure_ascii=False))

if __name__ == "__main__": main()
