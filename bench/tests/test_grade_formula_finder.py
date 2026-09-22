import os
from grader_rig import GraderCase, replace

def drop_last(d, name):
    path = os.path.join(d, name)
    txt = open(path).read().rstrip("\n").split("\n")
    open(path, "w").write("\n".join(txt[:-1]) + "\n")

class FormulaGraderTest(GraderCase):
    grader = "grade_formula_finder.py"
    grader_args = ["measured.tsv", "ranked.tsv", "stdout.log"]
    tool = "formula"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "stdout.log", "CPD1: 7 candidates", "CPD1: 8 candidates"), "c2 stdout candidate counts"),
            (lambda d: replace(d, "ranked.tsv", "CPD1\tC6H12O6", "CPD1\r\tC6H12O6"), "unix newlines, no CR"),
            (lambda d: replace(d, "ranked.tsv", "id\tformula\tcalc_mass\terror_ppm\tM1_calc\tM2_calc\tscore", "id,formula,calc_mass"), "tab-separated header, exact column order"),
            (lambda d: drop_last(d, "ranked.tsv"), "19 data rows"),
            (lambda d: replace(d, "ranked.tsv", "CPD1\tC6H12O6", "CPD2\tC6H12O6"), "blocks in input order with exact counts"),
            (lambda d: replace(d, "ranked.tsv", "CPD1\tC6H12O6", "CPD1\tH14N6O4S"), "CPD1 top hit is C6H12O6"),
            (lambda d: replace(d, "ranked.tsv", "CPD2\tC8H10N4O2", "CPD2\tH14N6O4S"), "CPD2 top hit is C8H10N4O2"),
            (lambda d: replace(d, "ranked.tsv", "CPD3\tC5H11NO2S", "CPD3\tH14N6O4S"), "CPD3 top hit is C5H11NO2S"),
            (lambda d: replace(d, "ranked.tsv", "1.2763", "1.9000"), "CPD1 calc_mass/score"),
            (lambda d: replace(d, "ranked.tsv", "2.1369", "3.0000"), "CPD2 calc_mass/score"),
            (lambda d: replace(d, "ranked.tsv", "2.5581", "3.0000"), "CPD3 calc_mass/score"),
            (lambda d: replace(d, "measured.tsv", "CPD1", "CPX1"), "CPD1 within tolerances"),
            (lambda d: replace(d, "measured.tsv", "CPD2", "CPX2"), "CPD2 within tolerances"),
            (lambda d: replace(d, "measured.tsv", "CPD3", "CPX3"), "CPD3 within tolerances"),
            (lambda d: replace(d, "ranked.tsv", "1.2763", "9.0000"), "CPD1 sorted by score asc"),
            (lambda d: replace(d, "ranked.tsv", "2.1369", "9.0000"), "CPD2 sorted by score asc"),
            (lambda d: replace(d, "ranked.tsv", "2.5581", "9.0000"), "CPD3 sorted by score asc"),
            (lambda d: replace(d, "ranked.tsv", "180.063390\t+0.000", "180.0634\t+0.0"), "column formats (6/±3/6/6/4 decimals)"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)
