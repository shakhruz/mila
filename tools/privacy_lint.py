#!/usr/bin/env python3
"""privacy-lint — наши значения не рождаются в публичном ядре (разбор «почему, а не как ловить»).

Что ищет в добавленных строках (коммит) или во всех файлах (CI, приёмка Качества):
  • id и номера из закрытого списка — и ВНУТРИ длинного числа (так родилась утечка 1025d: id внутри «тестового» числа);
  • имена и слаги закрытых клиентов, имена людей — целым словом или по корню («Квиринту» = «Квиринт»);
  • (если стоит gitleaks — его находки в индексе коммита).
Список «наших» значений — ТОЛЬКО вне репо: ~/.config/mila/privacy.json (600) или путь в PRIVACY_JSON
  ({"terms": [{"label", "value", "kind": num|word|stem}]}). В дереве — ни значений, ни хешей: хеш с открытой солью
  по короткому списку угадывается перебором (4 из 6 за секунды). CI получает список секретом Actions.
Значение в выводе не печатается — только «файл:строка метка».

  privacy_lint.py --staged            — добавленные строки индекса (pre-commit хук; находка → коммит не рождается)
  privacy_lint.py --all               — все отслеживаемые файлы (CI, Качество)
Код 0 — чисто, 1 — находки, 2 — ошибка запуска."""
import json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
def _repo():
    """Репо — git-корень ТЕКУЩЕЙ папки (Качество b: иначе запуск из соседней папки проверял чужое и давал ложное «чисто»)."""
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else os.path.dirname(HERE)


REPO = _repo()
PRIVATE = os.environ.get("PRIVACY_JSON") or os.path.expanduser("~/.config/mila/privacy.json")
SKIP = re.compile(r"(^|/)(\.git/)|\.(png|jpe?g|gif|webp|mp4|mp3|wav|ogg|ttf|woff2?|zip|gz|bundle|pdf)$", re.I)
NUM = re.compile(r"\d{5,}")
WORD = re.compile(r"[^\W\d_][\w-]*", re.U)


def norm(v):
    return str(v).strip().lower().replace("ё", "е")


def load_terms():
    if not os.path.isfile(PRIVATE):
        return []
    d = json.load(open(PRIVATE, encoding="utf-8"))
    pub = bool(os.environ.get("CI"))   # журнал CI публичный: там только обезличенная метка, своя — только локально
    return [(t.get("kind", "word"), norm(t["value"]), (t.get("public_label") or "наше значение #%d" % i) if pub else t.get("label", "наше значение"))
            for i, t in enumerate(d.get("terms", []), 1) if t.get("value")]


def find(line, terms):
    """Метки найденного в строке (без значений)."""
    low = norm(line); out = []
    nums = NUM.findall(low); words = WORD.findall(low)
    for kind, chk, label in terms:
        if kind == "num":
            hit = any(chk in n for n in nums) if chk.isdigit() else chk in low   # id внутри длинного числа; IP — подстрокой
        elif kind == "word":
            hit = chk in words
        else:   # stem: начало слова
            hit = any(w.startswith(chk) for w in words)
        if hit:
            out.append(label)
    return out


def staged_lines():
    diff = subprocess.run(["git", "-C", REPO, "diff", "--cached", "-U0", "--no-color"], capture_output=True, text=True).stdout
    f = ln = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            f = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line); ln = int(m.group(1)) if m else 0
        elif line.startswith("+") and f and not line.startswith("+++"):
            yield f, ln, line[1:]; ln += 1


def all_lines():
    files = subprocess.run(["git", "-C", REPO, "ls-files", "-z"], capture_output=True, text=True).stdout.split("\0")
    for f in filter(None, files):
        p = os.path.join(REPO, f)
        if SKIP.search(f) or not os.path.isfile(p) or os.path.getsize(p) > 5_000_000:
            continue
        try:
            for i, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
                yield f, i, line
        except OSError:
            continue


def main(argv):
    if argv[:1] not in (["--staged"], ["--all"]):
        print(__doc__); return 2
    terms = load_terms()
    if not terms:
        print("privacy-lint: нет закрытого списка %s — проверять нечем (CI без секрета PRIVACY_JSON — шаг пропускается)" % PRIVATE); return 2
    lines = staged_lines() if argv[0] == "--staged" else all_lines()
    bad = []
    for f, ln, text in lines:
        if SKIP.search(f):
            continue
        for label in find(text, terms):
            bad.append("%s:%d  %s" % (f, ln, label))
    if argv[0] == "--staged" and shutil.which("gitleaks"):
        r = subprocess.run(["gitleaks", "protect", "--staged", "--no-banner", "--redact", "-v"], cwd=REPO, capture_output=True, text=True)
        if r.returncode != 0:
            bad.append("gitleaks: найден секрет в индексе (gitleaks protect --staged -v)")
    for b in bad:
        print("  ✗ " + b)
    print("privacy-lint: %s (%d)" % ("НАЙДЕНО — уберите наши значения, в примеры — tests/fixtures/fake_people.py" if bad else "чисто", len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
