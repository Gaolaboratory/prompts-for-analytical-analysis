#!/usr/bin/env python3
"""grade_spectral_s.py <results.tsv> <stdout.log> — external grader for
examples/spectral_library/PROMPT.md.

Two independent kinds of expectation are graded:

- query/best_match/score/matched_peaks/total_library_peaks against the exact
  values pinned in data/spectral/README.md, written LITERALLY in this file
  (not sourced from spectral_ref), so a wrong reference implementation cannot
  certify a wrong tool; and
- the same table recomputed HERE by spectral_ref from the workspace's own
  queries.txt/library.txt, required to agree with those literal values too,
  so a submission cannot pass by memorising the published numbers while its
  matcher silently disagrees with an independent implementation run on the
  same inputs.

That reference recomputation is wrapped in try/except so a missing, empty or
corrupt queries.txt/library.txt leaves ref = None rather than propagating:
every one of the named criteria below must still print an explicit PASS or
FAIL and finish() must always be reached, as in grade_calibration_s /
grade_uvvis_s.

Criteria 2-5 publish EVERY graded value: the four best-match names, all four
scores, the matched-peak counts and the exact stdout summary line. A program
that prints those five lines and never opens queries.txt or library.txt would
satisfy criteria 1-5 outright -- that is not hypothetical, it is exactly the
hardcoded-table forgery a reviewer built against a sibling tool's grader.
Criterion 6 closes that hole: it removes the "nicotine" entry from a copy of
library.txt, re-runs the submitted libsearch.py against queries.txt and that
reduced library, and requires the WHOLE reported table to agree with
spectral_ref.run(queries.txt, <reduced library>) -- not merely to differ from
the unperturbed run. Removing nicotine changes q3's best match entirely (its
own annotated compound is gone from the library, so its top hit drops below
the 0.5 call threshold and becomes NO_MATCH against a different top-scoring
entry with a different score and matched-peak count) -- no correction applied
to a hardcoded four-row table produces that new row, because the new answer
depends on which OTHER library entries best explain q3's fragments once
nicotine is unavailable, not on any function of the original answer.

require_files is kept for the HARNESS-seeded input only: queries.txt and
library.txt are placed by run_bench, so their absence is a harness bug rather
than a graded failure mode of the submission (same distinction as
grade_calibration_s / grade_uvvis_s).
"""
import os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "reference", "short"))
from _grading import finish, require_files
import spectral_ref

QUERIES = "queries.txt"
LIBRARY = "library.txt"
TOOL = "libsearch.py"
SCORE_TOL = 0.0001
DROP_ENTRY = "nicotine"

# Published values (data/spectral/README.md "Expected results"). Written
# literally here, not sourced from spectral_ref, so a wrong reference
# implementation cannot certify a wrong tool.
PINNED = [
    {"query": "q1", "best_match": "caffeine", "score": 0.7473,
     "matched_peaks": 6, "total_library_peaks": 7},
    {"query": "q2", "best_match": "sulfamethoxazole", "score": 0.6669,
     "matched_peaks": 4, "total_library_peaks": 6},
    {"query": "q3", "best_match": "nicotine", "score": 0.8706,
     "matched_peaks": 6, "total_library_peaks": 8},
    {"query": "q4", "best_match": "NO_MATCH", "score": 0.0138,
     "matched_peaks": 2, "total_library_peaks": 6},
]
PINNED_STDOUT = "queries: 4  called: 3  no_match: 1"

results_tsv, stdout_log = sys.argv[1], sys.argv[2]
d = os.path.dirname(os.path.abspath(results_tsv)) or "."
require_files(os.path.join(d, QUERIES), os.path.join(d, LIBRARY))
results = []


def check(name, ok):
    results.append((name, bool(ok)))


