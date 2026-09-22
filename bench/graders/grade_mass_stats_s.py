#!/usr/bin/env python3
"""grade_mass_stats_s.py <stats.tsv> <stdout.log> -- grader for
examples/mass_stats/PROMPT.md.

There is no perturbation criterion here, unlike grade_calibration_s.py /
grade_uvvis_s.py -- and none is needed. The prompt publishes only three
summary integers (tested=618 filtered=0 significant=253) and a top-10 feature
ID list; criteria 2-5 compare ALL 618 rows against mass_stats_ref recomputed
from the workspace's own quant_mtbls14397_pos.csv/groups.tsv. Nobody can
hardcode 618 rows of Welch statistics from a prompt that does not contain
them, so a re-run-on-a-perturbed-input criterion would add nothing here.

Criterion 2 checks the `significant` COLUMN against the reference, not just the
stdout summary line: an earlier version of this grader counted `len(r) == 7`
without ever reading the seventh field's content, so a submission that moved
all 253 significant flags onto the wrong (highest-p) rows while keeping the
count at 253 scored 6/6. See CONVENTIONS.md rule 1 -- a mandated output
column can go ungraded exactly like a mandated stdout line can.

Published constants (Rule 3: literal, not sourced from the reference) are
TESTED/FILTERED/SIGNIFICANT and TOP10_IDS, both transcribed from
data/mass_stats/README.md's "Expected results" section -- so a wrong
mass_stats_ref could not certify a wrong tool on those two criteria. Every
per-row statistic (t, p_value, df, log2fc, q_value) is instead compared
against mass_stats_ref recomputed here, which is exactly what a submission
cannot forge: it would have to reproduce the real Welch/BH computation.

Missing, empty or corrupt inputs must not crash this grader: the reference
recomputation is wrapped in try/except so ref stays None on any failure, and
every one of the 6 named criteria below still prints an explicit FAIL rather
than vanishing from the verdict list (Rule 2).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "reference", "short"))
from _grading import finish, num_field
import mass_stats_ref

QUANT_CSV = "quant_mtbls14397_pos.csv"
GROUPS_TSV = "groups.tsv"

# Published in data/mass_stats/README.md's "Expected results" section --
# literal here so a wrong reference cannot certify a wrong tool (Rule 3).
TESTED, FILTERED, SIGNIFICANT = 618, 0, 253
TOP10_IDS = ["MET_235", "MET_433", "MET_410", "MET_438", "MET_594",
             "MET_283", "MET_173", "MET_186", "MET_607", "MET_498"]

EXPECTED_HEADER = ["feature_id", "log2fc", "t", "df", "p_value", "q_value", "significant"]
REL_TOL_TIGHT = 1e-6   # t, p_value, df, q_value
REL_TOL_LOG2FC = 1e-9  # log2fc
LOG2FC_ABS_FLOOR = 1e-9  # defensive floor: tol*abs(want) degenerates to exact
                          # equality when want == 0.0, which log2fc can
                          # legitimately be on some other dataset.

stats_path, stdout_path = sys.argv[1], sys.argv[2]
results = []


def check(name, ok):
    results.append((name, bool(ok)))


def read_text(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


stats_text = read_text(stats_path)
out = read_text(stdout_path) or ""

# Recompute the reference from the workspace's own inputs. Any failure
# (missing file, empty file, malformed CSV/TSV, ...) leaves ref = None
# rather than propagating, so every criterion below fails explicitly instead
# of the whole grader crashing before finish() is reached.
try:
    ref = mass_stats_ref.run(QUANT_CSV, GROUPS_TSV)
except Exception:
    ref = None
ref_by_id = {row["feature_id"]: row for row in ref["rows"]} if ref is not None else {}

lines = [l for l in (stats_text or "").split("\n") if l]
hdr = lines[0].split("\t") if lines else []
rows = [l.split("\t") for l in lines[1:]]


def is_sorted_by_p(rows):
    """True iff the file's own p_value column is non-decreasing. This is a
    self-consistency check on the file as printed, independent of whether
    the feature_id -> row mapping is otherwise correct (that is covered by
    criteria 3-6)."""
    try:
        ps = [float(r[4]) for r in rows]
    except (ValueError, IndexError):
        return False
    return all(ps[i] <= ps[i + 1] for i in range(len(ps) - 1))


# Basic structural validity (header, row count, column count per row) is
# split from sortedness on purpose: criteria 3-6 key their comparisons by
# feature_id, so they are correct regardless of what line a row sits on, and
# must not fail just because the file's row ORDER is wrong -- that is what
# criterion 1 (sortedness) and criterion 6 (top-10 order) are for. Gating
# them all behind one combined flag would make e.g. a two-row swap fail
# every criterion instead of only the ones that actually name an affected
# field.
basic_shape = (hdr == EXPECTED_HEADER and len(rows) == TESTED
               and all(len(r) == 7 for r in rows))
shape = basic_shape and is_sorted_by_p(rows)
check("stats.tsv: header + 618 rows sorted by p_value, columns in order", shape)

def rel_ok(got, want, tol, floor=0.0):
    return got is not None and abs(got - want) <= max(tol * abs(want), floor)


def _to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _to_int_flag(s):
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def parse_rows_by_header(hdr, rows):
    """Map feature_id -> {column name: raw string} using column POSITIONS
    TAKEN FROM THE HEADER, not the fixed positions of EXPECTED_HEADER, so a
    reordered stats.tsv still yields correct values for every field under
    its own name. Returns ({}, False) if feature_id itself can't be
    identified: it's missing from the header, a row's field count doesn't
    match the header's, or a feature_id repeats -- any of those means no
    field's identity can be trusted for that row, so every value criterion
    below fails explicitly rather than guessing.

    A genuinely MISSING column (e.g. `t` omitted entirely, as in
    mass_stats_s/local/2) is not an error here: it is simply absent from
    every row's dict, so `.get(name)` returns None for it below and only the
    criteria that actually name that field fail (Rule 10) -- the header
    identifying the missing column is itself criterion 1's job (`hdr ==
    EXPECTED_HEADER`), not this function's."""
    if "feature_id" not in hdr or len(hdr) != len(set(hdr)):
        return {}, False
    fid_idx = hdr.index("feature_id")
    out = {}
    for r in rows:
        if len(r) != len(hdr):
            return {}, False
        fid = r[fid_idx]
        if fid in out:
            return {}, False
        out[fid] = dict(zip(hdr, r))
    return out, True


raw_by_id, name_parse_ok = parse_rows_by_header(hdr, rows)

# Parse every data row into a dict keyed by feature_id, looking each of the
# per-row fields up BY NAME rather than by a fixed column index. This is
# what stops a column-order slip (t and df swapped, mass_stats_s/local/1 and
# /3) or a missing column (t omitted, mass_stats_s/local/2) from corrupting
# criteria 2-5: each field is read from whichever column carries its own
# name, so a defect in one column's position or presence can only ever fail
# the criteria that actually name that field. A field absent from the
# header (rawrow.get returns None) or unparseable as a number both surface
# as None here, which rel_ok() and the significant-flag comparison below
# both already treat as "does not match" rather than crashing (Rule 10).
parsed = {}
if name_parse_ok and len(raw_by_id) == TESTED:
    parsed = {
        fid: {
            "log2fc": _to_float(rawrow.get("log2fc")),
            "t": _to_float(rawrow.get("t")),
            "df": _to_float(rawrow.get("df")),
            "p_value": _to_float(rawrow.get("p_value")),
            "q_value": _to_float(rawrow.get("q_value")),
            "significant": _to_int_flag(rawrow.get("significant")),
        }
        for fid, rawrow in raw_by_id.items()
    }


def all_rows_agree(fields):
    """True iff every one of ref's 618 tested features has a matching row in
    `parsed` whose named fields all agree at the given relative tolerances.
    Checked from the reference's side (not the submission's) so a row for an
    id the reference does not recognise, or a missing id, both fail rather
    than being silently skipped. `fields` is a list of (name, tol) or
    (name, tol, floor) tuples; floor defaults to 0.0."""
    if ref is None or not parsed or len(parsed) != TESTED:
        return False
    for fid, refrow in ref_by_id.items():
        got = parsed.get(fid)
        if got is None:
            return False
        for spec in fields:
            field, tol = spec[0], spec[1]
            floor = spec[2] if len(spec) > 2 else 0.0
            if not rel_ok(got[field], refrow[field], tol, floor):
                return False
    return True


def significant_column_matches():
    """True iff every one of ref's 618 tested features has a matching row in
    `parsed` whose `significant` flag is exactly equal (0/1, not a
    tolerance-based comparison) to the reference's. A submission could print
    the right aggregate count in stdout while flagging the wrong 253 rows --
    this is what actually catches that (see CONVENTIONS.md rule 1)."""
    if ref is None or not parsed or len(parsed) != TESTED:
        return False
    for fid, refrow in ref_by_id.items():
        got = parsed.get(fid)
        if got is None or got["significant"] != refrow["significant"]:
            return False
    return True


check("stdout reports tested=618 filtered=0 significant=253, and the "
      "significant column matches the reference on every row",
      num_field(out, "tested") == TESTED and num_field(out, "filtered") == FILTERED
      and num_field(out, "significant") == SIGNIFICANT
      and significant_column_matches())

# Criteria 3-5 each cover a disjoint set of fields (t/p_value, df/log2fc,
# q_value) so that mutating one field fails only the criterion that names it
# (Rule 9), even though all three share the all_rows_agree helper. Criterion
# 2's `significant` field (above) is likewise disjoint from all of them.
check("t and p_value match the reference within 1e-6 relative on every row",
      all_rows_agree([("t", REL_TOL_TIGHT), ("p_value", REL_TOL_TIGHT)]))

check("df within 1e-6 relative and log2fc within 1e-9 relative on every row",
      all_rows_agree([("df", REL_TOL_TIGHT),
                       ("log2fc", REL_TOL_LOG2FC, LOG2FC_ABS_FLOOR)]))

# The top-8 BH plateau (all tied at q = 1.2607615866e-04, data/mass_stats/
# README.md) is not checked separately: comparing every row's q_value against
# the reference at 1e-6 relative (absolute ~1.3e-10 at this magnitude) already
# forces a submission to reproduce the tie, since any implementation that
# breaks it would produce at least one plateau row whose q_value disagrees
# with the reference by far more than that.
check("q_value within 1e-6 relative, with the top-8 BH plateau reproduced",
      all_rows_agree([("q_value", REL_TOL_TIGHT)]))

# feature_id, in file order -- from raw_by_id (built by header name, Rule
# 10) rather than positional r[0], so a column slip elsewhere in the row
# (t/df swapped, or missing) does not touch this criterion: it only cares
# where feature_id actually sits, and whether the file's own row order puts
# the right ten ids first.
top10_got = (list(raw_by_id.keys())[:10]
             if name_parse_ok and len(rows) >= 10 else [])
check("top 10 features by p_value are the reference ten, in order",
      top10_got == TOP10_IDS)

finish(results)
