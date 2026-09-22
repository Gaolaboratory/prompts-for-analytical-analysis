#!/usr/bin/env python3
"""grade_mass_reader_s.py — external grader for examples/mass_reader/PROMPT.md.

Runs in the agent's workspace and imports the agent's own modules, because the
importable interface is what dependent prompts rely on. Expected values are the
pyteomics-derived figures in data/mass_reader/README.md.

The last criterion also grades the CLI output the prompt mandates
(`python3 mzml_reader.py <file.mzML>` prints exactly one
`spectra=.. ms1=.. ms2=.. rt_first=.. rt_last=.. tic=..` line), read from the
stdout.log the spec's run_cmd already writes. It went ungraded before, and the
conformant fixture violated the prompt it was conformant to while still scoring
6/6.
"""
import importlib
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
from _grading import require_files, finish, num_field

# Only the real input data is required up front. fasta_reader.py / mzml_reader.py
# are the agent's own submission: their total absence, an import-time crash, or a
# renamed/missing function are graded failure modes in their own right (handled
# below), not reasons to abort before printing a single PASS/FAIL line.
require_files("ecoli_k12_48.fasta", "bsa_orbitrap_first40.mzML",
              "thermo_small_raw.mzML")

CRITERIA = [
    "fasta: 48 records, 19929 residues, first sp|P00509|AAT_ECOLI/396",
    "bsa: 40 spectra (10 MS1 / 30 MS2), ids spectrum=1011..spectrum=2471",
    "bsa: rt_first 1501.414 s, rt_last 1590.187 s",
    "bsa: first MS2 spectrum=2442, precursor 457.72397, z=2, charges {2,3}",
    "thermo: 2 MS1 x 19914 peaks, rt 0.2961/0.3561 s (minutes rule)",
    "tic totals within 0.1% (45709750.4 / 138763684.2) and the mandated "
    "one-line stdout summary for the bsa file",
]

STDOUT_LOG = "stdout.log"          # written by the spec's run_cmd
# The mandated field order; the prompt says "prints exactly one line".
SUMMARY_KEYS = ["spectra", "ms1", "ms2", "rt_first", "rt_last", "tic"]

results = []


def check(name, fn):
    try:
        ok = bool(fn())
    except Exception as exc:                     # a crash is a failed criterion
        print("# %s raised %s: %s" % (name, type(exc).__name__, exc))
        ok = False
    results.append((name, ok))


def _safe_import(modname):
    """Import a submitted module without letting an import-time crash — or a
    missing file, which raises ModuleNotFoundError here too — kill the grader
    before finish() runs."""
    try:
        return importlib.import_module(modname)
    except Exception as exc:
        print("# import %s failed: %s: %s" % (modname, type(exc).__name__, exc))
        return None


def _resolve(mod, modname, funcname):
    """getattr, but tolerant of a missing/renamed function. Done as its own step
    (not inline at a call site) because an attribute lookup used as a call
    argument is evaluated *before* any surrounding try/except around the call
    itself — a bare `mod.func(...)` would raise AttributeError outside any
    guard."""
    if mod is None:
        return None
    fn = getattr(mod, funcname, None)
    if fn is None:
        print("# %s.%s missing" % (modname, funcname))
    return fn


def _safe_call(label, fn, *args):
    """Never let a broken submission crash the grader before finish(). `fn` may
    already be None (import failed, or the function is missing/renamed — both
    already diagnosed by _safe_import/_resolve above); calling it may also raise
    (bad struct format, etc.). Either way this degrades to None instead of
    propagating, and prints its own diagnostic only for the call-raised case so
    the same failure isn't reported twice."""
    if fn is None:
        return None
    try:
        return fn(*args)
    except Exception as exc:
        print("# %s raised %s: %s" % (label, type(exc).__name__, exc))
        return None


# fasta_reader and mzml_reader are resolved and called *independently*: a broken
# mzml_reader.py must fail only the five mzML criteria below, not the FASTA one
# (fasta_reader.py is a separate file that may be perfectly correct), and
# vice versa. Whichever module is broken, its own _safe_import/_resolve/
# _safe_call already printed a diagnostic; the corresponding value here is just
# None, which check() turns into an explicit FAIL for the criteria that use it.
fasta_reader = _safe_import("fasta_reader")
read_fasta = _resolve(fasta_reader, "fasta_reader", "read_fasta")
recs = _safe_call("fasta_reader.read_fasta", read_fasta, "ecoli_k12_48.fasta")