def read_text(path, newline=None):
    try:
        with open(path, newline=newline, errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


FIELD_NAMES = ["query", "best_match", "score", "matched_peaks", "total_library_peaks"]


def header_col_map(hdr, names):
    """dict field name -> column index, valid only if `hdr` is exactly a
    permutation of `names` (no dupes, none missing, none extra). None
    otherwise -- a header that fails this leaves no column's identity
    trustworthy. Deliberately more permissive than `hdr == FIELD_NAMES`
    (criterion 1's "columns in order" requirement): EVERY name in `names`
    that appears EXACTLY ONCE in `hdr` is resolved INDEPENDENTLY, so a
    reordered-but-complete header still yields a working map, and a column
    genuinely ABSENT from the header (or duplicated) simply has no entry in
    the returned dict rather than blanking every other field too
    (CONVENTIONS.md rule 10)."""
    return {name: hdr.index(name) for name in names if hdr.count(name) == 1}


raw = read_text(results_tsv, newline="") or ""
body = raw[:-1] if raw.endswith("\n") else raw
lines = body.split("\n") if body else []
hdr = lines[0].split("\t") if lines else []
data_lines = lines[1:]
shape = ("\r" not in raw and len(data_lines) == 4
          and hdr == FIELD_NAMES
          and [ln.split("\t")[0] if ln.split("\t") else None
               for ln in data_lines] == ["q1", "q2", "q3", "q4"]
          and all(len(ln.split("\t")) == 5 for ln in data_lines))
check("results.tsv: header + 4 rows in q1..q4 order, columns in order", shape)

# rows feeds criteria 2-4 (best_match/score/peaks), which key their lookups
# by the "query" field's VALUE via by_query() below, not by row position --
# so this parse is deliberately independent of `shape`'s "q1..q4 in order"
# and "columns in order" requirements, using only col_map (rule 10): a
# results.tsv with a reordered-but-complete header, or rows in a different
# order, still yields a correct `rows` here. "query" is this grader's KEY
# field -- every criterion below locates its values by query VALUE, so
# `rows` fails closed only when query itself can't be resolved or a row's
# width disagrees with the header's. Any OTHER field genuinely absent from
# the header is simply None on every row, so only the criterion that names
# that field fails (best_match_agrees/score_agrees/peaks_agree below all
# already fail cleanly, without raising, on a None field value).
col_map = header_col_map(hdr, FIELD_NAMES)
rows = None
if ("query" in col_map and len(data_lines) == 4
        and all(len(ln.split("\t")) == len(hdr) for ln in data_lines)):
    rows = []
    for ln in data_lines:
        fields = ln.split("\t")
        row = {"query": fields[col_map["query"]]}
        row["best_match"] = (fields[col_map["best_match"]]
                              if "best_match" in col_map else None)
        try:
            row["score"] = (float(fields[col_map["score"]])
                             if "score" in col_map else None)
        except ValueError:
            row["score"] = None
        try:
            row["matched_peaks"] = (int(fields[col_map["matched_peaks"]])
                                     if "matched_peaks" in col_map else None)
        except ValueError:
            row["matched_peaks"] = None
        try:
            row["total_library_peaks"] = (
                int(fields[col_map["total_library_peaks"]])
                if "total_library_peaks" in col_map else None)
        except ValueError:
            row["total_library_peaks"] = None
        rows.append(row)

# Recompute the reference from the workspace's own queries.txt/library.txt.
# Any failure (missing files, empty files, malformed records, ...) leaves
# ref = None rather than propagating, so every criterion below fails
# explicitly instead of the whole grader crashing before finish() is reached.
try:
    ref = spectral_ref.run(os.path.join(d, QUERIES), os.path.join(d, LIBRARY))
    ref_by_query = {r["query"]: r for r in ref}
except Exception:
    ref_by_query = None


def score_ok(got, want):
    return got is not None and abs(got - want) <= SCORE_TOL


def best_match_agrees(row, pinned):
    """best_match identity only -- disjoint from score_agrees below, so a
    score-only mutation cannot fail this criterion and a best_match-only
    mutation cannot fail that one."""
    if row is None:
        return False
    ref_row = ref_by_query.get(pinned["query"]) if ref_by_query else None
    return (row["best_match"] == pinned["best_match"]
            and ref_row is not None
            and ref_row["best_match"] == pinned["best_match"])


def score_agrees(row, pinned):
    """score only (+/- SCORE_TOL) -- disjoint from best_match_agrees above."""
    if row is None:
        return False
    ref_row = ref_by_query.get(pinned["query"]) if ref_by_query else None
    return (score_ok(row["score"], pinned["score"])
            and ref_row is not None
            and score_ok(ref_row["score"], pinned["score"]))


def peaks_agree(row, pinned):
    if row is None:
        return False
    ref_row = ref_by_query.get(pinned["query"]) if ref_by_query else None
    return (row["matched_peaks"] == pinned["matched_peaks"]
            and row["total_library_peaks"] == pinned["total_library_peaks"]
            and ref_row is not None
            and ref_row["matched_peaks"] == pinned["matched_peaks"]
            and ref_row["total_library_peaks"] == pinned["total_library_peaks"])


def by_query(qid):
    if rows is None:
        return None
    for r in rows:
        if r["query"] == qid:
            return r
    return None


check("best_match: caffeine, sulfamethoxazole, nicotine, NO_MATCH",
      all(best_match_agrees(by_query(p["query"]), p) for p in PINNED))

check("scores 0.7473 / 0.6669 / 0.8706 / 0.0138 (+/- 0.0001)",
      all(score_agrees(by_query(p["query"]), p) for p in PINNED))

check("matched_peaks 6/4/6/2 and total_library_peaks 7/6/8/6",
      all(peaks_agree(by_query(p["query"]), p) for p in PINNED))

out = read_text(stdout_log) or ""
check("stdout: queries: 4  called: 3  no_match: 1",
      PINNED_STDOUT in out.splitlines())


def build_reduced_library(src_path, dst_path, drop_name):
    """Copy `src_path` with the `drop_name` record removed, using
    spectral_ref's own parser/writer conventions so the reduced file is a
    valid input regardless of the exact formatting of the original."""
    records = spectral_ref.parse_spectra(src_path)
    with open(dst_path, "w", newline="") as fh:
        fh.write("# library with %s removed\n" % drop_name)
        for name, peaks in records:
            if name == drop_name:
                continue
            fh.write("\n>NAME %s\n" % name)
            for mz, inten in peaks:
                fh.write("%r %r\n" % (mz, inten))


def read_rows(path):
    """list[dict] parsed from a results.tsv-shaped file, or None if
    unreadable/malformed. Looks each field up BY NAME via header_col_map,
    the same as the initial results.tsv above, so a column-order slip in the
    freshly re-run reduced-library output doesn't corrupt this criterion
    either (rule 10)."""
    text = read_text(path, newline="")
    if not text:
        return None
    body2 = text[:-1] if text.endswith("\n") else text
    ls = body2.split("\n") if body2 else []
    if len(ls) < 2:
        return None
    row_hdr = ls[0].split("\t")
    row_col_map = header_col_map(row_hdr, FIELD_NAMES)
    if not all(n in row_col_map for n in FIELD_NAMES):
        return None
    out = []
    for ln in ls[1:]:
        parts = ln.split("\t")
        if len(parts) != len(row_hdr):
            return None
        try:
            out.append({
                "query": parts[row_col_map["query"]],
                "best_match": parts[row_col_map["best_match"]],
                "score": float(parts[row_col_map["score"]]),
                "matched_peaks": int(parts[row_col_map["matched_peaks"]]),
                "total_library_peaks": int(parts[row_col_map["total_library_peaks"]]),
            })
        except ValueError:
            return None
    return out


def reduced_library_matches_reference():
    """True iff re-running the submitted libsearch.py with the "nicotine"
    entry removed from library.txt reports a table that agrees with
    spectral_ref.run(queries.txt, <reduced library>) -- not merely a table
    that differs from the unperturbed run.

    Removing nicotine changes q3's own best match (its annotated compound is
    gone), so the new answer depends on how the OTHER library entries score
    against q3's fragments -- a quantity no closed-form correction of the
    original four-row table can produce. A tool that hardcodes the published
    rows (criteria 1-5's exact hole) reports the unperturbed nicotine/0.8706
    row here and disagrees with the reduced-library reference.

    Any failure -- missing libsearch.py, a crash, a timeout, or unreadable
    output on either the reduced-library build or the re-run -- makes this
    criterion FAIL rather than raising: finish() must still be reached.
    """
    tmp = None
    try:
        tmp = _mkdtemp()
        for name in sorted(os.listdir(d)):
            if name.endswith(".py"):
                shutil.copy2(os.path.join(d, name), tmp)
        if not os.path.isfile(os.path.join(tmp, TOOL)):
            print("# %s missing: cannot re-run it on a reduced library" % TOOL)
            return False
        shutil.copy2(os.path.join(d, QUERIES), os.path.join(tmp, QUERIES))
        reduced_path = os.path.join(tmp, "library_reduced.txt")
        try:
            build_reduced_library(os.path.join(d, LIBRARY), reduced_path, DROP_ENTRY)
            want = spectral_ref.run(os.path.join(tmp, QUERIES), reduced_path)
        except Exception as exc:
            print("# building/scoring the reduced library raised %s: %s"
                  % (type(exc).__name__, exc))
            return False
        try:
            proc = subprocess.run(
                [sys.executable, TOOL, QUERIES, "library_reduced.txt",
                 "-o", "results_reduced.tsv"],
                cwd=tmp, timeout=120, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            print("# %s timed out on the reduced library" % TOOL)
            return False
        if proc.returncode != 0:
            print("# %s exited %d on the reduced library: %s"
                  % (TOOL, proc.returncode, (proc.stderr or "").strip()[:200]))
            return False
        got = read_rows(os.path.join(tmp, "results_reduced.tsv"))
        if got is None:
            print("# reduced-library run produced no readable results table")
            return False
        want_by_query = {r["query"]: r for r in want}
        got_by_query = {r["query"]: r for r in got}
        agrees = set(got_by_query) == set(want_by_query) and all(
            got_by_query[q]["best_match"] == want_by_query[q]["best_match"]
            and score_ok(got_by_query[q]["score"], want_by_query[q]["score"])
            and got_by_query[q]["matched_peaks"] == want_by_query[q]["matched_peaks"]
            and got_by_query[q]["total_library_peaks"] == want_by_query[q]["total_library_peaks"]
            for q in want_by_query)
        if not agrees:
            print("# reduced library: tool %r vs reference %r" % (got, want))
        return agrees
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def _mkdtemp():
    import tempfile
    return tempfile.mkdtemp(prefix="reduced_")


check("re-running libsearch.py on a library with one entry removed "
      "reproduces the reference result for that library",
      reduced_library_matches_reference())

finish(results)
