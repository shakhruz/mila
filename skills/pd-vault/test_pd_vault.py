"""pd_vault: подлоги ПДн в разных текстах → в файлах только ярлыки, в хранилище — значения, расшифровка только ключом, подмена — отказ."""
import json, os, subprocess, sys, tempfile
d = tempfile.mkdtemp(); H = os.path.dirname(os.path.abspath(__file__))
env = {**os.environ, "PD_KEY": os.path.join(d, "k", "pd.key"), "PD_VAULT": os.path.join(d, "v", "vault.enc")}
run = lambda *a, inp=None: subprocess.run([sys.executable, "-I", os.path.join(H, "pd_vault.py"), *a], env=env, input=inp, capture_output=True, text=True)
ok = all_ = 0
def chk(n, v, x=""):
    global ok, all_
    all_ += 1; ok += bool(v); print(("✅ " if v else "❌ ") + n + ("" if v else "  ← " + str(x)))
chk("init: ключ создан, 600", run("init").stdout.strip() == "created" and oct(os.stat(env["PD_KEY"]).st_mode)[-3:] == "600")
chk("init повторно — не перезаписывает", run("init").stdout.strip() == "exists")
SAMPLES = {
    "+998 90 123-45-67": "тел", "+998901234567": "тел", "8 (903) 123-45-67": "тел", "+7 916 555 44 33": "тел",
    "aziz.k@mail.uz": "почта", "8600 1234 5678 9013": None, "4111 1111 1111 1111": "карта", "AB1234567": "паспорт", "31205950123456": "ПИНФЛ",
}
text = "Клиент Азиз, тел +998 90 123-45-67, почта aziz.k@mail.uz, карта 4111 1111 1111 1111, паспорт AB1234567, ПИНФЛ 31205950123456. Повтор: +998901234567."
r = run("mask", inp=text); m = r.stdout
chk("mask: ни одного значения в тексте", not any(x in m for x in ["123-45-67", "aziz.k@", "4111 1111", "AB1234567", "31205950123456", "901234567"]), m)
chk("ярлыки по видам", all(l in m for l in ["⟦тел·1⟧", "⟦почта·1⟧", "⟦карта·1⟧", "⟦паспорт·1⟧", "⟦ПИНФЛ·1⟧"]), m)
chk("то же значение в другом виде записи — тот же ярлык", m.count("⟦тел·1⟧") == 2 and "⟦тел·2⟧" not in m, m)
chk("карта не по Луну — не трогаем (8600 1234 5678 9013)", "8600 1234 5678 9013" in run("mask", inp="номер 8600 1234 5678 9013").stdout)
chk("обычные числа не трогаем (сумма 59 000, дата 17.10.2026, 40 минут)", run("mask", inp="Счёт 59 000 сум, 17.10.2026, 40 минут, заказ 12345").stdout == "Счёт 59 000 сум, 17.10.2026, 40 минут, заказ 12345")
chk("reveal ярлыка → значение", run("reveal", "⟦паспорт·1⟧").stdout.strip() == "AB1234567")
raw = open(env["PD_VAULT"], "rb").read()
chk("хранилище зашифровано: значений в файле нет, файл 600", b"AB1234567" not in raw and b"aziz" not in raw and oct(os.stat(env["PD_VAULT"]).st_mode)[-3:] == "600")
f = os.path.join(d, "memory.md"); open(f, "w").write("Звонить Нодире: +998 93 777 11 22. Повтор ⟦тел·1⟧ не трогать.")
r = run("mask-file", f); t = open(f).read()
chk("mask-file: новый номер → ⟦тел·2⟧, старый ярлык цел", "⟦тел·2⟧" in t and "777 11 22" not in t and "⟦тел·1⟧" in t and json.loads(r.stdout)["masked_new"] == ["⟦тел·2⟧"], (t, r.stdout))
chk("scan: после маски — чисто (код 0)", run("scan", f).returncode == 0)
g = os.path.join(d, "x.md"); open(g, "w").write("почта a@b.uz")
chk("scan: найдено — код 1, без значений", (lambda r: r.returncode == 1 and "почта" in r.stdout and "a@b.uz" not in r.stdout)(run("scan", g)))
b = bytearray(raw); b[-1] ^= 1; open(env["PD_VAULT"], "wb").write(bytes(b))
chk("подмена хранилища → отказ", run("reveal", "⟦паспорт·1⟧").returncode != 0 and "tampered" in run("reveal", "⟦паспорт·1⟧").stderr)
open(env["PD_VAULT"], "wb").write(raw)
open(env["PD_KEY"], "w").write("0" * 64 + "\n")
chk("чужой ключ → отказ", run("reveal", "⟦паспорт·1⟧").returncode != 0)
print(f"итог {ok}/{all_}"); sys.exit(0 if ok == all_ else 1)
