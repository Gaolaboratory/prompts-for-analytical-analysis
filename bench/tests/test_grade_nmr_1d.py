from grader_rig import GraderCase, replace

class NmrGraderTest(GraderCase):
    grader = "grade_nmr_1d.py"
    grader_args = ["multiplets.tsv", "stdout.log", "stderr.log"]
    tool = "nmr"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "stdout.log", "points read: 10000", "points read: 9999"), "stdout points read: 10000"),
            (lambda d: replace(d, "stdout.log", "zero-filled to: 16384", "zero-filled to: 8192"), "stdout zero-filled to: 16384"),
            (lambda d: replace(d, "stdout.log", "peaks found: 4", "peaks found: 5"), "stdout peaks found: 4"),
            (lambda d: replace(d, "multiplets.tsv", "ppm_center\tintegral\trelative_integral", "ppm_center,integral,relative_integral"), "header"),
            (lambda d: replace(d, "multiplets.tsv", "7.2502\t8166.71\t0.3312\n", ""), "4 rows"),
            (lambda d: replace(d, "multiplets.tsv", "0.4998\t24654.39", "0.4998,24654.39"), "tab-separated"),
            (lambda d: replace(d, "multiplets.tsv", "0.4998\t24654.39\t1.0000", "7.2502\t24654.39\t1.0000"), "sorted ascending"),
            (lambda d: replace(d, "multiplets.tsv", "0.4998\t24654.39", "0.4998\t2465.4"), "decimals"),
            (lambda d: replace(d, "multiplets.tsv", "0.4998\t24654.39", "0.7000\t24654.39"), "ppm 0.5"),
            (lambda d: replace(d, "multiplets.tsv", "1.0000", "0.9000"), "rel 0.5"),
            (lambda d: replace(d, "multiplets.tsv", "24654.39", "29000.00"), "integral 0.5"),
            (lambda d: replace(d, "multiplets.tsv", "2.0994\t2768.91", "2.5000\t2768.91"), "ppm 2.1"),
            (lambda d: replace(d, "multiplets.tsv", "0.1123", "0.2000"), "rel 2.1"),
            (lambda d: replace(d, "multiplets.tsv", "2768.91", "3000.00"), "integral 2.1"),
            (lambda d: replace(d, "multiplets.tsv", "3.7998\t5451.26", "4.1000\t5451.26"), "ppm 3.8"),
            (lambda d: replace(d, "multiplets.tsv", "0.2211", "0.3000"), "rel 3.8"),
            (lambda d: replace(d, "multiplets.tsv", "5451.26", "6000.00"), "integral 3.8"),
            (lambda d: replace(d, "multiplets.tsv", "7.2502\t8166.71", "7.5000\t8166.71"), "ppm 7.25"),
            (lambda d: replace(d, "multiplets.tsv", "0.3312", "0.4000"), "rel 7.25"),
            (lambda d: replace(d, "multiplets.tsv", "8166.71", "9000.00"), "integral 7.25"),
            (lambda d: replace(d, "nmr_1d.py", "math.e **", "1j + math.e **"), "fft cosine"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)
