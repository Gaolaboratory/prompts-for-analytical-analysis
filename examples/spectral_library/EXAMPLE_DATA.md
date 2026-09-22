# Example data & expected results — spectral_library

**Dataset:** a real 5-entry MS/MS library (caffeine, acetaminophen, sulfamethoxazole, ketamine,
nicotine) and 4 real queries — q1–q3 are *different records* (other instrument/collision energy)
of library compounds, q4 (theophylline) is absent from the library
(`data/spectral/library.txt`, `data/spectral/queries.txt`). Accessions, conversion rules, and
licenses: `data/spectral/README.md`.

**Run:** `python3 libsearch.py queries.txt library.txt -o results.tsv` (format matches the
prompt's spec).

**Expected results (verified by a harness-side reference implementation of the prompt's scorer
— real same-compound different-CE scores are lower than the synthetic criteria):**

| query | best match | score | note |
|---|---|---|---|
| q1 | caffeine | 0.7473 (6/7) | > 0.5 threshold; runner-up ≤ 0.084 |
| q2 | sulfamethoxazole | 0.6669 (4/6) | > 0.5 |
| q3 | nicotine | 0.8706 (6/8) | > 0.5 |
| q4 | NO_MATCH | 0.0138 | below 0.5 |

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/spectral/local/tierc/`, 10 iterations): q1 caffeine 0.7473 (6/7), q2
sulfamethoxazole 0.6669 (4/6), q3 nicotine 0.8706 (6/8), q4 NO_MATCH 0.0138 (2/6) — **PASS**,
every score matches the reference to the fourth decimal.
