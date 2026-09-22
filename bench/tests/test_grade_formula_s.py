import shutil, tempfile

import fixtures
from grader_rig import GraderCase, replace, run_grader


class FormulaShortGraderTest(GraderCase):
    grader = "grade_formula_s.py"
    grader_args = ["ranked.tsv", "stdout.log"]
    tool = "formula_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "ranked.tsv", "id\trank\tformula", "cid\trnk\tform"),
             "ranked.tsv: header + 4 blocks in input order, ranks starting at 1"),
            (lambda d: _set_rank1_formula(d, "CAFFEINE", "C4H13N5O2P"),
             "rank-1 formula correct in all four blocks"),
            (lambda d: _set_rank1_field(d, "CAFFEINE", 4, "9.9"),
             "every rank-1 row has |error_ppm| <= 2.0 and score <= 0.5"),
            (lambda d: _squeeze_runner_up(d, "CAFFEINE"),
             "every rank-1 row beats its block runner-up by >= 5 score units"),
            (lambda d: _set_rank1_field(d, "AMPA", 3, "200.000000"),
             "rank-1 calc_mass matches the reference recomputed from the input (<=1e-5 Da)"),
            (lambda d: replace(d, "stdout.log", "candidates=", "ncand="),
             "stdout reports blocks and candidates"),
            (lambda d: replace(d, "stdout.log", "candidates=35", "candidates=6495441"),
             "stdout reports blocks and candidates"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)

    def test_wrong_candidates_value_fails_only_criterion_6(self):
        """Rule 9: criterion 6 must be independently discriminating. This is
        the actual defect that shipped -- a submission that enumerated the
        whole formula space (never applying the mandated 5 ppm window)
        still sorted correctly, so rank-1 stayed right in every block, and
        printed candidates=6495441 against a reference of 35. Corrupting
        ONLY the candidates figure in stdout.log (ranked.tsv, and the
        blocks figure, untouched) must fail criterion 6 alone: the criteria
        owning rank-1 formula, |error_ppm|/score bounds, the runner-up
        margin, and calc_mass read ranked.tsv, never stdout, so none of them
        can see this mutation."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        replace(d, "stdout.log", "candidates=35", "candidates=6495441")
        args = [a.replace("{d}", d) for a in self.grader_args]
        rc, verdicts, out = run_grader(self.grader, args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(verdicts["stdout reports blocks and candidates"], out)
        for crit in ("ranked.tsv: header + 4 blocks in input order, "
                     "ranks starting at 1",
                     "rank-1 formula correct in all four blocks",
                     "every rank-1 row has |error_ppm| <= 2.0 and score <= 0.5",
                     "every rank-1 row beats its block runner-up by >= 5 "
                     "score units",
                     "rank-1 calc_mass matches the reference recomputed "
                     "from the input (<=1e-5 Da)"):
            self.assertTrue(verdicts[crit], out)

    def test_boundary_tolerant_candidates_value_still_passes(self):
        """The chosen tolerance (CANDIDATES_TOL=4 in grade_formula_s.py)
        must leave room for a conforming-but-boundary-different
        implementation: one that legitimately disagrees with the reference
        by up to one candidate per block (four blocks) at the +/-5 ppm
        window edge. A stdout total 4 candidates off from the reference (35
        -> 39) must still PASS criterion 6; this is the complement of the
        mutation above, which is off by 6,495,406 -- proving the tolerance
        rejects an unfiltered enumeration while admitting a boundary tie."""
        d = tempfile.mkdtemp(prefix="conf_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        replace(d, "stdout.log", "candidates=35", "candidates=39")
        args = [a.replace("{d}", d) for a in self.grader_args]
        rc, verdicts, out = run_grader(self.grader, args, cwd=d)
        self.assertTrue(verdicts["stdout reports blocks and candidates"], out)

    def test_swapped_error_ppm_score_columns_fail_only_criterion_1(self):
        """Rule 10: a format deviation criterion 1 is supposed to own must
        not cascade into the value criteria. Swap the error_ppm and score
        COLUMNS, header included, in every row -- header_col_map() must
        still recover every field under its own (now-reordered) name, so
        this fails ONLY criterion 1, with criteria 2-5 all PASS."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _swap_cols_all_rows(d, 4, 5)
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(
            verdicts["ranked.tsv: header + 4 blocks in input order, "
                     "ranks starting at 1"], out)
        for crit in ("rank-1 formula correct in all four blocks",
                     "every rank-1 row has |error_ppm| <= 2.0 and score <= 0.5",
                     "every rank-1 row beats its block runner-up by >= 5 score units",
                     "rank-1 calc_mass matches the reference recomputed "
                     "from the input (<=1e-5 Da)",
                     "stdout reports blocks and candidates"):
            self.assertTrue(verdicts[crit], out)

    def test_truncated_rows_fail_only_criterion_1(self):
        """Rule 1: the prompt (PROMPT.md:16-19) mandates one row per
        candidate for every block, and defines stdout `candidates` as that
        total row count. Truncating ranked.tsv to keep only rank 1 and rank
        2 of each block (8 rows total, down from 35) while leaving
        stdout.log's `candidates=35` untouched used to score 6/6: every
        other check (header, block set/order, contiguous per-block ranks,
        every rank-1/runner-up value, and the stdout line itself) still
        passed, because nothing compared the file's own row count to
        anything. This must fail criterion 1 alone."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _truncate_to_top_n_per_block(d, 2)
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(
            verdicts["ranked.tsv: header + 4 blocks in input order, "
                     "ranks starting at 1"], out)
        for crit in ("rank-1 formula correct in all four blocks",
                     "every rank-1 row has |error_ppm| <= 2.0 and score <= 0.5",
                     "every rank-1 row beats its block runner-up by >= 5 score units",
                     "rank-1 calc_mass matches the reference recomputed "
                     "from the input (<=1e-5 Da)",
                     "stdout reports blocks and candidates"):
            self.assertTrue(verdicts[crit], out)

    def test_dropped_score_column_fails_only_criteria_that_need_it(self):
        """Rule 10 gap 2: header_col_map() used to require the header to be
        a COMPLETE permutation of the six mandated names, so dropping even
        one column (score, used by criteria 3 and 4) blanked every field
        and cascaded into criteria 2 and 5 (formula, calc_mass), which have
        nothing to do with score. Dropping score must fail criterion 1 and
        criteria 3/4 -- and nothing else."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _drop_col_all_rows(d, "score")
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(
            verdicts["ranked.tsv: header + 4 blocks in input order, "
                     "ranks starting at 1"], out)
        self.assertFalse(
            verdicts["every rank-1 row has |error_ppm| <= 2.0 and "
                     "score <= 0.5"], out)
        self.assertFalse(
            verdicts["every rank-1 row beats its block runner-up by "
                     ">= 5 score units"], out)
        for crit in ("rank-1 formula correct in all four blocks",
                     "rank-1 calc_mass matches the reference recomputed "
                     "from the input (<=1e-5 Da)",
                     "stdout reports blocks and candidates"):
            self.assertTrue(verdicts[crit], out)


