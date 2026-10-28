"""cards.py — края (Мила Сила 26.10): старая кнопка, пустой ключ, одинаковые подписи, «до завтра» ночью. Usage: python3 -I test_cards_kraya.py [папка с cards.py]"""
import json, os, subprocess, sys, tempfile, datetime as dt, importlib.util
D = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)); K = os.path.join(D, "cards.py")
R = []
def C(n, ok, i=""): R.append(bool(ok)); print(("✅" if ok else "🔴"), n, i)
W = tempfile.mkdtemp(); env = dict(os.environ, MILA_WORK=W, MILA_SLUG="sila")
def k(*a):
    p = subprocess.run([sys.executable, "-I", K, *a], env=env, capture_output=True, text=True)
    try: return json.loads(p.stdout or "{}"), p.returncode
    except ValueError: return {"raw": (p.stdout + p.stderr)[-200:]}, p.returncode
# 1. старая кнопка: показан A, потом срочный B с той же подписью «Да» — нажатие «Да» не должно молча уйти в B
a, _ = k("ask", "--q", "Выкладываем сайт сейчас?", "--why", "Готово", "--opt", "a|Да|выложу", "--opt", "b|Нет|подожду", "--rec", "a")
k("next", "inbox")
b, _ = k("ask", "--q", "Платим за домен?", "--why", "Сегодня срок", "--opt", "a|Да|оплачу", "--opt", "b|Нет|не платим", "--rec", "a", "--urgent")
k("next", "inbox")
r, rc = k("button", "[кнопка] Да")
st = {json.loads(l)["id"]: json.loads(l)["status"] for l in open(os.path.join(W, "inbox.jsonl"))}
C("«Да» подходит к двум открытым карточкам → спросить, к какой (ни одна не отвечена)", rc != 0 and r.get("ambiguous") and st.get(a.get("id")) == "open" and st.get(b.get("id")) == "open", str(r)[:120])
# 2. то же для задач: «✅ Да» при двух показанных открытых
t1, _ = k("task", "--task", "Собрать отчёт", "--why", "нужно", "--to", "admin"); k("next", "proposals")
t2, _ = k("task", "--task", "Срочно домен", "--why", "нужно", "--to", "admin", "--prio", "1"); k("next", "proposals")
r, rc = k("button", "[кнопка] ✅ Да")
C("«✅ Да» при двух показанных задачах → спросить, к какой", rc != 0 and r.get("ambiguous"), str(r)[:120])
# 3. однозначная кнопка — работает как раньше (сначала владелец ответил на A и B по id — колода чиста)
k("answer", a.get("id", "x"), "--pick", "b"); k("answer", b.get("id", "x"), "--pick", "a")
c, _ = k("ask", "--q", "Какой цвет?", "--why", "Вебмастер ждёт", "--opt", "g|Зелёный|как сейчас", "--opt", "s|Синий|как бренд", "--rec", "g"); k("next", "inbox")
r, rc = k("button", "[кнопка] Синий")
C("уникальная подпись «Синий» → ответ на свою карточку", rc == 0 and r.get("card", {}).get("answer", {}).get("key") == "s", str(r)[:100])
# 4. пустой ключ варианта
r, rc = k("ask", "--q", "Пустой ключ?", "--why", "проба", "--opt", "|Да|x", "--opt", "b|Нет|y", "--rec", "b")
C("пустой ключ варианта → отказ при создании", rc != 0 and "ключ" in json.dumps(r, ensure_ascii=False), str(r)[:120])
# 5. одинаковые подписи вариантов
r, rc = k("ask", "--q", "Две одинаковые?", "--why", "проба", "--opt", "a|Да|x", "--opt", "b|Да|y", "--rec", "a")
C("одинаковые подписи вариантов → отказ (нажатие не различить)", rc != 0, str(r)[:120])
# 6. «До завтра» в 00:30 → 09:00 того же утра, не через 32 часа
spec = importlib.util.spec_from_file_location("cc", K); M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
M.now = lambda: dt.datetime(2026, 10, 26, 0, 30, tzinfo=M.TZ); u = M.tomorrow_9()
C("«до завтра» в 00:30 → 26.10 09:00", (u.day, u.hour) == (26, 9), u.isoformat())
M.now = lambda: dt.datetime(2026, 10, 26, 14, 0, tzinfo=M.TZ); u = M.tomorrow_9()
C("«до завтра» в 14:00 → 27.10 09:00", (u.day, u.hour) == (27, 9), u.isoformat())
print("итог %d/%d" % (sum(R), len(R))); sys.exit(0 if all(R) else 1)
