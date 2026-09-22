# Example data & expected results — formula_finder

**Dataset:** 4 real measured-mass inputs derived from MassBank records (caffeine, acetaminophen,
sulfamethoxazole, AMPA) — `data/formula/measured_caffeine.tsv` (id, mass, M1, M2). M1/M2 are
computed from each record's CH$FORMULA with the prompt's own first-order isotope model (MS2
records carry no isotope intensities — see `data/formula/README.md` for the full rationale,
accessions, and licenses).

**Run:** `python3 formula_finder.py measured_caffeine.tsv -o ranked.tsv` (constants unchanged).

**Expected results (each record's own annotated CH$FORMULA, rank 1; error_ppm reflects the
records' published mass rounding):**

| id | rank-1 formula | published mass | expected error_ppm |
|---|---|---|---|
| CAFFEINE | C8H10N4O2 | 194.0804 | ≈ −0.12 |
| ACETAMINOPHEN | C8H9NO2 | 151.0633 | ≈ +0.19 |
| SULFAMETHOXAZOLE | C10H11N3O3S | 253.0521 | ≈ +0.05 |
| AMPA | CH6NO3P | 111.00853 | ≈ +0.01 |

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/formula/local/tierc/`, 10 iterations): all four true formulae ranked #1 with
errors −0.124 / +0.192 / +0.051 / +0.009 ppm and scores 0.12 / 0.19 / 0.05 / 0.01 — **PASS
4/4**, matching a harness-side reference enumeration exactly.
