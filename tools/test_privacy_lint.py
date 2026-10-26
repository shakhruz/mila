#!/usr/bin/env python3
"""privacy-lint на выдуманном списке (живых значений в тесте нет): id и внутри длинного числа, адрес, слаг словом, имя по корню; ложных нет.
В дереве нет ни списка, ни хешей (Качество 25.10: хеш с открытой солью угадывается перебором)."""
import importlib.util, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("pl", os.path.join(HERE, "privacy_lint.py")); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)
FAKE = {"terms": [{"label": "id #1", "value": "77712345", "kind": "num"}, {"label": "адрес #1", "value": "10.20.30.40", "kind": "num"},
                  {"label": "клиент #1", "value": "zebrino", "kind": "word"}, {"label": "имя #1", "value": "квиринт", "kind": "stem"}]}
T = tempfile.mkdtemp(); fj = os.path.join(T, "p.json"); json.dump(FAKE, open(fj, "w"), ensure_ascii=False)
_CI = os.environ.pop("CI", None)   # GitHub ставит CI=true всегда; положительные проверки ищут свою метку — режим CI (обезличенные метки) проверяю отдельно ниже (Качество 26.10: CI 4/9)
P.PRIVATE = fj; terms = P.load_terms(); f = lambda s: P.find(s, terms)
chk("id целиком", f("chat_id = 77712345") == ["id #1"])
chk("id внутри длинного числа (так родилась утечка 1025d)", f("пример 7771" + "23450 в тесте") == ["id #1"])
chk("адрес сервера и внутри root@адрес", f("ssh root@10.20.30.40") == ["адрес #1"])
chk("слаг клиента целым словом, регистр не важен", f("клиент Zebrino просил") == ["клиент #1"])
chk("имя по корню («Квиринту», «квиринта»)", f("позвонить Квиринту") == ["имя #1"] and f("квиринта") == ["имя #1"])
chk("ложных нет (zebra, 7771234, 10.20.30.41, «квир», zebrinos)", not f("zebra 7771234 10.20.30.41 квир zebrinos"))
chk("в дереве нет файла хешей и открытого списка", not os.path.exists(os.path.join(HERE, "privacy.hashes.json")) and not subprocess.run(["git", "-C", REPO, "ls-files", "*privacy*.json"], capture_output=True, text=True).stdout.strip())
r = subprocess.run([sys.executable, os.path.join(HERE, "privacy_lint.py"), "--all"], capture_output=True, text=True, env=dict(os.environ, PRIVACY_JSON=os.path.join(T, "nope.json")))
chk("без закрытого списка — код 2 и честное «проверять нечем», не «чисто»", r.returncode == 2 and "нечем" in r.stdout)
os.environ["CI"] = "true"; fc = P.find("клиент zebrino", P.load_terms())
if _CI is None: del os.environ["CI"]
else: os.environ["CI"] = _CI
chk("в CI (журнал публичный) метка обезличена — значения и своей метки нет", fc == ["наше значение #3"])
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
