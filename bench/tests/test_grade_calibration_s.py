import os, re, shutil, tempfile

import fixtures
from grader_rig import GraderCase, replace, run_grader

CRIT_SLOPE_INTERCEPT = "slope and intercept match the NIST certified values (<=1e-9 relative)"
CRIT_RESID_R2 = "residual_sd and r_squared match the NIST certified values (<=1e-9 relative)"

# NIST certified values, written literally here (not imported from the
# grader or the reference) for the same reason grade_calibration_s.py itself
# keeps them literal: a wrong upstream implementation must not certify a
# wrong test.
CERT = {
    "slope": 1.00211681802045,
    "intercept": -0.262323073774029,
    "resid_sd": 0.884796396144373,
    "r2": 0.999993745883712,
}


def _write_precision_row(d, sig_figs):
    """Overwrite the conformant fixture's results.tsv data row (and the
    matching stdout.log fields) with the certified slope/intercept/
    residual_sd/r_squared values rounded to EXACTLY `sig_figs` significant
    figures -- lod/loq are left as whatever the fixture already computed,
    since neither caller of this helper asserts on criterion 4."""
    fmt = {k: "%.*g" % (sig_figs, v) for k, v in CERT.items()}

    path = os.path.join(d, "results.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    row = lines[1].split("\t")
    row[0], row[1], row[2], row[3] = (
        fmt["slope"], fmt["intercept"], fmt["resid_sd"], fmt["r2"])
    lines[1] = "\t".join(row)
    open(path, "w", newline="").write("\n".join(lines) + "\n")

    stdout_path = os.path.join(d, "stdout.log")
    text = open(stdout_path).read()
    for key, value in (("slope", fmt["slope"]), ("intercept", fmt["intercept"]),
                        ("resid_sd", fmt["resid_sd"]), ("r2", fmt["r2"])):
        text = re.sub(r"(?<![A-Za-z0-9_])%s=[-+0-9.eE]+" % re.escape(key),
                       "%s=%s" % (key, value), text)
    open(stdout_path, "w").write(text)


class CalibrationShortGraderPrecisionTest(GraderCase):
    """Closes the precision cliff directly: a tool printing exactly the
    prompt's mandated minimum (12 significant figures) must pass criteria 2
    and 3, and the OLD 9-significant-figure mandate must still fail
    criterion 2 -- reproducing the defect this fix closes (a value beginning
    with "1", like slope, resolves ten times more coarsely per significant
    figure than one beginning with "8"; at 9 sig figs slope's relative error
    is 1.975e-9, past the grader's 1e-9 tolerance, while intercept/
    residual_sd/r_squared -- whose leading digits give finer resolution --
    stay under it. At 12 sig figs all four clear the tolerance by ~3 orders
    of magnitude: slope's relative error is 4.49e-13)."""

    grader = "grade_calibration_s.py"
    grader_args = ["."]
    tool = "calibration_s"

    def _run_at_precision(self, sig_figs):
        d = tempfile.mkdtemp(prefix="prec_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _write_precision_row(d, sig_figs)
        return run_grader(self.grader, self.grader_args, cwd=d)

    def test_12_sig_figs_minimum_passes(self):
        rc, verdicts, out = self._run_at_precision(12)
        self.assertTrue(verdicts.get(CRIT_SLOPE_INTERCEPT), out)
        self.assertTrue(verdicts.get(CRIT_RESID_R2), out)

    def test_9_sig_figs_old_mandate_still_fails(self):
        rc, verdicts, out = self._run_at_precision(9)
        self.assertFalse(verdicts.get(CRIT_SLOPE_INTERCEPT), out)
        # intercept/residual_sd/r_squared individually still clear 1e-9 at
        # 9 sig figs -- only slope (and, through the AND, criterion 2) falls
        # off the cliff, so criterion 3 stays PASS even here.
        self.assertTrue(verdicts.get(CRIT_RESID_R2), out)


class CalibrationShortGraderTest(GraderCase):
    grader = "grade_calibration_s.py"
    grader_args = ["."]
    tool = "calibration_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "results.tsv", "slope\tintercept", "m\tb"),
             "results.tsv: header + exactly one data row, columns in order, no CR"),
            (lambda d: _set_col(d, 0, "1.5"),
             "slope and intercept match the NIST certified values (<=1e-9 relative)"),
            (lambda d: _set_col(d, 3, "0.5"),
             "residual_sd and r_squared match the NIST certified values (<=1e-9 relative)"),
            (lambda d: _set_col(d, 4, "9.99"),
             "lod and loq match the reference recomputed from norris.csv (<=1e-6 relative)"),
            (lambda d: replace(d, "stdout.log", "loq=", "xx="),
             "stdout reports all seven fields"),
            (lambda d: _freeze_tool(d),
             "re-running calibrate.py on a perturbed norris.csv reproduces "
             "the reference fit for that input"),
            (lambda d: _scale_by_mean_ratio(d),
             "re-running calibrate.py on a perturbed norris.csv reproduces "
             "the reference fit for that input"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)

    def test_swapped_slope_intercept_columns_fail_only_criterion_1(self):
        """Rule 10: a format deviation criterion 1 is supposed to own must
        not cascade into the value criteria. Swap the slope and intercept
        COLUMNS, header included, so each value keeps sitting under its own
        (now-reordered) name -- named_fields() must still recover every
        field, so this fails ONLY criterion 1, with criteria 2-6 all PASS."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _swap_cols(d, 0, 1)
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(
            verdicts["results.tsv: header + exactly one data row, "
                     "columns in order, no CR"], out)
        for crit in (CRIT_SLOPE_INTERCEPT, CRIT_RESID_R2,
                     "lod and loq match the reference recomputed from "
                     "norris.csv (<=1e-6 relative)",
                     "stdout reports all seven fields",
                     "re-running calibrate.py on a perturbed norris.csv "
                     "reproduces the reference fit for that input"):
            self.assertTrue(verdicts[crit], out)

    def test_dropped_loq_column_fails_only_criteria_that_need_it(self):
        """Rule 10 gap 2: named_fields() used to require the header to be a
        COMPLETE permutation of the six mandated names, so dropping even
        one column (loq, used only by criterion 4) blanked every field and
        cascaded into criteria 2 and 3, which have nothing to do with loq.
        Dropping loq must fail criterion 1 (header no longer matches) and
        criterion 4 (loq genuinely absent) -- and nothing else."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _drop_col(d, "loq")
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(
            verdicts["results.tsv: header + exactly one data row, "
                     "columns in order, no CR"], out)
        self.assertFalse(
            verdicts["lod and loq match the reference recomputed from "
                     "norris.csv (<=1e-6 relative)"], out)
        for crit in (CRIT_SLOPE_INTERCEPT, CRIT_RESID_R2,
                     "stdout reports all seven fields"):
            self.assertTrue(verdicts[crit], out)


def _drop_col(d, name):
    """Rewrite results.tsv without the named column entirely, header and
    data row both."""
    path = os.path.join(d, "results.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    hdr = lines[0].split("\t")
    idx = hdr.index(name)
    new_hdr = hdr[:idx] + hdr[idx + 1:]
    row = lines[1].split("\t")
    new_row = row[:idx] + row[idx + 1:]
    open(path, "w").write("\t".join(new_hdr) + "\n" + "\t".join(new_row) + "\n")


def _swap_cols(d, i, j):
    """Swap columns `i` and `j` of results.tsv, header included, so each
    value stays labelled with its own (now-reordered) name."""
    path = os.path.join(d, "results.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    hdr = lines[0].split("\t")
    hdr[i], hdr[j] = hdr[j], hdr[i]
    row = lines[1].split("\t")
    row[i], row[j] = row[j], row[i]
    open(path, "w").write("\t".join(hdr) + "\n" + "\t".join(row) + "\n")


def _set_col(d, idx, value):
    """Overwrite one column of the single data row, leaving the header intact."""
    import os
    path = os.path.join(d, "results.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    row = lines[1].split("\t")
    row[idx] = value
    lines[1] = "\t".join(row)
    open(path, "w").write("\n".join(lines) + "\n")


def _freeze_tool(d):
    """Replace calibrate.py with one that ignores its input and prints the
    published constants -- the forgery the perturbation criterion exists to
    catch. Its results.tsv and stdout.log stay conformant, so only criterion 6
    may fail."""
    import os
    src = (
        "import argparse\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('input'); p.add_argument('-o', required=True)\n"
        "a = p.parse_args()\n"
        "row = (1.002116818, -0.262323074, 0.884796396, 0.999993746, 2.913660, 8.829274)\n"
        "open(a.o, 'w').write('slope\\tintercept\\tresidual_sd\\tr_squared\\tlod\\tloq\\n'\n"
        "                     + '\\t'.join('%.9f' % v for v in row) + '\\n')\n"
        "print('n=36 slope=%.9f intercept=%.9f resid_sd=%.9f r2=%.9f lod=%.6f loq=%.6f' % row)\n"
    )
    open(os.path.join(d, "calibrate.py"), "w").write(src)


def _scale_by_mean_ratio(d):
    """Replace calibrate.py with one that reads its input (so it is not the
    _freeze_tool forgery) and reports certified_slope * (mean_y / the
    original norris.csv's mean_y), with intercept/residual_sd/lod/loq scaled
    by the same ratio and r_squared scaled by it too.

    Under a UNIFORM y -> k*y rescale, slope/intercept/residual_sd genuinely
    scale by k and this closed-form correction would reproduce them exactly
    without ever doing per-point OLS -- which is why the grader's perturbation
    is no longer a uniform rescale (grade_calibration_s.perturbed_csv scales
    only every third row). Against that non-uniform perturbation, computing a
    single mean-ratio "scale factor" and applying it to hardcoded constants is
    simply wrong: it disagrees with the recomputed reference on every one of
    slope, intercept, residual_sd AND r_squared (verified: ~0.7%, ~92%, ~97%
    and ~4% relative, all far past the 1e-6 tolerance), not merely on
    r_squared as it did against the old uniform perturbation.
    """
    import os
    unperturbed_mean_y = 419.8027777777778   # mean(y) in data/calibration/norris.csv
    src = (
        "import argparse, csv\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('input'); p.add_argument('-o', required=True)\n"
        "a = p.parse_args()\n"
        "ys = [float(row['y']) for row in csv.DictReader(open(a.input))]\n"
        "ratio = (sum(ys) / len(ys)) / %r\n"
        "cert = (1.00211681802045, -0.262323073774029, 0.884796396144373,\n"
        "        0.999993745883712, 2.913660, 8.829274)\n"
        "row = tuple(v * ratio for v in cert)\n"
        "open(a.o, 'w').write('slope\\tintercept\\tresidual_sd\\tr_squared\\tlod\\tloq\\n'\n"
        "                     + '\\t'.join('%%.9f' %% v for v in row) + '\\n')\n"
        "print('n=36 slope=%%.9f intercept=%%.9f resid_sd=%%.9f r2=%%.9f "
        "lod=%%.6f loq=%%.6f' %% row)\n"
        % unperturbed_mean_y
    )
    open(os.path.join(d, "calibrate.py"), "w").write(src)
