import os

from grader_rig import GraderCase, replace


def _rewrite(d, name, fn):
    path = os.path.join(d, name)
    lines = open(path).read().split("\n")
    open(path, "w").write("\n".join(fn(lines)))


def _break_q_monotonicity(d):
    """Give the top-scoring PSM a worse q-value than the ones below it."""
    def fn(lines):
        body = [l for l in lines[1:] if l]
        body.sort(key=lambda l: -float(l.split("\t")[8]))
        top = body[0].split("\t")
        top[9] = "0.99000"
        body[0] = "\t".join(top)
        return [lines[0]] + body + [""]
    _rewrite(d, "psms.tsv", fn)


def _corrupt_scan1_peptide(d):
    def fn(lines):
        out = []
        for l in lines:
            f = l.split("\t")
            if len(f) == 10 and f[0] == "1":
                f[3] = "WRONGPEPTK"
            out.append("\t".join(f))
        return out
    _rewrite(d, "psms.tsv", fn)


def _drop_one_row(d):
    _rewrite(d, "psms.tsv", lambda lines: lines[:-2] + [""])


def _make_slow(d):
    open(os.path.join(d, "search.py"), "w").write(
        "import sys, time\ntime.sleep(3)\nopen(sys.argv[-1], 'w').write('')\n")


class DdaV2GraderTest(GraderCase):
    grader = "grade_dda_v2.py"
    grader_args = ["psms.tsv", "stdout.log"]
    tool = "dda_v2"

    def setUp(self):
        os.environ["DDA_TIME_LIMIT_S"] = "1"     # see grader: test-only override
        self.addCleanup(os.environ.pop, "DDA_TIME_LIMIT_S", None)

    def test_mutations(self):
        M = [
            # c1 — std-lib only, parses, fast
            (lambda d: replace(d, "search.py", "import argparse", "import argparse\nimport numpy"),
             "std-lib only (found: ['numpy'])"),
            (lambda d: replace(d, "search.py", "def build_index", "def build_index("),
             "search.py parses"),
            (_make_slow, "runs in <1 s (timeout)"),
            # c2 — index and spectrum counts
            (lambda d: replace(d, "stdout.log", "16853", "16000"), "stdout 16853 target peptides"),
            (lambda d: replace(d, "stdout.log", "16735", "16000"), "stdout 16735 decoy peptides"),
            (lambda d: replace(d, "stdout.log", "spectra read: 60", "spectra read: 61"),
             "stdout 60 spectra read"),
            (lambda d: replace(d, "stdout.log", "candidate: 59", "candidate: 58"),
             "stdout 59 spectra with a candidate"),
            # c3 — best hits and decoys
            (lambda d: replace(d, "stdout.log", "best hits: 59", "best hits: 58"),
             "stdout 59 best hits"),
            (lambda d: replace(d, "stdout.log", "decoy 9", "decoy 7", 2),
             "stdout 9 decoy best hits"),
            # c4 — accepted at 1% FDR
            (lambda d: replace(d, "stdout.log", "q <= 0.01: 31", "q <= 0.01: 25"),
             "stdout 31 target PSMs at q<=0.01"),
            # c5 — psms.tsv shape and monotone q
            (lambda d: replace(d, "psms.tsv", "scan\tprecursor_mz", "scan_id\tprecursor_mz"),
             "10-column header"),
            (_drop_one_row, "59 data rows"),
            (_break_q_monotonicity, "q_value non-decreasing by descending score"),
            # c6 — the differential peak-filtering report
            (lambda d: replace(d, "stdout.log",
                               "target PSMs at q <= 0.01 without peak filtering: 18 (decoy 9)", ""),
             "stdout reports 18 at q<=0.01 without peak filtering"),
            # c7 — the pinned PSM
            (_corrupt_scan1_peptide, "scan=1 -> EHHSESNHWK 9/18 target"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)
