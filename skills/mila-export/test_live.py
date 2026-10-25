"""mila-export: формы строк живого дома (по описанию Качества 25.10) — код и заглушки не секрет; литерал — секрет. Usage: python3 -I proby_live.py <папка>"""
import os, sys; sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))); import mila_export as M   # без аргумента — рядом (run_all)
cases=[("const KEY = process.env.OPENROUTER_API_KEY",0),("TOKEN = os.environ['BOT_TOKEN']",0),("API_KEY=os.getenv('X')",0),("SECRET = secrets.token_urlsafe(18)",0),
("TELEGRAM_BOT_TOKEN=1234" + "56789:AAH...",0),("OPENROUTER_API_KEY=$OPENROUTER_API_KEY",0),("BOT_TOKEN={{ bot_token }}",0),("PD_KEY=<64 hex>",0),("API_KEY=xxxxxxxx"+"xxxxxxxx",0),
("FAL_KEY=your-fal-key-1234",0),("TOKEN = Bun.env.TOKEN",0),("KEY=import.meta.env.VITE_KEY1",0),("MAX_TOKEN=4096",0),("PWD=/home/companion/work",0),
('"password": pw.group(1)',0),("PD_KEY_FILE=/home/x/.config/mila/pd.key1",0),("KEYS_FILE=keys2026.json",0),("API_KEY_PATH=/etc/k1",0),
("x"*600+" KEY_SYSTEM_"+"ERROR=abc"+"123def"+"456ghi",0),
("OPENROUTER_API_KE"+"Y=Xq7pL2"+"mN9vB4"+"kR8tY1wZ",1),("DB_PASSWO"+"RD=Tq9mZ2"+"xK8vLp",1)]
R=[]
for t,w in cases:
    g=1 if M.scan_bytes(t.encode()) else 0; R.append(g==w); print(("✅" if g==w else "🔴"), t, "→", "секрет" if g else "чисто")
g=M.scan_bytes(b"API_KE"+b"Y=Xq7pL2"+b"mN9vB4"+b"kR8tY1wZ", "work/site/hls.min.js"); R.append(not g); print(("✅" if not g else "🔴"), "сборка *.min.js — присвоение KEY= не ищется")
import random, string; rr=random.Random(3); tok="sk-"+"ant-"+"".join(rr.choice(string.ascii_letters+string.digits) for _ in range(40))
for where in ("work/site/dist/app.js", "work/site/hls.min.js", "work/site/app.js"):
    g=M.scan_bytes(("x"*24000+" "+tok).encode(), where); R.append(bool(g)); print(("✅" if g else "🔴"), "ключ sk-ant в строке 24 000 знаков, %s — ловится" % where)
print("итог %d/%d"%(sum(R),len(R))); sys.exit(0 if all(R) else 1)
