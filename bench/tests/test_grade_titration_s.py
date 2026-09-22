import os
import shutil
import sys
import tempfile
import unittest

import fixtures
from grader_rig import GraderCase, replace, run_grader

# Kept in sync with the criteria grade_titration_s.py prints.
CRITERIA = [
    "tsv: header + 1 row, 3 columns in order, LF only",
    "Veq 25.0 +/- 0.5 mL",
    "pKa 4.74 +/- 0.10",
    "concentration 0.100 M +/- 5%",
    "stdout: points/Veq/pKa/conc each present with a numeric value",
    "matches titration_ref recomputed from the input CSV, as given and perturbed "
    "(Veq +/-0.05 mL, pKa +/-0.02, conc +/-0.2%)",
]
REFERENCE_CRITERION = CRITERIA[5]
PUBLISHED_CRITERIA = CRITERIA[1:4]


class TitrationShortGraderTest(GraderCase):
    grader = "grade_titration_s.py"
    grader_args = ["."]
    tool = "titration_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "results.tsv", "equivalence_volume_mL", "veq_mL"),
             "tsv: header + 1 row, 3 columns in order, LF only"),
            (lambda d: replace(d, "results.tsv", "\t4.7", "\r\t4.7"),
             "tsv: header + 1 row, 3 columns in order, LF only"),
            (lambda d: _drop_column(d),
             "tsv: header + 1 row, 3 columns in order, LF only"),
            (lambda d: _blank_line(d),
             "tsv: header + 1 row, 3 columns in order, LF only"),
            (lambda d: _mutate_column(d, "veq"),
             "Veq 25.0 +/- 0.5 mL"),
            (lambda d: _mutate_column(d, "pka"),
             "pKa 4.74 +/- 0.10"),
            (lambda d: _mutate_column(d, "conc"),
             "concentration 0.100 M +/- 5%"),
            (lambda d: replace(d, "stdout.log", "points=", "npoints="),
             "stdout: points/Veq/pKa/conc each present with a numeric value"),
            (lambda d: replace(d, "stdout.log", "Veq=24.998", "Veq="),
             "stdout: points/Veq/pKa/conc each present with a numeric value"),
            # Reference agreement, mutated three ways: a value nudged outside the
            # tight reference band while staying inside the published band, a tool
            # that ignores the input path it is given, and a tool that is gone.
            (lambda d: _nudge_column(d, "veq"), REFERENCE_CRITERION),
            (lambda d: _nudge_column(d, "pka"), REFERENCE_CRITERION),
            (lambda d: _hardcode_input(d), REFERENCE_CRITERION),
            (lambda d: __import__("os").remove(
                __import__("os").path.join(d, "titration.py")),
             REFERENCE_CRITERION),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)


def _mutate_column(d, which):
    """Parse results.tsv, push the named column outside its criterion band,
    and write it back. Doing this by parsing (rather than matching a
    formatted string literal) is robust to however the reference happened
    to format the number."""
    import os
    path = os.path.join(d, "results.tsv")
    lines = open(path, newline="").read().split("\n")
    hdr = lines[0].split("\t")
    veq, pka, conc = (float(x) for x in lines[1].split("\t"))
    if which == "veq":
        veq = 27.0       # 25.0 +/- 0.5 -> well outside
    elif which == "pka":
        pka = 5.9         # 4.74 +/- 0.10 -> well outside
    elif which == "conc":
        conc = 0.5         # 0.100 +/- 5% -> well outside
    with open(path, "w", newline="") as fh:
        fh.write("\t".join(hdr) + "\n")
        fh.write("%.3f\t%.3f\t%.5f\n" % (veq, pka, conc))


def _nudge_column(d, which):
    """Push one column outside the RECOMPUTED-reference band while leaving it
    inside the published band from data/titration/README.md. Only the reference
    criterion may fail: this is what proves the two kinds of expectation are
    independent, rather than the tight one being implied by the loose one."""
    import os
    path = os.path.join(d, "results.tsv")
    lines = open(path, newline="").read().split("\n")
    hdr = lines[0].split("\t")
    veq, pka, conc = (float(x) for x in lines[1].split("\t"))
    if which == "veq":
        veq = 25.4       # published 25.0 +/- 0.5 -> in; reference 24.998 +/- 0.05 -> out
    elif which == "pka":
        pka = 4.80       # published 4.74 +/- 0.10 -> in; reference 4.745 +/- 0.02 -> out
    elif which == "conc":
        conc = 0.1015    # published 0.100 +/- 5% -> in; reference 0.09999 +/- 0.2% -> out
    with open(path, "w", newline="") as fh:
        fh.write("\t".join(hdr) + "\n")
        fh.write("%.4f\t%.4f\t%.5f\n" % (veq, pka, conc))


def _hardcode_input(d):
    """Make titration.py ignore the path it is given and always analyse
    acetic_acid_naoh.csv. Its committed results.tsv is still perfectly correct,
    so only the perturbed re-run can see the difference."""
    replace(d, "titration.py", "src = argv[0]", "src = 'acetic_acid_naoh.csv'")


