#!/usr/bin/env python3
"""Локальное распознавание со словами (faster-whisper, CPU, бесплатно): stt_words.py ролик.mp4 [...] → ролик.words.json
Язык — STT_LANG (ru), модель — STT_MODEL (medium). Длинное режется на куски по 30 с с нахлёстом 2 с: в контейнере 2,5 ГБ памяти."""
import json, os, subprocess, sys
import numpy as np
from faster_whisper import WhisperModel
m = WhisperModel(os.environ.get("STT_MODEL", "medium"), device="cpu", compute_type="int8")
SR, CH, OV = 16000, 30.0, 2.0
for f in sys.argv[1:]:
    pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", f, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    ws, t0 = [], 0.0
    while t0 < len(audio) / SR:
        seg = audio[int(t0 * SR):int((t0 + CH + OV) * SR)]
        segs, _ = m.transcribe(seg, language=os.environ.get("STT_LANG", "ru"), word_timestamps=True, vad_filter=True)
        for s in segs:
            for w in s.words:
                a = t0 + w.start
                if (t0 == 0 or a >= t0 + OV / 2) and a < t0 + CH + OV / 2:   # нахлёст: каждое слово берём один раз
                    ws.append({"w": w.word.strip(), "t0": round(a, 2), "t1": round(t0 + w.end, 2)})
        t0 += CH
    json.dump(ws, open(f.rsplit(".", 1)[0] + ".words.json", "w"), ensure_ascii=False)
    print(f, len(ws), " ".join(f"{x['w']}@{x['t0']}" for x in ws))
