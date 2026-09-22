# Linear calibration curve — fit, R² and detection limits

Write `calibrate.py`. Run: `python3 calibrate.py norris.csv -o results.tsv`

Python standard library plus numpy, pandas and scipy only. No other third-party packages.

## Input

`norris.csv` is in the working directory: header `y,x`, 36 rows. `y` is the measured
response and `x` is the prepared concentration, so the regression is **y on x**.

## Output

`results.tsv`: a header line plus exactly one tab-separated data row, LF endings:

```
slope	intercept	residual_sd	r_squared	lod	loq
```

One line on stdout: `n=<n> slope=<x> intercept=<x> residual_sd=<x> r_squared=<x> lod=<x> loq=<x>`

## Method

- Unweighted ordinary least squares of y on x. A weighted kernel with unit weights is
  algebraically identical to unweighted OLS, so do not add weights.
- Residual standard deviation uses **n − 2** degrees of freedom, not n or n − 1.
- R² is `1 − SS_res/SS_tot`, with SS_tot taken about the mean of y.
- `lod = 3.3 · residual_sd / slope` and `loq = 10 · residual_sd / slope`, in that order,
  and both on the concentration scale (x).
- Print slope, intercept, residual_sd and r_squared to at least 9 significant figures.

## Acceptance criteria

1. `results.tsv`: header + exactly one data row, columns in order, no CR.
2. slope and intercept match the NIST certified values (<=1e-9 relative).
3. residual_sd and r_squared match the NIST certified values (<=1e-9 relative).
4. lod and loq match the reference recomputed from norris.csv (<=1e-6 relative).
5. stdout reports all seven fields.
6. re-running calibrate.py on a perturbed norris.csv reproduces the reference fit for
   that input.

Do not tune a constant to make a number match; if a criterion fails, the fit is wrong.
