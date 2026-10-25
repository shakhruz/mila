"""mila-export: сканер секретов — края (Мила Сила 25.10). Значения поддельные, генерируются в тесте. Usage: python3 -I mila-export-test_scan.py <папка с mila_export.py>"""
import sys, random, string
import os
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))); import mila_export as M   # без аргумента — рядом (run_all)
r=random.Random(7); A=lambda n,al=string.ascii_letters+string.digits: "".join(r.choice(al) for _ in range(n))
H=lambda n: A(n,"0123456789abcdef")
cases=[
 ("OpenRouter key", "key: sk-"+"or-v1-"+H(64), 1),
 ("ElevenLabs sk_", "ELEVEN=sk_"+H(48), 1),
 ("Stripe sk_live_", "stripe sk_live_"+A(24), 1),
 ("Google AIza", "GOOGLE_KEY=AIza"+A(35), 1),
 ("fal key uuid:hex", "FAL_KEY="+H(8)+"-"+H(4)+"-"+H(4)+"-"+H(4)+"-"+H(12)+":"+H(32), 1),
 ("env OPENROUTER_API_KEY=", "OPENROUTER_API_"+"KEY="+A(40), 1),
 ("токен бота без AA", "BOT_TOK"+"EN="+str(r.randint(10**9,10**10-1))+":AB"+A(33), 1),
 ("Bearer в curl", 'curl -H "Authorization: Bearer '+A(40)+'"', 1),
 ("JWT", "eyJ"+A(20)+".eyJ"+A(40)+"."+A(43), 1),
 ("Slack xoxb", "xoxb-"+str(r.randint(10**11,10**12))+"-"+A(24), 1),
 ("пароль с символом", "pass"+"word = \"Qw!7rty#Lk9z2\"", 1),
 ("hex-ключ 64 (pd.key)", "PD_"+"KEY="+H(64), 1),
 ("секрет в конце длинной строки", "x"*20500+" sk-ant-"+A(40), 1),
 ("пароль по-русски", "паро"+"ль: Tashkent2026!Mila", 1),
 ("норма: sha256 в манифесте", '"sha256": "'+H(64)+'"', 0),
 ("норма: uuid", "id "+H(8)+"-"+H(4)+"-"+H(4)+"-"+H(4)+"-"+H(12), 0),
 ("норма: ссылка", "https://milagpt.io/sily/quiz-maker", 0),
 ("норма: плейсхолдер", "OPENROUTER_API_KEY=your-key-here", 0),
]
ok=0
for name,line,want in cases:
    got=1 if M.scan_bytes(line.encode()) else 0; g=got==want; ok+=g
    print(("✅" if g else "🔴"), name, "→", "найдено" if got else "чисто")
print("итог %d/%d"%(ok,len(cases))); sys.exit(0 if ok==len(cases) else 1)
