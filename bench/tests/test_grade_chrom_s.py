import os, shutil, tempfile

import fixtures
from grader_rig import GraderCase, replace, run_grader


class ChromShortGraderTest(GraderCase):
    grader = "grade_chrom_s.py"
    grader_args = ["."]
    tool = "chrom_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "peaks.tsv", "peak_id\trt_apex_s", "id\trt"),
             "peaks.tsv: header + exactly 10 rows sorted by rt_apex_s, columns in order"),
            (lambda d: _scale_col(d, 1, 1.0 / 60.0),
             "all ten reference apexes present within 5%, in seconds"),
            (lambda d: _scale_col(d, 2, 0.5),
             "apex heights within 5% of the reference recomputed from chrom.csv"),
            (lambda d: replace(d, "stdout.log", "baseline=-4.797", "baseline=0.000"),
             "baseline -4.797 +/- 0.5 and sigma 0.615 +/- 20%"),
            (lambda d: replace(d, "stdout.log", "sigma=0.615", "sigma=broken"),
             "stdout reports points, baseline, sigma and peaks"),
            (lambda d: _apex_rescale_forgery(d),
             "re-running chrom_integrate.py on a peak-injected chrom.csv "
             "reproduces the reference peak set for that input"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)

    def test_non_numeric_peak_id_fails_only_criterion_1(self):
        """Rule 10: a format deviation criterion 1 is supposed to own must not
        cascade into the value criteria. This is the real defect from
        chrom_s/local/2 -- peak_id written as p1..p10 instead of 1..10 -- cut
        down to a mutation test: it must fail ONLY criterion 1, with every
        apex-time and height value still exactly right and both left passing.
        """
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _reid_peaks(d)
        rc, verdicts, out = run_grader(self.grader, ["."], cwd=d)
        self.assertNotEqual(rc, 0, out)
        shape_crit = ("peaks.tsv: header + exactly 10 rows sorted by "
                      "rt_apex_s, columns in order")
        self.assertFalse(verdicts[shape_crit], out)
        self.assertTrue(verdicts["all ten reference apexes present within "
                                  "5%, in seconds"], out)
        self.assertTrue(verdicts["apex heights within 5% of the reference "
                                  "recomputed from chrom.csv"], out)

    def test_reordered_rt_apex_s_height_columns_fail_only_criterion_1(self):
        """Rule 10 gap 1: rt_apex_s and height were still unpacked
        positionally, gated on a header check that demanded the mandated
        column order -- a column-reorder probe (rt_apex_s and height
        swapped, header included, every value correct under its own
        relabeled name) used to fail both value criteria even though every
        apex and height was exactly right. Must fail ONLY criterion 1."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _swap_rt_height_columns(d)
        rc, verdicts, out = run_grader(self.grader, ["."], cwd=d)
        self.assertNotEqual(rc, 0, out)
        shape_crit = ("peaks.tsv: header + exactly 10 rows sorted by "
                      "rt_apex_s, columns in order")
        self.assertFalse(verdicts[shape_crit], out)
        self.assertTrue(verdicts["all ten reference apexes present within "
                                  "5%, in seconds"], out)
        self.assertTrue(verdicts["apex heights within 5% of the reference "
                                  "recomputed from chrom.csv"], out)

    def test_dropped_area_column_fails_only_criterion_1(self):
        """Rule 10 gap 1: `area` is deliberately ungraded by any value
        criterion (see the grader's module docstring), so dropping it from
        peaks.tsv is a pure shape defect -- it must fail criterion 1 alone
        and leave every other criterion, including the two value criteria
        and the perturbation re-run, passing."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _drop_area_column(d)
        rc, verdicts, out = run_grader(self.grader, ["."], cwd=d)
        self.assertNotEqual(rc, 0, out)
        shape_crit = ("peaks.tsv: header + exactly 10 rows sorted by "
                      "rt_apex_s, columns in order")
        self.assertFalse(verdicts[shape_crit], out)
        for crit, ok in verdicts.items():
            if crit != shape_crit:
                self.assertTrue(ok, "%s: %s" % (crit, out))


def _swap_rt_height_columns(d):
    """Rewrite peaks.tsv with the rt_apex_s and height columns swapped,
    header included, so every value stays correct under its own relabeled
    name -- a pure column-reorder defect."""
    path = os.path.join(d, "peaks.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    hdr = lines[0].split("\t")
    assert hdr == ["peak_id", "rt_apex_s", "height", "area"], hdr
    out = ["\t".join(["peak_id", "height", "rt_apex_s", "area"])]
    for line in lines[1:]:
        p = line.split("\t")
        out.append("\t".join([p[0], p[2], p[1], p[3]]))
    open(path, "w").write("\n".join(out) + "\n")


def _drop_area_column(d):
    """Rewrite peaks.tsv without the area column entirely."""
    path = os.path.join(d, "peaks.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    out = []
    for line in lines:
        out.append("\t".join(line.split("\t")[:3]))
    open(path, "w").write("\n".join(out) + "\n")


def _scale_col(d, idx, factor):
    """Multiply column `idx` (0-based) of every data row in peaks.tsv by
    `factor`, leaving the header and other columns intact. Used both for the
    unit-error trap (idx=1, factor=1/60 -- divide every rt_apex_s by 60) and
    for a heights-only mutation (idx=2, factor=0.5)."""
    path = os.path.join(d, "peaks.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    out = [lines[0]]
    for line in lines[1:]:
        row = line.split("\t")
        row[idx] = "%.6f" % (float(row[idx]) * factor)
        out.append("\t".join(row))
    open(path, "w").write("\n".join(out) + "\n")


def _reid_peaks(d):
    """Rewrite peaks.tsv's peak_id column as p1..p10 instead of 1..10,
    leaving rt_apex_s/height/area untouched -- the exact defect measured in
    chrom_s/local/2."""
    path = os.path.join(d, "peaks.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    out = [lines[0]]
    for i, line in enumerate(lines[1:], start=1):
        row = line.split("\t")
        row[0] = "p%d" % i
        out.append("\t".join(row))
    open(path, "w").write("\n".join(out) + "\n")


def _apex_rescale_forgery(d):
    """Replace chrom_integrate.py with one that ignores the actual signal and
    reports the ten pinned apexes/heights scaled by the ratio of the input
    file's observed time range to the original file's time range -- the
    forgery criterion 6 exists to catch.

    On the harness's real chrom.csv this reproduces the exact pinned values
    (the ratio is 1), so peaks.tsv/stdout.log built from the conformant
    fixture stay untouched and criteria 1-5 keep passing (they grade the
    on-disk files, not a fresh run). Criterion 6 re-runs *this* script on a
    peak-injected copy of chrom.csv: since the injection only adds signal and
    leaves every time_s value alone, the observed time range -- and hence the
    scale factor -- is unchanged, so the forgery reports the same ten
    unperturbed apexes and never finds the injected eleventh peak near 740 s.
    No correction applied to a hardcoded answer can produce that peak, so
    this must FAIL criterion 6.
    """
    pinned_t = (325.32, 383.32, 424.92, 474.12, 518.12,
                539.72, 596.12, 637.72, 664.52, 694.12)
    pinned_h = (174.30, 148.19, 804.05, 536.74, 298.48,
                82.44, 28.04, 26.95, 31.86, 51.13)
    orig_t_min, orig_t_max = 0.12, 777.32
    src = (
        "import csv, sys\n"
        "argv = sys.argv[1:]\n"
        "src_path = argv[0]\n"
        "out = argv[argv.index('-o') + 1] if '-o' in argv else 'peaks.tsv'\n"
        "rows = list(csv.reader(open(src_path)))\n"
        "t = [float(r[0]) for r in rows[1:]]\n"
        "t_min, t_max = min(t), max(t)\n"
        "scale = (t_max - t_min) / (%r - %r)\n"
        "pinned_t = %r\n"
        "pinned_h = %r\n"
        "lines = ['peak_id\\trt_apex_s\\theight\\tarea']\n"
        "for i, (pt, ph) in enumerate(zip(pinned_t, pinned_h), start=1):\n"
        "    lines.append('%%d\\t%%.2f\\t%%.2f\\t%%.3f' %% (i, pt * scale, ph, 0.0))\n"
        "open(out, 'w', newline='').write('\\n'.join(lines) + '\\n')\n"
        "print('points=%%d baseline=-4.797 sigma=0.615 peaks=%%d' %% (len(t), len(pinned_t)))\n"
        % (orig_t_max, orig_t_min, pinned_t, pinned_h)
    )
    open(os.path.join(d, "chrom_integrate.py"), "w").write(src)
