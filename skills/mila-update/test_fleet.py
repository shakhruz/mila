#!/usr/bin/env python3
"""FLEET-1021: раскатка с хоста — MILA_HOME (чужой дом вместо ~), MILA_CHOWN (всё тронутое и созданные родители — хозяину,
и после apply, и после rollback); нет доступа к дому — честный отказ, не «новое». os.chown подменён — запись, без root. python3 test_fleet.py"""
import json, os, runpy, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(H, "..", ".."))
T = tempfile.mkdtemp(); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + str(x)[:300]))
home = os.path.join(T, "srv", "acme", "home"); os.makedirs(os.path.join(home, "work")); open(os.path.join(home, "work", "USER.md"), "w").write("знакомство: пройдено")
rel = os.path.join(T, "rel"); shutil.copytree(REPO, rel, ignore=shutil.ignore_patterns(".git"))
def run(*args, chown=None):
    calls = []
    env = dict(os.environ, MILA_HOME=home, HOME=os.path.join(T, "admin-home")); env.pop("CLAUDE_CONFIG_DIR", None); env.pop("MILA_WORK", None)
    if chown: env["MILA_CHOWN"] = chown
    code = ("import os,sys,json,runpy\nC=[]\nos.lchown=lambda p,u,g: C.append((p,u,g))\nsys.argv=%r\n"
            "try:\n  runpy.run_path(%r, run_name='__main__')\nexcept SystemExit as e:\n  print(e) if e.code not in (None, 0) else None\nopen(%r,'w').write(json.dumps(C))\n") % (["update.py"] + list(args), os.path.join(H, "update.py"), os.path.join(T, "calls.json"))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    try: calls = json.load(open(os.path.join(T, "calls.json")))
    except Exception: calls = []
    return r, calls
r, c = run("apply", "--src", rel, "--yes", "тест флота", chown="4242")
check("MILA_HOME: навыки легли в дом Милы, не в ~ администратора", os.path.isfile(os.path.join(home, ".claude", "skills", "mila-update", "SKILL.md")) and not os.path.exists(os.path.join(T, "admin-home", ".claude", "skills")), r.stdout[-300:] + r.stderr[-300:])
paths = {p for p, u, g in c if u == 4242 and g == 4242}
check("MILA_CHOWN после apply: навык, хук, mila-update/ и созданный .claude — хозяину", any(p.endswith("skills/mila-update/SKILL.md") for p in paths) and any(p.endswith("hooks/send-guard.py") for p in paths)
      and any(p.endswith(".claude/mila-update") for p in paths) and any(p.endswith(os.sep + ".claude") for p in paths), sorted(paths)[:8])
check("за пределы дома chown не выходит", all(os.path.realpath(p).startswith(os.path.realpath(home)) for p in paths))
r, c = run("rollback", chown="4242:4242")
check("MILA_CHOWN после rollback — то, что вернули, и папка mila-update", any(p.endswith(".claude/mila-update") for p, u, g in c), c[:3])
r, c = run("apply", "--src", rel, "--yes", "без chown")
check("без MILA_CHOWN — chown не зовётся", c == [], c[:3])
# --- подлог (блокер Качества 21.10): журнал и бэкап в доме пишет сама Мила ---
import tarfile, io
other = os.path.join(T, "srv", "other", "home"); os.makedirs(other); victim = os.path.join(other, "secret.txt"); open(victim, "w").write("чужое")
outside = os.path.join(T, "outside.txt"); open(outside, "w").write("вне дома")
jr = os.path.join(home, ".claude", "mila-update", "journal.jsonl")
real_backup = [json.loads(l) for l in open(jr, encoding="utf-8") if '"event": "update"' in l][-1]["backup"]
evil_tar = os.path.join(home, ".claude", "mila-update", "backups", "evil.tgz")
with tarfile.open(evil_tar, "w:gz") as t:
    data = b"pwn"; ti = tarfile.TarInfo(os.path.join(T, "created-outside.txt").lstrip("/")); ti.size = len(data); t.addfile(ti, io.BytesIO(data))
    li = tarfile.TarInfo((home + "/.claude/skills/evil-link").lstrip("/")); li.type = tarfile.SYMTYPE; li.linkname = outside; t.addfile(li)
open(jr, "a", encoding="utf-8").write(json.dumps({"event": "update", "tag": "vX", "backup": evil_tar, "touched": ["/etc/passwd", victim, other]}, ensure_ascii=False) + "\n")
r, c = run("rollback", chown="4242")
called = {os.path.realpath(p) for p, u, g in c}
check("подложенный журнал: chown не зовётся на /etc/passwd и чужой дом", not any(p in called for p in ("/etc/passwd", os.path.realpath(victim), os.path.realpath(other))), sorted(called)[:5])
check("подложенный журнал: файл чужого дома не удалён", os.path.exists(victim))
check("подложенный бэкап: файл вне дома не создан, симлинк на файл вне дома не распакован", not os.path.exists(os.path.join(T, "created-outside.txt")) and not os.path.lexists(home + "/.claude/skills/evil-link"))
sk = os.path.join(home, ".claude", "skills", "mila-update")
if os.path.isdir(sk):
    os.symlink(outside, os.path.join(sk, "link-out")); os.link(outside, os.path.join(sk, "hard-out"))
r, c = run("apply", "--src", rel, "--yes", "повтор с ловушками", chown="4242")
called = {p for p, u, g in c}
check("симлинк в доме на файл вне дома: chown цели нет; жёсткая ссылка на файл вне дома — пропуск", os.path.realpath(outside) not in {os.path.realpath(p) for p in called if not os.path.islink(p)} and os.path.join(sk, "hard-out") not in called, sorted(called)[:5])
# прямой вызов fleet_chown: в тронутом — папка с симлинком и жёсткой ссылкой наружу, путь в чужой дом, «соседний» дом acme2
code = ("import os,sys,json\nsys.path.insert(0,%r)\nos.environ['MILA_CHOWN']='4242'\nimport update as U\nC=[]\nos.lchown=lambda p,u,g: C.append(p)\n"
        "U.RUN_TOUCHED.update([%r,%r,%r,%r])\nU.fleet_chown()\nprint(json.dumps(C))\n") % (H, sk, victim, "/etc/passwd", home + "2")
os.makedirs(home + "2", exist_ok=True)
r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(os.environ, MILA_HOME=home, HOME=os.path.join(T, "admin-home")))
C = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else []
check("прямой вызов: внутри папки — файлы навыка да; ссылка-симлинк — сама ссылка, не цель; жёсткая ссылка, чужой дом, /etc, сосед acme2 — нет",
      any(p.endswith("SKILL.md") for p in C) and os.path.join(sk, "hard-out") not in C and os.path.realpath(outside) not in [os.path.realpath(p) for p in C if not os.path.islink(p)]
      and victim not in C and "/etc/passwd" not in C and (home + "2") not in C, (r.stderr[-300:], C[:6]))
os.chmod(os.path.join(home, ".claude"), 0o000)
r, _ = run("diff", "--src", rel)
os.chmod(os.path.join(home, ".claude"), 0o755)
check("нет доступа к дому — отказ «нет доступа», не «новое»" if os.geteuid() != 0 else "root: проверка доступа пропущена", (("нет доступа" in r.stdout + r.stderr) and "новое" not in r.stdout) if os.geteuid() != 0 else True, r.stdout[:300])
shutil.rmtree(T, ignore_errors=True); print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
