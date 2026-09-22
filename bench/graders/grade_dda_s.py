#!/usr/bin/env python3
"""grade_dda_s.py <psms.tsv> <stdout.log> -- grader for
examples/database_search/PROMPT.md.

All six numbers below are literal constants transcribed from
data/database_search/README.md's "Expected results -- v2 rules" block
(computed by bench/reference/short/dda_ref.py, reviewed in Task 9). They are
NOT recomputed here: dda_ref.run() costs about 1 s per call on the full 1200-
spectrum MGF, and criteria 2-5 need nothing from the workspace's own input
files -- they are checked purely against the submission's own stdout.log
fields, the way grade_formula_s.py / grade_mass_stats_s.py / grade_pca_s.py
check their literal constants. Criteria 1 and 6 are the two that DO read the
submission's own output (psms.tsv): the qvalue range, and the UPS1-protein
best-hit count -- the two things a submission could not get right by only
copying numbers printed in the prompt's Method section.

Criterion 6 checks the reference's seven NAMED UPS1-standard proteins
individually (each must independently reach >= 2 best-hit spectra, and at
least 5 of the 7 must), not merely "some UPS-suffixed protein" -- an earlier
draft counted any target protein whose accession ended `_UPS`, but the FASTA
carries 50 such entries and the criterion text says "the reference's 7", so a
bare count reading admitted proteins the reference never found (fix round 1).

header_ok (exact column names, in order) and well_formed (every row has 6
tab-separated fields) are tracked separately so that renaming the header
fails ONLY criterion 1: criterion 6 parses rows positionally and does not
care about header text, and must keep working even when it is wrong (rule 9
-- each criterion should fail for its own, disjoint reason).

Missing, empty or malformed psms.tsv/stdout.log must not crash this grader:
every criterion below prints an explicit PASS or FAIL and finish() is always
reached. No require_files call is made -- psms.tsv and stdout.log are the
submission's own outputs (never require those, per the sweep's rule 2), and
the harness-seeded FASTA/MGF are not read by this grader at all.

Fix round 1 also closed a crash: `decoy_fraction = decoy_hits / best_hits if
best_hits else None` guarded only `best_hits`, so a conformant stdout.log
missing just `decoy_hits=` (or carrying only `best_hits=`) raised
`TypeError: unsupported operand type(s) for /: 'NoneType' and 'float'` before
finish() ran, losing all six criteria -- exactly the failure mode rule 2
exists to prevent, and the single most likely real failure this benchmark
grades (a submission whose stdout is missing a field). Both operands are now
checked for None before the division. No other arithmetic in this file
combines two independently-parsed num() results (criterion 5 only compares
psms_1pct/psms_1pct_unfiltered, already None-guarded on both sides before the
comparison runs), so this was the only instance of the asymmetry.

Task 19 (rule 10, gap 4): a submission that wrote `decoy` as `True`/`False`
instead of the mandated `1`/`0` scored 0/6 named UPS1 proteins in
`bench/runs/dda_s/solo/local/1`, because `named_ups_proteins_ge2` did
`int(r[decoy_idx])`, and `int("False")` raises -- every row's exception was
swallowed by the bare `except ValueError: continue`, so every row was
silently dropped and the count collapsed to 0, failing criterion 6 (a value
criterion) for what was actually a pure format deviation (criterion 1's job).
The real psms.tsv had all 7 of the reference's named proteins at >= 2
spectra. Two changes, kept independent per the rule-9 test below:

- Criterion 1 now also requires `decoy` to be exactly `"0"` or `"1"` in
  every row (`decoy_format_ok`) -- the encoding the prompt's Output section
  mandates (Task 19 also added that sentence; it was previously stated only
  in the Method, step 7). A boolean-spelled `decoy` column fails ONLY this
  criterion.
- Criterion 6's `named_ups_proteins_ge2` now parses `decoy` with
  `parse_decoy`, which recognises `1`/`0` AND `true`/`false` (any case) as
  booleans, so a boolean-spelled column still yields the CORRECT protein
  count instead of silently zeroing it. A row whose decoy value is neither
  (garbage, e.g. `"2"`) resolves to `None` and is skipped -- consistent with
  rule 10's "a mandated, graded value the tool did not actually produce"
  carve-out, under which failing both criteria together is legitimate,
  because that value genuinely is missing, not merely reformatted.

These two changes are independent in the rule-9 sense that matters: a
boolean-spelled `decoy` column costs ONLY criterion 1 (criterion 6 still
computes the true count via `parse_decoy`), and a semantically wrong
`decoy` value in the mandated `0`/`1` encoding (e.g. a UPS1 target
mislabelled as a decoy) costs ONLY criterion 6 (criterion 1 does not check
truth, only encoding). They fail together only when the value is neither a
mandated nor a recognisable encoding at all, which is the same "genuinely
absent" case rule 10 already treats as a legitimate double failure.

Whole-branch review, rule 10 (protein, the THIRD identifier column this
grader has): `protein` never had a format owner. Rewriting the fixture's
`protein` field as the full FASTA header (e.g. "P02741ups|CRP_HUMAN_UPS
C-reactive protein (Chain 19-224) - Homo sapiens (Human)" in place of the
bare "P02741ups|CRP_HUMAN_UPS") left criterion 1 passing -- nothing checked
protein's format -- while criterion 6's `protein.endswith(name)` stopped
matching every rewritten row, reporting 0 of 7 named proteins though every
value was correct. Two changes, the same shape as the decoy fix above:

- Criterion 1 now also requires `protein` to contain no whitespace
  (`protein_format_ok`) -- the prompt's Output section already says
  `protein` is "the header's first whitespace token ... not the full
  header line with its trailing description"; this was simply never
  checked. A full-header `protein` column fails ONLY this criterion.
- Criterion 6's `named_ups_proteins_ge2` now matches against only the
  first whitespace-delimited token of `protein` (falling back to the whole
  string when it has none), so a full-header `protein` column still yields
  the CORRECT count instead of silently zeroing it -- a whole-token
  suffix match against a fixed list of exact accession suffixes, not a
  substring search over free-text description, so a description that
  happens to mention another protein's name in prose cannot produce a
  false match.
"""
import os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grading import finish, num_field

