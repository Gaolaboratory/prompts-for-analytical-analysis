#!/usr/bin/env python3
"""grade_chrom_s.py <dir> — external grader for examples/chrom_integration/PROMPT.md.

Two independent kinds of expectation are graded:

- baseline/sigma against the harness-side reference values pinned in
  data/chrom/README.md (-4.797 mAU and 0.615 mAU), written LITERALLY in this
  file (not sourced from chrom_ref), so a wrong reference implementation
  cannot certify a wrong tool; and
- apex times and heights, which are not independently published outside the
  frozen analysis method, against chrom_ref recomputed HERE from the
  workspace's own chrom.csv.

That reference recomputation is wrapped in try/except so a missing, empty or
corrupt chrom.csv leaves ref = None rather than propagating: every one of the
named criteria below must still print an explicit PASS or FAIL and finish()
must always be reached, as in grade_calibration_s / grade_uvvis_s /
grade_spectral_s. A criterion that disappears is not a criterion that failed,
and it makes the per-criterion table non-comparable across tools.

Criteria 2 and 3 pair the tool's rows with the reference's peaks POSITIONALLY
(both are sorted ascending by rt_apex_s, and a correct tool reports exactly
ten rows), and each compares a single, disjoint field: criterion 2 only
rt_apex_s, criterion 3 only height. This is what makes the unit-error
mutation (divide every rt_apex_s by 60) fail ONLY criterion 2 -- heights are
untouched by that mutation and stay within tolerance of the reference -- and
what makes a heights-only mutation fail ONLY criterion 3.

Every constant a tool would need to fake criteria 1-5 is derivable from the
published README (the frozen method, and the pinned baseline/sigma/apex/
height table), so a tool could hardcode peaks.tsv/stdout.log and pass 1-5
without ever opening chrom.csv. Criterion 6 closes that hole: it adds a
synthetic ELEVENTH peak to a copy of chrom.csv -- a Gaussian of height 200
mAU and sigma 2 s -- and requires the reported peak set to agree with
chrom_ref recomputed from THAT injected input (11 apexes, each within 5%),
not merely to differ from the unperturbed run.

The injection center matters, and got one revision: the first version of this
plan placed it at 600 s. Measured (with two independent implementations of
the frozen method, including a direct stdlib port of data/chrom/
analyze_chrom.py), that choice does NOT yield 11 peaks -- it yields 10. The
nearest real apex is peak 7 at 596.12 s, only 3.88 s (9.7 samples) away, and a
sigma=2 s Gaussian is still steeply rising at that distance (contributing
~30 mAU there, more than the whole 28.04 mAU height of peak 7 itself); the
merge rule already collapses smoothed-trace local maxima within 5 samples
(2.0 s at this file's 0.4 s grid), and 596.12 stops being a separate local
maximum of the combined trace at all -- the two peaks merge into one apex at
600.12 s. The injection center was moved to 740.0 s: verified (against the
harness's real chrom.csv) that this leaves the original ten apexes and
heights numerically unchanged (the nearest real apex, peak 10 at 694.12 s, is
45.88 s away, far outside the Gaussian's support) while adding an eleventh,
cleanly separable peak near 740 s that the frozen method does not find in the
unperturbed data. See CONVENTIONS.md rule 5: measure what a perturbation
actually does before pinning anything to it.

A uniform time scaling would be the wrong choice of perturbation for the same
reason it was ruled out for other tools here: it multiplies every apex time
by the same factor, so a program that detects the scale and multiplies
hardcoded apex times by it would pass without ever analysing the signal. An
injected peak has no such closed-form correction: the mutation this criterion
exists to catch is a chrom_integrate.py that reports the ten pinned apexes
scaled by the observed time range (see test_grade_chrom_s.py's
_apex_rescale_forgery) -- since the injection changes no time_s value, that
forgery's scale factor is 1 on both the unperturbed and injected files, so it
reports the same unperturbed ten apexes both times and never reports anything
near 740 s. It must, and does, FAIL this criterion.

require_files is kept for the HARNESS-seeded input only: chrom.csv is placed
by run_bench, so its absence is a harness bug rather than a graded failure
mode of the submission (same distinction as grade_calibration_s /
grade_uvvis_s / grade_spectral_s).

Peak AREAS are deliberately not graded anywhere in this file: data/chrom/
README.md is explicit that peaks 7-10 ride a baseline wandering roughly -7 to
+5 mAU, so their areas are sensitive to the baseline model chosen for
integration, and pinning a number would fail a correct implementation that
picked a different, equally defensible convention.
"""
import math, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "reference", "short"))
from _grading import finish, num_field, require_files
import chrom_ref

