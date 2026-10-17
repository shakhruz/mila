#!/usr/bin/env python3
"""Alias (v1.4.0): skills/rashod/rashod.py → skills/spend/spend.py. Removed in v1.6.0."""
import os, runpy, sys
P = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../spend/spend.py"))
sys.argv[0] = P; sys.path.insert(0, os.path.dirname(P))
runpy.run_path(P, run_name="__main__")
