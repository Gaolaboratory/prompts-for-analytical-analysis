#!/usr/bin/env python3
"""grade_uvvis_s.py <dir> — external grader for examples/uvvis_spectrum/PROMPT.md.

Two independent kinds of expectation are graded:

- lambda_max/epsilon against the published/measured constants pinned in
  data/uvvis/README.md (317 +/- 3 nm, epsilon within 2% of 9283.39), written
  LITERALLY in this file (not sourced from uvvis_ref), so a wrong reference
  implementation cannot certify a wrong tool; and
- fwhm, which is not independently published, against uvvis_ref recomputed
  HERE from the workspace's own 4-nitrophenol.csv.

That reference recomputation is wrapped in try/except so a missing, empty or
corrupt 4-nitrophenol.csv leaves ref = None rather than propagating: every one
of the named criteria below must still print an explicit PASS or FAIL and
finish() must always be reached, as in grade_calibration_s / grade_titration_s.
A criterion that disappears is not a criterion that failed, and it makes the
per-criterion table non-comparable across tools.

Every constant a tool would need to fake criteria 2-5 is printed in
examples/uvvis_spectrum/PROMPT.md's Method section (the published lambda_max
and the README's measured epsilon are public), so a tool could hardcode
bands.tsv/stdout.log and pass 1-5 without ever opening 4-nitrophenol.csv.
Criterion 6 closes that hole: it re-runs the submitted uvvis.py on a copy of
4-nitrophenol.csv perturbed by an absorbance ramp and requires BOTH lambda_max
(within 0.5 nm) and epsilon (within 2%) to agree with uvvis_ref recomputed
from THAT perturbed input -- not merely to differ from the unperturbed run.

Both fields are checked because the wavelength grid on this file is ~1.0002
nm, so the ramp only moves the reference lambda_max by one grid step (317.015
-> 317.994) -- a real but narrow margin against the 0.5 nm tolerance that a
gentler ramp, a finer grid, or a different peak-location convention could
erode toward zero. The same ramped run moves epsilon by 18.4% (9283.39 ->
10994.08), roughly 9x wider against its 2% tolerance -- exactly the "check
every recoverable field, not one" lesson grade_calibration_s.py's perturbation
already encodes. FWHM is deliberately NOT part of this check: the ramp moves
it by only ~0.3 nm against a 2 nm tolerance, so it would add no discriminating
power, only a way for a correct tool to fail.

The perturbation matters: an earlier design for this task shifted every
wavelength by a constant (+5 nm). Under a uniform wavelength shift, lambda_max
moves by exactly that shift -- so a tool that detects the offset (e.g. by
comparing the first row's wavelength to a hardcoded expectation) and adds it
to a hardcoded 317.015 would reproduce the perturbed lambda_max *correctly*,
by closed-form arithmetic, without ever locating the band maximum. The ramp
1 + 0.002*(wavelength_nm - 225) instead tilts the band -- it multiplies
absorbance by a wavelength-dependent factor, leaving every wavelength where it
was -- so the apparent maximum shifts by an amount that depends on the whole
band shape and is obtainable only by re-analysing the ramped spectrum: no
wavelength offset (zero, in fact -- the grid is untouched) can be added to a
hardcoded lambda_max to reproduce it. The criterion's name reflects this: the
perturbation tilts absorbance, not wavelength, so it is described below as
"absorbance-tilted", not "wavelength-shifted".

require_files is kept for the HARNESS-seeded input only: 4-nitrophenol.csv is
placed by run_bench, so its absence is a harness bug rather than a graded
failure mode of the submission (same distinction as grade_calibration_s /
grade_titration_s).
"""
import os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "reference", "short"))
from _grading import finish, num_field, require_files
import uvvis_ref

CSV = "4-nitrophenol.csv"
TOOL = "uvvis.py"
RAMP_SLOPE = 0.002          # absorbance *= 1 + RAMP_SLOPE * (wavelength_nm - RAMP_ANCHOR)
RAMP_ANCHOR = 225.0
ABS_TOL_LAMBDA = 3.0        # published lambda_max, nm
REL_TOL_EPSILON = 0.02      # published epsilon, relative
ABS_TOL_FWHM = 2.0          # fwhm vs reference, nm
ABS_TOL_PERTURB_LAMBDA = 0.5   # perturbed re-run lambda_max vs reference, nm
REL_TOL_PERTURB_EPSILON = 0.02  # perturbed re-run epsilon vs reference, relative

