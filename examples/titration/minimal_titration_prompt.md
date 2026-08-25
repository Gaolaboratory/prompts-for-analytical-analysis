# Acid–base titration curve analysis

Standard library only — **no `numpy`, `scipy`, `pandas`**. Write two files: `titration.py` (the tool) and `make_test_data.py` (exactly the script below; run it to produce `titration.csv`).

`python3 titration.py titration.csv -o results.tsv` reads a potentiometric titration log — a weak monoprotic acid titrated with strong base — locates the equivalence point at the first-derivative maximum refined by parabolic interpolation, cross-checks it with the second-derivative zero crossing, and writes **one tab-separated data row**:

```
equivalence_volume_mL	equivalence_volume_d2_mL	pKa	analyte_concentration_M
```

The titrant is 0.1000 M strong base and the flask initially held 50.00 mL of analyte. Keep both as named constants at the top of `titration.py`.

## The parts you can't guess

- The equivalence point of a weak-acid/strong-base titration is **not** at pH 7 — here it sits near pH 8.73. Never search for a pH target; find the maximum of dpH/dV.
- Differentiate only the **smoothed** curve: a centered moving average with window 5 (the point itself plus two on each side, truncated to the points available near the edges). Raw electrode noise of ±0.02 pH explodes in a derivative and creates spurious maxima.
- Place each derivative value at the midpoint of its volume pair: `d1[i] = (sm[i+1]−sm[i]) / (V[i+1]−V[i])` at `x[i] = (V[i]+V[i+1])/2`.
- Refine the derivative maximum by parabolic interpolation. With `k` the index of the largest `d1`:

  ```
  delta = 0.5 * (d1[k-1] - d1[k+1]) / (d1[k-1] - 2*d1[k] + d1[k+1])
  Veq   = x[k] + delta * (x[k+1] - x[k])
  ```

- Cross-check with the second derivative: differentiate `(x, d1)` the same way, then find the sign change of `d2` **nearest the d1 maximum** and linearly interpolate its zero crossing. (Raw noise gives many sign changes away from the equivalence point; the nearest-to-max rule is what makes this robust.)
- pKa is the pH at the half-equivalence volume (Henderson–Hasselbalch: [HA] = [A−]). Read it by linear interpolation on the **raw, unsmoothed** curve at exactly `Veq/2` — not at half of the last volume.
- Analyte concentration is 1:1 stoichiometry: `C_a = C_b * Veq / V0`. Volumes in mL cancel; the result is in mol/L.
- Real electrode logs carry comment lines and units in the header. Skip lines starting with `#` and the column-header line; volumes have 2 decimals, pH 3 decimals, comma-separated, LF endings.

## Verify the refinement core before continuing

`refine((1.0, 3.0, 2.0))` on unit-spaced x must return `delta = 0.166667`, i.e. a refined position of `1.166667`. Hand-checkable: `0.5·(1−2)/(1−6+2) = 1/6`. Do not build the rest until this passes.

## Test data generator

Simulates the exact equilibrium of 50.00 mL of 0.1000 M weak acid (pKa 4.76) titrated with 0.1000 M NaOH: at total volume `V = V0 + v` the analytical concentrations are `ca = CA·V0/V` and `cb = CB·v/V`, and `[H+]` solves the charge balance

```
h + cb = Kw/h + ca*Ka/(Ka + h)
```

by bisection in h between 1e-14 and 1. pH noise of ±0.02 comes from a seeded LCG — never the `random` module.

```python
#!/usr/bin/env python3
"""Deterministic weak-acid/strong-base titration curve generator. Std-lib only."""
import math

KA = 10.0 ** (-4.76)   # pKa = 4.76 (acetic-acid-like)
KW = 1.0e-14
CA = 0.1000            # mol/L analyte in the flask
V0 = 50.00             # mL analyte
CB = 0.1000            # mol/L strong-base titrant

def ph_at(v_ml):
    V  = V0 + v_ml
    ca = CA * V0 / V
    cb = CB * v_ml / V
    def f(h):                      # charge balance, root in h
        return h + cb - KW / h - ca * KA / (KA + h)
    lo, hi = 1e-14, 1.0
    for _ in range(200):
        mid = math.sqrt(lo * hi)   # geometric bisection, h spans 14 decades
        if f(mid) > 0.0: hi = mid
        else:            lo = mid
    return -math.log10(math.sqrt(lo * hi))

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

rnd = lcg(20260824)
N = 50
lines = ["# pH titration log, electrode E-201, 25.0 C",
         "titrant_volume_mL,pH"]
for i in range(N):
    v = round(75.0 * i / (N - 1), 2)
    noise = (next(rnd) - 0.5) * 0.04        # ±0.02 pH
    lines.append(f"{v:.2f},{ph_at(v) + noise:.3f}")
open("titration.csv", "w").write("\n".join(lines) + "\n")
print("wrote titration.csv: 50 points, Veq = 50.00 mL")
```

## Acceptance criteria

Run `python3 make_test_data.py`, then `python3 titration.py titration.csv -o results.tsv`, and check all of:

1. `titration.csv` has one `#` comment line, the header `titrant_volume_mL,pH`, and exactly **50** data rows; first row `0.00,2.892`, last row `75.00,12.283`.
2. Generator kernel: `ph_at(25.00)` = 4.7605 ± 0.0001 (the hand-check: pH at half-equivalence ≈ pKa) and `ph_at(50.00)` = 8.7295 ± 0.0001.
3. `results.tsv` has the header above plus exactly **one** data row, **tab**-separated (real `\t`, LF endings), four columns in that exact order.
4. `equivalence_volume_mL` = 50.00 ± 0.50 mL.
5. `equivalence_volume_d2_mL` agrees with `equivalence_volume_mL` within 0.20 mL.
6. `pKa` = 4.76 ± 0.05.
7. `analyte_concentration_M` = 0.1000 ± 0.0020 (recovery within 2%).
8. The tool prints exactly one summary line **to stdout** containing the point count and all four results; reference values (last digit may differ): `points=50 Veq=50.245 Veq_d2=50.245 pKa=4.761 conc=0.10049`.

## If something fails

Crash on line 1 → you parsed the `#` comment or the header as data. Veq sitting on a sampled point (multiples of 1.53 mL) → missing parabolic refinement. d2 volume wildly different from d1 → you differentiated the raw curve, or took a far-away sign change instead of the one nearest the d1 maximum. pKa off by more than 0.05 → you interpolated at half the last volume (37.5 mL) instead of `Veq/2`. Concentration off by 2× or 0.5× → the ratio is `C_b·Veq/V0`, in that order. Veq found at pH 7 → you searched for a pH target; the weak-acid equivalence point is near pH 8.73 and only the derivative maximum locates it.

## Optional

Gran plot: pre-equivalence points give a straight line `V·10^(−pH)` vs `V` whose x-intercept is Veq — report it as a third estimate. A hand-rolled 5-point quadratic (Savitzky–Golay) smoother instead of the boxcar. CLI flags `--titrant-conc` / `--sample-vol` overriding the constants. Diprotic-acid support reporting two equivalence volumes.
