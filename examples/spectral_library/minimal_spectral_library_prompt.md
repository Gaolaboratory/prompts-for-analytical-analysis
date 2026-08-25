# Standalone — MS/MS spectral library search

Standard library only (no `numpy`, `pyteomics`, `matchms`). Write two files:

- `libsearch.py` — the search tool.
- `make_test_data.py` — exactly the script below; run it to produce the test files.

`python3 libsearch.py queries.txt library.txt -o results.tsv` — match each query MS/MS
spectrum against every library entry and write a ranked result table, one row per query,
sorted by `query_id` ascending:

```
query_id	best_match	score	matched_peaks	total_library_peaks
```

Write it **tab-separated** (real `\t`) with Unix newlines and the header above; `score` with
exactly 4 decimals. Print one summary line **to stdout**: `queries: 4  called: 3  no_match: 1`.

## The file format

Both files share one minimal text format: a comment line starting with `#`, then spectra
separated by blank lines. Each spectrum is a header `>NAME <id>` followed by one
`m/z intensity` pair per line (whitespace-separated; spacing may vary). Skip blank lines and
`#` comments.

## The parts you can't guess

- **Matching is greedy and one-to-one.** For each query peak in ascending m/z: among library
  peaks not yet matched with `|Δm/z| ≤ 0.5`, take the one with the smallest `|Δm/z|`; on a tie,
  the lower-m/z library peak. Each library peak matches at most one query peak.
- **Score** — square-root intensity weighting, matched peaks only, then normalized:

  `score = ( Σ_matched sqrt(Iq · Il) )² / ( Σ Iq · Σ Il )`

  Sum `Σ Iq` is over **all** query peaks and `Σ Il` over **all** library peaks of the entry
  (not just matched ones). If either sum is 0, the score is 0. No base-peak normalization is
  needed or allowed: the formula is already invariant to scaling either spectrum, so use the
  intensities as read.
- **Best match and the call.** The best match is the highest-scoring entry; ties broken by
  library file order (first entry wins). If the best score is `< 0.5`, `best_match` is the
  literal string `NO_MATCH`; `score`, `matched_peaks`, and `total_library_peaks` still describe
  the top-scoring entry (score below threshold, not forced to 0).

**Verify your core before continuing** — run your `score` on
query `[(100,100),(200,400),(300,900)]` vs reference `[(100,25),(200,100),(350,225)]`:
the 300 vs 350 pair is outside ±0.5, so 2 peaks match and the score must be
**0.1276** (hand-check: `(50+200)² / (1400·350) = 62500/490000 = 0.127551`).
Do not write the file parser until this prints correctly.

## Test data generator

```python
#!/usr/bin/env python3
"""Deterministic generator for the spectral-library-search test data. Std-lib only."""

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

LIBRARY = [
    ("caffeine",        [(42.1, 15), (58.0, 100), (69.0, 20), (82.0, 35),
                         (109.1, 55), (138.1, 60), (163.1, 10), (195.1, 90)]),
    ("acetaminophen",   [(43.0, 40), (65.0, 20), (80.9, 10), (92.0, 15),
                         (93.0, 60), (109.0, 45), (110.0, 35), (152.1, 80)]),
    ("sulfamethoxazole",[(65.0, 30), (92.0, 70), (99.0, 25), (108.0, 85),
                         (124.0, 20), (156.0, 90), (188.0, 50), (254.1, 75)]),
    ("nicotine",        [(42.0, 35), (84.1, 100), (117.0, 15), (119.1, 20),
                         (130.1, 25), (132.1, 40), (133.0, 10), (163.1, 60)]),
]

def write_spectra(path, entries, comment):
    lines = [comment, ""]
    for name, peaks in entries:
        lines.append(">NAME %s" % name)
        for i, (mz, inten) in enumerate(peaks):
            sep = "  " if i == 0 else " "   # real files mix spacing
            lines.append("%.4f%s%s" % (mz, sep, inten))
        lines.append("")
    with open(path, "w") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")

write_spectra("library.txt", LIBRARY, "# minimal text spectral library")

rnd = lcg(20260824)
queries = []
for qid, (name, peaks) in zip(("q1", "q2", "q3"), LIBRARY[:3]):
    out = []
    for mz, inten in peaks:
        jmz = mz + (next(rnd) - 0.5) * 0.2
        jint = inten * (0.75 + 0.5 * next(rnd))
        if jint < 12.0:            # low-intensity peaks are dropped
            continue
        out.append((jmz, round(jint, 1)))
    for _ in range(2):             # noise peaks
        out.append((round(60.0 + next(rnd) * 340.0, 4), round(3.0 + next(rnd) * 8.0, 1)))
    out.sort()
    queries.append((qid, out))

queries.append(("q4", [(90.2, 50.0), (131.1, 30.0), (176.1, 80.0),
                       (220.2, 25.0), (300.1, 60.0)]))

write_spectra("queries.txt", queries, "# query spectra")
print("wrote library.txt, queries.txt")
```

## Acceptance criteria

Run `python3 make_test_data.py`, then `python3 libsearch.py queries.txt library.txt -o results.tsv`, and check all of:

1. stdout prints exactly `queries: 4  called: 3  no_match: 1` (stdout, not stderr).
2. `results.tsv` is tab-separated, Unix newlines, exactly the 5 columns above in that order, 4 data rows sorted by `query_id`.
3. `q1` → best_match `caffeine`, score **0.9373** ± 0.001, matched_peaks **7**, total_library_peaks **8**.
4. `q2` → best_match `acetaminophen`, score **0.9113** ± 0.001, matched_peaks **7**, total_library_peaks **8**.
5. `q3` → best_match `sulfamethoxazole`, score **0.9583** ± 0.001, matched_peaks **8**, total_library_peaks **8**.
6. `q4` → best_match `NO_MATCH`, score **0.0000** ± 0.001 (below the 0.5 threshold).
7. Runner-up separation: for q1–q3 the second-best library score is < 0.03 (verified reference values: 0.0221 / 0.0247 / 0.0231) — your best match must not be a near-tie.

## If something fails

Score off by a constant factor → you normalized to base peak first (forbidden — the formula is already scale-invariant) or squared the sum twice. matched_peaks too high → you allowed a library peak to match more than one query peak. matched_peaks too low → you matched on exact m/z instead of ±0.5, or required both spectra's peaks to pair symmetrically. Wrong best match on q2/q3 → shared fragments (65.0, 92.0) dominate because you summed over matched peaks only in the denominator — `Σ Il` is over all peaks of the entry. q4 not NO_MATCH → threshold applied to the wrong score, or the comparison is `<=` instead of `<`.

## Optional

Report the top-3 per query with a reverse (library-to-query) dot product as a second column; parse real MassBank `.txt`/MSP records (`CH$NAME`, `PK$PEAK` blocks) as an alternate input format; ppm instead of Da tolerance; a dot-product with precursor-m/z prefilter.
