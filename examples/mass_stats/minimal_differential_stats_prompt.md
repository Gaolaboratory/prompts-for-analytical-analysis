# Task 4/4 — Two-condition differential quantification

Standard library only — **no `scipy`, `numpy`, `statsmodels`, `pandas`**. Write `quant_stats.py`.

Input is any `feature_id` × samples CSV with `CTRL_*` / `EXP_*` columns (here 4 + 4). It is analyte-agnostic: `PEP_*` rows are peptides, `MET_*` metabolites, and nothing in the pipeline treats them differently. In the wider series such tables come from task 3 (MS1 areas joined across runs) or task 2 (PSM counts per protein). Test on `quant.csv` below.

`python3 quant_stats.py quant.csv -o results.tsv` writes, sorted by p ascending:

```
feature_id	log2FC	t	df	p_value	q_value	significant
```

Write it **tab-separated** (real `\t`, not commas) with Unix newlines, all seven columns in that exact order, `df` included, and `significant` as `1`/`0` (not `yes`/`no`). Also print the number tested, filtered (with IDs), and significant.

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

## Test data — `quant.csv`

```csv
feature_id,CTRL_1,CTRL_2,CTRL_3,CTRL_4,EXP_1,EXP_2,EXP_3,EXP_4
PEP_001,457144.8,484198.1,478742.7,433847.0,1517463.9,1651378.7,1505301.5,1575561.0
PEP_002,777163.1,749462.7,543774.8,841718.4,792340.9,791302.6,541395.9,536490.6
PEP_003,1102341.9,2141494.0,2232411.1,1775093.0,392532.3,441504.8,448695.6,444440.2
PEP_004,6664952.7,7447176.8,5435297.8,,5701852.2,5941540.2,6752688.4,6318355.5
PEP_005,2490793.7,3046247.3,2421142.1,2586440.5,9030747.8,13312605.7,9531564.9,8779409.4
PEP_006,1117465.4,1498399.8,1555400.7,1375070.9,531510.0,482383.1,378314.2,562834.5
PEP_007,144964.3,152746.1,131697.8,117768.3,110858.1,130154.1,137168.9,194686.7
PEP_008,1496390.7,1613966.0,2212381.0,1244393.2,1374554.5,1844498.0,2272417.4,1956146.9
PEP_009,3270369.6,2338076.2,2285055.5,2802062.0,2328395.8,2295610.5,2140849.8,2431100.1
PEP_010,165361.9,139656.5,137248.3,137941.9,95597.7,156651.6,148031.2,137509.5
PEP_011,1750429.2,1113133.8,1512088.0,1241089.1,1198197.7,1498526.5,1909969.2,1032178.1
PEP_012,160096.7,169370.7,154523.4,184566.6,134942.1,140838.6,181271.0,152037.4
MET_001,343166.0,426931.3,470588.3,418207.6,418970.8,426206.3,720895.6,574672.4
MET_002,6161723.8,3975418.8,4321186.5,5525357.0,27672094.4,26408637.1,24159078.9,23324535.4
MET_003,226544.7,238610.1,209300.2,208813.7,218509.1,222616.5,203250.7,214862.8
MET_004,7760729.2,7835105.2,8338651.2,9808527.7,1493761.2,1692958.9,2177112.2,1015310.2
MET_005,807170.8,874839.1,986056.4,954939.9,842562.2,1200861.3,885701.2,896414.8
MET_006,11613724.2,12566002.6,12294295.8,12646187.6,24155748.9,35619398.7,46156386.9,31650918.2
MET_007,259929.1,301380.7,287118.7,225616.5,82351.9,68748.3,84456.0,109388.5
MET_008,18635862.1,12008249.7,17371221.6,11915810.9,15909350.3,18981255.1,,
```

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
