#!/usr/bin/env python3
"""check_frontmatter.py — заголовок YAML каждого SKILL.md разбирается без ошибок (Мила-доктор 13.10: «: » в description без кавычек
ломает разбор, Claude Code молча отбрасывает все поля). Только чтение; --fix — взять description (и другие однострочные значения с «: »)
в двойные кавычки с JSON-экранированием. Код выхода 1 — есть ошибки (для тестов репо).
  check_frontmatter.py <папка с навыками|SKILL.md …> [--fix]"""
import json, os, re, sys
import yaml

def files(args):
    for a in args:
        if os.path.isfile(a): yield a
        else:
            for root, dirs, fs in os.walk(a):
                dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules") and ".bak-" not in d]
                for f in fs:
                    if f == "SKILL.md": yield os.path.join(root, f)

def split(t):
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*(\n|$)", t, re.S)
    return (m.group(1), m.end()) if m else (None, 0)

def check(p):
    fm, _ = split(open(p, encoding="utf-8").read())
    if fm is None: return "нет заголовка --- … ---"
    try:
        d = yaml.safe_load(fm)
        if not isinstance(d, dict): return "заголовок не словарь"
        if not d.get("name") or not d.get("description"): return "нет name или description"
    except yaml.YAMLError as e:
        return str(e).split("\n")[0][:160]
    return ""

def fix(p):
    t = open(p, encoding="utf-8").read(); fm, end = split(t)
    if fm is None: return False
    out = []
    for line in fm.split("\n"):
        m = re.match(r"^([A-Za-z][\w-]*):[ \t]+(.+)$", line)
        if m and m.group(1) in ("name", "description", "argument-hint", "when_to_use", "model") :
            v = m.group(2).strip()
            if not (v[:1] in "\"'|>[{" ) and (": " in v or " #" in v or v.endswith(":")):
                line = f"{m.group(1)}: {json.dumps(v, ensure_ascii=False)}"
        out.append(line)
    new = "\n".join(out)
    if new == fm: return False
    open(p, "w", encoding="utf-8").write("---\n" + new + "\n---\n" + t[end:])
    return True

def main():
    args = [a for a in sys.argv[1:] if a != "--fix"]; doit = "--fix" in sys.argv
    bad = fixed = 0; n = 0
    for p in files(args):
        n += 1; err = check(p)
        if err and doit and fix(p):
            fixed += 1; err = check(p)
        if err: bad += 1; print(f"❌ {p}: {err}")
    print(f"SKILL.md: {n} · починено: {fixed} · ошибок: {bad}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__": main()
