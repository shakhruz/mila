#!/usr/bin/env python3
"""proverka.py — проверка русского текста перед отправкой наружу.

Ловит то, что правила humanizer-ru по спискам слов не видят: сочетания, которых в русском нет («отвезти решение»),
кальки, канцелярит, машинный тон. Три слоя:
  1) словарь правок СВОЕГО владельца — таблица «Правки владельца — так по-русски не говорят» в его STIL
     (PROVERKA_STIL, иначе ~/work/canon/STIL.md, иначе первый ~/work/canon/STIL-*.md). Нет файла — слой пропущен;
  2) встроенные правила без модели (два «а» подряд);
  3) чтение «носителем» — модель через OpenRouter на топливе самой Милы (OPENROUTER_API_KEY), центы за текст.

  proverka.py файл.md|файл.html|-      # текст из файла или stdin (HTML очищается от тегов)
  proverka.py --no-llm файл            # без модели: словарь и правила
Выход: «ПРОШЁЛ» (код 0) или «НАЙДЕНО N:» и строки «было → надо · почему» (код 1). 2 — ошибка запуска.
Модель — PROVERKA_MODEL (по умолчанию anthropic/claude-sonnet-5.5)."""
import glob, html, json, os, re, sys, urllib.error, urllib.request

MODEL = os.environ.get("PROVERKA_MODEL", "anthropic/claude-sonnet-5.5")
API = os.environ.get("PROVERKA_API", "https://openrouter.ai/api/v1/chat/completions")
MAX_TEXT = 12000
MAX_DAY = int(os.environ.get("PROVERKA_MAX") or 30)   # платных чтений носителем в сутки на Милу (у клиентской Милы на нашем ключе — наши деньги)
COUNT = os.path.expanduser(os.environ.get("PROVERKA_COUNT") or "~/.cache/mila/proverka-count.json")
_PD = [(re.compile(r"\+?\d[\d\s()-]{7,}\d"), "⟦тел⟧"), (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "⟦почта⟧"),
       (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "⟦карта⟧")]


_LAB = {"phone": "⟦тел⟧", "email": "⟦почта⟧", "card": "⟦карта⟧", "passport": "⟦паспорт⟧", "pinfl": "⟦ПИНФЛ⟧"}


def _pd_find():
    """Одна правда на всё ядро: поиск личных данных — pd_vault.find из соседнего навыка pd-vault (паспорт, ПИНФЛ,
    телефоны без ложных на суммах и id). Нет навыка рядом — свой короткий список."""
    try:
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        spec = importlib.util.spec_from_file_location("pd_vault", os.path.join(os.path.dirname(here), "pd-vault", "pd_vault.py"))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m.find
    except Exception:
        return None


def mask_pd(text):
    """Перед отправкой второму провайдеру: личные данные → метки (смысл фразы для носителя тот же). В хранилище ничего не пишу."""
    find = _pd_find()
    if find:
        for s0, e0, kind, _v in sorted(find(text), reverse=True):
            text = text[:s0] + _LAB.get(kind, "⟦данные⟧") + text[e0:]
        return text
    for rx, lab in (_PD[2], _PD[0], _PD[1]):
        text = rx.sub(lab, text)
    return text


