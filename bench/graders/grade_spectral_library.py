#!/usr/bin/env python3
"""grade_spectral_library.py results.tsv stdout.log — external grader.
Re-implements the prompt's matching + scoring independently (criterion 7)."""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grading import require_files, finish

results_tsv, stdout_log = sys.argv[1], sys.argv[2]
require_files(results_tsv, stdout_log, "library.txt", "queries.txt")

def parse(path):
    specs, name, peaks = [], None, []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(">NAME"):
            if name is not None:
                specs.append((name, peaks))
            name, peaks = line.split()[1], []
        else:
            parts = line.split()
            peaks.append((float(parts[0]), float(parts[1])))
    if name is not None:
        specs.append((name, peaks))
    return specs

def score(qpeaks, lpeaks):
    used = [False] * len(lpeaks)
    dot = 0.0
    matched = 0
    for qmz, qi in sorted(qpeaks):
        best = None
        for j, (lmz, li) in enumerate(lpeaks):
            if used[j] or abs(qmz - lmz) > 0.5:
                continue
            key = (abs(qmz - lmz), lmz)
            if best is None or key < best[0]:
                best = (key, j)
        if best is not None:
            used[best[1]] = True
            dot += math.sqrt(qi * lpeaks[best[1]][1])
            matched += 1
    dq = sum(i for _, i in qpeaks)
    dl = sum(i for _, i in lpeaks)
    return ((dot * dot) / (dq * dl) if dq > 0 and dl > 0 else 0.0), matched

EXP = {"q1": ("caffeine", 0.9363, 0.9383, 7, 8), "q2": ("acetaminophen", 0.9103, 0.9123, 7, 8),
       "q3": ("sulfamethoxazole", 0.9573, 0.9593, 8, 8), "q4": ("NO_MATCH", -1e-9, 0.001, None, None)}

checks = []
checks.append(("c1 stdout summary line", "queries: 4  called: 3  no_match: 1" in open(stdout_log).read().splitlines()))
raw = open(results_tsv, "rb").read().decode()
lines = raw.splitlines()
rows = [l.split("\t") for l in lines[1:] if l]
checks.append(("c2 header/rows/format",
    lines[0] == "query_id\tbest_match\tscore\tmatched_peaks\ttotal_library_peaks"
    and len(rows) == 4 and [r[0] for r in rows] == ["q1", "q2", "q3", "q4"]
    and "," not in raw and "\r" not in raw))
for i, (qid, (name, lo, hi, mp, tp)) in enumerate(EXP.items()):
    try:
        r = rows[i]
        ok = r[1] == name and lo <= float(r[2]) <= hi
        if mp is not None:
            ok = ok and int(r[3]) == mp and int(r[4]) == tp
    except (ValueError, IndexError):
        ok = False
    checks.append(("c%d %s %s" % (i + 3, qid, name), ok))

lib = parse("library.txt")
qs = dict(parse("queries.txt"))
ok7 = True
for qid, want in (("q1", "caffeine"), ("q2", "acetaminophen"), ("q3", "sulfamethoxazole")):
    best, second = None, None
    for nm, lp in lib:                     # file order; strict > keeps first entry on ties
        s, _ = score(qs[qid], lp)
        if best is None or s > best[0]:
            second = best[0] if best else second
            best = (s, nm)
        elif second is None or s > second:
            second = s
    if best[1] != want or (second is None or second >= 0.03):
        ok7 = False
checks.append(("c7 runner-up separation (independent scorer)", ok7))
finish(checks)
