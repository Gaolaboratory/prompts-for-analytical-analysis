import shutil, tempfile

import fixtures
from grader_rig import GraderCase, replace, run_grader


class UvvisShortGraderTest(GraderCase):
    grader = "grade_uvvis_s.py"
    grader_args = ["."]
    tool = "uvvis_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "bands.tsv", "lambda_max_nm\tepsilon", "lmax\teps"),
             "bands.tsv: header + exactly one band row, columns in order, no CR"),
            (lambda d: _set_col(d, 0, "400.0"),
             "lambda_max 317 +/- 3 nm"),
            (lambda d: _set_col(d, 1, "5000.0"),
             "epsilon within 2% of 9283"),
            (lambda d: _set_col(d, 2, "20.0"),
             "fwhm within 2 nm of the reference recomputed from the input"),
            (lambda d: replace(d, "stdout.log", "bands=", "xx="),
             "stdout reports points, bands, lambda_max and epsilon"),
            (lambda d: _freeze_tool(d),
             "re-running uvvis.py on an absorbance-tilted input reproduces "
             "the reference lambda_max and epsilon for that input"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)

    def test_swapped_lambda_max_epsilon_columns_fail_only_criterion_1(self):
        """Rule 10: a format deviation criterion 1 is supposed to own must
        not cascade into the value criteria. Swap the lambda_max_nm and
        epsilon COLUMNS, header included, so each value keeps sitting under
        its own (now-reordered) name -- named_fields() must still recover
        every field, so this fails ONLY criterion 1, with criteria 2-6 all
        PASS."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _swap_cols(d, 0, 1)
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(
            verdicts["bands.tsv: header + exactly one band row, "
                     "columns in order, no CR"], out)
        for crit in ("lambda_max 317 +/- 3 nm",
                     "epsilon within 2% of 9283",
                     "fwhm within 2 nm of the reference recomputed from the input",
                     "stdout reports points, bands, lambda_max and epsilon",
                     "re-running uvvis.py on an absorbance-tilted input "
                     "reproduces the reference lambda_max and epsilon for "
                     "that input"):
            self.assertTrue(verdicts[crit], out)

    def test_dropped_fwhm_column_fails_only_criteria_that_need_it(self):
        """Rule 10 gap 2: named_fields() used to require the header to be a
        COMPLETE permutation of the three mandated names, so dropping even
        one column (fwhm_nm, used only by criterion 4) blanked every field
        and cascaded into criteria 2 and 3 (lambda_max, epsilon), which have
        nothing to do with fwhm. Dropping fwhm_nm must fail criterion 1 and
        criterion 4 -- and nothing else."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _drop_col(d, "fwhm_nm")
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(
            verdicts["bands.tsv: header + exactly one band row, "
                     "columns in order, no CR"], out)
        self.assertFalse(
            verdicts["fwhm within 2 nm of the reference recomputed from "
                     "the input"], out)
        for crit in ("lambda_max 317 +/- 3 nm",
                     "epsilon within 2% of 9283",
                     "stdout reports points, bands, lambda_max and epsilon"):
            self.assertTrue(verdicts[crit], out)


def _drop_col(d, name):
    """Rewrite bands.tsv without the named column entirely, header and data
    row both."""
    import os
    path = os.path.join(d, "bands.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    hdr = lines[0].split("\t")
    idx = hdr.index(name)
    new_hdr = hdr[:idx] + hdr[idx + 1:]
    row = lines[1].split("\t")
    new_row = row[:idx] + row[idx + 1:]
    open(path, "w").write("\t".join(new_hdr) + "\n" + "\t".join(new_row) + "\n")


def _swap_cols(d, i, j):
    """Swap columns `i` and `j` of bands.tsv, header included, so each value
    stays labelled with its own (now-reordered) name."""
    import os
    path = os.path.join(d, "bands.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    hdr = lines[0].split("\t")
    hdr[i], hdr[j] = hdr[j], hdr[i]
    row = lines[1].split("\t")
    row[i], row[j] = row[j], row[i]
    open(path, "w").write("\t".join(hdr) + "\n" + "\t".join(row) + "\n")


def _set_col(d, idx, value):
    """Overwrite one column of the single data row, leaving the header intact."""
    import os
    path = os.path.join(d, "bands.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    row = lines[1].split("\t")
    row[idx] = value
    lines[1] = "\t".join(row)
    open(path, "w").write("\n".join(lines) + "\n")


def _freeze_tool(d):
    """Replace uvvis.py with a forgery that detects a uniform wavelength
    offset in its input (by comparing the first row's wavelength to the
    known unperturbed first wavelength) and adds that offset to a hardcoded
    lambda_max, rather than actually re-locating the band maximum.

    The grader's perturbation is NOT a wavelength shift -- it is an
    absorbance ramp, 1 + 0.002*(wavelength_nm - 225), applied to the
    unperturbed wavelengths. Under that ramp the apparent band maximum moves
    by an amount obtainable only by re-analysing the tilted band; a tool
    that looks for (and finds none of) a wavelength offset falls back to the
    unperturbed hardcoded lambda_max AND epsilon, both of which disagree with
    the reference recomputed from the ramped input (lambda_max by one grid
    step, epsilon by ~18%). fwhm is also hardcoded so only criterion 6 is
    expected to fail (others may incidentally fail too, which check_mutation
    permits).
    """
    import os
    src = (
        "import argparse, csv\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('input'); p.add_argument('-o', required=True)\n"
        "a = p.parse_args()\n"
        "rows = list(csv.DictReader(open(a.input)))\n"
        "first_w = float(rows[0]['wavelength_nm'])\n"
        "offset = first_w - 224.99365\n"
        "lambda_max = 317.015 + offset\n"
        "epsilon = 9283.39\n"
        "fwhm = 66.698\n"
        "open(a.o, 'w').write('lambda_max_nm\\tepsilon\\tfwhm_nm\\n'\n"
        "                     + '%.3f\\t%.2f\\t%.3f\\n' % (lambda_max, epsilon, fwhm))\n"
        "print('points=%d bands=1 lambda_max=%.3f epsilon=%.2f' % "
        "(len(rows), lambda_max, epsilon))\n"
    )
    open(os.path.join(d, "uvvis.py"), "w").write(src)
