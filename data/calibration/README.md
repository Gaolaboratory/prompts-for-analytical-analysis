# Calibration validation data (tier c)

## Source

NIST/ITL Statistical Reference Datasets (StRD) — Linear Least Squares Regression, dataset **Norris** (`Norris.dat`).

- Raw data file (working URL, HTTP 200, direct download):
  https://www.itl.nist.gov/div898/strd/lls/data/LINKS/DATA/Norris.dat
- Certified values page (working URL, HTTP 200, direct download):
  https://www.itl.nist.gov/div898/strd/lls/data/LINKS/v-Norris.shtml
- Certification method and definitions:
  https://www.itl.nist.gov/div898/strd/lls/data/LINKS/c-Norris.shtml
- Download date: 2026-08-26

Note: the shorter URL https://www.itl.nist.gov/div898/strd/lls/data/Norris.dat no longer serves the file — it redirects (HTTP 200 via redirect) to the NIST ITL landing page https://www.nist.gov/itl. The `LINKS/DATA/` path above is the working location.

License/access: the StRD is published by the National Institute of Standards and Technology (US DOC). As works of the US federal government, the dataset and certified values are in the public domain in the United States (17 U.S.C. § 105); NIST states no copyright is claimed. Freely accessible over HTTPS, no registration or authentication required.

## Contents

- `norris.csv` — 36 data rows plus a `y,x` header (37 lines total), columns in the file's native order (response `y` first, predictor `x` second), numeric tokens transcribed verbatim from `Norris.dat` lines 61–96.
- What it is: Norris's calibration study of ozone monitors (Norris, J., NIST, "Calibration of Ozone Monitors"). One response variable, one predictor variable, 36 observations, observed (not simulated) data, "lower level of difficulty" for the StRD linear-least-squares suite. NIST certifies it for the model `y = B0 + B1*x + e`.

## Expected results

NIST certified values for the **unweighted** linear least-squares kernel on this data (exact digit strings from the certified-values page):

| Quantity | Certified value |
| --- | --- |
| Slope B1 | 1.00211681802045 |
| Intercept B0 | −0.262323073774029 |
| Residual standard deviation | 0.884796396144373 |
| R-squared | 0.999993745883712 |

Supporting certified statistics (same page): SD of slope estimate 0.429796848199937E-03, SD of intercept estimate 0.232818234301152, residual SS 26.6173985294224 on 34 df (MSE 0.782864662630069), regression SS 4255954.13232369 on 1 df, F = 5436385.54079785.

These certify the unweighted least-squares kernel. The tool under test runs its weighted kernel with w = 1 for every observation, which is algebraically identical to unweighted OLS, so its slope/intercept/residual SD/R² must reproduce the certified values (to within numerical precision; an independent std-lib OLS recomputation from this CSV agrees to ≤ 1.3e-14).

## How obtained

Downloaded with `curl -sL` on 2026-08-26 from the two working URLs above (the short data URL was tried first and rejected because it redirects to an HTML landing page; no third-party mirror was needed). The CSV was written from the raw data, not retyped:

```sh
curl -sL "https://www.itl.nist.gov/div898/strd/lls/data/LINKS/DATA/Norris.dat" -o Norris.dat
# the file's own header documents: Data (lines 61 to 96)
awk 'NR>=61 && NR<=96 { sub(/\r$/,""); if (NF==2) print $1 "," $2 }' Norris.dat > norris.csv
# then the single header line "y,x" was prepended
```

Verified: 36 data rows, all numeric, and an independent Python 3 std-lib OLS (closed-form, no external packages) reproduces all four certified values to ~1e-14.
