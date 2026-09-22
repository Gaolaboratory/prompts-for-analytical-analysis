#!/usr/bin/env python3
"""grade_formula_s.py <ranked.tsv> <stdout.log> — grader for
examples/formula_finder/PROMPT.md.

Two independent kinds of expectation are graded:

- the rank-1 formula per block, and the |error_ppm| <= 2.0 / score <= 0.5
  bounds on those rows, against the MassBank-derived published values pinned
  in data/formula/README.md, written LITERALLY in this file (not sourced
  from formula_ref), so a wrong reference implementation cannot certify a
  wrong tool; and
- rank-1 calc_mass, which is not independently published to more precision
  than the formula/error_ppm/score already pin, against formula_ref
  recomputed HERE from the workspace's own measured_caffeine.tsv; and
- the stdout `blocks=<n> candidates=<n>` line, likewise against formula_ref
  recomputed from the same input: blocks exact (it is just the input's own
  row count), candidates within CANDIDATES_TOL (see that constant's comment)
  of the reference total. Before this criterion checked the reported VALUES
  rather than merely their presence, a submission that enumerated the
  entire unfiltered formula space -- never applying the prompt's mandated 5
  ppm window -- scored 6/6 while reporting candidates=6495441 against a
  reference of 35: it sorted correctly, so the right formula still landed
  at rank 1 in every block, and nothing compared the candidate count to
  anything (CONVENTIONS.md rule 1); and
- ranked.tsv's OWN row count (criterion 1), against that same reference
  total and the same CANDIDATES_TOL, because the stdout check above grades
  only what the submission SAYS, not what the file actually contains: the
  prompt (PROMPT.md:16-19) mandates "one row per candidate for every block"
  and defines stdout `candidates` as that total row count, but nothing
  compared the file's row count to anything until this check existed. A
  ranked.tsv truncated to 8 rows (2 per block: rank 1 and rank 2, so every
  other check here -- header, block set/order, contiguous per-block ranks,
  and every rank-1/runner-up value -- still passed) while stdout.log still
  claimed `candidates=35` used to score 6/6.

Both reference-recomputation uses share ONE `ref = formula_ref.run(...)`
call, made before ranked.tsv is even parsed (criterion 1 needs it too now).
It is wrapped in try/except so a missing, empty or corrupt
measured_caffeine.tsv leaves ref = None rather than propagating: every one
of the named criteria below must still print an explicit PASS or FAIL and
finish() must always be reached, as in grade_pca_s / grade_calibration_s. A
criterion that disappears is not a criterion that failed, and it makes the
per-criterion table non-comparable across tools.

There is no perturbation criterion here (unlike grade_calibration_s /
grade_uvvis_s): formula_finder.py has no natural non-uniform perturbation
that leaves the enumeration/scoring machinery exercised the same way a
re-fit or a re-located band maximum would be, so this grader follows the
pca_s shape instead -- static output checked against literal published
constants plus a same-input reference recomputation.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "reference", "short"))
from _grading import finish, num_field
import formula_ref

ranked_path, stdout_path = sys.argv[1], sys.argv[2]
results = []

# Published rank-1 formulae (data/formula/README.md), each compound's own
# MassBank CH$FORMULA. Written literally here, not sourced from formula_ref,
# so a wrong reference implementation cannot certify a wrong tool.
EXPECTED_IDS = ["CAFFEINE", "ACETAMINOPHEN", "SULFAMETHOXAZOLE", "AMPA"]
EXPECTED_FORMULA = {
    "CAFFEINE": "C8H10N4O2",
    "ACETAMINOPHEN": "C8H9NO2",
    "SULFAMETHOXAZOLE": "C10H11N3O3S",
    "AMPA": "CH6NO3P",
}
EXPECTED_HEADER = ["id", "rank", "formula", "calc_mass", "error_ppm", "score"]
ERROR_PPM_MAX = 2.0        # README-published bound on the rank-1 rows
SCORE_MAX = 0.5            # README-published bound on the rank-1 rows
MARGIN_MIN = 5.0           # README-published rank-1 vs runner-up margin
CALC_MASS_TOL = 1e-5       # rank-1 calc_mass vs reference recomputed from input, Da

# CANDIDATES_TOL: the enumeration is deterministic given the prompt's stated
# bounds and inclusive 5 ppm window, so blocks=4/candidates=35 is the one
# right answer for this fixed input -- probing formula_ref against
# measured_caffeine.tsv shows no candidate lands within 0.2 ppm of either
# window edge in any of the four blocks, so no legitimate implementation
# choice flips a candidate in or out for THIS data. The tolerance below
# exists only for the boundary difference data/formula/README.md flags in
# principle -- a candidate whose calc_mass a different but still-conforming
# floating-point formulation of "inclusive 5 ppm" could legitimately place
# on the other side of exactly +/-5.000000 ppm -- which can flip at most one
# candidate per block, four blocks. It is nowhere near wide enough to admit
# an unfiltered enumeration or a truncated file: the two defects this
# tolerance has to reject are stdout reporting candidates=6495441 against a
# reference of 35 (off by 6,495,406), and ranked.tsv itself carrying only 8
# rows while stdout still claims candidates=35 (off by 27) -- both are used
# for BOTH the stdout comparison (criterion 6) and the file's own row-count
# comparison (criterion 1) below, so one tolerance, one meaning, in two
# places.
CANDIDATES_TOL = 4


def check(name, ok):
    results.append((name, bool(ok)))


def read_text(path, newline=None):
    try:
        with open(path, newline=newline, errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


# Recompute the reference from the workspace's own measured_caffeine.tsv,
# before any of ranked.tsv is even parsed: criterion 1 below needs it to
# check the file's own row count (rule 1 -- the prompt mandates "one row per
# candidate for every block", and that mandate was previously ungraded: a
# ranked.tsv truncated from 35 rows to 8 scored 6/6 as long as stdout still
# claimed candidates=35). Any failure (missing file, empty file, malformed
# TSV, ...) leaves ref = None rather than propagating, so every criterion
# below still prints an explicit PASS or FAIL and finish() is always
# reached, as in grade_pca_s / grade_calibration_s.
try:
    # Resolve measured_caffeine.tsv against ranked_path's own directory
    # (both are always written into the same workspace, per bench/specs.py's
    # formula_s grader_args), not a bare relative name depending on the
    # grader's cwd happening to be the workspace -- true whenever run_bench
    # invokes this grader, but not guaranteed for every caller.
    workspace_dir = os.path.dirname(os.path.abspath(ranked_path))
    ref = formula_ref.run(os.path.join(workspace_dir, "measured_caffeine.tsv"))
except Exception:
    ref = None

raw = read_text(ranked_path, newline="") or ""
body = raw[:-1] if raw.endswith("\n") else raw
lines = body.split("\n") if body else []
hdr = lines[0].split("\t") if lines else []
data_rows = [ln.split("\t") for ln in lines[1:]]


def header_col_map(hdr):
    """dict field name -> column index, valid only if `hdr` is exactly a
    permutation of EXPECTED_HEADER's six names (no dupes, none missing, none
    extra). Instead, EVERY name that appears EXACTLY ONCE in `hdr` is
    resolved INDEPENDENTLY -- so a reordered-but-complete header still
    yields a working col_map, and a column genuinely ABSENT from the header
    (or duplicated) simply has no entry, rather than blanking every other
    field too (CONVENTIONS.md rule 10). This is DELIBERATELY more
    permissive than criterion 1's `hdr == EXPECTED_HEADER`, which
    additionally requires the mandated order AND completeness: criteria 2-5
    can find whichever fields ARE present under their own name even when
    criterion 1 (which owns "columns in order") fails."""
    return {name: hdr.index(name) for name in EXPECTED_HEADER
            if hdr.count(name) == 1}


col_map = header_col_map(hdr)

# Group consecutive rows sharing the same id into blocks, in the order they
# appear -- this is the "blocks in input order" the prompt mandates. `id` is
# this grader's KEY field (rule 10): every criterion below locates its
# values through a block built by id, so grouping fails closed (valid_rows
# False, blocks empty) only when id itself can't be resolved or a row's
# width disagrees with the header's width -- not when some OTHER mandated
# column is merely missing or reordered.
valid_rows = "id" in col_map and all(len(r) == len(hdr) for r in data_rows)
id_idx = col_map.get("id")
blocks = []
if valid_rows:
    cur_id, cur_rows = None, []
    for r in data_rows:
        rid = r[id_idx]
        if rid != cur_id:
            if cur_id is not None:
                blocks.append((cur_id, cur_rows))
            cur_id, cur_rows = rid, []
        cur_rows.append(r)
    if cur_id is not None:
        blocks.append((cur_id, cur_rows))
block_ids = [b for b, _ in blocks]


def ranks_ok(rows):
    if "rank" not in col_map:
        return False
    try:
        ranks = [int(r[col_map["rank"]]) for r in rows]
    except ValueError:
        return False
    return ranks == list(range(1, len(rows) + 1))


# Row count vs the reference's total candidate count, within CANDIDATES_TOL
# (defined above, alongside the constant's full justification) -- the same
# tolerance and the same reference total the stdout comparison (criterion 6)
# uses, applied instead to what ranked.tsv itself actually contains. This is
# what catches a ranked.tsv truncated to a handful of rows per block while
# stdout still claims the full candidate count: nothing else in this
# criterion (header, block set/order, contiguous per-block ranks) depends on
# how many rows a block has beyond what its own ranks say, so a truncated
# file with internally-consistent ranks (1, 2, ... within the rows that
# remain) used to pass every existing check here.
row_count_ok = (ref is not None
                and abs(len(data_rows) - ref["candidates"]) <= CANDIDATES_TOL)

shape = ("\r" not in raw and valid_rows and hdr == EXPECTED_HEADER
          and block_ids == EXPECTED_IDS
          and all(ranks_ok(rows) for _, rows in blocks)
          and row_count_ok)
check("ranked.tsv: header + 4 blocks in input order, ranks starting at 1", shape)

blocks_by_id = dict(blocks)


def row_field(bid, row_index, field):
    """`field` (a name, looked up via col_map -- rule 10) of the
    `row_index`-th row of block `bid`, or None if the block, row, or column
    is missing -- never raises. A `field` absent from col_map (a column
    genuinely missing from the header) returns None for every row, so only
    the criteria that actually name that field fail."""
    rows = blocks_by_id.get(bid)
    if rows is None or len(rows) <= row_index or field not in col_map:
        return None
    row = rows[row_index]
    idx = col_map[field]
    if len(row) <= idx:
        return None
    return row[idx]


def num_col(bid, row_index, field):
    v = row_field(bid, row_index, field)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


formula_ok = all(row_field(bid, 0, "formula") == EXPECTED_FORMULA[bid] for bid in EXPECTED_IDS)
check("rank-1 formula correct in all four blocks", formula_ok)


def rank1_bounds_ok(bid):
    err = num_col(bid, 0, "error_ppm")
    score = num_col(bid, 0, "score")
    return err is not None and abs(err) <= ERROR_PPM_MAX \
        and score is not None and score <= SCORE_MAX


check("every rank-1 row has |error_ppm| <= 2.0 and score <= 0.5",
      all(rank1_bounds_ok(bid) for bid in EXPECTED_IDS))


def margin_ok(bid):
    top = num_col(bid, 0, "score")
    runner_up = num_col(bid, 1, "score")
    return top is not None and runner_up is not None and (runner_up - top) >= MARGIN_MIN


check("every rank-1 row beats its block runner-up by >= 5 score units",
      all(margin_ok(bid) for bid in EXPECTED_IDS))

# ref was already recomputed above (before ranked.tsv was even parsed), so
# criterion 1's row-count check could use it too.


def ref_rank1_mass(bid):
    if ref is None:
        return None
    block = ref.get(bid)
    if not block:
        return None
    return block[0]["calc_mass"]


def calc_mass_ok(bid):
    got = num_col(bid, 0, "calc_mass")
    want = ref_rank1_mass(bid)
    return got is not None and want is not None and abs(got - want) <= CALC_MASS_TOL


check("rank-1 calc_mass matches the reference recomputed from the input (<=1e-5 Da)",
      ref is not None and all(calc_mass_ok(bid) for bid in EXPECTED_IDS))

out = read_text(stdout_path) or ""
stdout_blocks = num_field(out, "blocks")
stdout_candidates = num_field(out, "candidates")


def stdout_matches_ref():
    if ref is None or stdout_blocks is None or stdout_candidates is None:
        return False
    return (int(stdout_blocks) == ref["blocks"]
            and abs(stdout_candidates - ref["candidates"]) <= CANDIDATES_TOL)


check("stdout reports blocks and candidates", stdout_matches_ref())

finish(results)
