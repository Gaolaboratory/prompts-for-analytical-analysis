#!/usr/bin/env python3
"""grade_calibration_s.py <dir> — external grader for examples/calibration/PROMPT.md.

Two independent kinds of expectation are graded:

- slope/intercept/residual_sd/r_squared against the NIST StRD Norris certified
  values, written LITERALLY in this file (not sourced from calibration_ref), so
  a wrong reference implementation cannot certify a wrong tool; and
- lod/loq, which are not NIST-certified quantities, against calibration_ref
  recomputed HERE from the workspace's own norris.csv.

That reference recomputation is wrapped in try/except so a missing, empty or
corrupt norris.csv leaves ref = None rather than propagating: every one of the
named criteria below must still print an explicit PASS or FAIL and finish()
must always be reached, as in grade_titration_s / grade_pca_s / grade_
mass_reader_s. A criterion that disappears is not a criterion that failed, and
it makes the per-criterion table non-comparable across tools.

Every constant a tool would need to fake criteria 2-4 is printed in
examples/calibration/PROMPT.md's Method section (the NIST table is public), so
a tool could hardcode results.tsv/stdout.log and pass 1-5 without ever opening
norris.csv. Criterion 6 closes that hole: it re-runs the submitted calibrate.py
on a copy of norris.csv perturbed to a different, non-certified answer and
requires slope/intercept/residual_sd/r_squared to agree with calibration_ref
recomputed from THAT perturbed input, at 1e-6 relative -- not merely to differ
from the unperturbed run.

The perturbation matters: an EARLIER version of this file scaled every y by a
single factor (1.05). Under a uniform y -> k*y rescale, OLS slope, intercept
and residual SD all scale by exactly k -- so a tool that computes the scale
factor and multiplies hardcoded constants by it reproduces three of the four
fields *correctly*, by closed-form algebra, without ever doing per-point OLS.
Only R-squared (scale-invariant) caught that forgery, which means the
criterion was surviving on one field's accident rather than doing its job.
PERTURB_FACTOR is therefore applied to every third row ONLY (index % 3 == 0),
leaving the rest of the data untouched: no single scale factor, or any other
closed-form correction, relates the perturbed fit back to the original or the
certified values, so a tool that does not actually re-fit the perturbed data
cannot reproduce all four fields.

require_files is kept for the HARNESS-seeded input only: norris.csv is placed
by run_bench, so its absence is a harness bug rather than a graded failure mode
of the submission (same distinction as grade_titration_s / grade_mass_reader_s).
"""
import os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "reference", "short"))
from _grading import finish, num_field, require_files
import calibration_ref

CSV = "norris.csv"
TOOL = "calibrate.py"
PERTURB_FACTOR = 1.10      # every third row's y scaled by this (see below)
PERTURB_STRIDE = 3         # row index % PERTURB_STRIDE == 0 gets scaled
REL_TOL_CERT = 1e-9        # slope/intercept/residual_sd/r_squared vs NIST
REL_TOL_REF = 1e-6         # lod/loq, and the perturbed re-run, vs the reference

# NIST StRD certified values for the Norris dataset (data/calibration/README.md).
# Written literally here, not sourced from calibration_ref, so a wrong reference
# implementation cannot certify a wrong tool.
CERT_SLOPE = 1.00211681802045
CERT_INTERCEPT = -0.262323073774029
CERT_RESID_SD = 0.884796396144373
CERT_R2 = 0.999993745883712

d = sys.argv[1]
require_files(os.path.join(d, CSV))
results = []


def check(name, ok):
    results.append((name, bool(ok)))


