# Standalone tool — Weighted calibration with internal standards

Standard library only — **no `numpy`, `scipy`, `pandas`, `statsmodels`**. Write `calibrate.py`.

`python3 calibrate.py standards.csv unknowns.csv -o results.tsv` reads a standards CSV (nominal concentration, analyte peak area, internal-standard peak area), fits a **weighted (1/x²) least-squares** calibration line, prints the line statistics and detection limits **to stdout**, and back-calculates the unknowns in `unknowns.csv` into `results.tsv` with % bias against their true values.

CSV parsing rules: skip blank lines and lines starting with `#`; the first remaining line is the header; fields are comma-separated. Real exports from instrument software are full of comment lines and unit-bearing headers — handle them.

## The parts you can't guess

Everything else is ordinary CSV I/O and arithmetic — this is the domain knowledge you will get wrong:

- **The response is the ratio, not the area.** For every point compute `y = analyte_area / is_area` first. All fitting is done on `y` vs nominal concentration `x`. Never fit analyte area directly, and never back-calculate analyte and IS separately.
- **Weighting is 1/x², not 1/y², and not unweighted.** Signals in LC–MS are heteroscedastic: absolute noise grows with concentration. The weight uses the *nominal* level:
  ```
  wᵢ = 1 / xᵢ²
  xw = Σwᵢxᵢ / Σwᵢ          yw = Σwᵢyᵢ / Σwᵢ
  slope     = Σ wᵢ(xᵢ−xw)(yᵢ−yw) / Σ wᵢ(xᵢ−xw)²
  intercept = yw − slope · xw
  ```
- **r² is the weighted r²:** `r² = 1 − Σwᵢ(yᵢ−ŷᵢ)² / Σwᵢ(yᵢ−yw)²` with `ŷᵢ = slope·xᵢ + intercept`.
- **σ for LOD/LOQ is the residual SD of the low standards**, not of all standards and not of raw replicates: take the residuals `rᵢ = yᵢ − ŷᵢ` at the **two lowest levels** (m = 6 points here) and `σ = sqrt(Σrᵢ² / (m−1))`. Then `LOD = 3.3·σ/slope`, `LOQ = 10·σ/slope` (ICH Q2).
- **Correction order for unknowns:** ratio first, then invert the line — `conc = (ratio − intercept) / slope`. `% bias = 100 · (calc − true) / true`.

## Test data generator — `make_cal_data.py`

```python
#!/usr/bin/env python3
"""Deterministic generator: 6 levels x 3 replicates, heteroscedastic noise, 3 unknowns."""
import math

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

def gauss(rnd):
    u1 = max(next(rnd), 1e-12)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * next(rnd))

SLOPE, INTERCEPT = 2.5, 0.03
LEVELS = [0.05, 0.20, 0.50, 1.00, 2.50, 5.00]
UNKNOWNS = [("UNK_1", 0.15), ("UNK_2", 1.20), ("UNK_3", 3.80)]

rnd = lcg(20260824)

def one_point(x):
    ratio = SLOPE * x + INTERCEPT
    is_area = 50000.0 * (1.0 + 0.04 * gauss(rnd))
    noise = gauss(rnd) * (0.012 * ratio + 0.0012)   # noise grows with level
    return is_area * (ratio + noise), is_area

lines = ["# calibration standards, generated synthetic", "# conc in ug/mL",
         "conc_ug_mL,analyte_area,is_area"]
for x in LEVELS:
    for rep in range(3):
        a, s = one_point(x)
        lines.append(f"{x:.2f},{a:.1f},{s:.1f}")
open("standards.csv", "w").write("\n".join(lines) + "\n")

lines = ["# unknown samples", "sample_id,analyte_area,is_area,true_conc_ug_mL"]
for sid, x in UNKNOWNS:
    a, s = one_point(x)
    lines.append(f"{sid},{a:.1f},{s:.1f},{x:.2f}")
open("unknowns.csv", "w").write("\n".join(lines) + "\n")
print("wrote standards.csv, unknowns.csv")
```

True line: slope 2.5, intercept 0.03. Noise is proportional to level (plus a small floor), which is exactly why the unweighted fit is wrong here.

## Verify your core before continuing

A 3-point weighted fit you can check by hand (multiply the weights 1, 1/4, 1/16 by 16 → 16, 4, 1):

| call | slope | intercept |
|---|---|---|
| `wls([1, 2, 4], [2.1, 4.0, 8.3])` | 2.0250 | 0.0571 |

If you get slope 2.0786 / intercept −0.0500 you forgot the weights — that is the unweighted answer. Do not write the rest of the tool until this matches.

## Acceptance criteria

Run `python3 make_cal_data.py`, then `python3 calibrate.py standards.csv unknowns.csv -o results.tsv`, and check all of:

1. Stdout is exactly six lines, `name<TAB>value` with 4 decimal places, in this order and nothing else: `slope`, `intercept`, `r2`, `sigma`, `LOD`, `LOQ`.
2. slope 2.5025 ± 0.02 · intercept 0.0276 ± 0.005 · r2 0.9998 ± 0.0005.
3. sigma 0.0046 ± 0.0005 · LOD 0.0060 ± 0.0007 · LOQ 0.0183 ± 0.0020 (all in µg/mL except sigma, which is in ratio units).
4. `results.tsv` is **tab-separated**, header exactly `sample_id	ratio	calc_conc_ug_mL	true_conc_ug_mL	bias_pct`, three rows in input-file order; `ratio` and `calc_conc_ug_mL` to 4 decimals, `bias_pct` signed with 2 decimals.
5. Recoveries: |bias| ≤ 5.0% for all three unknowns (reference: UNK_1 +0.43%, UNK_2 −0.33%, UNK_3 +0.49%; calc_conc ≈ 0.1506 / 1.1960 / 3.8186).
6. The self-check above reproduces slope 2.0250 / intercept 0.0571.

## If something fails

slope ≈ 2.4884 / intercept ≈ 0.0349 → you fit unweighted (see the 1/x² rule). slope right, sigma wrong → σ uses residuals about the fitted line at the two lowest levels with (m−1), not all 18 points and not raw-ratio SD. LOD/LOQ off by a fixed factor → the multipliers are 3.3 and 10, and you divide by slope. Biases huge or systematic → you inverted the line before forming the ratio, or used IS/analyte instead of analyte/IS. r² slightly off → it must be the weighted r² with weighted mean yw. Crash on the CSV → `#` comment lines and blank lines must be skipped before the header.

## Optional

A `--weight` flag comparing 1/x² vs unweighted side by side; replicate-averaged fit as a cross-check; bootstrap (via the LCG, not `random`) confidence interval on the slope; a residual-vs-concentration summary printed per level.
