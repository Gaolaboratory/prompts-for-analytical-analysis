import os, shutil, tempfile

import fixtures
from grader_rig import GraderCase, replace, run_grader

CRIT1 = "stats.tsv: header + 618 rows sorted by p_value, columns in order"
CRIT2 = ("stdout reports tested=618 filtered=0 significant=253, and the "
         "significant column matches the reference on every row")
CRIT3 = "t and p_value match the reference within 1e-6 relative on every row"
CRIT4 = "df within 1e-6 relative and log2fc within 1e-9 relative on every row"
CRIT5 = "q_value within 1e-6 relative, with the top-8 BH plateau reproduced"
CRIT6 = "top 10 features by p_value are the reference ten, in order"


class MassStatsShortGraderTest(GraderCase):
    grader = "grade_mass_stats_s.py"
    grader_args = ["stats.tsv", "stdout.log"]
    tool = "mass_stats_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "stats.tsv", "feature_id\tlog2fc", "id\tlog2fc"),
             CRIT1),
            (lambda d: replace(d, "stdout.log", "significant=253", "significant=100"),
             CRIT2),
            # Fix round 1: keep the count at 253 but move every significant=1
            # flag onto the wrong (highest-p) rows. Before the fix this scored
            # 6/6 -- criterion 2 only read stdout, never the tsv column.
            (lambda d: _invert_significant(d), CRIT2),
            (lambda d: _scale_column(d, 2, 1.01), CRIT3),
            (lambda d: _round_column_to_int(d, 3), CRIT4),
            (lambda d: _perturb_plateau_q(d), CRIT5),
            # Swapping the first two data rows breaks CRIT6 (the top-10 order
            # no longer matches the published list). On this real dataset the
            # first two rows do NOT share a p_value (9.80969e-07 vs
            # 1.18206e-06, data/mass_stats/README.md), so this swap also
            # inverts the file's own p_value column at that position and
            # collaterally fails CRIT1 -- permitted by grader_rig's mutation
            # contract (a mutation tripping a neighbouring criterion is
            # fine); no adjacent equal-p pair exists within the top 10 to
            # swap instead.
            (lambda d: _swap_rows(d, 0, 1), CRIT6),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)

    def test_swapped_t_df_columns_fail_only_criterion_1(self):
        """Rule 10: a format deviation criterion 1 is supposed to own must
        not cascade into the value criteria. This is the real defect from
        mass_stats_s/local/1 and /3 -- the t and df columns swapped, header
        included -- cut down to a mutation test: since the header still
        names each column correctly, by-name parsing must recover every
        value and fail ONLY criterion 1, with criteria 2-6 all still PASS."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _swap_t_df_columns(d)
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(verdicts[CRIT1], out)
        for crit in (CRIT2, CRIT3, CRIT4, CRIT5, CRIT6):
            self.assertTrue(verdicts[crit], out)

    def test_missing_t_column_fails_only_criteria_that_need_t(self):
        """Rule 10, other half: the real mass_stats_s/local/2 defect --
        `t` omitted from the header and every row entirely. Unlike the
        column-swap case, this one has a genuinely missing value, so it is
        correct for CRIT3 (which names t) to fail too -- but it must not
        drag down df/log2fc, q_value, significant or the top-10 order, which
        never depended on t being present."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _drop_t_column(d)
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(verdicts[CRIT1], out)
        self.assertFalse(verdicts[CRIT3], out)
        for crit in (CRIT2, CRIT4, CRIT5, CRIT6):
            self.assertTrue(verdicts[crit], out)


def _read_stats(d):
    path = os.path.join(d, "stats.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    return path, lines[0], [l.split("\t") for l in lines[1:]]


def _write_stats(path, header, rows):
    with open(path, "w") as fh:
        fh.write(header + "\n")
        for r in rows:
            fh.write("\t".join(r) + "\n")


def _scale_column(d, col, factor):
    path, header, rows = _read_stats(d)
    for r in rows:
        r[col] = repr(float(r[col]) * factor)
    _write_stats(path, header, rows)


def _round_column_to_int(d, col):
    path, header, rows = _read_stats(d)
    for r in rows:
        r[col] = str(int(round(float(r[col]))))
    _write_stats(path, header, rows)


def _perturb_plateau_q(d):
    """Change one of the top-8 BH-plateau rows' q_value (all tied at
    1.2607615866e-04, data/mass_stats/README.md) to a different value,
    breaking the tie for that row only."""
    path, header, rows = _read_stats(d)
    q = float(rows[3][5])
    rows[3][5] = repr(q * 1.5)
    _write_stats(path, header, rows)


def _invert_significant(d):
    """Move all `significant=1` flags onto the highest-p rows instead of the
    lowest, keeping the total count unchanged. Since rows are sorted
    ascending by p_value, that means flagging the LAST n_sig rows and
    clearing the rest -- same count, completely wrong rows."""
    path, header, rows = _read_stats(d)
    n_sig = sum(1 for r in rows if r[6] == "1")
    cutoff = len(rows) - n_sig
    for i, r in enumerate(rows):
        r[6] = "0" if i < cutoff else "1"
    _write_stats(path, header, rows)


def _swap_rows(d, i, j):
    path, header, rows = _read_stats(d)
    rows[i], rows[j] = rows[j], rows[i]
    _write_stats(path, header, rows)


def _swap_t_df_columns(d):
    """Swap the t and df COLUMNS, header included, so every row keeps its
    own value under the other's name -- the exact shape of the real
    mass_stats_s/local/1 and /3 defect (columns 2 and 3, 0-based, in
    EXPECTED_HEADER)."""
    path, header, rows = _read_stats(d)
    cols = header.split("\t")
    cols[2], cols[3] = cols[3], cols[2]
    header = "\t".join(cols)
    for r in rows:
        r[2], r[3] = r[3], r[2]
    _write_stats(path, header, rows)


def _drop_t_column(d):
    """Remove the t column entirely, header and every row -- the exact
    shape of the real mass_stats_s/local/2 defect."""
    path, header, rows = _read_stats(d)
    cols = header.split("\t")
    t_idx = cols.index("t")
    del cols[t_idx]
    header = "\t".join(cols)
    for r in rows:
        del r[t_idx]
    _write_stats(path, header, rows)
