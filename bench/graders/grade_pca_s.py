#!/usr/bin/env python3
"""grade_pca_s.py <scores.tsv> <stdout.log> — grader for examples/pca_untargeted/PROMPT.md.

Recomputes the reference from the workspace's own features.csv rather than trusting a
stored table, so a tool that overwrote its input cannot pass by accident.
Expected values: data/pca/README.md (184 kept, PC1 0.1558, PC2 0.1008, |r| > 0.999).

Missing, empty or corrupt features.csv/groups.csv/scores.tsv must not crash this
grader: every one of the 5 named criteria below must still print an explicit FAIL
and finish() must still be reached, rather than criteria vanishing from the verdict
list because of an uncaught exception.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "reference", "short"))
from _grading import finish, num_field
import pca_ref

scores_path, stdout_path = sys.argv[1], sys.argv[2]
results = []


def check(name, ok):
    results.append((name, bool(ok)))


def read_text(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


scores_text = read_text(scores_path)
out = read_text(stdout_path) or ""

# Recompute the reference from the workspace's own features.csv/groups.csv. Any
# failure (missing file, empty file, malformed CSV, wrong shape, ...) leaves
# ref = None rather than propagating, so every criterion below fails explicitly
# instead of the whole grader crashing before finish() is reached.
try:
    ref = pca_ref.run("features.csv", "groups.csv")
except Exception:
    ref = None

lines = [l for l in (scores_text or "").split("\n") if l]
hdr = lines[0].split("\t") if lines else []
rows = [l.split("\t") for l in lines[1:]]
group_of = dict(zip(ref["samples"], ref["groups"])) if ref is not None else {}
# The prompt requires the rows "in the order the columns appear in features.csv",
# and ref["samples"] IS that column order, so grade it rather than leaving an
# unevidenced requirement in the prompt. (The criteria below reorder before
# comparing, on purpose: a row-order slip should fail one criterion, not four.)
order_ok = ref is not None and [r[0] for r in rows if r] == ref["samples"]
shape = (ref is not None and hdr == ["sample", "group", "PC1", "PC2"]
          and len(rows) == 60
          and all(len(r) == 4 and group_of.get(r[0]) == r[1] for r in rows)
          and order_ok)
check("scores.tsv: header + 60 rows in features.csv column order, groups match "
      "groups.csv", shape)


def num(key):
    """Value of a `key=<number>` field in the tool's stdout, or None. Shared
    with the other graders (_grading.num_field): an absent key, an empty or
    non-numeric value, and a longer field that merely ends with `key` (e.g.
    "xfeatures_in=" searched for "features_in") all yield None."""
    return num_field(out, key)


check("stdout: features_in=200 features_kept=184",
      num("features_in") == 200 and num("features_kept") == 184)

pc1_var, pc2_var = num("pc1_var"), num("pc2_var")
check("pc1_var 0.1558 +/- 0.01 and pc2_var 0.1008 +/- 0.01",
      pc1_var is not None and abs(pc1_var - 0.1558) <= 0.01
      and pc2_var is not None and abs(pc2_var - 0.1008) <= 0.01)

corr_ok = False
first_positive = False
if shape:
    try:
        got = np.array([[float(r[2]), float(r[3])] for r in rows])
        order = [ref["samples"].index(r[0]) for r in rows]
        want = ref["scores"][order]
        corr_ok = all(abs(np.corrcoef(got[:, j], want[:, j])[0, 1]) >= 0.999
                      for j in (0, 1))
        first_positive = got[0, 0] > 0 and got[0, 1] > 0
    except (ValueError, IndexError):
        pass

check("PC1 and PC2 correlate with the reference at |r| >= 0.999", corr_ok)
check("first sample's PC1 and PC2 are positive (sign rule)", first_positive)

finish(results)