CSV = "chrom.csv"
TOOL = "chrom_integrate.py"
N_PEAKS = 10
REL_TOL_APEX = 0.05          # apex times vs reference, relative
REL_TOL_HEIGHT = 0.05        # apex heights vs reference, relative
BASELINE_PUBLISHED = -4.797  # data/chrom/README.md, mAU
BASELINE_ABS_TOL = 0.5
SIGMA_PUBLISHED = 0.615      # data/chrom/README.md, mAU
SIGMA_REL_TOL = 0.20

INJECT_HEIGHT = 200.0        # synthetic 11th peak, mAU
INJECT_SIGMA = 2.0           # seconds
INJECT_CENTER = 740.0        # seconds -- see docstring for why not 600
REL_TOL_PERTURB_APEX = 0.05  # injected-run apex times vs reference, relative

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


def rel_ok(got, want, tol):
    return got is not None and abs(got - want) <= tol * abs(want)


def abs_ok(got, want, tol):
    return got is not None and abs(got - want) <= tol


raw = read_text(os.path.join(d, "peaks.tsv"), newline="") or ""
# Only a single trailing newline is stripped (if present) before splitting, so a
# blank line anywhere else in the file -- e.g. between the header and the first
# data row -- surfaces as an extra element and fails the row-count check below,
# rather than being silently dropped.
body = raw[:-1] if raw.endswith("\n") else raw
lines = body.split("\n") if body else []
hdr = lines[0].split("\t") if lines else []
data_lines = lines[1:]
well_formed = all(len(ln.split("\t")) == 4 for ln in data_lines)
rt_values = None
if well_formed and data_lines:
    try:
        rt_values = [float(ln.split("\t")[1]) for ln in data_lines]
    except ValueError:
        rt_values = None
# peak_id is an identifier, not a number the tool computes -- the prompt's
# "peak_id numbered from 1" requirement is graded HERE, in criterion 1 (shape
# and ordering), rather than by coercing it with int() while building `rows`
# below. A submission that wrote "p1".."p10" used to hit int("p1") ->
# ValueError there, which set rows = None and cascaded into failing the two
# apex/height criteria even though every apex and height it reported was
# exactly right (see CONVENTIONS.md rule 10 -- chrom_s/local/2).
peak_ids_ok = (well_formed and len(data_lines) == N_PEAKS
               and [ln.split("\t")[0] for ln in data_lines]
               == [str(i) for i in range(1, N_PEAKS + 1)])
shape = ("\r" not in raw and len(data_lines) == N_PEAKS
         and hdr == ["peak_id", "rt_apex_s", "height", "area"]
         and well_formed
         and rt_values is not None
         and rt_values == sorted(rt_values)
         and peak_ids_ok)
check("peaks.tsv: header + exactly 10 rows sorted by rt_apex_s, columns in order", shape)

def col_index(hdr, name):
    """Column index of `name` in `hdr`, or None if it is missing or appears
    more than once -- a repeated name is treated the same as an absent one,
    since no single position for it could be trusted."""
    idxs = [i for i, h in enumerate(hdr) if h == name]
    return idxs[0] if len(idxs) == 1 else None


