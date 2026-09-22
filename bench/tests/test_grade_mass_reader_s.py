import os
import shutil
import tempfile
import unittest

import fixtures
from grader_rig import GraderCase, replace, run_grader

# Kept in sync with the CRITERIA list in bench/graders/grade_mass_reader_s.py.
CRITERIA = [
    "fasta: 48 records, 19929 residues, first sp|P00509|AAT_ECOLI/396",
    "bsa: 40 spectra (10 MS1 / 30 MS2), ids spectrum=1011..spectrum=2471",
    "bsa: rt_first 1501.414 s, rt_last 1590.187 s",
    "bsa: first MS2 spectrum=2442, precursor 457.72397, z=2, charges {2,3}",
    "thermo: 2 MS1 x 19914 peaks, rt 0.2961/0.3561 s (minutes rule)",
    "tic totals within 0.1% (45709750.4 / 138763684.2) and the mandated "
    "one-line stdout summary for the bsa file",
]
FASTA_CRITERION = CRITERIA[0]
MZML_CRITERIA = CRITERIA[1:]


class MassReaderShortGraderTest(GraderCase):
    grader = "grade_mass_reader_s.py"
    grader_args = []
    tool = "mass_reader_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "fasta_reader.py",
                               'line[1:].split()[0] if line[1:].split() else ""',
                               '"WRONG"'),
             "fasta: 48 records, 19929 residues, first sp|P00509|AAT_ECOLI/396"),
            (lambda d: replace(d, "mzml_reader.py",
                               'int(top[MS_LEVEL].get("value")) if MS_LEVEL in top else None',
                               '9'),
             "bsa: 40 spectra (10 MS1 / 30 MS2), ids spectrum=1011..spectrum=2471"),
            (lambda d: replace(d, "mzml_reader.py", "rt * 60.0", "rt * 1.0"),
             "thermo: 2 MS1 x 19914 peaks, rt 0.2961/0.3561 s (minutes rule)"),
            (lambda d: replace(d, "mzml_reader.py",
                               'float(cv.get("value"))', 'float(cv.get("value")) + 1.0'),
             "bsa: rt_first 1501.414 s, rt_last 1590.187 s"),
            (lambda d: replace(d, "mzml_reader.py",
                               'int(p[CHARGE].get("value"))', 'None'),
             "bsa: first MS2 spectrum=2442, precursor 457.72397, z=2, charges {2,3}"),
            (lambda d: replace(d, "mzml_reader.py", '"<%df"', '"<%dd"'),
             CRITERIA[5]),
            # The stdout half of that criterion, mutated on its own: the imported
            # reader still gives the right TIC totals in all three cases, so only
            # the mandated summary line can fail.
            (lambda d: replace(d, "stdout.log", "spectra=", "n_spectra="),
             CRITERIA[5]),
            (lambda d: replace(d, "stdout.log", "ms1=10", "ms1=40"), CRITERIA[5]),
            (lambda d: _second_line(d), CRITERIA[5]),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)


def _second_line(d):
    """A second output line: the prompt says "prints exactly one line"."""
    with open(os.path.join(d, "stdout.log"), "a") as fh:
        fh.write("spectrum=1011 ms1 rt=1501.41394042969 peaks=467\n")


class MassReaderBrokenSubmissionTest(unittest.TestCase):
    """Total-breakage shapes: a module that raises at import, that has had its
    entry point renamed away, or that is missing entirely. The grader must
    still reach finish() and report an explicit PASS/FAIL for every one of the
    six criteria -- an absent criterion is not the same as a failed one -- AND
    the two modules must be graded independently: breaking mzml_reader.py must
    fail only the five mzML criteria (fasta_reader.py is a separate file that
    may be perfectly correct), and breaking fasta_reader.py must fail only the
    FASTA criterion."""

    def _run(self, mutate):
        d = tempfile.mkdtemp(prefix="broken_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts("mass_reader_s", d)
        mutate(d)
        return run_grader("grade_mass_reader_s.py", [], d)

    def _assert_split(self, rc, verdicts, out, fasta_pass, mzml_pass):
        self.assertNotEqual(rc, 0, out)
        for crit in CRITERIA:
            self.assertIn(crit, verdicts, out)
        self.assertEqual(verdicts[FASTA_CRITERION], fasta_pass, out)
        for crit in MZML_CRITERIA:
            self.assertEqual(verdicts[crit], mzml_pass, out)

    def test_mzml_reader_raises_at_import(self):
        def mutate(d):
            with open(os.path.join(d, "mzml_reader.py"), "a") as f:
                f.write("\nraise RuntimeError('boom at import time')\n")

        rc, verdicts, out = self._run(mutate)
        self._assert_split(rc, verdicts, out, fasta_pass=True, mzml_pass=False)

    def test_read_mzml_renamed(self):
        def mutate(d):
            replace(d, "mzml_reader.py", "def read_mzml(", "def read_mzml_renamed(")

        rc, verdicts, out = self._run(mutate)
        self._assert_split(rc, verdicts, out, fasta_pass=True, mzml_pass=False)

    def test_mzml_reader_deleted(self):
        def mutate(d):
            os.remove(os.path.join(d, "mzml_reader.py"))

        rc, verdicts, out = self._run(mutate)
        self._assert_split(rc, verdicts, out, fasta_pass=True, mzml_pass=False)

    def test_fasta_reader_deleted(self):
        def mutate(d):
            os.remove(os.path.join(d, "fasta_reader.py"))

        rc, verdicts, out = self._run(mutate)
        self._assert_split(rc, verdicts, out, fasta_pass=False, mzml_pass=True)
