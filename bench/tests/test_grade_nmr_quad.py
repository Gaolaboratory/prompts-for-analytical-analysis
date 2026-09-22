from grader_rig import GraderCase, replace


class NmrQuadGraderTest(GraderCase):
    grader = "grade_nmr_quad.py"
    grader_args = ["multiplets.tsv", "stdout.log", "stderr.log"]
    tool = "nmr_quad"

    def test_mutations(self):
        M = [
            # c1 — the three pinned stdout lines
            (lambda d: replace(d, "stdout.log", "points read: 8192", "points read: 8191"),
             "stdout 'points read: 8192'"),
            (lambda d: replace(d, "stdout.log", "zero-filled to: 16384", "zero-filled to: 8192"),
             "stdout 'zero-filled to: 16384'"),
            (lambda d: replace(d, "stdout.log", "peaks found: 4", "peaks found: 5"),
             "stdout 'peaks found: 4'"),
            # c2 — file shape
            (lambda d: replace(d, "multiplets.tsv", "ppm_center\tintegral\trelative_integral",
                               "ppm,integral,relative_integral"), "header"),
            (lambda d: replace(d, "multiplets.tsv", "8.4998\t3.5749e+03\t0.1110\n", ""),
             "4 rows x 3 cols"),
            (lambda d: replace(d, "multiplets.tsv", "1.2000\t3.2215e+04", "1.2000,3.2215e+04"),
             "tab-separated, unix newlines"),
            (lambda d: replace(d, "multiplets.tsv", "1.2000\t3.2215e+04", "9.9000\t3.2215e+04"),
             "sorted by ppm ascending"),
            (lambda d: replace(d, "multiplets.tsv", "3.4998\t", "3.50\t"),
             "4-decimal ppm and relative_integral"),
            # c3 — ppm centres, one mutation per row
            (lambda d: replace(d, "multiplets.tsv", "1.2000\t", "1.3000\t"), "ppm 1.20"),
            (lambda d: replace(d, "multiplets.tsv", "3.4998\t", "3.6000\t"), "ppm 3.50"),
            (lambda d: replace(d, "multiplets.tsv", "7.1997\t", "7.3500\t"), "ppm 7.20"),
            (lambda d: replace(d, "multiplets.tsv", "8.4998\t", "8.6500\t"), "ppm 8.50"),
            # c4 — relative integrals
            (lambda d: replace(d, "multiplets.tsv", "\t1.0000\n", "\t0.9000\n"),
             "relative_integral 1.20"),
            (lambda d: replace(d, "multiplets.tsv", "\t0.2245\n", "\t0.2800\n"),
             "relative_integral 3.50"),
            (lambda d: replace(d, "multiplets.tsv", "\t0.3360\n", "\t0.3900\n"),
             "relative_integral 7.20"),
            (lambda d: replace(d, "multiplets.tsv", "\t0.1110\n", "\t0.1600\n"),
             "relative_integral 8.50"),
            # c5 — absolute integrals (>3% off)
            (lambda d: replace(d, "multiplets.tsv", "3.2215e+04", "3.4000e+04"), "integral 1.20"),
            (lambda d: replace(d, "multiplets.tsv", "7.2307e+03", "7.7000e+03"), "integral 3.50"),
            (lambda d: replace(d, "multiplets.tsv", "1.0825e+04", "1.1500e+04"), "integral 7.20"),
            (lambda d: replace(d, "multiplets.tsv", "3.5749e+03", "3.8000e+03"), "integral 8.50"),
            # c6 — the FFT sign convention
            (lambda d: replace(d, "nmr_quad.py", "cmath.exp(-2j", "cmath.exp(2j"),
             "fft convention self-check"),
            # c7 — the baseline step must remove the 5.60 ppm broad component
            (lambda d: replace(d, "multiplets.tsv", "3.4998\t", "5.6000\t"),
             "no peak in 5.4-5.9 ppm"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)
