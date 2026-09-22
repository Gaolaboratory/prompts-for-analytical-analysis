# Molecular formula assignment from accurate mass

Write `formula_finder.py`. Run: `python3 formula_finder.py measured_caffeine.tsv -o ranked.tsv`

Python standard library plus numpy, pandas and scipy only. No other third-party packages.

## Input

`measured_caffeine.tsv` is in the working directory: header `id	mass	M1	M2`, 4 rows.
`mass` is the neutral monoisotopic mass in Da (no proton, electron, or adduct correction
anywhere). `M1`/`M2` are the measured relative intensities of the first and second
isotope peaks, base peak (M) normalized to 1.0.

## Output

`ranked.tsv`: tab-separated, header `id	rank	formula	calc_mass	error_ppm	score`, one row
per candidate for every block, ranks starting at 1 within each block, blocks in input
order, each block sorted by `score` ascending. One line on stdout: `blocks=<n>
candidates=<n>`, where `candidates` is the total row count across every block.

## Method

- **Isotope table.** Use exactly these values, no others:

| element | isotope | mass (Da) | abundance (%) |
|---|---|---|---|
| H | 1H | 1.007825 | 99.9885 |
| H | 2H | 2.014102 | 0.0115 |
| C | 12C | 12.000000 | 98.93 |
| C | 13C | 13.003355 | 1.07 |
| N | 14N | 14.003074 | 99.636 |
| N | 15N | 15.000109 | 0.364 |
| O | 16O | 15.994915 | 99.757 |
| O | 17O | 16.999131 | 0.038 |
| O | 18O | 17.999160 | 0.205 |
| P | 31P | 30.973762 | 100.0 |
| S | 32S | 31.972071 | 94.99 |
| S | 33S | 32.971459 | 0.75 |
| S | 34S | 33.967867 | 4.25 |

- **Isotope-pattern approximation.** With `r1 = a1/a0`, `r2 = a2/a0` the abundance
  ratios against the monoisotope of the same element: `M1 = Σ n_e·r1_e` and
  `M2 = Σ n_e·r2_e + Σ n_e·(n_e−1)/2 · r1_e²` — first order in the rare isotopes plus
  the same-element pair term (two ¹³C, two ¹⁵N, …); cross-element second-order terms
  are neglected. Verify against `CO2` → 43.989830 / 0.011578 / 0.004110 and `CH4` →
  16.031300 / 0.011276 / 0.000000 before trusting anything downstream.
- **Enumeration.** Brute force over C 0–30, H 0–60, N 0–10, O 0–10, P 0–2, S 0–2 —
  zero counts allowed — keeping candidates with `|calc_mass − measured| ≤ 5 ppm`, an
  **inclusive** window at both ends (a candidate at exactly 5.000 ppm is kept). No
  valence, DBE, or nitrogen-rule filtering: the candidate count is set by the limits and
  the window alone.
- **Formula strings are Hill order:** C first (if present), then H, then the remaining
  elements alphabetically (N, O, P, S). Omit elements with count 0 and the count when
  it is 1: `C6H12O6`, `H14N6O4S`.
- **Score.** `score = |error_ppm| + 100·|M1_meas − M1_calc| + 100·|M2_meas − M2_calc|`,
  with `error_ppm = (calc_mass − measured)/measured·1e6`. Sort each block by `score`
  ascending; break ties by formula string ascending.

## Acceptance criteria

1. ranked.tsv: header + 4 blocks in input order, ranks starting at 1
2. rank-1 formula correct in all four blocks
3. every rank-1 row has |error_ppm| <= 2.0 and score <= 0.5
4. every rank-1 row beats its block runner-up by >= 5 score units
5. rank-1 calc_mass matches the reference recomputed from the input (<=1e-5 Da)
6. stdout reports blocks and candidates

Do not tune a constant to make a number match; if a criterion fails, the enumeration
or scoring is wrong.
