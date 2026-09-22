#!/usr/bin/env python3
"""grade_nmr_1d.py multiplets.tsv stdout.log stderr.log — external grader (TEST_PLAN tier a)."""
import math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grading import require_files, finish

tsv_path, out_path, err_path = sys.argv[1:4]
require_files(tsv_path, out_path)
tsv = open(tsv_path, newline="").read()
out = open(out_path).read()
checks = []

for line in ("points read: 10000", "zero-filled to: 16384", "peaks found: 4"):
    checks.append(("stdout %s" % line, line in out.splitlines()))

lines = tsv.split("\n")
checks.append(("header", lines[0] == "ppm_center\tintegral\trelative_integral"))
rows = [l.split("\t") for l in lines[1:] if l]
checks.append(("4 rows", len(rows) == 4 and all(len(r) == 3 for r in rows)))
checks.append(("tab-separated", "," not in tsv and "\r" not in tsv))
try:
    ppms = [float(r[0]) for r in rows]
    ok = True
except ValueError:
    ok = False
checks.append(("sorted ascending", ok and ppms == sorted(ppms)))
checks.append(("decimals", all(re.fullmatch(r"-?\d+\.\d{4}", r[0]) and re.fullmatch(r"-?\d+\.\d{2}", r[1])
                               and re.fullmatch(r"-?\d+\.\d{4}", r[2]) for r in rows)))
ORACLE = [(0.50, 1.0, 24654.39), (2.10, 1 / 9, 2768.91), (3.80, 2 / 9, 5451.26), (7.25, 3 / 9, 8166.71)]
for r, (p, rel, integ) in zip(rows, ORACLE):
    try:
        okp = abs(float(r[0]) - p) <= 0.02
        okr = abs(float(r[2]) - rel) <= 0.02
        oki = abs(float(r[1]) - integ) / integ <= 0.02
    except (ValueError, IndexError):
        okp = okr = oki = False
    checks.append(("ppm %s" % p, okp))
    checks.append(("rel %s" % p, okr))
    checks.append(("integral %s" % p, oki))

ok_fft = False
try:
    sys.path.insert(0, os.getcwd())
    from nmr_1d import fft
    X = fft([math.cos(2 * math.pi * 2 * n / 8) for n in range(8)])
    ok_fft = (abs(X[2] - 4) < 1e-9 and abs(X[6] - 4) < 1e-9
              and max(abs(X[k]) for k in range(8) if k not in (2, 6)) < 1e-9)
except Exception:
    pass
checks.append(("fft cosine", ok_fft))
finish(checks)
