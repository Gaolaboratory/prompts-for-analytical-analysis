from grader_rig import GraderCase, replace


SHAPE_CRITERION = ("scores.tsv: header + 60 rows in features.csv column order, "
                   "groups match groups.csv")


class PcaShortGraderTest(GraderCase):
    grader = "grade_pca_s.py"
    grader_args = ["scores.tsv", "stdout.log"]
    tool = "pca_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "scores.tsv", "sample\tgroup", "id\tclass"),
             SHAPE_CRITERION),
            # The prompt's row-order requirement, now graded: swapping two rows
            # in the middle leaves the header, the row count, every group label
            # and the first row's sign untouched.
            (lambda d: _swap_rows(d, 2, 3), SHAPE_CRITERION),
            (lambda d: replace(d, "stdout.log", "features_kept=184", "features_kept=200"),
             "stdout: features_in=200 features_kept=184"),
            (lambda d: replace(d, "stdout.log", "pc1_var=0.1558", "pc1_var=0.4000"),
             "pc1_var 0.1558 +/- 0.01 and pc2_var 0.1008 +/- 0.01"),
            (lambda d: _shuffle_pc1(d),
             "PC1 and PC2 correlate with the reference at |r| >= 0.999"),
            (lambda d: _negate_first_row(d),
             "first sample's PC1 and PC2 are positive (sign rule)"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)


def _shuffle_pc1(d):
    """Reverse the PC1 column: preserves every summary statistic, destroys r."""
    import os
    path = os.path.join(d, "scores.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    rows = [l.split("\t") for l in lines[1:]]
    pc1 = [r[2] for r in rows][::-1]
    for r, v in zip(rows, pc1):
        r[2] = v
    open(path, "w").write("\n".join([lines[0]] + ["\t".join(r) for r in rows]) + "\n")


def _negate_first_row(d):
    import os
    path = os.path.join(d, "scores.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    r = lines[1].split("\t")
    r[2], r[3] = "-" + r[2].lstrip("-"), "-" + r[3].lstrip("-")
    lines[1] = "\t".join(r)
    open(path, "w").write("\n".join(lines) + "\n")


def _swap_rows(d, i, j):
    import os
    path = os.path.join(d, "scores.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    lines[i], lines[j] = lines[j], lines[i]      # 0 is the header
    open(path, "w").write("\n".join(lines) + "\n")
