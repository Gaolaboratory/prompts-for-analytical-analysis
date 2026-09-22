#!/usr/bin/env python3
"""grade_dda_v2.py psms.tsv stdout.log — tier (a) grader for the FDR search prompt.

Oracle verified against bench/reference/dda_search.py with the prompt's pinned
settings (count score, 12 peaks / 100 Da window, len 6-18, 0.02 Da x z precursor,
0.5 Da fragment): 16853/16735 peptides, 60 spectra, 59 best hits, 9 decoys,
31 target PSMs at q<=0.01, and 18 when peak filtering is disabled.

Stdout phrasing is NOT pinned by the prompt, so the stdout checks match a number
near its keyword rather than an exact line. That looseness is a finding about the
prompt, recorded in the Phase 0 report, not a grader convenience.
"""
import ast, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grading import require_files, finish

STDLIB = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()

tsv_path, out_path = sys.argv[1], sys.argv[2]
require_files(tsv_path, out_path, "search.py")
tsv = open(tsv_path, newline="").read()
raw = open(out_path).read()
flat = raw.replace(",", "")          # tolerate "16,853"
checks = []


def near(keyword, value, text=None):
    """A line mentioning `keyword` that also carries the exact integer `value`."""
    text = flat if text is None else text
    pat = r"(?im)^.*(?:%s).*$" % keyword
    return any(re.search(r"(?<![\d.])%d(?![\d.])" % value, m)
               for m in re.findall(pat, text))


# --- c1: std-lib only, and fast ---------------------------------------------
third_party = set()
try:
    tree = ast.parse(open("search.py").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [(node.module or "").split(".")[0]] if node.level == 0 else []
        else:
            continue
        for m in mods:
            if m and STDLIB and m not in STDLIB and not os.path.exists(m + ".py"):
                third_party.add(m)
    parsed = True
except SyntaxError:
    parsed = False
checks.append(("search.py parses", parsed))
checks.append(("std-lib only (found: %s)" % (sorted(third_party) or "none"), not third_party))

# DDA_TIME_LIMIT_S exists so the grader's own mutation test need not sleep 60 s.
# Production runs never set it; the criterion is 60 s.
LIMIT = float(os.environ.get("DDA_TIME_LIMIT_S", "60"))
elapsed = None
try:
    t0 = time.time()
    subprocess.run([sys.executable, "search.py", "bench.fasta", "bench.mgf",
                    "-o", "_regrade_psms.tsv"], timeout=2 * LIMIT,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elapsed = time.time() - t0
except (subprocess.TimeoutExpired, OSError):
    pass
checks.append(("runs in <%g s (%s)" % (LIMIT, "%.1f s" % elapsed if elapsed else "timeout"),
               elapsed is not None and elapsed < LIMIT))

# --- c2: index and spectrum counts ------------------------------------------
checks.append(("stdout 16853 target peptides", near(r"target", 16853)))
checks.append(("stdout 16735 decoy peptides", near(r"decoy", 16735)))
checks.append(("stdout 60 spectra read", near(r"spectra|scans", 60)))
checks.append(("stdout 59 spectra with a candidate", near(r"candidate", 59)))

# --- c3/c4: best hits, decoys, accepted -------------------------------------
checks.append(("stdout 59 best hits", near(r"best hit|hits", 59)))
checks.append(("stdout 9 decoy best hits", near(r"decoy", 9)))
checks.append(("stdout 31 target PSMs at q<=0.01",
               near(r"q\s*[<≤]?=?\s*0?\.01|1\s*%|fdr|accept", 31)))

# --- c5: psms.tsv shape and monotone q --------------------------------------
HEADER = ("scan\tprecursor_mz\tcharge\tpeptide\tprotein\tdecoy\t"
          "matched_fragments\ttotal_fragments\tscore\tq_value")
lines = tsv.split("\n")
checks.append(("10-column header", lines[0] == HEADER))
rows = [l.split("\t") for l in lines[1:] if l]
checks.append(("59 data rows", len(rows) == 59))
mono = False
try:
    pairs = sorted(((float(r[8]), float(r[9])) for r in rows), key=lambda x: -x[0])
    qs = [q for _, q in pairs]
    mono = all(b >= a - 1e-9 for a, b in zip(qs, qs[1:]))
except (ValueError, IndexError):
    pass
checks.append(("q_value non-decreasing by descending score", mono))

# --- c6: the differential peak-filtering check ------------------------------
checks.append(("stdout reports 18 at q<=0.01 without peak filtering",
               re.search(r"(?<![\d.])18(?![\d.])", flat) is not None))

# --- c7: the pinned PSM -----------------------------------------------------
ok7 = False
try:
    r = next(r for r in rows if r[0] in ("1", "scan=1"))
    ok7 = (r[3] == "EHHSESNHWK" and r[4] == "sp|SYN0146|SYN0146_TEST"
           and r[5] == "0" and int(float(r[6])) == 9 and int(float(r[7])) == 18)
except (StopIteration, ValueError, IndexError):
    pass
checks.append(("scan=1 -> EHHSESNHWK 9/18 target", ok7))

finish(checks)
