#!/usr/bin/env python3
"""Alias (v1.4.0): skills/yasno/yasno_check.py → skills/plain-words/plain_words_check.py. Removed in v1.7.0."""
import os, runpy, sys
P = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../plain-words/plain_words_check.py"))
sys.argv[0] = P; sys.path.insert(0, os.path.dirname(P))
runpy.run_path(P, run_name="__main__")
