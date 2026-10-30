#!/bin/bash
# live-frames: движок собирает 3-секундный ролик из подменного голоса и двух сцен (текст, значок, счётчик, пилюля) → mp4 нужной
# длины со звуком. Без сети; нет numpy/Pillow — пропуск. bash skills/live-frames/test_live_frames.sh
set -u; H="$(cd "$(dirname "$0")" && pwd)"; T=$(mktemp -d); trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; cd $T
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
python3 -c "import numpy, PIL" 2>/dev/null || { echo "⏭ нет numpy/Pillow — пропуск"; echo "итог 0/0"; exit 0; }
ffmpeg -nostdin -v error -y -f lavfi -i "sine=f=200:d=3" -ac 1 voice.wav
cat > spec.py <<P
VOICE = "$T/voice.wav"
W, H = 640, 360
SCENES = [{"t": 0.0, "bg": "dark", "els": [("text", "Проба", 320, 120, 48, 0.2), ("icon", "rocket", 320, 230, 90, 0.6)]},
          {"t": 1.5, "bg": "warm", "els": [("count", 1, 40, "×{:.0f}", 320, 150, 70, 1.6, 0.6), ("pill", "меньше ошибок", 320, 260, 30, 2.0)]}]
P
python3 "$H/tools/motion.py" spec.py out.mp4 > log.txt 2>&1
chk "ролик собран: mp4 ~3 с" "python3 -c \"import subprocess;d=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0','out.mp4'],capture_output=True,text=True).stdout);assert abs(d-3)<1.2,d\""
chk "есть звук" "ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 out.mp4 | grep -q audio"
echo "итог $ok/$n"; cd /; rm -rf $T; [ $ok -eq $n ]
