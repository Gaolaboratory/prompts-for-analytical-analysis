# UV-Vis spectrum processing

Standard library only — **no `numpy`, `scipy`, or `pandas`**. Write `uvvis.py`.

Read a UV-Vis spectrum CSV (`wavelength_nm,absorbance`, one point per nm), subtract a linear
baseline anchored on two stated edge regions, smooth with a 5-point Savitzky–Golay filter, pick
the absorption bands (lambda_max, A_max), and compute the analyte concentration from a stated
molar absorptivity via Beer–Lambert `A = epsilon * c * l`.

`python3 uvvis.py sample.csv -o peaks.tsv` — write the band table, sorted by wavelength:

```
band	lambda_max_nm	a_max
```

Also print **to stdout** (not stderr) `bands: <n>` and `concentration_uM: <value>` (`%.1f`).

## Dependencies

None — this is a base module. Other prompts depend on it.

## Data

Run `python3 make_uvvis_data.py` (shipped beside this prompt) to write `sample.csv`. It is the
oracle: the numbers below hold only for its exact output. Don't edit it and
don't generate the data any other way.

## The parts you can't guess

Everything else is ordinary CSV work — this is the domain knowledge and the exact conventions:

- **CSV quirks.** Real instrument exports prepend `#` comment lines before the column header.
  Skip lines starting with `#`, and skip any line whose first comma-field is not numeric
  (the header). Data lines are `lambda,absorbance`, ascending, 1 nm apart.
- **Baseline.** Anchor 1 = mean absorbance over 200–215 nm, attached at the interval midpoint
  207.5 nm; anchor 2 = mean over 780–800 nm at 790.0 nm. Subtract the straight line through the
  two anchors. This removes slope but only approximately removes curvature — that residual is
  expected and already priced into the tolerances below.
- **Smoothing.** Savitzky–Golay, window 5, polynomial order 2. The convolution coefficients for
  offsets −2..+2 are — use them verbatim, divide by 35, and do **not** re-derive them:

  ```
  (-3, 12, 17, 12, -3) / 35
  ```

  Apply to interior points only; copy the first and last two points through unchanged.
- **Band picking.** On the baseline-corrected **and smoothed** trace: a band is a point with
  `A[i] > A[i-1]`, `A[i] >= A[i+1]`, and `A[i] >= 0.20`. Merge picked maxima closer than 40 nm,
  keeping the higher one. The 0.20 floor matters: overlapping bands leave a valley shoulder near
  0.13 that a lower threshold reports as a phantom band.
- **Quantitation.** Quantify the band nearest 420 nm. `epsilon = 26000 L mol^-1 cm^-1`,
  `l = 1.0 cm`; `c = A_max / (epsilon * l)`, reported in µmol/L.

## Verify your core before continuing

Run your SG routine on these two known inputs and compare — both are hand-checkable
(17/35 = 0.485714, 12/35 = 0.342857):

| call | output |
|---|---|
| `sg_smooth([3,5,7,9,11,13,15])` | `[3, 5, 7, 9, 11, 13, 15]` (a ramp passes through unchanged) |
| `sg_smooth([0,0,0,1,0,0,0])` | `[0, 0, 0.342857, 0.485714, 0.342857, 0, 0]` |

Do not continue until both match.


## Acceptance criteria

Run `python3 make_uvvis_data.py`, then `python3 uvvis.py sample.csv -o peaks.tsv`, and check:

1. stdout shows exactly `bands: 3` and `concentration_uM: 48.8` — on stdout, not stderr.
2. `peaks.tsv` has exactly 3 data rows under the header `band	lambda_max_nm	a_max`,
   **tab-separated** with Unix newlines, rows sorted by `lambda_max_nm` ascending,
   `lambda_max_nm` an integer, `a_max` formatted `%.4f`.
3. `lambda_max_nm` within ±2 nm of **320 / 420 / 540**.
4. `a_max` within ±0.02 of **0.8803 / 1.2677 / 0.6691** (band order as above).
5. `concentration_uM` within 5% of the true 50.0 µmol/L.
6. No fourth band is reported — in particular nothing near 481 nm.

Reference output (last digit may differ): `1  320  0.8803` · `2  419  1.2677` · `3  541  0.6691`.

## If something fails

4 bands, one near 481 nm → threshold below 0.20, or you picked peaks before smoothing. 2 bands →
merge window too wide or you dropped endpoints. `a_max` ~0.8 too high → baseline not subtracted.
`a_max` off by ~0.03 → anchors attached at interval edges (200/800) instead of midpoints
(207.5/790.0). `lambda_max` jittering run-to-run → you picked peaks on the noisy raw trace.
Crash on the first lines → `#` comments and the non-numeric header must be skipped. Concentration
1000× off → `epsilon` is per mole; convert to µmol/L. SG self-check wrong → coefficient order is
offsets −2..+2, and don't forget the `/35`.

## Optional

Report concentrations for all bands with per-band `epsilon`; detect shoulders via a
second-derivative sign change; compare against a rubberband baseline; run on a real spectrum
(e.g. from the AIST SDBS database) and check lambda_max against the literature value.