HEADER = ["scan", "peptide", "protein", "decoy", "score", "qvalue"]

# data/database_search/README.md, "Expected results -- v2 rules".
REF_TARGETS = 87060
REF_DECOYS = 87188
# Reference: 18 (bench/reference/short/dda_ref.py, tie-grouped q-values --
# docs/design/2026-09-12-dda-fdr-tie-fix.md). Score is an integer
# matched-fragment count, so hundreds of best hits share one score; the
# prompt (step 8) now states that every PSM in a score group gets the FDR
# evaluated once at the end of that group. A conforming implementation
# reproduces 18 exactly or within a couple of PSMs of it (measured: dropping
# candidates via a 0.001 Da precursor-window perturbation left it unchanged
# at 18); band was previously (15, 40) around a reference of 26 -- wide
# because the pre-fix rule made the count depend on arbitrary tie order
# (measured range 18-26 across 8 reorderings of the same PSM set). Now that
# the count is deterministic, the band is narrow: it still passes a
# correct-but-differently-implemented pipeline while catching the kind of
# tie-order-dependent divergence tier (b) exposed (submissions reporting 38,
# 27, 36 and 11, 24, 18 on unperturbed/perturbed inputs against this same
# reference).
PSMS_1PCT_BAND = (16, 20)
REF_DECOY_FRACTION = 0.333
DECOY_FRACTION_TOL = 0.05
UPS_MIN_SPECTRA = 2
MIN_NAMED_UPS = 5                  # reference: 7
# The reference's 7 UPS1-standard proteins with >= 2 best-hit spectra.
# data/database_search/README.md's v2 block pins only the COUNT (7), not
# these names -- the names themselves come from a live `dda_ref.run()`
# against the real FASTA/MGF (matching this module's own docstring: "the
# harness-side reference"), grouping by protein and keeping every one with
# >= 2 non-decoy best-hit spectra: P02741ups|CRP_HUMAN_UPS (7),
# P02144ups|MYG_HUMAN_UPS (5), P01008ups|ANT3_HUMAN_UPS (5),
# P12081ups|SYHC_HUMAN_UPS (3), P00167ups|CYB5_HUMAN_UPS (2),
# P06396ups|GELS_HUMAN_UPS (2), P08263ups|GSTA1_HUMAN_UPS (2). Accessions
# carry a "ups|" infix, e.g. "P02741ups|CRP_HUMAN_UPS", so matching below is
# by suffix.
NAMED_UPS_PROTEINS = ["CRP_HUMAN_UPS", "SYHC_HUMAN_UPS", "CYB5_HUMAN_UPS",
                      "MYG_HUMAN_UPS", "GELS_HUMAN_UPS", "GSTA1_HUMAN_UPS",
                      "ANT3_HUMAN_UPS"]