mzml_reader = _safe_import("mzml_reader")
read_mzml = _resolve(mzml_reader, "mzml_reader", "read_mzml")
bsa = _safe_call("mzml_reader.read_mzml(bsa)", read_mzml, "bsa_orbitrap_first40.mzML")
thermo = _safe_call("mzml_reader.read_mzml(thermo)", read_mzml, "thermo_small_raw.mzML")


def close(a, b, tol):
    return a is not None and abs(float(a) - b) <= tol


def tic(spectra):
    return sum(float(v) for s in spectra for v in s["intensity"])


check(CRITERIA[0],
      lambda: len(recs) == 48
      and sum(len(s) for _, s in recs) == 19929
      and recs[0][0] == "sp|P00509|AAT_ECOLI" and len(recs[0][1]) == 396)

check(CRITERIA[1],
      lambda: len(bsa) == 40
      and sum(1 for s in bsa if s["ms_level"] == 1) == 10
      and sum(1 for s in bsa if s["ms_level"] == 2) == 30
      and bsa[0]["id"] == "spectrum=1011" and len(bsa[0]["mz"]) == 467
      and bsa[-1]["id"] == "spectrum=2471")

check(CRITERIA[2],
      lambda: close(bsa[0]["rt"], 1501.41394042969, 1e-3)
      and close(bsa[-1]["rt"], 1590.18725585938, 1e-3))


def bsa_precursors():
    ms2 = [s for s in bsa if s["ms_level"] == 2]
    charges = sorted({s["precursor_charge"] for s in ms2})
    return (ms2[0]["id"] == "spectrum=2442"
            and close(ms2[0]["precursor_mz"], 457.723968505859, 1e-4)
            and ms2[0]["precursor_charge"] == 2
            and charges == [2, 3] and len(ms2) == 30)


check(CRITERIA[3], bsa_precursors)

check(CRITERIA[4],
      lambda: len(thermo) == 2
      and all(s["ms_level"] == 1 and len(s["mz"]) == 19914 for s in thermo)
      and close(thermo[0]["rt"], 0.2961, 1e-4)
      and close(thermo[1]["rt"], 0.3561, 1e-4))

def summary_line_ok():
    """The stdout.log written by `python3 mzml_reader.py bsa_orbitrap_first40.mzML`
    must be exactly one line carrying the six mandated fields in the mandated
    order, with the values for that file."""
    try:
        with open(STDOUT_LOG, errors="replace") as fh:
            text = fh.read()
    except OSError:
        print("# %s missing: the mandated stdout summary cannot be graded"
              % STDOUT_LOG)
        return False
    lines = [l for l in text.split("\n") if l.strip()]
    if len(lines) != 1:
        print("# %s holds %d non-blank lines, the prompt mandates exactly one"
              % (STDOUT_LOG, len(lines)))
        return False
    line = lines[0]
    if not re.search(r"\s+".join(k + r"=\S+" for k in SUMMARY_KEYS), line):
        print("# stdout summary is not `%s`: %r"
              % (" ".join(k + "=<n>" for k in SUMMARY_KEYS), line[:200]))
        return False
    vals = {k: num_field(line, k) for k in SUMMARY_KEYS}
    if vals["spectra"] != 40 or vals["ms1"] != 10 or vals["ms2"] != 30:
        print("# stdout counts wrong: %s" % vals)
        return False
    if not (close(vals["rt_first"], 1501.41394042969, 1e-3)
            and close(vals["rt_last"], 1590.18725585938, 1e-3)):
        print("# stdout rt_first/rt_last wrong: %s" % vals)
        return False
    if vals["tic"] is None or abs(vals["tic"] - 45709750.399179935) > \
            1e-3 * 45709750.399179935:
        print("# stdout tic wrong: %s" % vals)
        return False
    return True


check(CRITERIA[5],
      lambda: abs(tic(bsa) - 45709750.399179935) <= 1e-3 * 45709750.399179935
      and abs(tic(thermo) - 138763684.23791504) <= 1e-3 * 138763684.23791504
      and summary_line_ok())

finish(results)
