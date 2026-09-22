#!/usr/bin/env python3
"""grade_calibration.py stdout.txt results.tsv [session] — external grader (TEST_PLAN tier a)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grading import require_files, finish, session_text_excluding_user

stdout_txt, results_tsv = sys.argv[1], sys.argv[2]
session = sys.argv[3] if len(sys.argv) > 3 and os.path.isfile(sys.argv[3]) else None
require_files(stdout_txt, results_tsv)

out = open(stdout_txt).read().splitlines()
checks = []
names = [l.split("\t")[0] for l in out]
checks.append(("c1 six stdout lines in order",
    len(out) == 6 and names == ["slope", "intercept", "r2", "sigma", "LOD", "LOQ"]))
vals = {}
for l in out:
    k, _, v = l.partition("\t")
    vals[k] = v

def close(key, want, tol):
    try:
        return abs(float(vals[key]) - want) <= tol
    except (KeyError, ValueError):
        return False

checks.append(("c2 slope/intercept/r2", close("slope", 2.5025, 0.02)
    and close("intercept", 0.0276, 0.005) and close("r2", 0.9998, 0.0005)))
checks.append(("c3 sigma/LOD/LOQ", close("sigma", 0.0046, 0.0005)
    and close("LOD", 0.0060, 0.0007) and close("LOQ", 0.0183, 0.0020)))
rows = [l.split("\t") for l in open(results_tsv).read().splitlines()]
checks.append(("c4 header + 3 rows in order", rows and rows[0] ==
    ["sample_id", "ratio", "calc_conc_ug_mL", "true_conc_ug_mL", "bias_pct"]
    and [r[0] for r in rows[1:]] == ["UNK_1", "UNK_2", "UNK_3"]))
try:
    checks.append(("c5 |bias| <= 5%", len(rows) == 4
        and all(abs(float(r[4])) <= 5.0 for r in rows[1:])))
except (ValueError, IndexError):
    checks.append(("c5 |bias| <= 5%", False))

ok6 = False
try:
    sys.path.insert(0, os.getcwd())
    from calibrate import wls
    res = wls([1, 2, 4], [2.1, 4.0, 8.3])
    ok6 = abs(res[0] - 2.0250) <= 0.0001 and abs(res[1] - 0.0571) <= 0.0001
except Exception:
    if session:
        # Fallback scans agent-side evidence only (non-user text): the session's
        # opening user message is the prompt, which quotes 2.0250/0.0571 and
        # would otherwise satisfy this criterion vacuously.
        txt = session_text_excluding_user(session)
        ok6 = "2.0250" in txt and "0.0571" in txt
checks.append(("c6 wls self-check 2.0250/0.0571", ok6))
finish(checks)