# rows is built for criteria 2/3 (apex times, heights) by resolving
# rt_apex_s/height/peak_id INDEPENDENTLY BY COLUMN NAME, not by requiring
# `hdr` to equal the mandated header verbatim (criterion 1's "columns in
# order" job alone -- CONVENTIONS.md rule 10). This is what lets a column
# reorder (rt_apex_s and height swapped, header included, every value
# correct under its own relabeled name) or the drop of a column neither
# criterion reads (`area`, which this grader deliberately never scores --
# see the module docstring) leave both fields resolvable, instead of
# blanking `rows` entirely the way requiring the full mandated header would.
# A field whose name is genuinely absent from the header is not an error
# here: it is left None on every row, and rel_ok()'s `got is not None`
# guard below means only the criterion that actually names that field
# fails -- peak_id is kept as a string for the same reason it always was
# (an id-format defect is criterion 1's alone, see above).
rt_idx = col_index(hdr, "rt_apex_s")
ht_idx = col_index(hdr, "height")
pid_idx = col_index(hdr, "peak_id")

rows = None
if "\r" not in raw and len(data_lines) == N_PEAKS:
    rows = []
    for ln in data_lines:
        parts = ln.split("\t")
        if len(parts) != len(hdr):
            # A row whose own field count disagrees with the header's makes
            # every column's position ambiguous for that row -- fail closed
            # entirely rather than guess.
            rows = None
            break
        row = {"peak_id": parts[pid_idx] if pid_idx is not None else None}
        try:
            row["rt_apex_s"] = float(parts[rt_idx]) if rt_idx is not None else None
        except ValueError:
            row["rt_apex_s"] = None
        try:
            row["height"] = float(parts[ht_idx]) if ht_idx is not None else None
        except ValueError:
            row["height"] = None
        rows.append(row)
    if rows is not None:
        # Positional pairing with the reference's ascending-by-rt_apex_s
        # peak list below is only sound once the submission's own rows are
        # verifiably in that order; without a present, ascending rt_apex_s
        # column no positional pairing can be trusted for either criterion.
        # This mirrors what the old `well_formed_for_values` gate already
        # required, just computed from the by-name-resolved column instead
        # of a fixed position.
        rt_seq = [r["rt_apex_s"] for r in rows]
        if not (all(v is not None for v in rt_seq) and rt_seq == sorted(rt_seq)):
            rows = None

# Recompute the reference from the workspace's own chrom.csv. Any failure
# (missing file, empty file, malformed CSV, non-numeric columns, ...) leaves
# ref = None rather than propagating, so every criterion below fails
# explicitly instead of the whole grader crashing before finish() is reached.
try:
    ref = chrom_ref.run(os.path.join(d, CSV))
except Exception:
    ref = None
ref_peaks = ref["peaks"] if ref is not None else None

paired = (rows is not None and ref_peaks is not None
          and len(rows) == len(ref_peaks) == N_PEAKS)

check("all ten reference apexes present within 5%, in seconds",
      paired and all(rel_ok(r["rt_apex_s"], p["rt_apex_s"], REL_TOL_APEX)
                     for r, p in zip(rows, ref_peaks)))

check("apex heights within 5% of the reference recomputed from chrom.csv",
      paired and all(rel_ok(r["height"], p["height"], REL_TOL_HEIGHT)
                     for r, p in zip(rows, ref_peaks)))

out = read_text(os.path.join(d, "stdout.log")) or ""
baseline_val = num_field(out, "baseline")
sigma_val = num_field(out, "sigma")

check("baseline -4.797 +/- 0.5 and sigma 0.615 +/- 20%",
      abs_ok(baseline_val, BASELINE_PUBLISHED, BASELINE_ABS_TOL)
      and rel_ok(sigma_val, SIGMA_PUBLISHED, SIGMA_REL_TOL))

check("stdout reports points, baseline, sigma and peaks",
      all(num_field(out, key) is not None
          for key in ("points", "baseline", "sigma", "peaks")))


def inject_peak_csv(src, dst):
    """Copy `src` with a synthetic Gaussian peak (INJECT_HEIGHT mAU, sigma
    INJECT_SIGMA s, centered at INJECT_CENTER s) added to every point's
    signal, time_s untouched.

    Adding a genuinely new local maximum -- rather than scaling or shifting
    the whole trace -- means no closed-form correction applied to a
    hardcoded ten-apex answer can reproduce it: a tool has to actually
    re-detect peaks on the injected trace to find an eleventh apex near
    INJECT_CENTER.
    """
    with open(src, newline="") as fh:
        raw_lines = [l for l in fh.read().split("\n") if l.strip()]
    out_lines = [raw_lines[0]]
    for line in raw_lines[1:]:
        t_str, y_str = line.split(",", 1)
        t_val = float(t_str)
        bump = INJECT_HEIGHT * math.exp(
            -0.5 * ((t_val - INJECT_CENTER) / INJECT_SIGMA) ** 2)
        out_lines.append("%.4f,%.8f" % (t_val, float(y_str) + bump))
    with open(dst, "w", newline="") as fh:
        fh.write("\n".join(out_lines) + "\n")


