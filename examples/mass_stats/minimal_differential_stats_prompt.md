# Two-condition differential quantification

Standard library only — **no `scipy`, `numpy`, `statsmodels`, `pandas`**. Write `quant_stats.py`.

Input is any `feature_id` × samples CSV with `CTRL_*` / `EXP_*` columns (here 4 + 4). It is analyte-agnostic: `PEP_*` rows are peptides, `MET_*` metabolites, and nothing in the pipeline treats them differently.

`python3 quant_stats.py quant.csv -o results.tsv` writes, sorted by p ascending:

```
feature_id	log2FC	t	df	p_value	q_value	significant
```

Write it **tab-separated** (real `\t`, not commas) with Unix newlines, all seven columns in that exact order, `df` included, and `significant` as `1`/`0` (not `yes`/`no`). Also print the number tested, filtered (with IDs), and significant.

## Dependencies

None — the input is a plain feature-by-sample CSV, not a raw MS file.

## Data

`quant.csv` ships beside this prompt. It is the oracle: the numbers below hold
only for that exact file. Don't edit it.

## Pipeline

The standard minimal workflow — a toy Perseus/MSstats:

1. **Filter** — empty cells are missing values; require ≥ 3 valid values *per condition*, otherwise report the feature as filtered.
2. **Transform** — `math.log2` every valid value.
3. **Test** — Welch's two-sample t-test (unequal variances, sample variance with `n−1`), `log2FC = mean(EXP) − mean(CTRL)`.
4. **Correct** — Benjamini–Hochberg across the tested features → q-values (ranks start at 1; enforce monotonicity sweeping from the largest rank down; cap at 1.0).
5. **Call** — significant iff `q < 0.05` **and** `|log2FC| ≥ 1.0`.

**The one thing you can't import:** the two-sided p-value, `p = I_x(df/2, 1/2)` with `x = df/(df + t²)`, where `I_x` is the regularized incomplete beta function. Use this verbatim — do **not** try to derive the t-distribution integral yourself:

```python
def _betacf(a, b, x):
    FPMIN = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1.0)
    d = 1.0 / (FPMIN if abs(d) < FPMIN else d)
    h = d
    for m in range(1, 501):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((a - 1.0 + m2) * (a + m2)),
                   -(a + m) * (a + b + m) * x / ((a + m2) * (a + 1.0 + m2))):
            d = 1.0 + aa * d; d = FPMIN if abs(d) < FPMIN else d
            c = 1.0 + aa / c; c = FPMIN if abs(c) < FPMIN else c
            d = 1.0 / d; h *= d * c
        if abs(d * c - 1.0) < 3e-14:
            break
    return h

def betai(a, b, x):
    if x <= 0.0: return 0.0
    if x >= 1.0: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log(1.0 - x))
    return (bt * _betacf(a, b, x) / a if x < (a + 1.0) / (a + b + 2.0)
            else 1.0 - bt * _betacf(b, a, 1.0 - x) / b)
```

**Verify that core before going further** — both cases are hand-checkable, since each list has sample variance 5/3 and standard error `sqrt(2·(5/3)/4) = 0.912871`:

| call | log2FC | t | df | p |
|---|---|---|---|---|
| `ttest_welch([1,2,3,4], [3,4,5,6])` | +2.0 | 2.1909 | 6.0 | 0.070988 |
| `ttest_welch([1,2,3,4], [5,6,7,8])` | +4.0 | 4.3818 | 6.0 | 0.004659 |


## Acceptance criteria

1. **19 tested**; `MET_008` filtered (only 2 valid EXP values); `PEP_004` tested (3 valid CTRL values is enough).
2. Exactly **8 significant**: `PEP_001, PEP_003, PEP_005, PEP_006, MET_002, MET_004, MET_006, MET_007`.
3. log2FC within ±0.02 — PEP_001 +1.75 · PEP_003 −2.02 · PEP_005 +1.93 · PEP_006 −1.51 · MET_002 +2.37 · MET_004 −2.45 · MET_006 +1.45 · MET_007 −1.65.
4. Within 1% — PEP_001 p 3.72e-08, q 7.06e-07 · PEP_003 p 2.58e-03, q 7.00e-03 · MET_006 p 4.45e-03, q 1.06e-02 · PEP_011 (most null) p 0.963, q 0.963.
5. Nothing else is called significant — e.g. MET_001 (+0.34) and PEP_009 (−0.20) must have q > 0.05.
6. Output is tab-separated with all seven columns (including `df`) in the specified order, `significant` is `1`/`0`, and rows are sorted by `p_value` ascending.

## If something fails

Crash on `MET_008` / `PEP_004` → skip empty strings *before* `float()`/log2. Signs flipped → EXP − CTRL. t right, p wrong → incomplete-beta bug: re-run the two self-checks, and confirm `x = df/(df+t²)`, not `t²/(df+t²)`. p right, q wrong → BH: missing the monotone sweep, rank starting at 0, or using m = 20 instead of the 19 *tested*. Too many/few significant → both halves of the rule must apply to the same row.

## Optional

Median normalization across samples; a pooled-variance (Student) comparison; a top-5 volcano summary.
