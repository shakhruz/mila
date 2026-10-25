#!/usr/bin/env python3
"""Our own secret scanner (mila_export scan_bytes) over every tracked file of the core.
Why: fleet-git-sync stood 3 days on fake tokens in core tests — gitleaks in CI did not stop them, our scanner on the homes did.
Fakes in tests are built by splicing ("sk-" "abc…", "PRIV""ATE"), never written whole. Usage: python3 tests/test_secret_scan.py"""
import os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "mila-export"))
import mila_export as mx

ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)

files = [f for f in subprocess.run(["git", "-C", ROOT, "ls-files", "-z"], capture_output=True, check=True).stdout.decode().split("\0") if f]
hits = []
for rel in files:
    p = os.path.join(ROOT, rel)
    if os.path.splitext(rel)[1].lower() in mx.MEDIA_EXT or not os.path.isfile(p) or os.path.getsize(p) > mx.MAX_FILE: continue
    hits += ["%s:%d  %s" % (rel, ln, k) for ln, k in mx.scan_bytes(open(p, "rb").read(), rel)]
for h in hits: print("   " + h)
chk("в ядре нет строк, похожих на секрет (%d файлов)" % len(files), not hits)

# mutant: the scanner must still bite — a planted fake of each kind is caught
for fake in ["sk-" + "a" * 24, "1234567890:" + "AA" + "c" * 34, "gh" + "p_" + "d" * 36, "-----BEGIN RSA PRIV" + "ATE KEY-----", "pass" + "word=Abcdef123456", "AK" + "IA" + "E" * 16, "re" + "_" + "f" * 24, "sk-" + "ant-" + "b" * 12]:
    chk("подложенная фальшивка ловится: %s…" % fake[:5], mx.scan_bytes(("x " + fake).encode(), "t.txt"))
chk("склейка не ловится (так пишем фальшивки)", not mx.scan_bytes(b'"sk-" "abcdefghijklmnopqrstuv"', "t.py"))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