psms_path, stdout_path = sys.argv[1], sys.argv[2]
results = []


def check(name, ok):
    results.append((name, bool(ok)))


def read_text(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def num(text, key):
    return num_field(text, key)


psms_text = read_text(psms_path)
out = read_text(stdout_path) or ""

lines = [l for l in (psms_text or "").split("\n") if l != ""]
hdr = lines[0].split("\t") if lines else []
rows = [l.split("\t") for l in lines[1:]]
header_ok = hdr == HEADER
well_formed = bool(rows) and all(len(r) == 6 for r in rows)
# Row width matched against the file's OWN header length, not a hardcoded
# 6 -- criterion 1 (via `well_formed` above) still requires exactly 6
# columns since it also requires `header_ok`, but criterion 6 only ever
# needs protein/decoy (found by name_index below) and must not fail just
# because an unrelated column (e.g. "scan") was dropped, shrinking every
# row to 5 fields (CONVENTIONS.md rule 10 gap 3).
rows_consistent = bool(rows) and all(len(r) == len(hdr) for r in rows)


def name_index(hdr, name):
    """Column index of `name` in `hdr`, or None if it is missing or appears
    more than once. Deliberately narrower than requiring the WHOLE header to
    match HEADER (criterion 1's "columns in order" job): criterion 6 below
    only ever needs protein/decoy, so renaming or moving an unrelated
    column (e.g. "scan") must not affect it, while a genuine protein/decoy
    swap is still found correctly under its own name wherever it sits
    (rule 9/10)."""
    idxs = [i for i, h in enumerate(hdr) if h == name]
    return idxs[0] if len(idxs) == 1 else None


protein_idx = name_index(hdr, "protein")
decoy_idx = name_index(hdr, "decoy")

qvalues_ok = False
if well_formed:
    try:
        qvalues_ok = all(0.0 <= float(r[5]) <= 1.0 for r in rows)
    except ValueError:
        qvalues_ok = False

# The prompt's Output section mandates `decoy` as literal `1`/`0` (Task 19).
# Checked positionally (r[3]), gated on well_formed/header_ok exactly like
# qvalues_ok above, so this is criterion 1's job alone -- criterion 6 below
# parses decoy tolerantly and does not depend on this passing.
decoy_format_ok = well_formed and all(r[3] in ("0", "1") for r in rows)

# The prompt's Output section mandates `protein` as "the FASTA record id ...
# (the header's first whitespace token) ... not the full header line with
# its trailing description" -- this is the THIRD identifier column this
# grader has, after peak_id (chrom_s) and decoy (dda_s itself), and the one
# CONVENTIONS.md flags as never having had its format graded at all: a
# submission that wrote the full FASTA header (e.g. "P02741ups|CRP_HUMAN_UPS
# C-reactive protein (Chain 19-224) - Homo sapiens (Human)") instead of the
# bare id passed criterion 1 -- nothing here checked protein's format -- and
# then reported 0 of the reference's 7 named UPS1 proteins in criterion 6,
# because `protein.endswith(name)` no longer matches a string that now ENDS
# with a description instead of the name. Every underlying value was
# correct; only the verdict was wrong, naming criterion 6's defect for what
# was actually criterion 1's job. Checked positionally (r[2]), gated on
# well_formed exactly like decoy_format_ok: a record id is a single
# whitespace-free token by the prompt's own definition, so any embedded
# whitespace means the field is not the bare id.
protein_format_ok = well_formed and all(
    r[2] != "" and not any(c.isspace() for c in r[2]) for r in rows)

check("psms.tsv: header + rows, columns in order, decoy encoded 0/1, "
      "protein is the bare record id (no whitespace), every qvalue in [0,1]",
      header_ok and well_formed and qvalues_ok and decoy_format_ok
      and protein_format_ok)

spectra = num(out, "spectra")
with_candidate = num(out, "with_candidate")
targets = num(out, "targets")
decoys = num(out, "decoys")
check("stdout reports spectra=1200, with_candidate=1025 and the reference "
      "target/decoy peptide counts",
      spectra == 1200 and with_candidate == 1025
      and targets == REF_TARGETS and decoys == REF_DECOYS)

psms_1pct = num(out, "psms_1pct")
check("target PSMs at q<=0.01 between 16 and 20 (reference 18)",
      psms_1pct is not None
      and PSMS_1PCT_BAND[0] <= psms_1pct <= PSMS_1PCT_BAND[1])

best_hits = num(out, "best_hits")
decoy_hits = num(out, "decoy_hits")
# Both operands must be present (and best_hits non-zero) before dividing --
# see the module docstring's fix-round-1 note. A stdout.log missing either
# field must FAIL this criterion, not crash the grader.
decoy_fraction = None
if best_hits is not None and decoy_hits is not None and best_hits:
    decoy_fraction = decoy_hits / best_hits
check("decoy fraction among best hits within 0.05 of 0.333",
      decoy_fraction is not None
      and abs(decoy_fraction - REF_DECOY_FRACTION) <= DECOY_FRACTION_TOL)

psms_1pct_unfiltered = num(out, "psms_1pct_unfiltered")
check("the unfiltered rerun reports fewer 1% FDR PSMs than the filtered run",
      psms_1pct is not None and psms_1pct_unfiltered is not None
      and psms_1pct_unfiltered < psms_1pct)


def parse_decoy(v):
    """Tolerant decoy-flag parse: True/False/None. Recognises the mandated
    `1`/`0` encoding AND a boolean spelling (`true`/`false`, any case), so a
    submission that wrote `True`/`False` instead of `1`/`0` -- which
    criterion 1 independently rejects as a format deviation -- still
    contributes its rows to this criterion's count instead of silently
    dropping every one of them (Task 19: `int("False")` used to raise,
    caught by a bare `except ValueError: continue`, zeroing the count).
    Anything else (e.g. "2", "maybe") returns None and the row is skipped:
    that value is not a format spelling of the mandated field at all, it is
    genuinely absent, so both this criterion and criterion 1 may legitimately
    fail together on it (rule 10's carve-out for a missing mandated value)."""
    v = v.strip().lower()
    if v in ("1", "true"):
        return True
    if v in ("0", "false"):
        return False
    return None


def named_ups_proteins_ge2():
    """Number of the reference's 7 NAMED UPS1-standard proteins that
    individually reach >= 2 best-hit target (decoy=0) spectra in the
    submitted psms.tsv. Matches by accession suffix (e.g. a protein field of
    "P02741ups|CRP_HUMAN_UPS" matches "CRP_HUMAN_UPS"), summed across any rows
    whose protein ends with that name. Requires only `rows_consistent`
    (every row's width matches the file's OWN header length, not a
    hardcoded 6) and protein_idx/decoy_idx (protein/decoy findable by
    name), not `header_ok` (exact order) or `well_formed` (exactly 6
    columns): this criterion must keep working even when the header is
    renamed OR reordered OR an unrelated column is dropped, per rule 9/10."""
    if not rows_consistent or protein_idx is None or decoy_idx is None:
        return False
    by_name = defaultdict(int)
    for r in rows:
        decoy = parse_decoy(r[decoy_idx])
        if decoy is None or decoy:
            continue
        # Tolerant protein match: take only the first whitespace-delimited
        # token, exactly as `read_fasta` derives a record id from a FASTA
        # header. A submission that wrote the full header instead of the
        # bare id (a format deviation criterion 1's protein_format_ok above
        # independently fails) still ends with the right token once its
        # trailing description is discarded, so this criterion keeps
        # reporting the TRUE count instead of silently zeroing it -- the
        # same shape of fix as parse_decoy's boolean-spelling tolerance
        # above. This is a whole-token match against a fixed list of exact
        # accession suffixes, not a substring search over free-text
        # description, so a description that happens to mention another
        # protein's name in prose cannot produce a false match.
        protein = r[protein_idx].split()[0] if r[protein_idx].strip() else ""
        for name in NAMED_UPS_PROTEINS:
            if protein.endswith(name):
                by_name[name] += 1
                break
    n = sum(1 for name in NAMED_UPS_PROTEINS if by_name[name] >= UPS_MIN_SPECTRA)
    if n < MIN_NAMED_UPS:
        print("# only %d of the reference's 7 named UPS1 proteins have >= %d "
              "best-hit spectra (need >= %d): %s"
              % (n, UPS_MIN_SPECTRA, MIN_NAMED_UPS, dict(by_name)))
    return n >= MIN_NAMED_UPS


check("at least 5 of the reference's 7 named UPS1 proteins have >= 2 best-hit spectra",
      named_ups_proteins_ge2())

finish(results)
