#!/usr/bin/env python3
"""grade_features_s.py <features.tsv> <stdout.log> — grader for
examples/feature_extraction/PROMPT.md.

Bounds are the qualitative consistency bounds pinned in
data/feature_extraction/README.md: N within a factor ~2 of the reference 240, and at
least half of the reference top-10 events recovered.

Those bounds alone are forgeable: the ten reference (m/z, RT) pairs are printed in
examples/feature_extraction/PROMPT.md, so a fabricated 120-row features.tsv carrying
those ten pairs scored 5/5 without ever opening BSA1_F1.mzML. The last criterion
therefore recomputes the reference HERE, from the workspace's own mzML, and requires
substantial agreement over the reference's top 100 features -- ninety of which appear
nowhere in the prompt -- plus consistency between the tool's own reported feature
count and the rows it actually wrote.

Missing, empty or malformed features.tsv/stdout.log must not crash this grader:
every one of the 5 named criteria below must still print an explicit FAIL and
finish() must still be reached, rather than criteria vanishing from the verdict
list because of an uncaught exception or an early sys.exit before finish().
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "reference", "short"))
from _grading import finish, num_field
import features_ref

# data/feature_extraction/README.md, "Top 10 events by apex intensity" (m/z, RT s)
TOP10 = [(395.2392, 1943.80), (487.7323, 1848.68), (395.7405, 1941.74),
         (325.4912, 1850.10), (488.2334, 1848.68), (388.2539, 1977.38),
         (443.7112, 1749.73), (722.3250, 1788.01), (738.3110, 1900.27),
         (344.2280, 1827.04)]
HEADER = ["feature_id", "mz", "rt_apex", "rt_start", "rt_end",
          "apex_intensity", "n_scans"]
MZML = "BSA1_F1.mzML"           # the input the spec's run_cmd pins
MZ_TOL, RT_TOL = 0.01, 10.0     # data/feature_extraction/README.md match window
# Agreement window and threshold for the recomputed-reference criterion. TOP_N is
# far beyond the 10 features printed in the prompt, so the criterion cannot be
# satisfied from the prompt text. The threshold has wide margin over every
# measured pilot output (240/240, 240/240, 252 -> 97/100, 240 -> 100/100) and over
# the reference recipe's own documented parameter sensitivity (K in {100, 300},
# k_mad in {4, 6}, min_run 4, mz_tol 0.02 -> 81..100 of the same top 100).
TOP_N, MIN_MATCHED = 100, 70

feat_path, stdout_path = sys.argv[1], sys.argv[2]
results = []


def check(name, ok):
    results.append((name, bool(ok)))


def read_text(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


feat_text = read_text(feat_path)
out = read_text(stdout_path) or ""

lines = [l for l in (feat_text or "").split("\n") if l]
hdr = lines[0].split("\t") if lines else []
rows = [l.split("\t") for l in lines[1:]]
shape = hdr == HEADER and bool(rows) and all(len(r) == 7 for r in rows)
check("features.tsv: header + N rows, 7 columns in order", shape)
check("120 <= N <= 480", shape and 120 <= len(rows) <= 480)

parsed = []
if shape:
    for r in rows:
        try:
            parsed.append((float(r[1]), float(r[2]), float(r[3]), float(r[4]),
                           float(r[5])))
        except ValueError:
            parsed = []
            break

matched = sum(1 for mz, rt in TOP10
              if any(abs(p[0] - mz) <= 0.01 and abs(p[1] - rt) <= 10.0
                     for p in parsed))
check("at least 5 of the 10 reference features matched", matched >= 5)
check("every apex_intensity > 0 and rt_start <= rt_apex <= rt_end",
      bool(parsed) and all(p[4] > 0 and p[2] <= p[1] <= p[3] for p in parsed))


def num(key):
    """Value of a `key=<number>` field in the tool's stdout, or None. Shared
    with the other graders (_grading.num_field): an absent key, an empty or
    non-numeric value, and a longer field that merely ends with `key` (e.g.
    "total_ms1_scans=" searched for "ms1_scans") all yield None."""
    return num_field(out, key)


check("stdout: ms1_scans=286", num("ms1_scans") == 286)


def reference_agreement():
    """True iff the tool's feature set covers most of the reference's top TOP_N
    features, recomputed from the workspace's own mzML, and the tool's reported
    feature count matches the rows it wrote.

    Any failure -- missing/unreadable mzML, a reference crash, malformed rows --
    makes this criterion FAIL rather than raising, so finish() is still reached.
    """
    if not parsed:
        return False
    try:
        ref = features_ref.detect(MZML)
    except Exception as exc:
        print("# features_ref.detect(%s) raised %s: %s"
              % (MZML, type(exc).__name__, exc))
        return False
    top = ref["features"][:TOP_N]
    if len(top) < TOP_N:
        print("# reference produced only %d features, expected >= %d"
              % (len(top), TOP_N))
        return False
    matched_ref = sum(1 for f in top
                      if any(abs(p[0] - f["mz"]) <= MZ_TOL
                             and abs(p[1] - f["rt_apex"]) <= RT_TOL
                             for p in parsed))
    reported = num("features")
    consistent = reported is not None and int(reported) == len(rows)
    if not consistent:
        print("# stdout features=%s but features.tsv holds %d data rows"
              % (reported, len(rows)))
    if matched_ref < MIN_MATCHED:
        print("# only %d of the reference's top %d features matched (need %d)"
              % (matched_ref, TOP_N, MIN_MATCHED))
    return matched_ref >= MIN_MATCHED and consistent


check("at least 70 of the recomputed reference's top 100 features matched, and "
      "stdout features=N equals the row count", reference_agreement())

finish(results)
