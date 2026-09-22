# MS/MS spectral library search

Write `libsearch.py`. Run: `python3 libsearch.py queries.txt library.txt -o results.tsv`

Python standard library plus numpy, pandas and scipy only. No other third-party packages.

## Input

`queries.txt` and `library.txt` are both in the working directory: a `#` comment line,
then records separated by blank lines, each record a `>NAME <name>` header followed by
one `m/z intensity` pair per line (whitespace-separated). `library.txt` has 5 entries,
`queries.txt` has 4 queries. Intensities are relative and their **scale differs between
records** (e.g. one record's base peak is 999, another's 405) — that is harmless because
the score below is scale-invariant, so do not renormalise.

## Output

`results.tsv`: a header line plus one tab-separated data row per query, in input order,
LF endings:

```
query	best_match	score	matched_peaks	total_library_peaks
```

`score` to 4 decimals. `matched_peaks` is the number of query peaks paired with a library
peak under the greedy one-to-one rule below, for the reported best-matching entry.
`total_library_peaks` is the number of peaks in that library entry. One line on stdout:
`queries: <n>  called: <n>  no_match: <n>` (two spaces before `called` and before
`no_match`).

## Method

- Score every query against every library entry. Matching is **greedy and one-to-one**:
  form every candidate pair of a query peak and a library peak with `|Δm/z| ≤ 0.5`, sort
  the candidates by the product of their square-rooted intensities, descending, and take
  them in that order, skipping any pair where either peak has already been used. A peak
  already matched cannot match again — allowing reuse inflates every score.
- `score = (Σ_matched √(Iq·Il))² / (Σ Iq · Σ Il)`, where `Σ Iq` and `Σ Il` are the sums
  over **all** peaks of the query and of the library entry (not only the matched ones).
- The best match is the highest-scoring library entry. If its score is below **0.5**,
  `best_match` is `NO_MATCH` — but `score`, `matched_peaks` and `total_library_peaks`
  still describe that top-scoring entry, not a forced zero.

## Acceptance criteria

1. `results.tsv: header + 4 rows in q1..q4 order, columns in order`
2. `best_match: caffeine, sulfamethoxazole, nicotine, NO_MATCH`
3. `scores 0.7473 / 0.6669 / 0.8706 / 0.0138 (+/- 0.0001)`
4. `matched_peaks 6/4/6/2 and total_library_peaks 7/6/8/6`
5. `stdout: queries: 4  called: 3  no_match: 1`
6. `re-running libsearch.py on a library with one entry removed reproduces the reference result for that library`

Do not tune a constant to make a number match; if a criterion fails, the matcher is wrong.
