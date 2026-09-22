#!/usr/bin/env python3
"""grade_nmr_s.py <multiplets.tsv> <stdout.log> — grader for
examples/nmr_1d/PROMPT.md.

Two independent kinds of expectation are graded:

- the six assigned resonances' ppm positions, against the nominal chemical
  shifts pinned in data/nmr/README.md, written LITERALLY in this file (not
  sourced from nmr_ref), so a wrong reference implementation cannot certify
  a wrong tool; and
- the four graded metabolite integrals (acetate, citrate, creatinine CH3,
  creatinine CH2), which are not independently published to any precision
  finer than the README's own oracle output, against nmr_ref recomputed HERE
  from the workspace's own fid_complex.csv.

That reference recomputation is wrapped in try/except so a missing, empty or
corrupt fid_complex.csv leaves ref = None rather than propagating: every one
of the named criteria below must still print an explicit PASS or FAIL and
finish() must always be reached, as in grade_formula_s / grade_calibration_s.
A criterion that disappears is not a criterion that failed, and it makes the
per-criterion table non-comparable across tools.

TSP/DSS is the normalisation reference (data/nmr/README.md): its integral is
1.000 by construction, not an independently graded field, so criterion 3
checks both that the submitted TSP/DSS row sits at 1.000 AND that the four
metabolite integrals agree with the reference -- two things sharing one
criterion string because a submission that normalises to the wrong resonance
fails both at once, by construction. Water's position is graded (criterion
2); its integral is deliberately not graded anywhere in this file -- a
presaturated water line is broad and its integral is unusually sensitive to
the exact window width (data/nmr/README.md, "Oracle sensitivity check": the
worst ambiguous-reading deviation reaches +7.88% on the graded integrals but
was measured at +20.92% when water was normalised against in an earlier,
rejected design).

Criterion 4 exists because of this dataset's own history: the retired
real-channel-only FID (data/nmr/README.md) folds every resonance below the
carrier onto a mirror image at `ppm_tool = 9.5330 - ppm_true` -- so a tool
that sums `real` alone instead of `real + 1j*imag` produces a plausible-
looking spectrum whose TSP/DSS mirror lands near 9.53 ppm. No genuine
resonance in this sample is anywhere near there, so any row within
MIRROR_ABS_TOL of MIRROR_PPM is exactly that failure signature.

require_files is kept for the HARNESS-seeded input only: fid_complex.csv is
placed by run_bench, so its absence is a harness bug rather than a graded
failure mode of the submission (same distinction as grade_calibration_s /
grade_formula_s).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "reference", "short"))
from _grading import finish, num_field, require_files
import nmr_ref

CSV = "fid_complex.csv"
multiplets_path, stdout_path = sys.argv[1], sys.argv[2]
d = os.path.dirname(os.path.abspath(multiplets_path)) or "."
csv_path = os.path.join(d, CSV)
require_files(csv_path)
results = []

# Nominal chemical shifts (data/nmr/README.md). Written literally here, not
# sourced from nmr_ref, so a wrong reference implementation cannot certify a
# wrong tool.
NOMINAL_PPM = {
    "TSP/DSS": 0.000,
    "acetate": 1.921,
    "citrate": 2.549,
    "creatinine CH3": 3.048,
    "creatinine CH2": 4.058,
    "water": 4.767,
}
REFERENCE_NAME = "TSP/DSS"
GRADED_INTEGRAL_NAMES = ("acetate", "citrate", "creatinine CH3", "creatinine CH2")

POSITION_TOL_PPM = 0.05          # criterion 2, per README/prompt
TSP_TOL = 0.02                   # criterion 3: submitted TSP/DSS row vs 1.000
INTEGRAL_REL_TOL = 0.20          # criterion 3, per README/prompt
# Search radius used to LOCATE the row/peak nearest a nominal ppm, for both
# criterion 2 and criterion 3. Deliberately wider than POSITION_TOL_PPM: a
# position-only mutation that moves one ppm_center just past the 0.05 ppm
# tolerance (but not past this radius) must still be findable here, so that
# criterion 3 -- which relies on this same lookup to pair a row with its
# resonance -- keeps evaluating the (untouched) integral_rel instead of
# collapsing to "no row found" and failing for an unrelated reason. Without
# this margin the two criteria would not be independently discriminating
# (CONVENTIONS.md rule 9): a ppm-only mutation would trip both at once.
MATCH_WINDOW_PPM = 0.15
MIRROR_PPM = 9.5330              # 2*CARRIER_PPM - 0.000: the real-channel TSP/DSS mirror
MIRROR_ABS_TOL = 0.10            # no genuine resonance in this sample is anywhere near here
STDOUT_REF_PPM_TOL = 0.05        # criterion 5: reference_ppm=0.000 field


def check(name, ok):
    results.append((name, bool(ok)))


def read_text(path, newline=None):
    try:
        with open(path, newline=newline, errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


raw = read_text(multiplets_path, newline="") or ""
# Only a single trailing newline is stripped (if present) before splitting, so a
# blank line anywhere else in the file -- e.g. between the header and the first
# data row -- surfaces as an extra element and fails the row-parsing check
# below, rather than being silently dropped.
body = raw[:-1] if raw.endswith("\n") else raw
lines = body.split("\n") if body else []
hdr = lines[0].split("\t") if lines else []
data_rows = [ln.split("\t") for ln in lines[1:]]

FIELD_NAMES = ["ppm_center", "integral_rel"]


def header_col_map(hdr, names):
    """dict field name -> column index, valid only if `hdr` is exactly a
    permutation of `names` (no dupes, none missing, none extra). None
    otherwise. Deliberately more permissive than `hdr == FIELD_NAMES`
    (criterion 1's "columns in order" requirement): a reordered-but-complete
    header still yields a working map, so `rows` below -- and every value
    criterion built on it -- can find both fields under their own name even
    when criterion 1 fails on order alone. EVERY name in `names` that
    appears EXACTLY ONCE in `hdr` is resolved INDEPENDENTLY, so a column
    genuinely ABSENT from the header (or duplicated) simply has no entry in
    the returned dict rather than blanking the other field too
    (CONVENTIONS.md rule 10)."""
    return {name: hdr.index(name) for name in names if hdr.count(name) == 1}


# ppm_center is this grader's KEY field: every criterion below locates a
# row by searching `rows` for the nearest ppm_center to a nominal value
# (nearest_row), so `rows` fails closed only when ppm_center itself can't
# be resolved or a row's width disagrees with the header's. integral_rel
# is not a key -- if it is genuinely absent from the header, every row's
# second element is None, which only affects the criterion that reads it
# (integral_ok/tsp_ok below already guard against a None second element;
# positions_ok and the mirror check only ever read the first element).
col_map = header_col_map(hdr, FIELD_NAMES)
rows = []
if "ppm_center" in col_map and all(len(r) == len(hdr) for r in data_rows):
    try:
        rows = [(float(r[col_map["ppm_center"]]),
                  float(r[col_map["integral_rel"]])
                  if "integral_rel" in col_map else None)
                for r in data_rows]
    except ValueError:
        rows = []

sorted_ok = bool(rows) and [r[0] for r in rows] == sorted(r[0] for r in rows)
shape = ("\r" not in raw and hdr == FIELD_NAMES
          and all(len(r) == 2 for r in data_rows) and bool(rows) and sorted_ok)
check("multiplets.tsv: header + rows sorted by ppm_center, columns in order", shape)


def nearest_row(ppm_list, nominal, window=MATCH_WINDOW_PPM):
    """(ppm, integral) of the row nearest `nominal` within `window` ppm, or
    None if no row is that close."""
    candidates = [r for r in ppm_list if abs(r[0] - nominal) <= window]
    if not candidates:
        return None
    return min(candidates, key=lambda r: abs(r[0] - nominal))


positions_ok = rows and all(
    nearest_row(rows, nominal) is not None
    and abs(nearest_row(rows, nominal)[0] - nominal) <= POSITION_TOL_PPM
    for nominal in NOMINAL_PPM.values()
)
check("all six assigned resonances within 0.05 ppm on the true axis", positions_ok)

# Recompute the reference from the workspace's own fid_complex.csv. Any
# failure (missing file, empty file, malformed CSV, ...) leaves ref = None
# rather than propagating, so criterion 3 below fails explicitly instead of
# the whole grader crashing before finish() is reached.
try:
    ref = nmr_ref.run(csv_path)
except Exception:
    ref = None

ref_by_name = {}
if ref is not None:
    ref_rows = [(p["ppm_center"], p["integral_rel"]) for p in ref["peaks"]]
    for name, nominal in NOMINAL_PPM.items():
        r = nearest_row(ref_rows, nominal)
        if r is not None:
            ref_by_name[name] = r[1]


def integral_ok(name):
    nominal = NOMINAL_PPM[name]
    got_row = nearest_row(rows, nominal) if rows else None
    ref_integral = ref_by_name.get(name)
    if got_row is None or got_row[1] is None or ref_integral is None:
        return False
    return abs(got_row[1] - ref_integral) <= INTEGRAL_REL_TOL * abs(ref_integral)


tsp_row = nearest_row(rows, NOMINAL_PPM[REFERENCE_NAME]) if rows else None
tsp_ok = (tsp_row is not None and tsp_row[1] is not None
          and abs(tsp_row[1] - 1.000) <= TSP_TOL)

check("TSP is the reference row at 1.000 and the four metabolite integrals "
      "match the reference within 20%",
      ref is not None and tsp_ok and all(integral_ok(n) for n in GRADED_INTEGRAL_NAMES))

mirror_row = nearest_row(rows, MIRROR_PPM, window=MIRROR_ABS_TOL) if rows else None
# Gated on `bool(rows)`, not `shape`: an absent/malformed multiplets.tsv has
# no rows to search, which would otherwise make "no mirrored peak found"
# vacuously true for a submission that produced no readable output at all --
# the same failure mode this fix round exists to close for require_files,
# applied to a criterion that is phrased as an absence. `rows` (rule 10)
# already carries this protection -- it stays [] on a missing/malformed
# file exactly like `shape` did -- while, unlike `shape`, it still
# populates when the only defect is column order, so a reordered-but-
# complete header no longer drags this criterion down with criterion 1.
check("no mirrored peak near 9.53 ppm (real-channel processing)",
      bool(rows) and mirror_row is None)

out = read_text(stdout_path) or ""
points_field = num_field(out, "points")
peaks_field = num_field(out, "peaks")
ref_ppm_field = num_field(out, "reference_ppm")
check("stdout reports points, peaks and reference_ppm=0.000",
      points_field is not None and peaks_field is not None
      and ref_ppm_field is not None and abs(ref_ppm_field) <= STDOUT_REF_PPM_TOL)

finish(results)
