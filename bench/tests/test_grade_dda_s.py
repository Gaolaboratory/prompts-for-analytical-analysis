import os
import shutil
import tempfile
import unittest

from grader_rig import GraderCase, replace, run_grader

CRIT1 = ("psms.tsv: header + rows, columns in order, decoy encoded 0/1, "
         "protein is the bare record id (no whitespace), every qvalue in [0,1]")
CRIT2 = ("stdout reports spectra=1200, with_candidate=1025 and the reference "
         "target/decoy peptide counts")
CRIT3 = "target PSMs at q<=0.01 between 16 and 20 (reference 18)"
CRIT4 = "decoy fraction among best hits within 0.05 of 0.333"
CRIT5 = "the unfiltered rerun reports fewer 1% FDR PSMs than the filtered run"
CRIT6 = "at least 5 of the reference's 7 named UPS1 proteins have >= 2 best-hit spectra"

ALL_CRITERIA = [CRIT1, CRIT2, CRIT3, CRIT4, CRIT5, CRIT6]

# Two of the reference's 7 named UPS1 proteins (data/database_search/README.md)
# are left untouched by _rename_five_named_ups below; these five are renamed.
RENAME_MAP = {
    "CRP_HUMAN_UPS": "FAKE1_HUMAN_UPS",
    "SYHC_HUMAN_UPS": "FAKE2_HUMAN_UPS",
    "MYG_HUMAN_UPS": "FAKE3_HUMAN_UPS",
    "GSTA1_HUMAN_UPS": "FAKE4_HUMAN_UPS",
    "ANT3_HUMAN_UPS": "FAKE5_HUMAN_UPS",
}


