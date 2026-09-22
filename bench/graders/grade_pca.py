#!/usr/bin/env python3
"""grade_pca.py — external grader for pca_untargeted (TEST_PLAN tier a). Reads cwd files."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grading import require_files, finish

require_files("stdout.txt", "scores.tsv", "loadings.tsv")

def close(a, b, tol):
    return a is not None and abs(a - b) <= tol

def load_tsv(path):
    lines = open(path).read().splitlines()
    header = lines[0].split("\t")
    rows = [l.split("\t") for l in lines[1:]]
    return header, rows

def num(r, i):
    try:
        return float(r[i])
    except (ValueError, IndexError):
        return None

checks = []
out = open("stdout.txt").read().splitlines()
checks.append(("stdout counts", out and out[0] == "kept 27 of 28 features (filtered: MET_X28)"))
checks.append(("stdout PC1", len(out) > 1 and out[1] == "PC1 variance fraction 0.9218"))
checks.append(("stdout PC2", len(out) > 2 and out[2] == "PC2 variance fraction 0.0719"))

sh, srows = load_tsv("scores.tsv")
checks.append(("scores header", sh == ["sample", "PC1", "PC2"]))
checks.append(("scores order", [r[0] for r in srows] ==
               ["CTRL_%d" % i for i in range(1, 6)] + ["EXP_%d" % i for i in range(1, 6)]))
pc1 = [num(r, 1) for r in srows]
checks.append(("sign rule", pc1[0] is not None and pc1[0] > 0))
checks.append(("separation", all(v is not None for v in pc1) and min(pc1[:5]) > max(pc1[5:])))
checks.append(("CTRL_1 PC1", close(pc1[0] if pc1 else None, 3.4354, 0.01)))
checks.append(("EXP_1 PC1", close(pc1[5] if len(pc1) > 5 else None, -3.6524, 0.01)))
checks.append(("CTRL_2 PC2", close(num(srows[1], 2) if len(srows) > 1 else None, -1.7934, 0.01)))

lh, lrows = load_tsv("loadings.tsv")
checks.append(("loadings header", lh == ["feature", "PC1", "PC2"]))
checks.append(("loadings rows", len(lrows) == 27 and "MET_X28" not in [r[0] for r in lrows]))
l1 = {r[0]: num(r, 1) for r in lrows}
l2 = {r[0]: num(r, 2) for r in lrows}
checks.append(("signal loadings", all(l1.get("MET_S%02d" % i) is not None
    and -0.35 <= l1["MET_S%02d" % i] <= -0.20 for i in range(1, 13))))
checks.append(("blockB loadings", all(l2.get("MET_B%02d" % i) is not None
    and 0.35 <= l2["MET_B%02d" % i] <= 0.45 for i in range(13, 19))))
checks.append(("noise loadings", all(abs(l1["MET_N%02d" % i]) < 0.05 for i in range(19, 27) if l1.get("MET_N%02d" % i) is not None)
    and l1.get("MET_M27") is not None and abs(l1["MET_M27"]) < 0.05))
finish(checks)
