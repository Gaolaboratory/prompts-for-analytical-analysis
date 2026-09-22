#!/usr/bin/env python3
"""grade_titration_s.py <dir> — external grader for examples/titration/PROMPT.md.

Two independent kinds of expectation are graded:

- the published-table figures in data/titration/README.md (Veq 25.0 +/- 0.5 mL,
  pKa 4.74 +/- 0.10, conc 0.100 M +/- 5%), and
- agreement with the reference recomputed HERE, from the workspace's own
  acetic_acid_naoh.csv, at much tighter tolerances.

The second kind exists because every constant in the first kind is printed in
examples/titration/PROMPT.md: a results.tsv of 25.0 / 4.74 / 0.100 plus the
matching stdout line scored 5/5 without the tool ever opening the input file.
Recomputing from the workspace input closes only half of that hole -- the
published figures happen to agree with the true answer to three decimals -- so
the reference criterion also re-runs the submitted titration.py on a PERTURBED
copy of the workspace CSV (every titrant volume shifted by +3.00 mL) and
requires it to track the reference there too. A tool that hardcodes constants,
or that ignores the input path it is given, cannot pass that.

A missing, empty or malformed results.tsv/stdout.log must not make criteria
vanish: every one of the named criteria below prints an explicit PASS or FAIL and
finish() is always reached, as in grade_features_s / grade_pca_s / grade_
mass_reader_s. A criterion that disappears is not a criterion that failed, and it
makes the per-criterion table non-comparable across tools.

require_files is kept for the HARNESS-seeded input only: acetic_acid_naoh.csv is
placed by run_bench, so its absence is a harness bug rather than a graded failure
mode of the submission (same distinction as grade_mass_reader_s).
"""
import os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "reference", "short"))
from _grading import finish, num_field, require_files
import titration_ref

CSV = "acetic_acid_naoh.csv"
TOOL = "titration.py"
PERTURB_ML = 3.00          # volume offset applied to the perturbed copy
VEQ_TOL, PKA_TOL, CONC_REL_TOL = 0.05, 0.02, 0.002

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
shape = ("\r" not in raw and len(lines) == 2
         and hdr == ["equivalence_volume_mL", "pKa", "analyte_concentration_M"]
         and len(data_fields) == 3)
check("tsv: header + 1 row, 3 columns in order, LF only", shape)

veq = pka = conc = None
if shape:
    try:
        veq, pka, conc = (float(x) for x in data_fields)
    except ValueError:
        pass

check("Veq 25.0 +/- 0.5 mL", veq is not None and abs(veq - 25.0) <= 0.5)
check("pKa 4.74 +/- 0.10", pka is not None and abs(pka - 4.74) <= 0.10)
check("concentration 0.100 M +/- 5%", conc is not None and abs(conc - 0.100) <= 0.005)

out = read_text(os.path.join(d, "stdout.log")) or ""

check("stdout: points/Veq/pKa/conc each present with a numeric value",
      all(num_field(out, key) is not None
          for key in ("points", "Veq", "pKa", "conc")))


def agrees(triple, ref):
    """The tool's (Veq, pKa, conc) against a reference dict, tightly."""
    if triple is None or ref is None or any(v is None for v in triple):
        return False
    veq_t, pka_t, conc_t = triple
    return (abs(veq_t - ref["veq"]) <= VEQ_TOL
            and abs(pka_t - ref["pka"]) <= PKA_TOL
            and abs(conc_t - ref["conc"]) <= CONC_REL_TOL * abs(ref["conc"]))


def perturbed_csv(src, dst):
    """Copy `src` with every titrant volume shifted by +PERTURB_ML.

    The volume grid spacing is untouched, so the reference recipe's derivative,
    its parabolic vertex and therefore Veq all shift by exactly the offset --
    the perturbed file is as analysable as the original, but none of its answers
    are the ones printed in the prompt.
    """
    with open(src, newline="") as fh:
        lines = [l for l in fh.read().split("\n") if l.strip()]
    out_lines = [lines[0]]
    for line in lines[1:]:
        vol, rest = line.split(",", 1)
        out_lines.append("%.2f,%s" % (float(vol) + PERTURB_ML, rest))
    with open(dst, "w", newline="") as fh:
        fh.write("\n".join(out_lines) + "\n")


def read_triple(path):
    """(Veq, pKa, conc) from a results.tsv, or None if unreadable/malformed."""
    text = read_text(path, newline="")
    if not text:
        return None
    rows = [l for l in text.split("\n") if l.strip()]
    if len(rows) < 2:
        return None
    fields = rows[1].split("\t")
    if len(fields) != 3:
        return None
    try:
        return tuple(float(x) for x in fields)
    except ValueError:
        return None


def reference_agreement():
    """True iff the submission tracks titration_ref on the workspace's own CSV
    AND on a perturbed copy of it, at the tight tolerances above.

    Any failure -- unreadable CSV, missing titration.py, a tool that crashes,
    hangs, ignores its input path or writes no output -- makes this criterion
    FAIL rather than raising: finish() must still be reached.
    """
    csv_path = os.path.join(d, CSV)
    try:
        ref = titration_ref.analyse(csv_path)
    except Exception as exc:
        print("# titration_ref on %s raised %s: %s" % (CSV, type(exc).__name__, exc))
        return False
    if not agrees(read_triple(os.path.join(d, "results.tsv")), ref):
        return False

    tmp = tempfile.mkdtemp(prefix="perturb_")
    try:
        # Run in a scratch directory so the submission cannot overwrite its own
        # graded results.tsv, and copy every module it shipped in case it split
        # the analysis across files.
        for name in sorted(os.listdir(d)):
            if name.endswith(".py"):
                shutil.copy2(os.path.join(d, name), tmp)
        if not os.path.isfile(os.path.join(tmp, TOOL)):
            print("# %s missing: cannot re-run it on a perturbed input" % TOOL)
            return False
        try:
            perturbed_csv(csv_path, os.path.join(tmp, "perturbed.csv"))
            want = titration_ref.analyse(os.path.join(tmp, "perturbed.csv"))
        except Exception as exc:
            print("# building the perturbed input raised %s: %s"
                  % (type(exc).__name__, exc))
            return False
        try:
            proc = subprocess.run(
                [sys.executable, TOOL, "perturbed.csv", "-o", "perturbed.tsv"],
                cwd=tmp, timeout=120, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            print("# %s timed out on the perturbed input" % TOOL)
            return False
        if proc.returncode != 0:
            print("# %s exited %d on the perturbed input: %s"
                  % (TOOL, proc.returncode, (proc.stderr or "").strip()[:200]))
            return False
        # Honour -o if the tool does; fall back to the prompt's default output
        # name so a tool that hardcodes "results.tsv" is judged on its numbers
        # rather than on that detail.
        got = (read_triple(os.path.join(tmp, "perturbed.tsv"))
               or read_triple(os.path.join(tmp, "results.tsv")))
        if not agrees(got, want):
            print("# perturbed input: tool %s vs reference (%.4f, %.4f, %.5f)"
                  % (got, want["veq"], want["pka"], want["conc"]))
            return False
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


check("matches titration_ref recomputed from the input CSV, as given and "
      "perturbed (Veq +/-0.05 mL, pKa +/-0.02, conc +/-0.2%)",
      reference_agreement())

finish(results)
