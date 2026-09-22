#!/usr/bin/env python3
"""grade_uvvis.py peaks.tsv stdout.txt stderr.txt — external grader (TEST_PLAN tier a)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grading import require_files, finish

peaks, out_p, err_p = sys.argv[1:4]
require_files(peaks, out_p)
lines = open(peaks).read().splitlines()
stdout = open(out_p).read()
checks = []

checks.append(("header+tabs", lines[0] == "band\tlambda_max_nm\ta_max"))
rows = [l.split("\t") for l in lines[1:] if l]
checks.append(("3 rows", len(rows) == 3 and all(len(r) == 3 for r in rows)))
try:
    lams = [int(r[1]) for r in rows]
    amaxs = [float(r[2]) for r in rows]
    ok = True
except (ValueError, IndexError):
    lams = amaxs = None
    ok = False
checks.append(("sorted", ok and lams == sorted(lams)))
checks.append(("lambda within 2nm", ok and all(abs(a - b) <= 2 for a, b in zip(lams, [320, 420, 540]))))
checks.append(("a_max within 0.02", ok and all(abs(a - b) <= 0.02 for a, b in zip(amaxs, [0.8803, 1.2677, 0.6691]))))
checks.append(("a_max %.4f format", ok and all(r[2] == "%.4f" % float(r[2]) for r in rows)))
checks.append(("stdout bands line", "bands: 3" in stdout.splitlines()))
try:
    conc = float(next(l.split(":")[1] for l in stdout.splitlines() if l.startswith("concentration_uM:")))
except (StopIteration, ValueError):
    conc = None
checks.append(("conc within 5% of 50.0", conc is not None and abs(conc - 50.0) <= 2.5))
checks.append(("no 4th band near 481", ok and all(abs(l - 481) > 5 for l in lams)))
finish(checks)