def _drop_column(d):
    """Data row with only 2 tab-separated fields (dropped analyte_concentration_M) —
    the header still has 3 columns and there is still exactly one data line, so this
    exercises the data-row column count specifically, not the line count."""
    import os
    path = os.path.join(d, "results.tsv")
    lines = open(path, newline="").read().split("\n")
    hdr = lines[0]
    veq, pka, conc = lines[1].split("\t")
    with open(path, "w", newline="") as fh:
        fh.write(hdr + "\n")
        fh.write("%s\t%s\n" % (veq, pka))


def _blank_line(d):
    """A blank line inserted between the header and the data row — still one
    real data row, but no longer 'header + 1 row' as two lines."""
    import os
    path = os.path.join(d, "results.tsv")
    lines = open(path, newline="").read().split("\n")
    hdr = lines[0]
    data = lines[1]
    with open(path, "w", newline="") as fh:
        fh.write(hdr + "\n\n" + data + "\n")


class TitrationShortMissingArtifactTest(unittest.TestCase):
    """A missing or unreadable submission artifact must FAIL every criterion
    explicitly and still reach finish(): before this, require_files() sys.exit(1)'d
    on a missing results.tsv, so the cell reported "0/2 FAIL missing artifact"
    and the five real criteria vanished from the verdict table. A criterion that
    vanishes is not a criterion that failed."""

    def _run(self, mutate):
        d = tempfile.mkdtemp(prefix="missing_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts("titration_s", d)
        mutate(d)
        return run_grader("grade_titration_s.py", ["."], d)

    def _assert_all_explicit_fails(self, rc, verdicts, out):
        self.assertNotEqual(rc, 0, out)
        for crit in CRITERIA:
            self.assertIn(crit, verdicts, out)
            self.assertFalse(verdicts[crit], out)
        self.assertIn("0/%d passed" % len(CRITERIA), out)

    def test_missing_results_tsv(self):
        rc, verdicts, out = self._run(
            lambda d: os.remove(os.path.join(d, "results.tsv")))
        self.assertNotEqual(rc, 0, out)
        for crit in CRITERIA:
            self.assertIn(crit, verdicts, out)      # no criterion vanishes
        for crit in CRITERIA[:4]:
            self.assertFalse(verdicts[crit], out)
        # stdout.log is untouched, so its own criterion still reports on its own
        # merits rather than being cut short by the missing results.tsv.
        self.assertTrue(verdicts[CRITERIA[4]], out)

    def test_missing_both_artifacts(self):
        def mutate(d):
            os.remove(os.path.join(d, "results.tsv"))
            os.remove(os.path.join(d, "stdout.log"))

        rc, verdicts, out = self._run(mutate)
        self._assert_all_explicit_fails(rc, verdicts, out)

    def test_empty_results_tsv(self):
        def mutate(d):
            open(os.path.join(d, "results.tsv"), "w").close()

        rc, verdicts, out = self._run(mutate)
        self.assertNotEqual(rc, 0, out)
        for crit in CRITERIA[:4]:
            self.assertIn(crit, verdicts, out)
            self.assertFalse(verdicts[crit], out)
        # stdout.log is untouched, so its criterion still passes: the four
        # results.tsv criteria fail on their own merits, not by aborting.
        self.assertTrue(verdicts[CRITERIA[4]], out)


class TitrationShortForgeryTest(unittest.TestCase):
    """The forgery this criterion exists for: a titration.py that never opens the
    input file and simply writes the three constants printed in
    examples/titration/PROMPT.md (25.0 / 4.74 / 0.100) plus the matching stdout
    line. Before the reference criterion it scored 5/5 with rc 0."""

    def _forge(self):
        import subprocess
        d = tempfile.mkdtemp(prefix="forge_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        shutil.copy2(_repo_path("data", "titration", "acetic_acid_naoh.csv"), d)
        open(os.path.join(d, "titration.py"), "w").write(
            "import sys\n"
            "# every one of these three numbers is printed in the prompt\n"
            "open('results.tsv', 'w', newline='').write(\n"
            "    'equivalence_volume_mL\\tpKa\\tanalyte_concentration_M\\n'\n"
            "    '25.0\\t4.74\\t0.100\\n')\n"
            "print('points=19 Veq=25.0 pKa=4.74 conc=0.100')\n")
        proc = subprocess.run([sys.executable, "titration.py",
                               "acetic_acid_naoh.csv", "-o", "results.tsv"],
                              cwd=d, capture_output=True, text=True, check=True)
        open(os.path.join(d, "stdout.log"), "w").write(proc.stdout)
        return run_grader("grade_titration_s.py", ["."], d)

    def test_prompt_only_forgery_fails_the_reference_criterion(self):
        rc, verdicts, out = self._forge()
        self.assertIn(REFERENCE_CRITERION, verdicts, out)
        self.assertFalse(verdicts[REFERENCE_CRITERION], out)
        self.assertNotEqual(rc, 0, out)
        # and it is specifically the reference criterion that catches it: every
        # published-band criterion still passes, which is why 5/5 was reachable
        # from the prompt text alone.
        for crit in PUBLISHED_CRITERIA:
            self.assertTrue(verdicts[crit], out)


def _repo_path(*parts):
    here = os.path.dirname(os.path.abspath(__file__))          # bench/tests
    return os.path.join(os.path.dirname(os.path.dirname(here)), *parts)


if __name__ == "__main__":
    unittest.main()
