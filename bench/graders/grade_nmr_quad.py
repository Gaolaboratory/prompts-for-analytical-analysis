#!/usr/bin/env python3
"""grade_nmr_quad.py multiplets.tsv stdout.log stderr.log — tier (a) grader.

Oracle numbers come from bench/reference/nmr_quad_spec.py, a literal implementation
of the prompt, and were checked insensitive to every ambiguous reading of the spec
(valley-stop comparison, maxbins rounding, sigma estimator, segment-centre convention).
"""
import cmath, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grading import require_files, finish

tsv_path, out_path = sys.argv[1], sys.argv[2]
require_files(tsv_path, out_path)
tsv = open(tsv_path, newline="").read()
out = open(out_path).read()
checks = []

# --- c1: pinned stdout lines -------------------------------------------------
for line in ("points read: 8192", "zero-filled to: 16384", "peaks found: 4"):
    checks.append(("stdout %r" % line, line in out.splitlines()))

# --- c2: file shape ----------------------------------------------------------
lines = tsv.split("\n")
checks.append(("header", lines[0] == "ppm_center\tintegral\trelative_integral"))
rows = [l.split("\t") for l in lines[1:] if l]
checks.append(("4 rows x 3 cols", len(rows) == 4 and all(len(r) == 3 for r in rows)))
checks.append(("tab-separated, unix newlines", "," not in tsv and "\r" not in tsv))

try:
    ppms = [float(r[0]) for r in rows]
    sorted_ok = ppms == sorted(ppms)
except (ValueError, IndexError):
    ppms, sorted_ok = [], False
checks.append(("sorted by ppm ascending", sorted_ok))
checks.append(("4-decimal ppm and relative_integral",
               len(rows) == 4 and all(re.fullmatch(r"-?\d+\.\d{4}", r[0])
                                      and re.fullmatch(r"-?\d+\.\d{4}", r[2]) for r in rows)))

# --- c3/c4/c5: values --------------------------------------------------------
# (ppm, ideal proton ratio, integral from the spec-exact reference)
ORACLE = [(1.20, 1.0, 3.2215e4), (3.50, 2 / 9, 7.2307e3),
          (7.20, 3 / 9, 1.0825e4), (8.50, 1 / 9, 3.5749e3)]
for i, (p, rel, integ) in enumerate(ORACLE):
    try:
        r = rows[i]
        okp = abs(float(r[0]) - p) <= 0.01
        okr = abs(float(r[2]) - rel) <= 0.02
        oki = abs(float(r[1]) - integ) / integ <= 0.03
    except (ValueError, IndexError):
        okp = okr = oki = False
    checks.append(("ppm %.2f" % p, okp))
    checks.append(("relative_integral %.2f" % p, okr))
    checks.append(("integral %.2f" % p, oki))

# --- c6: the agent's own fft against the pinned convention -------------------
ok_fft = False
try:
    sys.path.insert(0, os.getcwd())
    from nmr_quad import fft
    X = fft([math.cos(2 * math.pi * 2 * n / 8) for n in range(8)])
    delta = fft([1.0] + [0.0] * 7)
    # A real even input is symmetric under both sign conventions, so the cosine and
    # impulse checks cannot detect a flipped exponent. The complex exponential can:
    # exp(-2j..) puts the energy in bin 2, exp(+2j..) puts it in bin 6.
    cx = fft([cmath.exp(2j * math.pi * 2 * n / 8) for n in range(8)])
    ok_fft = (abs(X[2] - 4) < 1e-9 and abs(X[6] - 4) < 1e-9
              and max(abs(X[k]) for k in range(8) if k not in (2, 6)) < 1e-9
              and all(abs(d - 1) < 1e-9 for d in delta)
              and abs(cx[2] - 8) < 1e-9
              and max(abs(cx[k]) for k in range(8) if k != 2) < 1e-9)
except Exception:
    pass
checks.append(("fft convention self-check", ok_fft))

# --- c7: baseline step removes the 5.60 ppm broad component ------------------
checks.append(("no peak in 5.4-5.9 ppm", all(not (5.4 <= p <= 5.9) for p in ppms)))

finish(checks)
