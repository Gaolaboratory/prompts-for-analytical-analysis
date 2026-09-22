from grader_rig import GraderCase, replace

class UvvisGraderTest(GraderCase):
    grader = "grade_uvvis.py"
    grader_args = ["peaks.tsv", "stdout.txt", "stderr.txt"]
    tool = "uvvis"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "peaks.tsv", "band\tlambda_max_nm\ta_max", "band,lambda_max_nm,a_max"), "header+tabs"),
            (lambda d: replace(d, "peaks.tsv", "b3\t540\t0.6691\n", ""), "3 rows"),
            (lambda d: replace(d, "peaks.tsv", "b1\t320", "b1\t550"), "sorted"),
            (lambda d: replace(d, "peaks.tsv", "b1\t320", "b1\t330"), "lambda within 2nm"),
            (lambda d: replace(d, "peaks.tsv", "b2\t420\t1.2677", "b2\t420\t1.4000"), "a_max within 0.02"),
            (lambda d: replace(d, "peaks.tsv", "b1\t320\t0.8803", "b1\t320\t0.88"), "a_max %.4f format"),
            (lambda d: replace(d, "stdout.txt", "bands: 3", "bands: 2"), "stdout bands line"),
            (lambda d: replace(d, "stdout.txt", "concentration_uM: 50.0", "concentration_uM: 62.0"), "conc within 5% of 50.0"),
            (lambda d: replace(d, "peaks.tsv", "b3\t540\t0.6691", "b3\t482\t0.6691"), "no 4th band near 481"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)