def take_quota(today=None):
    """Счётчик чтений за сутки. → True, если можно ещё одно."""
    import time
    today = today or time.strftime("%Y-%m-%d")
    try:
        d = json.load(open(COUNT, encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    if d.get("day") != today:
        d = {"day": today, "n": 0}
    if d["n"] >= MAX_DAY:
        return False
    d["n"] += 1
    try:
        os.makedirs(os.path.dirname(COUNT), exist_ok=True)
        with open(COUNT, "w", encoding="utf-8") as f: json.dump(d, f)
    except OSError:
        pass
    return True


def stil_path():
    p = os.environ.get("PROVERKA_STIL")
    if p:
        return p if os.path.isfile(p) else None
    canon = os.path.expanduser("~/work/canon")
    if os.path.isfile(os.path.join(canon, "STIL.md")):
        return os.path.join(canon, "STIL.md")
    found = sorted(glob.glob(os.path.join(canon, "STIL-*.md")))
    return found[0] if found else None


def text_of(path):
    raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    if re.search(r"<[a-zA-Z/][^>]*>", raw):
        raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
        raw = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"[ \t]+", " ", raw).strip()


def owner_fixes(path):
    """Строки таблицы правок владельца: [было, надо, где]."""
    out, on = [], False
    for line in open(path, encoding="utf-8"):
        if line.startswith("## "):
            on = "так по-русски не говорят" in line.lower()
            continue
        if on and line.startswith("|") and not re.match(r"\|\s*:?-{3}", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[0] and cells[0].lower() not in ("было", "так не говорят"):
                out.append((cells + [""])[:3])
    return out


def _norm(s):
    return re.sub(r"\s+", " ", s.lower().replace("ё", "е")).strip()


def dict_check(text, path):
    """Правка владельца — и точной фразой, и по корням значимых слов (≥4 букв) подряд, с любыми окончаниями."""
    found, low = [], _norm(text)
    for bad, good, where in owner_fixes(path):
        b = _norm(bad.strip("«»\"'"))
        words = [w for w in re.findall(r"\w+", b) if len(w) >= 4]
        stems = [w[:max(4, len(w) - 2)] for w in words]
        rx = r"(?<!\w)" + r"\w*[\s,]+(?:\w+[\s,]+){0,1}".join(re.escape(s) for s in stems) + r"\w*" if stems else None
        if b in low or (rx and re.search(rx, low)):
            found.append("%s → %s · правка владельца%s" % (bad, good, (" (" + where + ")") if where else ""))
    return found


def rules_check(text):
    """Без модели: два «а» в одном предложении или два предложения подряд с «А» в начале — читается как спотыкание."""
    found = []
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+|\n+", text) if s.strip()]
    for s in sents:
        if len(re.findall(r"(?<![\w-])а(?![\w-])", s.lower())) >= 2:
            found.append("%s → оставить одно «а» · два «а» в одном предложении" % s[:80])
    for a, b in zip(sents, sents[1:]):
        if re.match(r"а\b", a.lower()) and re.match(r"а\b", b.lower()):
            found.append("%s … %s → одно «А» в начале · два предложения подряд с «А»" % (a[:40], b[:40]))
    return found


PROMPT = """Ты — редактор-носитель русского языка, 40 лет правишь деловые тексты. Прочитай текст вслух про себя.
Найди только то, что носитель так НЕ скажет: неверные сочетания слов (например «отвезти решение»), кальки с английского,
канцелярит, машинный тон, двусмысленность. Не трогай стиль, если он живой. Не исправляй факты и цифры.
Ответь строго JSON-списком, без пояснений вокруг: [{"было": "...", "надо": "...", "почему": "..."}]. Нечего править — [].

Текст:
"""


def llm_check(text):
    """→ (находки, заметка). Ключ — топливо самой Милы; нет ключа или сбой — заметка, а не падение."""
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return [], "чтение носителем пропущено: нет OPENROUTER_API_KEY"
    if not take_quota():
        return [], "чтение носителем пропущено: лимит %d в сутки (PROVERKA_MAX)" % MAX_DAY
    body = json.dumps({"model": MODEL, "temperature": 0, "usage": {"include": True},
                       "messages": [{"role": "user", "content": PROMPT + mask_pd(text)[:MAX_TEXT]}]}).encode()
    req = urllib.request.Request(API, data=body, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            j = json.load(r)
        ans = j["choices"][0]["message"]["content"] or ""
        m = re.search(r"\[.*\]", ans, re.S)
        items = json.loads(m.group(0)) if m else []
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TypeError) as e:
        return [], "чтение носителем не удалось: %s" % type(e).__name__
    cost = (j.get("usage") or {}).get("cost")
    note = "носитель: %s%s" % (MODEL, (", $%.4f" % cost) if isinstance(cost, (int, float)) else "")
    return ["%s → %s · %s" % (i.get("было", ""), i.get("надо", ""), i.get("почему", "")) for i in items if isinstance(i, dict) and i.get("было")], note


def check(text, use_llm=True):
    """→ (находки, заметки)."""
    found, notes = [], []
    sp = stil_path()
    if sp:
        found += dict_check(text, sp)
    else:
        notes.append("личный словарь не найден (~/work/canon/STIL.md) — слой пропущен")
    found += rules_check(text)
    if use_llm:
        f, note = llm_check(text)
        found += f
        if note: notes.append(note)
    seen, out = set(), []
    for f in found:   # одно место — одна строка, даже если поймали два слоя
        k = _norm(f.split("→")[0])
        if k not in seen:
            seen.add(k); out.append(f)
    return out, notes


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__); return 2
    try:
        text = text_of(args[0])
    except OSError as e:
        print("не прочитать %s: %s" % (args[0], e)); return 2
    found, notes = check(text, use_llm="--no-llm" not in argv)
    tail = ("  (" + "; ".join(notes) + ")") if notes else ""
    if not found:
        print("ПРОШЁЛ" + tail); return 0
    print("НАЙДЕНО %d:%s" % (len(found), tail))
    for f in found:
        print("• " + f)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
