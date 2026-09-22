#!/usr/bin/env python3
"""grade_formula_finder.py measured.tsv ranked.tsv stdout.log — external grader."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grading import require_files, finish

meas_path, ranked_path, stdout_path = sys.argv[1], sys.argv[2], sys.argv[3]
require_files(meas_path, ranked_path, stdout_path)

meas = {}
for r in (l.split("\t") for l in open(meas_path).read().splitlines()[1:]):
    meas[r[0]] = tuple(map(float, r[1:]))
lines = open(ranked_path, "rb").read().decode().split("\n")
checks = []

stdout = open(stdout_path).read().splitlines()
checks.append(("c2 stdout candidate counts",
    stdout == ["CPD1: 7 candidates", "CPD2: 10 candidates", "CPD3: 2 candidates"]))

checks.append(("unix newlines, no CR", "\r" not in open(ranked_path, "rb").read().decode()))
hdr = "id\tformula\tcalc_mass\terror_ppm\tM1_calc\tM2_calc\tscore"
checks.append(("tab-separated header, exact column order", lines[0] == hdr))
rows = [l.split("\t") for l in lines[1:] if l]
checks.append(("19 data rows", len(rows) == 19))
counts = {"CPD1": 7, "CPD2": 10, "CPD3": 2}
seq = [cid for cid in counts for _ in range(counts[cid])]
checks.append(("blocks in input order with exact counts", [r[0] for r in rows] == seq))

for cid, formula, mass, score in [("CPD1", "C6H12O6", 180.063390, 1.2763),
                                  ("CPD2", "C8H10N4O2", 194.080376, 2.1369),
                                  ("CPD3", "C5H11NO2S", 149.051050, 2.5581)]:
    top = next((r for r in rows if r[0] == cid), None)
    checks.append(("%s top hit is %s" % (cid, formula), top is not None and top[1] == formula))
    try:
        ok = abs(float(top[2]) - mass) < 1e-6 and abs(float(top[6]) - score) < 1e-3
    except (TypeError, ValueError, IndexError):
        ok = False
    checks.append(("%s calc_mass/score" % cid, ok))
    try:
        mm, m1m, m2m = meas[cid]
        ok = (abs(float(top[3])) <= 5.0 and abs(float(top[4]) - m1m) <= 0.005
              and abs(float(top[5]) - m2m) <= 0.005)
    except (KeyError, TypeError, ValueError, IndexError):
        ok = False
    checks.append(("%s within tolerances" % cid, ok))
    try:
        blk = [float(r[6]) for r in rows if r[0] == cid]
        ok = blk == sorted(blk)
    except (ValueError, IndexError):
        ok = False
    checks.append(("%s sorted by score asc" % cid, ok))

fmt = re.compile(r"^-?\d+\.\d{6}\t[+-]\d+\.\d{3}\t-?\d+\.\d{6}\t-?\d+\.\d{6}\t\d+\.\d{4}$")
checks.append(("column formats (6/±3/6/6/4 decimals)",
    all(fmt.search("\t".join(r[2:])) for r in rows if len(r) == 7)))
finish(checks)
