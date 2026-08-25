# Task: Build a Minimal Two-Condition Differential Quantification Stats Tool (Python, standard library only)

You are a coding agent. Build a **minimal but statistically correct** differential-analysis tool in a single Python file `quant_stats.py`. It reads a quantification table (features × samples) for a two-condition experiment — **CTRL vs EXP, 4 replicates each** — and reports every feature that changed significantly between the conditions. The same code must work for **proteomics** (features = peptides/proteins, `PEP_*`) and **metabolomics** (features = metabolites, `MET_*`); nothing in the pipeline is analyte-specific.

**Hard constraint:** use only the Python standard library (`csv`, `math`, `argparse`). Do **not** use `scipy`, `numpy`, `statsmodels`, `pandas`, or any third-party package. The exact statistics you need — including how to compute a t-distribution p-value without scipy — are specified below.

---

## Background (the standard two-condition workflow)

For each quantified feature we ask: is the abundance different between CTRL and EXP beyond replicate noise? The standard minimal pipeline (a toy version of what Perseus / MSstats do):

1. **Log2-transform** the intensities (MS intensities are roughly log-normal; fold changes become additive: `log2FC = mean(log2 EXP) − mean(log2 CTRL)`).
2. **Welch's two-sample t-test** per feature (does not assume equal variances — the safe default for real data).
3. **Benjamini–Hochberg (BH) correction** across all tested features, because testing thousands of features at α = 0.05 would produce many false positives. The adjusted value is the **q-value**.
4. Call a feature **significant** when `q < 0.05` **and** `|log2FC| ≥ 1` (i.e. at least a 2-fold change). A p-value alone is not enough — a tiny but statistically rock-solid 5% change is usually not biologically interesting.

---

## Where the quant table comes from

`quant_stats.py` is deliberately analyte-agnostic: its input is any `feature_id × samples` CSV with `CTRL_*`/`EXP_*` columns. In the mini-tool series these tables are produced by the upstream tools:

- **Label-free MS1 quant (metabolomics or proteomics):** run `features.py` (MSFeature task) on each run's mzML, then join the per-run `features.tsv` files on (charge, m/z); the `area` column is the quant value.
- **Spectral counting (proteomics):** run `search.py` (MSSearch task) on each run, count PSMs per protein in each `psms.tsv`, and add a 0.5 pseudocount.

The combined-pipeline prompt (`minimal_analysis_pipeline_prompt.md`) exercises both paths end to end. For this task, test directly on the embedded `quant.csv` below.

## Step 1 — Parse the quantification table

CSV format: header row `feature_id` followed by one column per sample; sample names encode the condition (`CTRL_*` vs `EXP_*`). **Empty cells are missing values** — common in MS quant (a feature not detected in a run). Parse with the `csv` module.

Test file `quant.csv` (create it exactly like this; 20 features — 12 peptides, 8 metabolites — × 8 samples):

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

Note the missing values: `PEP_004` has 3 valid CTRL values, `MET_008` has only 2 valid EXP values.

## Step 2 — Filter and transform

- Keep a feature only if it has **≥ 3 valid (non-missing) values in each condition**; record skipped features as *filtered*. Here: `MET_008` must be filtered (only 2 EXP values), `PEP_004` must be kept (3 CTRL values are enough), so exactly **19 features are tested**.
- Log2-transform every valid value with `math.log2`.

## Step 3 — Welch's t-test per feature

For log2-transformed CTRL values `x` (n₁ values) and EXP values `y` (n₂ values), with sample means `m₁, m₂` and sample variances `s₁², s₂²` (divide by `n−1`):

```
t  = (m₂ − m₁) / sqrt(s₁²/n₁ + s₂²/n₂)
df = (a + b)² / (a²/(n₁−1) + b²/(n₂−1))     where a = s₁²/n₁, b = s₂²/n₂   (Welch–Satterthwaite)
```

`log2FC = m₂ − m₁`.

### Computing the two-sided p-value without scipy

The two-sided p-value for Welch's t is the regularized incomplete beta function:

```
p = I_x(df/2, 1/2)   with   x = df / (df + t²)
```

