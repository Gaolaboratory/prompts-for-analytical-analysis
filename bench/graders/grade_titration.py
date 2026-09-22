#!/usr/bin/env python3
"""grade_titration.py <dir> — external grader for the titration prompt (TEST_PLAN tier a)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grading import require_files, finish

d = sys.argv[1]
require_files(os.path.join(d, "titration.csv"), os.path.join(d, "results.tsv"))
results = []

def check(name, ok):
    results.append((name, bool(ok)))

rows = open(os.path.join(d, "titration.csv")).read().splitlines()
data = [l for l in rows if l and not l.startswith("#") and not l.startswith("titrant_volume")]
check("csv: comment+header+50 rows", rows[0].startswith("#") and rows[1] == "titrant_volume_mL,pH" and len(data) == 50)
check("csv: first row 0.00,2.892", data[0] == "0.00,2.892")
check("csv: last row 75.00,12.283", data[-1] == "75.00,12.283")

tsv = open(os.path.join(d, "results.tsv"), newline="").read()
check("tsv: LF only, no CR", "\r" not in tsv)
lines = [l for l in tsv.split("\n") if l]
check("tsv: header + 1 row", len(lines) == 2)
hdr = lines[0].split("\t")
check("tsv: 4 tab-separated columns in order",
      hdr == ["equivalence_volume_mL", "equivalence_volume_d2_mL", "pKa", "analyte_concentration_M"])
try:
    v1, v2, pka, ca = map(float, lines[1].split("\t"))
    ok = True
except (ValueError, IndexError):
    v1 = v2 = pka = ca = None
    ok = False
check("Veq within 0.50 mL of 50.00", ok and abs(v1 - 50.00) <= 0.50)
check("d1/d2 agree within 0.20 mL", ok and abs(v1 - v2) <= 0.20)
check("pKa within 0.05 of 4.76", ok and abs(pka - 4.76) <= 0.05)
check("concentration recovery within 2%", ok and abs(ca - 0.1000) <= 0.0020)
finish(results)