class DdaShortGraderTest(GraderCase):
    grader = "grade_dda_s.py"
    grader_args = ["psms.tsv", "stdout.log"]
    tool = "dda_s"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "psms.tsv", "scan\tpeptide", "id\tpeptide"),
             CRIT1),
            (lambda d: replace(d, "stdout.log", "spectra=1200", "spectra=900"),
             CRIT2),
            (lambda d: replace(d, "stdout.log", "psms_1pct=18", "psms_1pct=3"),
             CRIT3),
            # decoy_hits=341 / best_hits=1025 = 0.333; moving decoy_hits to
            # 546 shifts the fraction to ~0.533, 0.2 away from 0.333 and
            # outside the 0.05 tolerance.
            (lambda d: replace(d, "stdout.log", "decoy_hits=341", "decoy_hits=546"),
             CRIT4),
            (lambda d: replace(d, "stdout.log", "psms_1pct_unfiltered=0",
                               "psms_1pct_unfiltered=26"),
             CRIT5),
            (lambda d: _drop_ups_rows_but_one(d), CRIT6),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)

    def test_mutations_are_disjoint(self):
        """Rule 9: mutate one field at a time and confirm ONLY the criterion
        naming that field fails -- the mutation rig (check_mutation) tolerates
        collateral failure by design, so this is checked separately here."""
        M = [
            (lambda d: replace(d, "psms.tsv", "scan\tpeptide", "id\tpeptide"),
             CRIT1),
            (lambda d: replace(d, "stdout.log", "spectra=1200", "spectra=900"),
             CRIT2),
            (lambda d: replace(d, "stdout.log", "psms_1pct=18", "psms_1pct=3"),
             CRIT3),
            (lambda d: replace(d, "stdout.log", "decoy_hits=341", "decoy_hits=546"),
             CRIT4),
            (lambda d: replace(d, "stdout.log", "psms_1pct_unfiltered=0",
                               "psms_1pct_unfiltered=26"),
             CRIT5),
            (lambda d: _drop_ups_rows_but_one(d), CRIT6),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                _, verdicts, out = self._mutated(mutate)
                for name, ok in verdicts.items():
                    if name == crit:
                        self.assertFalse(ok, out)
                    else:
                        self.assertTrue(ok, "%s: %s\n%s" % (crit, name, out))

    def test_swapped_protein_decoy_columns_fail_only_criterion_1(self):
        """Rule 10: a format deviation criterion 1 is supposed to own must
        not cascade into the value criteria. Swap the protein and decoy
        COLUMNS, header included, in every row -- name_index() must still
        find both columns under their own (now-reordered) names, so this
        fails ONLY criterion 1, with criteria 2-6 all PASS (criteria 2-5
        read stdout.log only and were never at risk; criterion 6 is the one
        this fix protects, since it reads psms.tsv positionally by name)."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        import fixtures
        fixtures.build_artifacts(self.tool, d)
        _swap_protein_decoy_columns(d)
        rc, verdicts, out = run_grader(self.grader, list(self.grader_args), d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(verdicts[CRIT1], out)
        for crit in (CRIT2, CRIT3, CRIT4, CRIT5, CRIT6):
            self.assertTrue(verdicts[crit], out)

    def test_full_header_protein_costs_only_criterion_1(self):
        """Whole-branch review, rule 10 (protein, the third identifier
        column this grader has): rewrite every target row's `protein` field
        as the FULL FASTA header (e.g. "P02741ups|CRP_HUMAN_UPS C-reactive
        protein (Chain 19-224) - Homo sapiens (Human)") instead of the bare
        record id -- a pure format deviation the prompt's Output section
        already forbids ("not the full header line with its trailing
        description"). Before the fix this passed criterion 1 (nothing
        checked protein's format) and FAILED criterion 6 (`protein.
        endswith(name)` no longer matches a string that now ends with a
        description), reporting 0 of 7 named proteins though every
        underlying value was correct. Must now fail ONLY criterion 1;
        criterion 6 must still PASS, because its match now looks only at
        protein's first whitespace token."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        import fixtures
        fixtures.build_artifacts(self.tool, d)
        changed = _use_full_fasta_headers_for_protein(d)
        self.assertGreater(changed, 0, "mutation touched no rows")
        rc, verdicts, out = run_grader(self.grader, list(self.grader_args), d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(verdicts[CRIT1], out)
        for crit in (CRIT2, CRIT3, CRIT4, CRIT5, CRIT6):
            self.assertTrue(verdicts[crit], out)

    def test_dropped_scan_column_fails_only_criterion_1(self):
        """Rule 10 gap 3: `well_formed` gated criterion 6 on a hardcoded
        `len(r) == 6`, so dropping the unrelated `scan` column (which
        criterion 6's name_index-based protein/decoy lookup never reads)
        shrank every row to 5 fields and spuriously failed criterion 6 too.
        Must fail ONLY criterion 1."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        import fixtures
        fixtures.build_artifacts(self.tool, d)
        _drop_scan_column(d)
        rc, verdicts, out = run_grader(self.grader, list(self.grader_args), d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(verdicts[CRIT1], out)
        for crit in (CRIT2, CRIT3, CRIT4, CRIT5, CRIT6):
            self.assertTrue(verdicts[crit], out)

    def test_named_check_rejects_renamed_named_proteins(self):
        """Fix round 1: criterion 6 changed from "some target protein whose
        accession ends _UPS" (the FASTA carries 50 of those) to "the
        reference's 7 NAMED proteins" (data/database_search/README.md).
        Renaming 5 of the 7 named proteins to other _UPS-suffixed accessions
        keeps the *count* of UPS-suffixed proteins with >= 2 spectra at 7 (2
        untouched real names + 5 renamed fakes, every one still >= 2 spectra)
        -- which the old bare-suffix-count reading of this criterion PASSED
        -- but leaves only 2 of the reference's actual named proteins, which
        the fixed, name-based check must now reject."""
        d = tempfile.mkdtemp(prefix="rename_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        import fixtures
        fixtures.build_artifacts(self.tool, d)
        _rename_named_ups_proteins(d, RENAME_MAP)
        # The renamed accessions still end `_UPS`, so a bare-suffix-count
        # reading would find 7 qualifying proteins here -- confirm the
        # mutation actually produced that shape (7 distinct _UPS-suffixed
        # proteins with >= 2 spectra each) before checking the grader
        # rejects it, so this is a test of the fixed logic, not a mutation
        # that merely broke parsing outright.
        _, _, rows = _rows(d)
        by_suffix = {}
        for r in rows:
            if r[3] == "0" and r[2].endswith("_UPS"):
                by_suffix[r[2]] = by_suffix.get(r[2], 0) + 1
        qualifying = sum(1 for c in by_suffix.values() if c >= 2)
        self.assertGreaterEqual(qualifying, 7, by_suffix)
        rc, verdicts, out = run_grader(self.grader, list(self.grader_args), d)
        self.assertIn(CRIT6, verdicts, out)
        self.assertFalse(verdicts[CRIT6], out)
        self.assertNotEqual(rc, 0, out)

    def test_decoy_boolean_spelling_costs_only_criterion_1(self):
        """Task 19 (rule 10, gap 4): reproduces bench/runs/dda_s/solo/local/1,
        where a submission wrote `decoy` as `True`/`False` instead of the
        mandated `1`/`0`. Before the fix, `named_ups_proteins_ge2` did
        `int(r[decoy_idx])`, `int("False")` raised, and the bare `except
        ValueError: continue` silently dropped every row, scoring 0 of the
        reference's 7 named proteins though the true count was 7 of 7. This
        must now fail ONLY criterion 1 (the mandated-encoding owner);
        criterion 6 must still PASS, because parse_decoy recognises the
        boolean spelling and recovers the true (correct) protein count."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        import fixtures
        fixtures.build_artifacts(self.tool, d)
        _boolean_spell_decoy(d)
        rc, verdicts, out = run_grader(self.grader, list(self.grader_args), d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(verdicts[CRIT1], out)
        for crit in (CRIT2, CRIT3, CRIT4, CRIT5, CRIT6):
            self.assertTrue(verdicts[crit], out)

    def test_decoy_wrong_value_costs_only_criterion_6(self):
        """Rule 10's counterpart to the probe above: `decoy` stays in the
        mandated `0`/`1` encoding (so criterion 1, which owns format only,
        must not care), but 3 of the fixture's UPS1 proteins that sit
        exactly at the >=2-spectra threshold (GSTA1/GELS/CYB5, each with
        exactly 2 real target spectra) have one spectrum each mislabelled
        decoy=1, dropping each to 1 -- below threshold. That leaves 4 of 7
        (CRP, MYG, ANT3, SYHC untouched) -- under the 5-of-7 band. A
        genuinely wrong (not just oddly spelled) value must fail ONLY
        criterion 6, the criterion that actually depends on it."""
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        import fixtures
        fixtures.build_artifacts(self.tool, d)
        _mislabel_one_spectrum_per_protein(
            d, ["GSTA1_HUMAN_UPS", "GELS_HUMAN_UPS", "CYB5_HUMAN_UPS"])
        rc, verdicts, out = run_grader(self.grader, list(self.grader_args), d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(verdicts[CRIT6], out)
        for crit in (CRIT1, CRIT2, CRIT3, CRIT4, CRIT5):
            self.assertTrue(verdicts[crit], out)

    def _mutated(self, mutate):
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        import fixtures
        fixtures.build_artifacts(self.tool, d)
        mutate(d)
        return run_grader(self.grader, list(self.grader_args), d)


class DdaShortCrashGuardTest(unittest.TestCase):
    """Fix round 1, Critical: `decoy_fraction = decoy_hits / best_hits if
    best_hits else None` guarded only best_hits. A conformant stdout.log
    missing just decoy_hits= (or carrying only best_hits=) raised
    `TypeError: unsupported operand type(s) for /: 'NoneType' and 'float'`
    before finish() ran, losing all six criteria -- the exact failure mode
    rule 2 exists to prevent. The original rule-2 check only exercised full
    deletion of both outputs, where both operands become None symmetrically;
    these three cases include the asymmetric one that actually crashed."""

    def _grade(self, mutate_stdout=None, delete_all=False):
        d = tempfile.mkdtemp(prefix="crash_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        import fixtures
        fixtures.build_artifacts("dda_s", d)
        if delete_all:
            os.remove(os.path.join(d, "psms.tsv"))
            os.remove(os.path.join(d, "stdout.log"))
        elif mutate_stdout is not None:
            # NB: read the original content into a variable BEFORE opening
            # for write -- `open(p, "w").write(f(open(p).read()))` evaluates
            # the "w"-mode open() (which truncates) before the argument
            # expression, so it would silently pass f("") instead of the
            # real content.
            path = os.path.join(d, "stdout.log")
            original = open(path).read()
            open(path, "w").write(mutate_stdout(original))
        return run_grader("grade_dda_s.py", ["psms.tsv", "stdout.log"], d)

    def _assert_no_crash(self, rc, verdicts, out):
        self.assertNotEqual(rc, 0, out)
        self.assertEqual(len(verdicts), len(ALL_CRITERIA), out)
        for crit in ALL_CRITERIA:
            self.assertIn(crit, verdicts, out)
        self.assertIn("passed", out, out)          # finish()'s "k/n passed" line
        self.assertNotIn("Traceback", out, out)

    def test_both_outputs_deleted(self):
        rc, verdicts, out = self._grade(delete_all=True)
        self._assert_no_crash(rc, verdicts, out)
        self.assertTrue(all(v is False for v in verdicts.values()), out)

    def test_decoy_hits_field_stripped(self):
        rc, verdicts, out = self._grade(
            mutate_stdout=lambda t: t.replace(" decoy_hits=341", ""))
        self._assert_no_crash(rc, verdicts, out)
        self.assertFalse(verdicts[CRIT4], out)

    def test_stdout_carries_only_best_hits(self):
        rc, verdicts, out = self._grade(mutate_stdout=lambda t: "best_hits=1025\n")
        self._assert_no_crash(rc, verdicts, out)
        self.assertFalse(verdicts[CRIT2], out)
        self.assertFalse(verdicts[CRIT3], out)
        self.assertFalse(verdicts[CRIT4], out)
        self.assertFalse(verdicts[CRIT5], out)


def _rows(d):
    path = os.path.join(d, "psms.tsv")
    lines = open(path).read().rstrip("\n").split("\n")
    return path, lines[0], [l.split("\t") for l in lines[1:]]


def _write(path, hdr, rows):
    open(path, "w").write("\n".join([hdr] + ["\t".join(r) for r in rows]) + "\n")


def _drop_ups_rows_but_one(d):
    """Keep only the first UPS1-protein (target, ending `_UPS`) row and drop
    every other row belonging to a UPS1 protein. This leaves at most one
    protein with exactly 1 best-hit spectrum -- 0 of the reference's 7 named
    proteins clear the >= 2 threshold, well under the 5-of-7 band -- while
    every non-UPS row (which is what stdout's counts are checked against) is
    untouched."""
    path, hdr, rows = _rows(d)
    kept, kept_one = [], False
    for r in rows:
        is_ups = len(r) == 6 and r[3] == "0" and r[2].endswith("_UPS")
        if is_ups:
            if not kept_one:
                kept.append(r)
                kept_one = True
        else:
            kept.append(r)
    assert kept_one, "fixture has no UPS1-protein row to keep"
    _write(path, hdr, kept)


def _use_full_fasta_headers_for_protein(d):
    """Rewrite every row's `protein` field from the bare record id to the
    FULL FASTA header line it was taken from (id + its trailing
    description), for whichever rows' protein value is a target accession
    literally present in the real FASTA -- decoy rows (`DECOY_`-prefixed)
    have no such header and are left untouched. Returns the number of rows
    changed. Reproduces the exact reviewer finding: this is a pure format
    deviation (the prompt's Output section already says protein is the bare
    id, "not the full header line with its trailing description"), so
    nothing about the underlying search result is wrong."""
    here = os.path.dirname(os.path.abspath(__file__))          # bench/tests
    fasta_path = os.path.join(os.path.dirname(os.path.dirname(here)),
                               "data", "database_search",
                               "yeast_pe1_plus_ups.fasta")
    headers = {}
    for line in open(fasta_path):
        if line.startswith(">"):
            h = line[1:].rstrip("\n")
            headers[h.split()[0]] = h
    path, hdr, rows = _rows(d)
    changed = 0
    for r in rows:
        full = headers.get(r[2])
        if full is not None:
            r[2] = full
            changed += 1
    _write(path, hdr, rows)
    return changed


def _swap_protein_decoy_columns(d):
    """Swap the protein and decoy COLUMNS of psms.tsv, header AND every
    data row, so each value stays labelled with its own (now-reordered)
    name -- HEADER's positions are ["scan","peptide","protein","decoy",
    "score","qvalue"], so protein/decoy are indices 2 and 3."""
    path, hdr, rows = _rows(d)
    cols = hdr.split("\t")
    cols[2], cols[3] = cols[3], cols[2]
    for r in rows:
        r[2], r[3] = r[3], r[2]
    _write(path, "\t".join(cols), rows)


def _drop_scan_column(d):
    """Drop the `scan` column of psms.tsv entirely, header and every data
    row -- criterion 6 never reads it (name_index only looks up
    protein/decoy), so this is a pure shape defect that must fail
    criterion 1 alone."""
    path, hdr, rows = _rows(d)
    cols = hdr.split("\t")
    idx = cols.index("scan")
    del cols[idx]
    for r in rows:
        del r[idx]
    _write(path, "\t".join(cols), rows)


def _boolean_spell_decoy(d):
    """Rewrite every row's `decoy` field from the mandated `0`/`1` to a
    boolean spelling (`0`->"False", `1`->"True"), header untouched -- the
    exact defect in bench/runs/dda_s/solo/local/1."""
    path, hdr, rows = _rows(d)
    for r in rows:
        r[3] = "True" if r[3] == "1" else "False"
    _write(path, hdr, rows)


def _mislabel_one_spectrum_per_protein(d, protein_names):
    """For each name in protein_names, flip exactly one of its target
    (decoy=0) rows to decoy=1 -- still the mandated `0`/`1` encoding, just
    the wrong value for that row. Used to probe that a genuinely wrong
    (not merely oddly-spelled) decoy value fails only the criterion that
    depends on its truth (criterion 6), not the one that owns its format
    (criterion 1)."""
    path, hdr, rows = _rows(d)
    remaining = set(protein_names)
    for r in rows:
        if not remaining:
            break
        if r[3] == "0" and any(r[2].endswith(n) for n in remaining):
            for n in list(remaining):
                if r[2].endswith(n):
                    r[3] = "1"
                    remaining.discard(n)
                    break
    assert not remaining, "fixture is missing rows for: %s" % remaining
    _write(path, hdr, rows)


def _rename_named_ups_proteins(d, old_to_new):
    """Rewrite the `protein` field of every row whose accession ends with one
    of old_to_new's keys, replacing that suffix with the mapped value. Used to
    confirm criterion 6 checks the reference's named proteins, not merely
    "some _UPS-suffixed protein"."""
    path, hdr, rows = _rows(d)
    renamed_any = {k: False for k in old_to_new}
    for r in rows:
        protein = r[2]
        for old, new in old_to_new.items():
            if protein.endswith(old):
                r[2] = protein[:-len(old)] + new
                renamed_any[old] = True
                break
    assert all(renamed_any.values()), (
        "fixture is missing rows for: %s"
        % [k for k, v in renamed_any.items() if not v])
    _write(path, hdr, rows)