Implement `I_x(a, b)` (a.k.a. `betai`) with `math.lgamma` and a continued fraction (Lentz's method, from *Numerical Recipes*). Reference implementation — you may use it verbatim:

```python
import math

def _betacf(a, b, x):
    FPMIN = 1e-300
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1.0)
    d = FPMIN if abs(d) < FPMIN else d
    d = 1.0 / d
    h = d
    for m in range(1, 501):
        m2 = 2 * m
        aa = m * (b - m) * x / ((a - 1.0 + m2) * (a + m2))
        d = 1.0 + aa * d;  d = FPMIN if abs(d) < FPMIN else d
        c = 1.0 + aa / c;  c = FPMIN if abs(c) < FPMIN else c
        d = 1.0 / d;  h *= d * c
        aa = -(a + m) * (a + b + m) * x / ((a + m2) * (a + 1.0 + m2))
        d = 1.0 + aa * d;  d = FPMIN if abs(d) < FPMIN else d
        c = 1.0 + aa / c;  c = FPMIN if abs(c) < FPMIN else c
        d = 1.0 / d;  delta = d * c;  h *= delta
        if abs(delta - 1.0) < 3e-14:
            break
    return h

def betai(a, b, x):
    if x <= 0.0: return 0.0
    if x >= 1.0: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b

def ttest_welch(x, y):
    """x, y: lists of log2 values. Returns (log2FC, t, df, p_two_sided)."""
    n1, n2 = len(x), len(y)
    m1, m2 = sum(x) / n1, sum(y) / n2
    v1 = sum((v - m1) ** 2 for v in x) / (n1 - 1)
    v2 = sum((v - m2) ** 2 for v in y) / (n2 - 1)
    a, b = v1 / n1, v2 / n2
    t = (m2 - m1) / math.sqrt(a + b)
    df = (a + b) ** 2 / (a * a / (n1 - 1) + b * b / (n2 - 1))
    p = betai(df / 2.0, 0.5, df / (df + t * t))
    return m2 - m1, t, df, p
```

Self-check for your stats core: `ttest_welch([1,2,3,4], [3,4,5,6])` must return `t = 4.4721`, `df = 6.0`, `p ≈ 0.00419`.

## Step 4 — Benjamini–Hochberg q-values

For `m` tested features with p-values `p₁..pₘ`:

1. Sort p-values ascending: `p₍₁₎ ≤ ... ≤ p₍ₘ₎`.
2. Raw BH adjustment for rank `i`: `q₍ᵢ₎ = p₍ᵢ₎ × m / i`.
3. Enforce monotonicity from the top down: `q₍ᵢ₎ = min(q₍ᵢ₎, q₍ᵢ₊₁₎)` (walk ranks from `m` to `1`), and cap at 1.0.
4. Assign each q-value back to its feature.

## Step 5 — Significance call and output

A feature is **significant** iff `q < 0.05` **and** `|log2FC| ≥ 1.0`.

CLI: `python3 quant_stats.py quant.csv -o results.tsv`

Write a TSV sorted by p-value ascending, with header:

```
feature_id	log2FC	t	df	p_value	q_value	significant
```

Also print to stdout: number of features tested, number filtered (with their IDs), and number significant.

---

## How to test (acceptance criteria)

Run the exact command above against the embedded file. **All** of these must hold:

1. The program runs with no third-party packages and no errors.
2. **19 features tested**; `MET_008` reported as filtered (too few valid EXP values); `PEP_004` is tested despite its missing CTRL value.
3. Exactly **8 significant features**: `PEP_001, PEP_003, PEP_005, PEP_006, MET_002, MET_004, MET_006, MET_007`.
4. Direction and size of the changes (log2FC within ±0.02):

| feature | log2FC | feature | log2FC |
|---------|--------|---------|--------|
| PEP_001 | +1.75 | MET_002 | +2.37 |
| PEP_003 | −2.02 | MET_004 | −2.45 |
| PEP_005 | +1.93 | MET_006 | +1.45 |
| PEP_006 | −1.51 | MET_007 | −1.65 |

5. Spot-check p/q-values (within 1% relative): `PEP_001`: p ≈ 3.72e-08, q ≈ 7.06e-07 · `MET_006`: p ≈ 4.45e-03, q ≈ 1.06e-02 · `PEP_003`: p ≈ 2.58e-03, q ≈ 7.00e-03 · `PEP_011` (most null): p ≈ 0.963, q ≈ 0.963.
6. No null feature (any not in the list of criterion 3) is called significant — e.g. `MET_001` (log2FC ≈ +0.34) and `PEP_009` (log2FC ≈ −0.20) must have q > 0.05.
7. Rows are sorted by p-value ascending; every significant row has `significant=1`.

## If a test fails — debugging checklist

Work through these in order; fix the first thing that is wrong, then re-run:

1. **Crash on `MET_008` or `PEP_004`** → missing-value handling. Empty CSV cells are empty strings; skip them *before* `float()`/log2, then apply the ≥ 3-per-condition filter. Never log2 an empty cell.
2. **log2FC values all roughly correct but signs flipped** → convention: log2FC = mean(EXP) − mean(CTRL).
3. **log2FC off by a large factor** → you tested raw intensities instead of log2-transformed ones, or used `log10`/`ln` instead of `log2`.
4. **t correct but p wrong** → incomplete-beta bug. Run the self-check in Step 3 (`p ≈ 0.00419`); if that fails, check the `betai` symmetry branch (`x < (a+1)/(a+b+2)`) and that `math.lgamma` (not `lgamma` of `a*b` etc.) is used. Also confirm `x = df/(df+t²)`, not `t²/(df+t²)`.
5. **p correct but q wrong** → BH bug. Common causes: forgetting the monotone `min` sweep from rank m down to 1; using rank starting at 0 (ranks start at 1); multiplying by the wrong `m` (m = number of *tested* features = 19, not 20).
6. **PEP_004 missing from output or MET_008 present** → filter logic: require ≥ 3 valid values *per condition*; PEP_004 has 3 CTRL + 4 EXP (test it), MET_008 has 4 CTRL + 2 EXP (filter it).
7. **Too many/few significant** → the significance rule has two parts: `q < 0.05` AND `|log2FC| ≥ 1.0`. Check both are applied to the same row.
8. **Everything significant or nothing is** → you likely used `n` instead of `n−1` in the variance (or vice versa somewhere inconsistent), or pooled-variance (Student) formulas with the Welch df. Print intermediate `s₁², s₂², df` for `PEP_001` and compare against a hand calculation.

## Optional stretch goals (only after all acceptance criteria pass)

- Median-based normalization across samples before testing (subtract per-sample median log2 intensity offset).
- A Student (pooled-variance) t-test option side by side with Welch to compare calls.
- A plain-text "volcano summary": top 5 features by `−log10(q) × sign(log2FC)`.
- An `assert`-based `test_quant_stats.py` that runs the acceptance criteria automatically.