# Published/measured constants (data/uvvis/README.md). Written literally here,
# not sourced from uvvis_ref, so a wrong reference implementation cannot
# certify a wrong tool.
PUBLISHED_LAMBDA_MAX = 317.0
PUBLISHED_EPSILON = 9283.39

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


raw = read_text(os.path.join(d, "bands.tsv"), newline="") or ""
# Only a single trailing newline is stripped (if present) before splitting, so a
# blank line anywhere else in the file -- e.g. between the header and the data
# row -- surfaces as an extra element and fails the line-count check below,
# rather than being silently dropped.
body = raw[:-1] if raw.endswith("\n") else raw
lines = body.split("\n") if body else []
hdr = lines[0].split("\t") if lines else []
data_fields = lines[1].split("\t") if len(lines) > 1 else []
FIELD_NAMES = ["lambda_max_nm", "epsilon", "fwhm_nm"]
shape = ("\r" not in raw and len(lines) == 2
         and hdr == FIELD_NAMES
         and len(data_fields) == 3)
check("bands.tsv: header + exactly one band row, columns in order, no CR", shape)


def named_fields(hdr, fields, names):
    """dict name -> field string, resolved INDEPENDENTLY for each name in
    `names` that appears EXACTLY ONCE in `hdr` -- so a bands.tsv whose
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


lambda_max = epsilon = fwhm = None
named = named_fields(hdr, data_fields, FIELD_NAMES)
try:
    lambda_max = float(named["lambda_max_nm"]) if "lambda_max_nm" in named else None
except ValueError:
    lambda_max = None
try:
    epsilon = float(named["epsilon"]) if "epsilon" in named else None
except ValueError:
    epsilon = None
try:
    fwhm = float(named["fwhm_nm"]) if "fwhm_nm" in named else None
except ValueError:
    fwhm = None


def abs_ok(got, want, tol):
    return got is not None and abs(got - want) <= tol


def rel_ok(got, want, tol):
    return got is not None and abs(got - want) <= tol * abs(want)


check("lambda_max 317 +/- 3 nm",
      abs_ok(lambda_max, PUBLISHED_LAMBDA_MAX, ABS_TOL_LAMBDA))

check("epsilon within 2% of 9283",
      rel_ok(epsilon, PUBLISHED_EPSILON, REL_TOL_EPSILON))

# Recompute the reference from the workspace's own 4-nitrophenol.csv. Any
# failure (missing file, empty file, malformed CSV, non-numeric columns, ...)
# leaves ref = None rather than propagating, so every criterion below fails
# explicitly instead of the whole grader crashing before finish() is reached.
try:
    ref = uvvis_ref.run(os.path.join(d, CSV))
except Exception:
    ref = None

check("fwhm within 2 nm of the reference recomputed from the input",
      ref is not None and abs_ok(fwhm, ref["fwhm"], ABS_TOL_FWHM))

out = read_text(os.path.join(d, "stdout.log")) or ""

check("stdout reports points, bands, lambda_max and epsilon",
      all(num_field(out, key) is not None
          for key in ("points", "bands", "lambda_max", "epsilon")))


def ramped_csv(src, dst):
    """Copy `src` with absorbance multiplied by the wavelength-dependent ramp
    1 + RAMP_SLOPE * (wavelength_nm - RAMP_ANCHOR), wavelengths untouched.

    Tilting the band by a factor that grows with wavelength -- rather than
    shifting every wavelength by a constant -- means no wavelength offset (or
    any other closed-form correction applied to a hardcoded lambda_max) maps
    the original band maximum onto the ramped one: a tool has to actually
    re-locate the maximum of the ramped trace to reproduce lambda_max, not
    just add an offset to its old answer.
    """
    with open(src, newline="") as fh:
        lines = [l for l in fh.read().split("\n") if l.strip()]
    out_lines = [lines[0]]
    for line in lines[1:]:
        wl, absb = line.split(",", 1)
        wl_f = float(wl)
        factor = 1.0 + RAMP_SLOPE * (wl_f - RAMP_ANCHOR)
        out_lines.append("%.5f,%.5f" % (wl_f, float(absb) * factor))
    with open(dst, "w", newline="") as fh:
        fh.write("\n".join(out_lines) + "\n")


def read_lambda_max_epsilon(path):
    """(lambda_max, epsilon) from a bands.tsv, or None if unreadable/malformed.
    Looks each field up BY NAME in whatever order the file's own header
    gives (via named_fields), the same as the initial bands.tsv above, so a
    column-order slip in the freshly re-run ramped output doesn't corrupt
    this criterion either (rule 10)."""
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
        return float(named["lambda_max_nm"]), float(named["epsilon"])
    except (KeyError, ValueError):
        return None


def perturbation_matches_reference():
    """True iff re-running the submitted uvvis.py on a ramped copy of
    4-nitrophenol.csv reports a lambda_max (within ABS_TOL_PERTURB_LAMBDA) AND
    an epsilon (within REL_TOL_PERTURB_EPSILON) that both agree with
    uvvis_ref recomputed from THAT ramped input -- not merely values that
    differ from the unperturbed run.

    Both fields are required because, on this file's ~1.0002 nm grid, the
    ramp only moves the reference lambda_max by one grid step (317.015 ->
    317.994): real, but a margin against the 0.5 nm tolerance that is easily
    eroded by a gentler ramp, a finer grid, or a different peak-location
    convention. The same ramped run moves epsilon by 18.4% (9283.39 ->
    10994.08), roughly 9x its own 2% tolerance -- a substantially wider
    margin than lambda_max's, on a field a tool already reports on the same
    line, so checking it too costs nothing. It does not widen lambda_max's
    own margin (checking epsilon leaves that criterion exactly as narrow as
    before); it adds a second, independent way to catch a forger, so the
    forger must now fool both fields rather than only the narrower one. A
    tool that detects a wavelength offset and reports hardcoded_317.015 +
    offset (plus a hardcoded epsilon) without ever re-locating the band
    maximum would satisfy a movement-only check while still not analysing the
    perturbed data; comparing both fields against the reference for the
    ramped input catches that (the ramp introduces no wavelength offset at
    all, so such a tool reports the unperturbed 317.015 and 9283.39, both of
    which disagree with the ramped reference).

    Any failure -- missing uvvis.py, a crash, a timeout, or unreadable output
    on either the perturbation build or the re-run -- makes this criterion
    FAIL rather than raising: finish() must still be reached.
    """
    tmp = tempfile.mkdtemp(prefix="ramp_")
    try:
        # Run in a scratch directory so the submission cannot overwrite its
        # own graded bands.tsv, and copy every module it shipped in case it
        # split the analysis across files.
        for name in sorted(os.listdir(d)):
            if name.endswith(".py"):
                shutil.copy2(os.path.join(d, name), tmp)
        if not os.path.isfile(os.path.join(tmp, TOOL)):
            print("# %s missing: cannot re-run it on a perturbed input" % TOOL)
            return False
        ramped_path = os.path.join(tmp, "4-nitrophenol_ramped.csv")
        try:
            ramped_csv(os.path.join(d, CSV), ramped_path)
            want = uvvis_ref.run(ramped_path)
        except Exception as exc:
            print("# building/reference-fitting the ramped input raised "
                  "%s: %s" % (type(exc).__name__, exc))
            return False
        try:
            proc = subprocess.run(
                [sys.executable, TOOL, "4-nitrophenol_ramped.csv", "-o", "ramped.tsv"],
                cwd=tmp, timeout=120, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            print("# %s timed out on the ramped input" % TOOL)
            return False
        if proc.returncode != 0:
            print("# %s exited %d on the ramped input: %s"
                  % (TOOL, proc.returncode, (proc.stderr or "").strip()[:200]))
            return False
        got = read_lambda_max_epsilon(os.path.join(tmp, "ramped.tsv"))
        if got is None:
            got = read_lambda_max_epsilon(os.path.join(tmp, "bands.tsv"))
        if got is None:
            print("# ramped run produced no readable lambda_max/epsilon")
            return False
        got_lambda_max, got_epsilon = got
        agrees = (abs_ok(got_lambda_max, want["lambda_max"], ABS_TOL_PERTURB_LAMBDA)
                  and rel_ok(got_epsilon, want["epsilon"], REL_TOL_PERTURB_EPSILON))
        if not agrees:
            print("# ramped input: tool (lambda_max=%r epsilon=%r) vs reference "
                  "(lambda_max=%.3f epsilon=%.2f)"
                  % (got_lambda_max, got_epsilon, want["lambda_max"], want["epsilon"]))
        return agrees
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


check("re-running uvvis.py on an absorbance-tilted input reproduces "
      "the reference lambda_max and epsilon for that input",
      perturbation_matches_reference())

finish(results)
