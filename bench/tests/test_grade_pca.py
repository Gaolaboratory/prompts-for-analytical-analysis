from grader_rig import GraderCase, replace

class PcaGraderTest(GraderCase):
    grader = "grade_pca.py"
    grader_args = []
    tool = "pca"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "stdout.txt", "kept 27 of 28 features (filtered: MET_X28)", "kept 26 of 28"), "stdout counts"),
            (lambda d: replace(d, "stdout.txt", "PC1 variance fraction 0.9218", "PC1 variance fraction 0.9000"), "stdout PC1"),
            (lambda d: replace(d, "stdout.txt", "PC2 variance fraction 0.0719", "PC2 variance fraction 0.0700"), "stdout PC2"),
            (lambda d: replace(d, "scores.tsv", "sample\tPC1\tPC2", "sample,PC1,PC2"), "scores header"),
            (lambda d: replace(d, "scores.tsv", "CTRL_1\t3.4354", "ZZZ_1\t3.4354"), "scores order"),
            (lambda d: replace(d, "scores.tsv", "CTRL_1\t3.4354", "CTRL_1\t-3.4354"), "sign rule"),
            (lambda d: replace(d, "scores.tsv", "EXP_1\t-3.6524", "EXP_1\t4.0000"), "separation"),
            (lambda d: replace(d, "scores.tsv", "CTRL_1\t3.4354", "CTRL_1\t3.3000"), "CTRL_1 PC1"),
            (lambda d: replace(d, "scores.tsv", "EXP_1\t-3.6524", "EXP_1\t-3.4000"), "EXP_1 PC1"),
            (lambda d: replace(d, "scores.tsv", "CTRL_2\t3.3354\t-1.7934", "CTRL_2\t3.3354\t-1.5000"), "CTRL_2 PC2"),
            (lambda d: replace(d, "loadings.tsv", "feature\tPC1\tPC2", "feature,PC1,PC2"), "loadings header"),
            (lambda d: replace(d, "loadings.tsv", "MET_M27\t0.0100", "MET_X28\t0.0100"), "loadings rows"),
            (lambda d: replace(d, "loadings.tsv", "MET_S01\t-0.2800", "MET_S01\t-0.1000"), "signal loadings"),
            (lambda d: replace(d, "loadings.tsv", "MET_B13\t0.0500\t0.4000", "MET_B13\t0.0500\t0.2000"), "blockB loadings"),
            (lambda d: replace(d, "loadings.tsv", "MET_N19\t0.0100", "MET_N19\t0.2000"), "noise loadings"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)