def read_text(path, newline=None):
    try:
        with open(path, newline=newline, errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


raw = read_text(os.path.join(d, "results.tsv"), newline="") or ""
# Only a single trailing newline is stripped (if present) before splitting, so a
# blank line anywhere else in the file — e.g. between the header and the data
# row — surfaces as an extra element and fails the line-count check below,
# rather than being silently dropped.
body = raw[:-1] if raw.endswith("\n") else raw
lines = body.split("\n") if body else []
hdr = lines[0].split("\t") if lines else []
data_fields = lines[1].split("\t") if len(lines) > 1 else []
FIELD_NAMES = ["slope", "intercept", "residual_sd", "r_squared", "lod", "loq"]
shape = ("\r" not in raw and len(lines) == 2
         and hdr == FIELD_NAMES
         and len(data_fields) == 6)
check("results.tsv: header + exactly one data row, columns in order, no CR", shape)


def named_fields(hdr, fields, names):
    """dict name -> field string, resolved INDEPENDENTLY for each name in
    `names` that appears EXACTLY ONCE in `hdr` -- so a results.tsv whose
    columns are present but reordered still yields every value under its
    own name, and a column that is genuinely ABSENT from the header (or
    duplicated) simply has no entry in the returned dict rather than
    blanking every other field too (CONVENTIONS.md rule 10). Returns {}
    only if the row's width doesn't match the header's at all, since then
    no column's position can be trusted for this row, full stop. Used for
    criteria 2-4/6, kept separate from `shape`'s strict "in order and
    complete" requirement, which is criterion 1's job alone."""
    if len(fields) != len(hdr):
        return {}
    return {name: fields[hdr.index(name)] for name in names
            if hdr.count(name) == 1}


def _floats(named, names):
    """dict name -> float for every name in `names` present in `named` and
    parseable as a number; a name that's missing or unparseable is simply
    absent from the returned dict (Rule 10) -- callers use .get(name)."""
    out = {}
    for n in names:
        v = named.get(n)
        if v is None:
            continue
        try:
            out[n] = float(v)
        except ValueError:
            pass
    return out


named = named_fields(hdr, data_fields, FIELD_NAMES)
values = _floats(named, FIELD_NAMES)
slope = values.get("slope")
intercept = values.get("intercept")
resid_sd = values.get("residual_sd")
r2 = values.get("r_squared")
lod = values.get("lod")
loq = values.get("loq")


def rel_ok(got, want, tol):
    return got is not None and abs(got - want) <= tol * abs(want)


check("slope and intercept match the NIST certified values (<=1e-9 relative)",
      rel_ok(slope, CERT_SLOPE, REL_TOL_CERT)
      and rel_ok(intercept, CERT_INTERCEPT, REL_TOL_CERT))

check("residual_sd and r_squared match the NIST certified values (<=1e-9 relative)",
      rel_ok(resid_sd, CERT_RESID_SD, REL_TOL_CERT)
      and rel_ok(r2, CERT_R2, REL_TOL_CERT))

# Recompute the reference from the workspace's own norris.csv. Any failure
# (missing file, empty file, malformed CSV, non-numeric columns, ...) leaves
# ref = None rather than propagating, so every criterion below fails
# explicitly instead of the whole grader crashing before finish() is reached.
try:
    ref = calibration_ref.run(os.path.join(d, CSV))
except Exception:
    ref = None

check("lod and loq match the reference recomputed from norris.csv (<=1e-6 relative)",
      ref is not None
      and rel_ok(lod, ref["lod"], REL_TOL_REF)
      and rel_ok(loq, ref["loq"], REL_TOL_REF))

out = read_text(os.path.join(d, "stdout.log")) or ""

check("stdout reports all seven fields",
      all(num_field(out, key) is not None
          for key in ("n", "slope", "intercept", "residual_sd", "r_squared",
                      "lod", "loq")))


def perturbed_csv(src, dst):
    """Copy `src` with every PERTURB_STRIDE-th data row's y scaled by
    PERTURB_FACTOR, the rest untouched.

    Scaling only a subset of rows -- rather than every row by one factor --
    means no single scale factor (or any other closed-form transform) maps
    the original fit onto the perturbed one: a tool has to actually re-run
    OLS on the perturbed points to reproduce slope/intercept/residual_sd/R^2,
    not just rescale its old answer.
    """
    with open(src, newline="") as fh:
        lines = [l for l in fh.read().split("\n") if l.strip()]
    out_lines = [lines[0]]
    for i, line in enumerate(lines[1:]):
        y, rest = line.split(",", 1)
        factor = PERTURB_FACTOR if i % PERTURB_STRIDE == 0 else 1.0
        out_lines.append("%.10g,%s" % (float(y) * factor, rest))
    with open(dst, "w", newline="") as fh:
        fh.write("\n".join(out_lines) + "\n")


def read_row(path):
    """(slope, intercept, resid_sd, r2) from a results.tsv, or None if
    unreadable/malformed. Looks each field up BY NAME in whatever order the
    file's own header gives (via named_fields), the same as the initial
    results.tsv above, so a column-order slip in the freshly re-run
    perturbed output doesn't corrupt this criterion either (rule 10)."""
    text = read_text(path, newline="")
    if not text:
        return None
    rows = [l for l in text.split("\n") if l.strip()]
    if len(rows) < 2:
        return None
    row_hdr = rows[0].split("\t")
    fields = rows[1].split("\t")
    named = named_fields(row_hdr, fields, FIELD_NAMES)
    try:
        return tuple(float(named[n]) for n in
                     ("slope", "intercept", "residual_sd", "r_squared"))
    except (KeyError, ValueError):
        return None


def perturbation_matches_reference():
    """True iff re-running the submitted calibrate.py on a perturbed copy of
    norris.csv reports slope/intercept/residual_sd/r_squared that agree, at
    REL_TOL_REF, with calibration_ref recomputed from THAT perturbed input --
    not merely a slope that differs from the unperturbed run. A tool that
    detects the every-third-row perturbation (see PERTURB_FACTOR above) and
    reports certified_constant * some derived ratio without doing per-point
    OLS would satisfy a movement-only check while still not analysing the
    perturbed data; comparing against the reference for the perturbed input
    catches that.

    Any failure -- missing calibrate.py, a crash, a timeout, or unreadable
    output on either the perturbation build or the re-run -- makes this
    criterion FAIL rather than raising: finish() must still be reached.
    """
    tmp = tempfile.mkdtemp(prefix="perturb_")
    try:
        # Run in a scratch directory so the submission cannot overwrite its
        # own graded results.tsv, and copy every module it shipped in case it
        # split the analysis across files.
        for name in sorted(os.listdir(d)):
            if name.endswith(".py"):
                shutil.copy2(os.path.join(d, name), tmp)
        if not os.path.isfile(os.path.join(tmp, TOOL)):
            print("# %s missing: cannot re-run it on a perturbed input" % TOOL)
            return False
        perturbed_path = os.path.join(tmp, "norris_perturbed.csv")
        try:
            perturbed_csv(os.path.join(d, CSV), perturbed_path)
            want = calibration_ref.run(perturbed_path)
        except Exception as exc:
            print("# building/reference-fitting the perturbed input raised "
                  "%s: %s" % (type(exc).__name__, exc))
            return False
        try:
            proc = subprocess.run(
                [sys.executable, TOOL, "norris_perturbed.csv", "-o", "perturbed.tsv"],
                cwd=tmp, timeout=120, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            print("# %s timed out on the perturbed input" % TOOL)
            return False
        if proc.returncode != 0:
            print("# %s exited %d on the perturbed input: %s"
                  % (TOOL, proc.returncode, (proc.stderr or "").strip()[:200]))
            return False
        got = read_row(os.path.join(tmp, "perturbed.tsv"))
        if got is None:
            got = read_row(os.path.join(tmp, "results.tsv"))
        if got is None:
            print("# perturbed run produced no readable results row")
            return False
        got_slope, got_intercept, got_residual_sd, got_r_squared = got
        agrees = (rel_ok(got_slope, want["slope"], REL_TOL_REF)
                  and rel_ok(got_intercept, want["intercept"], REL_TOL_REF)
                  and rel_ok(got_residual_sd, want["residual_sd"], REL_TOL_REF)
                  and rel_ok(got_r_squared, want["r_squared"], REL_TOL_REF))
        if not agrees:
            print("# perturbed input: tool %r vs reference "
                  "(slope=%.9f intercept=%.9f residual_sd=%.9f r_squared=%.9f)"
                  % (got, want["slope"], want["intercept"], want["residual_sd"],
                     want["r_squared"]))
        return agrees
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


check("re-running calibrate.py on a perturbed norris.csv reproduces the "
      "reference fit for that input",
      perturbation_matches_reference())

finish(results)
