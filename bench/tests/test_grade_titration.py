from grader_rig import GraderCase, replace

class TitrationGraderTest(GraderCase):
    grader = "grade_titration.py"
    grader_args = ["."]
    tool = "titration"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "titration.csv", "titrant_volume_mL,pH", "volume,pH"), "csv: comment+header+50 rows"),
            (lambda d: replace(d, "titration.csv", "0.00,2.892", "0.00,3.892"), "csv: first row 0.00,2.892"),
            (lambda d: replace(d, "titration.csv", "75.00,12.283", "75.00,12.000"), "csv: last row 75.00,12.283"),
            (lambda d: replace(d, "results.tsv", "50.245\t50.245", "50.245\t50.245\r"), "tsv: LF only, no CR"),
            (lambda d: replace(d, "results.tsv", "4.761", "4.761\nextra"), "tsv: header + 1 row"),
            (lambda d: replace(d, "results.tsv", "equivalence_volume_mL", "veq_mL"), "tsv: 4 tab-separated columns in order"),
            (lambda d: replace(d, "results.tsv", "50.245", "49.000", 1), "Veq within 0.50 mL of 50.00"),
            (lambda d: replace(d, "results.tsv", "50.245\t50.245", "50.245\t51.500"), "d1/d2 agree within 0.20 mL"),
            (lambda d: replace(d, "results.tsv", "4.761", "5.200"), "pKa within 0.05 of 4.76"),
            (lambda d: replace(d, "results.tsv", "0.1005", "0.1500"), "concentration recovery within 2%"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)
