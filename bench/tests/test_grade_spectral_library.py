import os
from grader_rig import GraderCase, replace

def clone_caffeine(d):
    lib = open(os.path.join(d, "library.txt")).read()
    block = lib.split(">NAME caffeine", 1)[1].split("\n\n", 1)[0]
    open(os.path.join(d, "library.txt"), "w").write(lib + ">NAME caffeine_clone" + block + "\n")

class SpectralGraderTest(GraderCase):
    grader = "grade_spectral_library.py"
    grader_args = ["results.tsv", "stdout.log"]
    tool = "spectral"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "stdout.log", "queries: 4  called: 3  no_match: 1", "queries: 4  called: 2  no_match: 1"), "c1 stdout summary line"),
            (lambda d: replace(d, "results.tsv", "query_id\tbest_match", "query_id,best_match"), "c2 header/rows/format"),
            (lambda d: replace(d, "results.tsv", "q1\tcaffeine", "q1\tnicotine"), "c3 q1 caffeine"),
            (lambda d: replace(d, "results.tsv", "q2\tacetaminophen", "q2\tnicotine"), "c4 q2 acetaminophen"),
            (lambda d: replace(d, "results.tsv", "q3\tsulfamethoxazole", "q3\tnicotine"), "c5 q3 sulfamethoxazole"),
            (lambda d: replace(d, "results.tsv", "q4\tNO_MATCH", "q4\tcaffeine"), "c6 q4 NO_MATCH"),
            (clone_caffeine, "c7 runner-up separation (independent scorer)"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)