def read_peak_rows(path):
    """list[dict] of {rt_apex_s, height} from a peaks.tsv-shaped file, sorted
    as written, or None if unreadable/malformed."""
    text = read_text(path, newline="")
    if not text:
        return None
    body2 = text[:-1] if text.endswith("\n") else text
    ls = body2.split("\n") if body2 else []
    if len(ls) < 2 or ls[0].split("\t") != ["peak_id", "rt_apex_s", "height", "area"]:
        return None
    out = []
    for ln in ls[1:]:
        parts = ln.split("\t")
        if len(parts) != 4:
            return None
        try:
            out.append({"rt_apex_s": float(parts[1]), "height": float(parts[2])})
        except ValueError:
            return None
    return out


def perturbation_matches_reference():
    """True iff re-running the submitted chrom_integrate.py on a
    peak-injected copy of chrom.csv reports an eleven-row peak table whose
    rt_apex_s values all agree, at REL_TOL_PERTURB_APEX, with chrom_ref
    recomputed from THAT injected input -- not merely a peak count that
    differs from the unperturbed run.

    Any failure -- missing chrom_integrate.py, a crash, a timeout, or
    unreadable output on either the injection build or the re-run -- makes
    this criterion FAIL rather than raising: finish() must still be reached.
    """
    tmp = tempfile.mkdtemp(prefix="inject_")
    try:
        # Run in a scratch directory so the submission cannot overwrite its
        # own graded peaks.tsv, and copy every module it shipped in case it
        # split the analysis across files.
        for name in sorted(os.listdir(d)):
            if name.endswith(".py"):
                shutil.copy2(os.path.join(d, name), tmp)
        if not os.path.isfile(os.path.join(tmp, TOOL)):
            print("# %s missing: cannot re-run it on a peak-injected input" % TOOL)
            return False
        injected_path = os.path.join(tmp, "chrom_injected.csv")
        try:
            inject_peak_csv(os.path.join(d, CSV), injected_path)
            want = chrom_ref.run(injected_path)
        except Exception as exc:
            print("# building/analysing the peak-injected input raised "
                  "%s: %s" % (type(exc).__name__, exc))
            return False
        try:
            proc = subprocess.run(
                [sys.executable, TOOL, "chrom_injected.csv", "-o", "injected.tsv"],
                cwd=tmp, timeout=120, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            print("# %s timed out on the peak-injected input" % TOOL)
            return False
        if proc.returncode != 0:
            print("# %s exited %d on the peak-injected input: %s"
                  % (TOOL, proc.returncode, (proc.stderr or "").strip()[:200]))
            return False
        got = read_peak_rows(os.path.join(tmp, "injected.tsv"))
        if got is None:
            got = read_peak_rows(os.path.join(tmp, "peaks.tsv"))
        if got is None:
            print("# peak-injected run produced no readable peak table")
            return False
        want_peaks = want["peaks"]
        agrees = (len(got) == len(want_peaks) == N_PEAKS + 1
                  and all(rel_ok(g["rt_apex_s"], p["rt_apex_s"], REL_TOL_PERTURB_APEX)
                          for g, p in zip(got, want_peaks)))
        if not agrees:
            print("# peak-injected input: tool reported %d peaks %r vs "
                  "reference %d peaks %r"
                  % (len(got), [round(g["rt_apex_s"], 2) for g in got],
                     len(want_peaks), [round(p["rt_apex_s"], 2) for p in want_peaks]))
        return agrees
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


check("re-running chrom_integrate.py on a peak-injected chrom.csv "
      "reproduces the reference peak set for that input",
      perturbation_matches_reference())

finish(results)
