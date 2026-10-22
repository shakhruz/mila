#!/usr/bin/env python3
"""Alias (v1.4.0): skills/naglyadno/scripts/gallery.py → skills/visual/scripts/gallery.py. Removed in v1.6.0."""
import os, runpy, sys
P = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../visual/scripts/gallery.py"))
sys.argv[0] = P; sys.path.insert(0, os.path.dirname(P))
runpy.run_path(P, run_name="__main__")
