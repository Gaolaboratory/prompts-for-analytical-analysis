# Elemental composition assignment from accurate mass

Standard library only — **no `numpy`, `scipy`, `pyteomics`, `periodictable`**. Write two files:

- `formula_finder.py` — the tool specified below.
- `make_test_data.py` — exactly the script below; run it to produce `measured.tsv`.

`python3 formula_finder.py measured.tsv -o ranked.tsv` reads measured neutral monoisotopic masses together with the M+1 and M+2 isotope intensities (relative to M = 1.0), enumerates every elemental composition within 5 ppm by brute force, simulates each candidate's isotope pattern, and writes all candidates ranked by a combined mass-plus-isotope score:

```
id	formula	calc_mass	error_ppm	M1_calc	M2_calc	score
```

One block of rows per input compound, blocks in input order, each block sorted by `score` ascending.

## The parts you can't guess

Everything else is ordinary parsing and looping — this is the domain knowledge you need:

- **Isotope table.** Complete for the element set — use exactly these values, no others:

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

(36S at 0.01% abundance is deliberately omitted. Do not add elements or isotopes beyond this table.)

- **Isotope-pattern approximation.** With M normalized to 1.0, and `r1 = a1/a0`, `r2 = a2/a0` the abundance ratios against the monoisotope of the same element: `M1 = Σ n_e·r1_e` and `M2 = Σ n_e·r2_e + Σ n_e·(n_e−1)/2 · r1_e²`. That is: first order in the rare isotopes, plus the same-element pair term (two 13C, two 15N, …); cross-element second-order terms are neglected. Generator and tool must use this identical formula.
- **Formula strings are Hill order:** C first (if present), then H, then the remaining elements alphabetically (N, O, P, S). Omit elements with count 0 and the count when it is 1: `C6H12O6`, `C5H11NO2S`, `H14N6O4S`.
- **Neutral masses.** Inputs are neutral monoisotopic masses — no proton, electron, or adduct corrections anywhere.
- **Enumeration.** Brute force over C 0–30, H 0–60, N 0–10, O 0–10, P 0–2, S 0–2 — zero counts allowed (C-free candidates such as `H14N6O4S` are valid) — keeping candidates with `|calc_mass − measured| ≤ 5 ppm` (window inclusive at both ends). **No valence, DBE, or nitrogen-rule filtering**: the candidate count is pinned by the limits and the window alone.
- **Score.** `score = |error_ppm| + 100·|M1_meas − M1_calc| + 100·|M2_meas − M2_calc|`, with `error_ppm = (calc_mass − measured)/measured·1e6`.

**Verify the core before continuing** — `pattern()` on these two formulae (both hand-checkable from the table):

| call | mass | M1 | M2 |
|---|---|---|---|
| `CO2` | 43.989830 | 0.011578 | 0.004110 |
| `CH4` | 16.031300 | 0.011276 | 0.000000 |

## Test data generator

```python
#!/usr/bin/env python3
"""Deterministic generator for formula_finder test data. Std-lib only."""
# isotope table: element -> [(mass, abundance %), ...], monoisotopic first
ISO = {
 "C": [(12.000000, 98.93), (13.003355, 1.07)],
 "H": [(1.007825, 99.9885), (2.014102, 0.0115)],
 "N": [(14.003074, 99.636), (15.000109, 0.364)],
 "O": [(15.994915, 99.757), (16.999131, 0.038), (17.999160, 0.205)],
 "P": [(30.973762, 100.0)],
 "S": [(31.972071, 94.99), (32.971459, 0.75), (33.967867, 4.25)],
}
TRUE = [("CPD1", {"C":6,"H":12,"O":6}),            # glucose
        ("CPD2", {"C":8,"H":10,"N":4,"O":2}),      # caffeine
        ("CPD3", {"C":5,"H":11,"N":1,"O":2,"S":1})] # methionine

def pattern(counts):
    mass = sum(ISO[e][0][0]*n for e, n in counts.items())
    m1 = m2 = 0.0
    for e, n in counts.items():
        a = ISO[e]
        if len(a) > 1:
            r1 = a[1][1]/a[0][1]
            m1 += n*r1; m2 += n*(n-1)/2.0*r1*r1
        if len(a) > 2:
            m2 += n*a[2][1]/a[0][1]
    return mass, m1, m2

def lcg(state):
    while True:
        state = (1103515245*state + 12345) % 2147483648
        yield state/2147483648.0

rnd = lcg(20260824)
lines = ["id\tmass\tM1\tM2"]
for cid, counts in TRUE:
    m, m1, m2 = pattern(counts)
    m  += (2*next(rnd)-1) * 2.5*m/1e6       # +/-2.5 ppm mass error
    m1 *= 1 + (2*next(rnd)-1)*0.04          # +/-4% relative isotope noise
    m2 *= 1 + (2*next(rnd)-1)*0.04
    lines.append(f"{cid}\t{m:.4f}\t{m1:.6f}\t{m2:.6f}")
open("measured.tsv", "w").write("\n".join(lines) + "\n")
print("wrote measured.tsv")
```

`measured.tsv` is a tab-separated file with header `id	mass	M1	M2` and three data rows.

## Acceptance criteria

Run `python3 make_test_data.py`, then `python3 formula_finder.py measured.tsv -o ranked.tsv`, and check all of:

1. The self-check above matches: `CO2` → 43.989830 / 0.011578 / 0.004110 and `CH4` → 16.031300 / 0.011276 / 0.000000 (mass, M1, M2; ±1e-6).
2. Prints `CPD1: 7 candidates`, `CPD2: 10 candidates`, `CPD3: 2 candidates` — one line per compound, in input order, **on stdout, not stderr**.
3. `ranked.tsv` is **tab-separated** (real `\t`, not commas) with Unix newlines: the header `id	formula	calc_mass	error_ppm	M1_calc	M2_calc	score` plus exactly **19** data rows — 7 for CPD1, then 10 for CPD2, then 2 for CPD3, blocks in input order, each block sorted by `score` ascending (ties by formula string ascending).
4. First row of each block: CPD1 `C6H12O6` calc_mass 180.063390, score 1.2763 ± 0.001 · CPD2 `C8H10N4O2` calc_mass 194.080376, score 2.1369 ± 0.001 · CPD3 `C5H11NO2S` calc_mass 149.051050, score 2.5581 ± 0.001.
5. Every top hit has `|error_ppm| ≤ 5.0` and `|M1_meas − M1_calc| ≤ 0.005`, `|M2_meas − M2_calc| ≤ 0.005` against the values in `measured.tsv`.
6. Column formats: `calc_mass` 6 decimals, `error_ppm` 3 decimals with explicit sign (`+1.937`), `M1_calc`/`M2_calc` 6 decimals, `score` 4 decimals. `formula` strings in Hill order as specified above.

## If something fails

Self-check off → you divided by the wrong abundance (`r1 = a1/a0` within one element) or used mass numbers as abundances. Candidate counts off → window not inclusive, wrong limits, or you filtered by valence/DBE — the count is set by the limits and the 5 ppm window alone. True formula not first → missing the same-element pair term in M2 (watch C6H12O6, where the two-13C term dominates M2), or score weights other than 1/100/100. Counts right but order wrong → sort by score, not by mass error. Comma-separated output or `yes`/`no`-style encodings → re-read criteria 3 and 6.

## Optional

Exact isotope simulation by polynomial convolution instead of the first-order approximation; a `--ppm` flag overriding the 5 ppm default; a DBE column (computed, not used for filtering); an `[M+H]+` input mode subtracting the proton mass 1.007276.
