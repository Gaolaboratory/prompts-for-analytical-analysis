#!/usr/bin/env python3
"""grade_chrom.py peaks.tsv stdout.log [session] — external grader (TEST_PLAN tier a)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grading import require_files, finish, session_text_excluding_user

peaks_tsv, stdout_log = sys.argv[1], sys.argv[2]
session = sys.argv[3] if len(sys.argv) > 3 and os.path.isfile(sys.argv[3]) else None
require_files(peaks_tsv, stdout_log)

HEADER = "peak_id\trt_apex\trt_start\trt_end\theight\tarea\twidth\tN\ttf\tsn\trs_to_previous"
lines = open(peaks_tsv).read().splitlines()
out = open(stdout_log).read()
checks = []

def num(row, i):
    try:
        return float(row[i])
    except (ValueError, IndexError):
        return None

def rng(v, lo, hi):
    return v is not None and lo <= v <= hi

def near(v, want, tol):
    return v is not None and abs(v - want) <= tol

rows = [l.split("\t") for l in lines[1:] if l]
numeric_ok = all(num(r, i) is not None for r in rows for i in range(1, 10))
checks.append(("c2 peaks.tsv structure", lines[0] == HEADER and len(rows) == 3 and numeric_ok
    and [num(r, 1) for r in rows] == sorted(num(r, 1) for r in rows) and rows[0][10] == "-"))

m = re.search(r"n\s*=\s*(\d+)[^\n]*?mean\s*=\s*([0-9.]+)[^\n]*?sd\s*=\s*([0-9.]+)", out)
checks.append(("c3 stdout noise stats", m is not None and m.group(1) == "26"
    and abs(float(m.group(2)) - 51.076) <= 0.001 and abs(float(m.group(3)) - 4.291) <= 0.001))
checks.append(("c4 stdout peaks detected: 3", "peaks detected: 3" in out.splitlines()))

apex = [num(r, 1) for r in rows]
checks.append(("c5 rt_apex ±1.0", len(apex) == 3
    and all(near(a, w, 1.0) for a, w in zip(apex, [60.0, 150.0, 244.0]))))
area = [num(r, 5) for r in rows]
height = [num(r, 4) for r in rows]
checks.append(("c6 area ±5% and height ±5%",
    all(near(a, w, 0.05 * w) for a, w in zip(area, [7821.509, 14920.273, 12032.407]))
    and all(near(h, w, 0.05 * w) for h, w in zip(height, [786.254, 1198.618, 725.128]))))
tf = [num(r, 8) for r in rows]
checks.append(("c7 tf bands", all(near(t, w, 0.10) for t, w in zip(tf, [0.993, 0.988, 1.339]))
    and rng(tf[0], 0.9, 1.1) and rng(tf[1], 0.9, 1.1) and tf[2] is not None and tf[2] > 1.2))
nplate = [num(r, 7) for r in rows]
rs = [num(rows[1], 10), num(rows[2], 10)] if len(rows) == 3 else [None, None]
sn = [num(r, 9) for r in rows]
checks.append(("c8 N/rs/sn",
    all(near(n, w, 0.15 * w) for n, w in zip(nplate, [100.0, 330.579, 314.901]))
    and all(near(v, w, 0.15) for v, w in zip(rs, [3.158, 2.136]))
    and all(near(s, w, 0.10 * w) for s, w in zip(sn, [183.245, 279.350, 168.999]))))

ok1 = False
if session:
    # Agent-side evidence only: the session's first user message is the prompt
    # itself and echoes these literals, so a whole-file scan would pass
    # vacuously (regression: chrom/local/1 passed c1 with no agent self-check).
    txt = session_text_excluding_user(session)
    ok1 = all(t in txt for t in ("4.000", "2.000", "1.000", "0.100", "3.900"))
checks.append(("c1 triangle self-check (session)", ok1))
finish(checks)
