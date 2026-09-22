import os, shutil, tempfile

import fixtures
from grader_rig import GraderCase, replace, run_grader


class SpectralShortGraderTest(GraderCase):
    grader = "grade_spectral_s.py"
    grader_args = ["results.tsv", "stdout.log"]
    tool = "spectral_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "results.tsv", "query\tbest_match", "id\tmatch"),
             "results.tsv: header + 4 rows in q1..q4 order, columns in order"),
            (lambda d: replace(d, "results.tsv", "q4\tNO_MATCH", "q4\tacetaminophen"),
             "best_match: caffeine, sulfamethoxazole, nicotine, NO_MATCH"),
            (lambda d: replace(d, "results.tsv", "q1\tcaffeine\t0.7473",
                                "q1\tcaffeine\t0.9000"),
             "scores 0.7473 / 0.6669 / 0.8706 / 0.0138 (+/- 0.0001)"),
            (lambda d: replace(d, "results.tsv", "q2\tsulfamethoxazole\t0.6669\t4",
                                "q2\tsulfamethoxazole\t0.6669\t5"),
             "matched_peaks 6/4/6/2 and total_library_peaks 7/6/8/6"),
            (lambda d: replace(d, "stdout.log", "called: 3", "called: 4"),
             "stdout: queries: 4  called: 3  no_match: 1"),
            (lambda d: _freeze_tool(d),
             "re-running libsearch.py on a library with one entry removed "
             "reproduces the reference result for that library"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)

    def test_swapped_score_matched_peaks_columns_fail_only_criterion_1(self):
        """Rule 10: a format deviation criterion 1 is supposed to own must
        not cascade into the value criteria. Swap the score and
        matched_peaks COLUMNS, header included, in every row --
        header_col_map() must still recover every field under its own
        (now-reordered) name, so this fails ONLY criterion 1 (both its
        "columns in order" clause and its "q1..q4 order" clause are
        untouched by the swap, but the swap alone already breaks "columns
        in order"), with criteria 2-6 all PASS."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _swap_cols_all_rows(d, 2, 3)
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(
            verdicts["results.tsv: header + 4 rows in q1..q4 order, "
                     "columns in order"], out)
        for crit in ("best_match: caffeine, sulfamethoxazole, nicotine, NO_MATCH",
                     "scores 0.7473 / 0.6669 / 0.8706 / 0.0138 (+/- 0.0001)",
                     "matched_peaks 6/4/6/2 and total_library_peaks 7/6/8/6",
                     "stdout: queries: 4  called: 3  no_match: 1",
                     "re-running libsearch.py on a library with one entry "
                     "removed reproduces the reference result for that "
                     "library"):
            self.assertTrue(verdicts[crit], out)

    def test_dropped_total_library_peaks_column_fails_only_criteria_that_need_it(self):
        """Rule 10 gap 2: header_col_map() used to require the header to be
        a COMPLETE permutation of the five mandated names, so dropping even
        one column (total_library_peaks, used only by criterion 4) blanked
        every field and cascaded into criteria 2 and 3 (best_match, score),
        which have nothing to do with it. Dropping it must fail criterion 1
        and criterion 4 -- and nothing else."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        _drop_col_all_rows(d, "total_library_peaks")
        rc, verdicts, out = run_grader(self.grader, self.grader_args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(
            verdicts["results.tsv: header + 4 rows in q1..q4 order, "
                     "columns in order"], out)
        self.assertFalse(
            verdicts["matched_peaks 6/4/6/2 and total_library_peaks 7/6/8/6"], out)
        for crit in ("best_match: caffeine, sulfamethoxazole, nicotine, NO_MATCH",
                     "scores 0.7473 / 0.6669 / 0.8706 / 0.0138 (+/- 0.0001)",
                     "stdout: queries: 4  called: 3  no_match: 1"):
            self.assertTrue(verdicts[crit], out)


def _drop_col_all_rows(d, name):
    """Rewrite results.tsv without the named column entirely, header and
    every data row."""
    path = os.path.join(d, "results.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    hdr = lines[0].split("\t")
    idx = hdr.index(name)
    out = ["\t".join(hdr[:idx] + hdr[idx + 1:])]
    for line in lines[1:]:
        row = line.split("\t")
        out.append("\t".join(row[:idx] + row[idx + 1:]))
    open(path, "w").write("\n".join(out) + "\n")


def _swap_cols_all_rows(d, i, j):
    """Swap columns `i` and `j` of results.tsv, header AND every data row,
    so each value stays labelled with its own (now-reordered) name."""
    path = os.path.join(d, "results.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    hdr = lines[0].split("\t")
    hdr[i], hdr[j] = hdr[j], hdr[i]
    out = ["\t".join(hdr)]
    for line in lines[1:]:
        row = line.split("\t")
        row[i], row[j] = row[j], row[i]
        out.append("\t".join(row))
    open(path, "w").write("\n".join(out) + "\n")


def _freeze_tool(d):
    """Replace libsearch.py with one that ignores its inputs and prints the
    four pinned rows verbatim -- the forgery criterion 6 exists to catch.
    Its results.tsv and stdout.log stay conformant, so only criterion 6 may
    fail."""
    rows = (
        ("q1", "caffeine", 0.7473, 6, 7),
        ("q2", "sulfamethoxazole", 0.6669, 4, 6),
        ("q3", "nicotine", 0.8706, 6, 8),
        ("q4", "NO_MATCH", 0.0138, 2, 6),
    )
    src = (
        "import argparse\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('queries'); p.add_argument('library')\n"
        "p.add_argument('-o', required=True)\n"
        "a = p.parse_args()\n"
        "rows = %r\n"
        "with open(a.o, 'w', newline='') as fh:\n"
        "    fh.write('query\\tbest_match\\tscore\\tmatched_peaks\\ttotal_library_peaks\\n')\n"
        "    for r in rows:\n"
        "        fh.write('%%s\\t%%s\\t%%.4f\\t%%d\\t%%d\\n' %% r)\n"
        "called = sum(1 for r in rows if r[1] != 'NO_MATCH')\n"
        "print('queries: %%d  called: %%d  no_match: %%d' %% "
        "(len(rows), called, len(rows) - called))\n"
        % (rows,)
    )
    open(os.path.join(d, "libsearch.py"), "w").write(src)
