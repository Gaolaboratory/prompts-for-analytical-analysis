# Example data & expected results — calibration

**Dataset:** NIST StRD *Norris* linear-regression benchmark — 36 observations from Norris's
ozone-monitor calibration study (`data/calibration/norris.csv`, columns `y,x`). Full provenance,
license, and certified-values citation: `data/calibration/README.md`.

**Run (after writing `calibrate.py` from the prompt):** apply the tool's weighted least-squares
kernel **with all weights = 1 (unweighted mode)** to `norris.csv`, regressing y on x, and report
slope, intercept, residual SD about the fit, and unweighted R² to ≥9 significant digits.

**Expected results (NIST certified values — certify the unweighted LS kernel):**

| slope | intercept | residual SD | R² |
|---|---|---|---|
| 1.00211681802045 | −0.262323073774029 | 0.884796396144373 | 0.999993745883712 |

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/calibration/local/tierc/`, 17 iterations): n=36, slope 1.00211682, intercept
−0.262323074, residual SD 0.884796396, R² 0.999993746 — **PASS**, all four values match the
certified values to 9 significant figures (the agent also hand-verified its OLS and demonstrated
that fitting unweighted *synthetic* data reproduces the documented 2.4884/0.0349 failure mode).