def _truncate_to_top_n_per_block(d, n):
    """Keep only the first `n` rows (by rank) of every block, in the same
    input order, discarding the rest -- a ranked.tsv that reports far fewer
    candidates than it claims to have enumerated, while every row it DOES
    keep (rank 1, runner-up, ...) stays byte-for-byte correct."""
    path, header, rows = _read_rows(d)
    from collections import OrderedDict
    blocks = OrderedDict()
    for r in rows:
        blocks.setdefault(r[0], []).append(r)
    new_rows = []
    for rs in blocks.values():
        new_rows.extend(rs[:n])
    _write_rows(path, header, new_rows)


def _drop_col_all_rows(d, name):
    """Rewrite ranked.tsv without the named column entirely, header and
    every data row."""
    path, header, rows = _read_rows(d)
    hdr = header.split("\t")
    idx = hdr.index(name)
    new_hdr = hdr[:idx] + hdr[idx + 1:]
    for r in rows:
        del r[idx]
    _write_rows(path, "\t".join(new_hdr), rows)


def _swap_cols_all_rows(d, i, j):
    """Swap columns `i` and `j` of ranked.tsv, header AND every data row, so
    each value stays labelled with its own (now-reordered) name."""
    path, header, rows = _read_rows(d)
    hdr = header.split("\t")
    hdr[i], hdr[j] = hdr[j], hdr[i]
    for r in rows:
        r[i], r[j] = r[j], r[i]
    _write_rows(path, "\t".join(hdr), rows)


def _read_rows(d):
    import os
    path = os.path.join(d, "ranked.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    return path, lines[0], [l.split("\t") for l in lines[1:]]


def _write_rows(path, header, rows):
    open(path, "w").write("\n".join([header] + ["\t".join(r) for r in rows]) + "\n")


def _rank1_index(rows, cid):
    for i, r in enumerate(rows):
        if r[0] == cid and r[1] == "1":
            return i
    raise AssertionError("no rank-1 row for %r" % cid)


def _set_rank1_formula(d, cid, formula):
    path, header, rows = _read_rows(d)
    i = _rank1_index(rows, cid)
    rows[i][2] = formula
    _write_rows(path, header, rows)


def _set_rank1_field(d, cid, col, value):
    """Overwrite one column of the block's rank-1 row, leaving every other
    row (including that block's runner-up, used by criterion 4) untouched."""
    path, header, rows = _read_rows(d)
    i = _rank1_index(rows, cid)
    rows[i][col] = value
    _write_rows(path, header, rows)


def _squeeze_runner_up(d, cid):
    """Replace every non-rank-1 row of block `cid` with a single fake
    runner-up whose score is only 0.2 above the rank-1 score -- a margin
    that fails the >=5 threshold. Block membership, header, and every other
    block are left untouched, so this must break criterion 4 only: not
    criterion 1 (ranks in the shrunk block still run 1, 2, contiguous and in
    the same input-order position), not 2/3/5 (the rank-1 row itself is
    never touched)."""
    path, header, rows = _read_rows(d)
    i = _rank1_index(rows, cid)
    j = i + 1
    while j < len(rows) and rows[j][0] == cid:
        j += 1
    rank1_score = float(rows[i][5])
    fake = [cid, "2", "FAKE1", rows[i][3], rows[i][4], "%.4f" % (rank1_score + 0.2)]
    rows[i + 1:j] = [fake]
    _write_rows(path, header, rows)
