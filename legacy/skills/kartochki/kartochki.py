#!/usr/bin/env python3
"""Alias (v1.4.0): skills/kartochki/kartochki.py → skills/cards/cards.py. Removed in v1.7.0."""
import os, runpy, sys
P = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../cards/cards.py"))
sys.argv[0] = P; sys.path.insert(0, os.path.dirname(P))
runpy.run_path(P, run_name="__main__")
