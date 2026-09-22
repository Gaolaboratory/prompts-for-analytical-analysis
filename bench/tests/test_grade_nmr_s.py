import os, shutil, tempfile

import fixtures
from grader_rig import GraderCase, replace, run_grader


class NmrShortGraderTest(GraderCase):
    grader = "grade_nmr_s.py"
    grader_args = ["multiplets.tsv", "stdout.log"]
    tool = "nmr_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "multiplets.tsv",
                                "ppm_center\tintegral_rel", "center\trel_int"),
             "multiplets.tsv: header + rows sorted by ppm_center, columns in order"),
            (lambda d: _shift_ppm(d, 0.3),
             "all six assigned resonances within 0.05 ppm on the true axis"),
            (lambda d: _double_integral_near(d, 1.921),
             "TSP is the reference row at 1.000 and the four metabolite "
             "integrals match the reference within 20%"),
            (lambda d: _append_row(d, 9.533, 0.5),
             "no mirrored peak near 9.53 ppm (real-channel processing)"),
            (lambda d: replace(d, "stdout.log", "reference_ppm=", "ref_ppm="),
             "stdout reports points, peaks and reference_ppm=0.000"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)

    def test_swapped_ppm_center_integral_rel_columns_fail_only_criterion_1(self):
        """Rule 10: a format deviation criterion 1 is supposed to own must
        not cascade into the value criteria. Swap the ppm_center and
        integral_rel COLUMNS, header included, in every row --
        header_col_map() must still recover both fields under their own
        (now-reordered) names, so this fails ONLY criterion 1, with
        criteria 2-5 all PASS."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _swap_cols_all_rows(d, 0, 1)
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(
            verdicts["multiplets.tsv: header + rows sorted by ppm_center, "
                     "columns in order"], out)
        for crit in ("all six assigned resonances within 0.05 ppm on the true axis",
                     "TSP is the reference row at 1.000 and the four "
                     "metabolite integrals match the reference within 20%",
                     "no mirrored peak near 9.53 ppm (real-channel processing)",
                     "stdout reports points, peaks and reference_ppm=0.000"):
            self.assertTrue(verdicts[crit], out)

    def test_dropped_integral_rel_column_fails_only_criteria_that_need_it(self):
        """Rule 10 gap 2: header_col_map() used to require the header to be
        a COMPLETE permutation of the two mandated names, so dropping
        integral_rel (used only by criterion 3) blanked `rows` entirely and
        cascaded into criteria 2 and 4 (position, mirror), which only ever
        read ppm_center. Not moot despite there being only two columns:
        ppm_center is the KEY field every criterion locates rows by, so
        only integral_rel's own criterion should fail alongside criterion 1."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _drop_col(d, "integral_rel")
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(
            verdicts["multiplets.tsv: header + rows sorted by ppm_center, "
                     "columns in order"], out)
        self.assertFalse(
            verdicts["TSP is the reference row at 1.000 and the four "
                     "metabolite integrals match the reference within 20%"], out)
        for crit in ("all six assigned resonances within 0.05 ppm on the true axis",
                     "no mirrored peak near 9.53 ppm (real-channel processing)",
                     "stdout reports points, peaks and reference_ppm=0.000"):
            self.assertTrue(verdicts[crit], out)


def _drop_col(d, name):
    """Rewrite multiplets.tsv without the named column entirely, header and
    every data row."""
    path, header, rows = _read_rows(d)
    hdr = header.split("\t")
    idx = hdr.index(name)
    for r in rows:
        del r[idx]
    _write_rows(path, "\t".join(hdr[:idx] + hdr[idx + 1:]), rows)


def _swap_cols_all_rows(d, i, j):
    """Swap columns `i` and `j` of multiplets.tsv, header AND every data
    row, so each value stays labelled with its own (now-reordered) name."""
    path, header, rows = _read_rows(d)
    hdr = header.split("\t")
    hdr[i], hdr[j] = hdr[j], hdr[i]
    for r in rows:
        r[i], r[j] = r[j], r[i]
    _write_rows(path, "\t".join(hdr), rows)


def _read_rows(d):
    path = os.path.join(d, "multiplets.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    return path, lines[0], [l.split("\t") for l in lines[1:]]


def _write_rows(path, header, rows):
    open(path, "w").write("\n".join([header] + ["\t".join(r) for r in rows]) + "\n")


def _shift_ppm(d, delta):
    """Shift every ppm_center in multiplets.tsv by `delta`, leaving every
    integral_rel untouched -- trips only the position criterion."""
    path, header, rows = _read_rows(d)
    for r in rows:
        r[0] = "%.4f" % (float(r[0]) + delta)
    _write_rows(path, header, rows)


def _double_integral_near(d, nominal):
    """Double the integral_rel of the row nearest `nominal` ppm, leaving
    every ppm_center and every other row untouched -- trips only the
    integral criterion, not the position criterion."""
    path, header, rows = _read_rows(d)
    i = min(range(len(rows)), key=lambda i: abs(float(rows[i][0]) - nominal))
    rows[i][1] = "%.6f" % (float(rows[i][1]) * 2.0)
    _write_rows(path, header, rows)


def _append_row(d, ppm_center, integral_rel):
    """Append one extra row to multiplets.tsv without touching any existing
    row -- used to plant the real-channel mirror signature (a peak near
    9.5330 - true_ppm) that criterion 4 exists to catch."""
    path, header, rows = _read_rows(d)
    rows.append(["%.4f" % ppm_center, "%.6f" % integral_rel])
    _write_rows(path, header, rows)
