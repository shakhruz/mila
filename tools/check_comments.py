r"""Проверка «код не съеден комментарием»: строка вида `код; // коммент` где в комментарии похоже на код
(присваивание, вызов с «;»). Запуск: python3 check_comments.py $(git ls-files "*.js" "*.mjs" "*.html" | grep -v -e vendor/ -e "\.min\.js$") → список подозрительных строк, код 1 если есть."""
import re, sys
CODE = re.compile(r"(\b[A-Za-z_$][\w$.\[\]]*\s*(=|\+=|-=)\s*[^=>\s][^;]*;)|(\b[A-Za-z_$][\w$.]*\([^)]*\)\s*;)|(\breturn\b[^;]*;)")   # «function x() {» в пояснении — проза, не съеденный код
bad = 0
for f in sys.argv[1:]:
    if "/_shot-" in f: continue   # снимки для кадров — сгенерированы, не выкладываются
    for i, ln in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
        m = re.search(r"(?<![:\"'\\/])//(?!/)(.*)$", ln)
        if not m or re.match(r"^\s*//", ln): continue   # комментарий на всю строку код не съест
        if re.search(r"https?:$", ln[:m.start()]) or "base64," in ln: continue   # ссылка или data:-URI, не комментарий
        com = m.group(1)
        if CODE.search(com):
            bad += 1; print("%s:%d: %s" % (f, i, ln.strip()[:160]))
sys.exit(1 if bad else 0)
