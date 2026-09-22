import os
import shutil
import tempfile
import unittest

from grader_rig import GraderCase, replace, run_grader

REFERENCE_CRITERION = ("at least 70 of the recomputed reference's top 100 features "
                       "matched, and stdout features=N equals the row count")
# The criteria that a fabricated features.tsv built from the prompt text alone
# already satisfied.
PROMPT_ONLY_CRITERIA = [
    "features.tsv: header + N rows, 7 columns in order",
    "120 <= N <= 480",
    "at least 5 of the 10 reference features matched",
    "every apex_intensity > 0 and rt_start <= rt_apex <= rt_end",
    "stdout: ms1_scans=286",
]

# data/feature_extraction/README.md top-10 events, i.e. exactly the ten (m/z, RT)
# pairs printed in examples/feature_extraction/PROMPT.md.
TOP10 = [(395.2392, 1943.80), (487.7323, 1848.68), (395.7405, 1941.74),
         (325.4912, 1850.10), (488.2334, 1848.68), (388.2539, 1977.38),
         (443.7112, 1749.73), (722.3250, 1788.01), (738.3110, 1900.27),
         (344.2280, 1827.04)]


class FeaturesShortGraderTest(GraderCase):
    grader = "grade_features_s.py"
    grader_args = ["features.tsv", "stdout.log"]
    tool = "features_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "features.tsv", "feature_id\tmz", "id\tmass"),
             "features.tsv: header + N rows, 7 columns in order"),
            (lambda d: _truncate_rows(d, 40),
             "120 <= N <= 480"),
            (lambda d: _shift_all_mz(d, 5.0),
             "at least 5 of the 10 reference features matched"),
            (lambda d: _break_rt_order(d),
             "every apex_intensity > 0 and rt_start <= rt_apex <= rt_end"),
            (lambda d: replace(d, "stdout.log", "ms1_scans=286", "ms1_scans=767"),
             "stdout: ms1_scans=286"),
            # Reference agreement, mutated both ways it can fail: the rows stop
            # tracking the recomputed reference beyond the ten features the
            # prompt prints, and the reported count stops matching the rows.
            (lambda d: _shift_mz_below_top10(d, 5.0), REFERENCE_CRITERION),
            (lambda d: replace(d, "stdout.log", "features=240", "features=999"),
             REFERENCE_CRITERION),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)


def _rows(d):
    import os
    path = os.path.join(d, "features.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    return path, lines[0], [l.split("\t") for l in lines[1:]]


def _write(path, hdr, rows):
    open(path, "w").write("\n".join([hdr] + ["\t".join(r) for r in rows]) + "\n")


def _truncate_rows(d, n):
    path, hdr, rows = _rows(d)
    _write(path, hdr, rows[:n])


def _shift_all_mz(d, delta):
    path, hdr, rows = _rows(d)
    for r in rows:
        r[1] = "%.4f" % (float(r[1]) + delta)
    _write(path, hdr, rows)


def _break_rt_order(d):
    path, hdr, rows = _rows(d)
    rows[0][3], rows[0][4] = rows[0][4], rows[0][3]   # rt_start <-> rt_end
    _write(path, hdr, rows)


def _shift_mz_below_top10(d, delta):
    """Corrupt every row except the ten the prompt prints: the top-10 criterion
    still passes and N is unchanged, so only the recomputed-reference criterion
    can notice. This is the forgery in miniature."""
    path, hdr, rows = _rows(d)
    keep = set()
    for mz, rt in TOP10:
        for i, r in enumerate(rows):
            if (i not in keep and abs(float(r[1]) - mz) <= 0.01
                    and abs(float(r[2]) - rt) <= 10.0):
                keep.add(i)
                break
    assert len(keep) == len(TOP10), keep
    for i, r in enumerate(rows):
        if i not in keep:
            r[1] = "%.4f" % (float(r[1]) + delta)
    _write(path, hdr, rows)


class FeaturesShortForgeryTest(unittest.TestCase):
    """The forgery this criterion exists for: a fabricated 120-row features.tsv
    whose only real content is the ten (m/z, RT) pairs printed in
    examples/feature_extraction/PROMPT.md, with the rest invented and BSA1_F1.mzML
    never opened. Before the reference criterion it scored 5/5 with rc 0."""

    def _forge(self):
        d = tempfile.mkdtemp(prefix="forge_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        here = os.path.dirname(os.path.abspath(__file__))            # bench/tests
        repo = os.path.dirname(os.path.dirname(here))
        shutil.copy2(os.path.join(repo, "data", "feature_extraction",
                                  "BSA1_F1.mzML"), d)
        rows = [(mz, rt, 1e7 / i) for i, (mz, rt) in enumerate(TOP10, 1)]
        rows += [(300.0 + i * 0.7, 1500.0 + i * 4.0, 1e6 / i)
                 for i in range(len(TOP10) + 1, 121)]
        with open(os.path.join(d, "features.tsv"), "w") as fh:
            fh.write("feature_id\tmz\trt_apex\trt_start\trt_end\t"
                     "apex_intensity\tn_scans\n")
            for n, (mz, rt, inten) in enumerate(rows, 1):
                fh.write("F%04d\t%.4f\t%.2f\t%.2f\t%.2f\t%.1f\t%d\n"
                         % (n, mz, rt, rt - 5.0, rt + 5.0, inten, 7))
        with open(os.path.join(d, "stdout.log"), "w") as fh:
            fh.write("ms1_scans=286 windows=200 features=120\n")
        return run_grader("grade_features_s.py", ["features.tsv", "stdout.log"], d)

    def test_prompt_only_forgery_fails_the_reference_criterion(self):
        rc, verdicts, out = self._forge()
        self.assertIn(REFERENCE_CRITERION, verdicts, out)
        self.assertFalse(verdicts[REFERENCE_CRITERION], out)
        self.assertNotEqual(rc, 0, out)
        # and it is specifically the new criterion that catches it: the five
        # older criteria, all satisfiable from the prompt text, still pass.
        for crit in PROMPT_ONLY_CRITERIA:
            self.assertTrue(verdicts[crit], out)


if __name__ == "__main__":
    unittest.main()
