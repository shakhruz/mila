"""pd-vault — края (Мила Сила 25.10). Своё хранилище и ключ во временной папке. Usage: python3 -I test_pd_kraya.py <папка с pd_vault.py>"""
import os, sys, tempfile, subprocess
T = tempfile.mkdtemp(); os.environ["PD_KEY"] = T + "/k/pd.key"; os.environ["PD_VAULT"] = T + "/v/vault.enc"
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, SRC); import pd_vault as P   # без аргумента — рядом (run_all)
R = []
def C(name, ok, info=""): R.append(bool(ok)); print(("✅" if ok else "🔴"), name, info)
PY = [sys.executable, "-I", os.path.join(SRC, "pd_vault.py")]
f = T + "/f.md"; open(f, "w").write("Клиент Азиз +998 90 123 45 67\n")
rc = subprocess.run(PY + ["mask-file", f], capture_output=True, env=os.environ).returncode
C("нет ключа → mask-file не трогает файл (иначе метка без значения)", "+998 90 123 45 67" in open(f).read(), "rc=%d, файл: %r" % (rc, open(f).read().strip()))
r = subprocess.run(PY + ["mask"], input=b"tel +998901234567", capture_output=True, env=os.environ)
C("нет ключа → mask не печатает пустоту вместо текста (код ≠ 0)", r.returncode != 0)
subprocess.run(PY + ["init"], capture_output=True, env=os.environ)
for t, want in [("тел 90 123 45 67", 1), ("тел (90) 123-45-67", 1), ("номер: 901234567", 1), ("+998 90 123 45 67", 1), ("998901234567", 1),
                ("паспорт ab1234567", 1), ("паспорт АВ1234567", 1), ("AB 1234567", 1),
                ("Перевёл на 1500000 сум", 0), ("оплата ок 1200000", 0), ("сумма 50 000 00 00", 0), ("мой номер в телеграм 901234567", 1),
                ("номер 335550101 в телеграме", 0), ("номер чата 335550101", 0), ("паспорт ab 1234567", 1),
                ("счёт 901234567 оплачен, тел 901234568", 1),
                ("оплата по номеру 90 123 45 67", 1), ("оплата: звоните 90 123 45 67", 1), ("оплата 90 123 45 67", 0),
                ("id 335550101", 0), ("заказ 901234567", 0), ("сумма 1 500 000", 0), ("25.10.2026 11:05", 0), ("счёт 20208000123456789012", 0)]:
    C("найти %r → %s" % (t, "да" if want else "нет"), bool(P.find(t)) == bool(want), str([(k, v) for _, _, k, v in P.find(t)]))
m1, _ = P.mask("+998 90 123 45 67"); m2, _ = P.mask("90 123 45 67"); m3, _ = P.mask("тел 901234567")
C("один номер в трёх записях → одна метка", m1 == m2 and m3.endswith(m1), "%s %s %s" % (m1, m2, m3))
a, _ = P.mask("паспорт AB1234567"); b, _ = P.mask("паспорт АВ1234567")
C("паспорт латиницей и кириллицей → одна метка", a == b, "%s | %s" % (a, b))
C("reveal метки → значение", subprocess.run(PY + ["reveal", m2], capture_output=True, env=os.environ).returncode == 0)
print("итог %d/%d" % (sum(R), len(R))); sys.exit(0 if all(R) else 1)
