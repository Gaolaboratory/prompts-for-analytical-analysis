# PCA of an untargeted feature table

Standard library only — **no `numpy`, `scipy`, `pandas`, `sklearn`**. Write `pca.py`.

Read a feature-by-sample CSV (header `feature_id,<sample names…>`, one feature per row, empty cells are missing values), keep features with ≥ 80% valid values, impute the rest, log2-transform, mean-center each feature (**no** unit-variance scaling — this is covariance PCA, not correlation PCA), and extract the top 2 principal components by power iteration with deflation. Print feature counts and variance fractions to stdout, and write a scores table and a loadings table.

```
python3 pca.py features.csv -o scores.tsv --loadings loadings.tsv
```

## The parts you can't guess

Preprocessing, in this exact order:

1. **Filter** — keep a feature only if it has a valid (non-empty) value in ≥ 80% of samples (≥ 8 of 10 here). Decide filtering *before* imputation.
2. **Impute** — fill each remaining missing cell with the feature's mean over its *valid* values, in the **linear** scale (before log2).
3. **Transform** — `math.log2` every value.
4. **Center** — subtract the per-feature mean (mean over samples). Do **not** divide by the per-feature standard deviation.
5. **Covariance** — with `X` the `n × p` matrix (10 samples × p kept features, centered): `C = Xᵀ·X / (n − 1)`, a `p × p` matrix. Variance fraction of a PC is its eigenvalue divided by `trace(C)` (the sum of the diagonal, i.e. total variance).

Power iteration with deflation — use this kernel, verbatim; do not substitute a Jacobi or analytic solver:

```python
def top_eigenpair(C):
    n = len(C)
    v = [1.0 / math.sqrt(n)] * n          # deterministic start
    lam_prev = 0.0
    for _ in range(10000):
        w = [sum(C[i][j] * v[j] for j in range(n)) for i in range(n)]
        lam = math.sqrt(sum(x * x for x in w))   # v stays unit, so lam = |Cv|
        v = [x / lam for x in w]
        if abs(lam - lam_prev) <= 1e-12 * max(1.0, lam):
            break
        lam_prev = lam
    return lam, v

# PC1 = top_eigenpair(C); then deflate and repeat for PC2:
#     C[i][j] -= lam * v[i] * v[j]        # for all i, j
```

Scores are `X·v` (length n); loadings are `v` (length p, one per kept feature). **Sign convention:** eigenvectors are only defined up to sign, so flip `v` (scores *and* loadings together) whenever the first sample's score is negative — the first sample's PC1 and PC2 scores must come out positive.

**Verify that core before going further.** Apply `top_eigenpair` twice (with deflation between) to

```
A = [[2, 1, 1],
     [1, 3, 0],
     [1, 0, 1]]
```

You must get λ1 = 3.732051, v1 ≈ (0.577350, 0.788675, 0.211325), and after deflation λ2 = 2.000000, v2 ≈ (0.577350, −0.577351, 0.577350) (tolerance 1e-4; eigenvectors shown with first component positive, your kernel may return either sign). λ1 is exactly 2 + √3 — hand-checkable, since `det(A − λI) = (2−λ)(3−λ)(1−λ) − (1−λ) − (3−λ)`.

## Test data generator — `make_test_data.py`

Exactly this script; run it to produce `features.csv`. Fully deterministic, std-lib only.

```python
#!/usr/bin/env python3
import math

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

rnd = lcg(20260824)

SAMPLES = ["CTRL_%d" % i for i in range(1, 6)] + ["EXP_%d" % i for i in range(1, 6)]
GROUP = [-1.0] * 5 + [1.0] * 5

# shared per-sample jitter (within-group structure): drives the PC2 block
delta = [(next(rnd) + next(rnd) + next(rnd) - 1.5) for _ in SAMPLES]

rows = []  # (feature_id, [10 values or None])
fid = 0

def noise(amp):
    return amp * (next(rnd) + next(rnd) - 1.0)

# block A: 12 group-signal features, up in EXP, correlated via the shared group term
for _ in range(12):
    fid += 1
    base = 1.0e4 * (10.0 ** (next(rnd) * 2.0))          # 1e4..1e6
    loading = 0.8 + 0.6 * next(rnd)                      # 0.8..1.4
    vals = [base * (2.0 ** (loading * GROUP[j] + 0.1 * delta[j] + noise(0.10)))
            for j in range(10)]
    rows.append(("MET_S%02d" % fid, vals))

# block B: 6 features tracking the shared per-sample jitter (within-group structure)
for _ in range(6):
    fid += 1
    base = 1.0e4 * (10.0 ** (next(rnd) * 2.0))
    vals = [base * (2.0 ** (1.2 * delta[j] + noise(0.10))) for j in range(10)]
    rows.append(("MET_B%02d" % fid, vals))

# 8 pure-noise features
for _ in range(8):
    fid += 1
    base = 1.0e4 * (10.0 ** (next(rnd) * 2.0))
    rows.append(("MET_N%02d" % fid, [base * (2.0 ** noise(0.30)) for j in range(10)]))

# 1 feature with 2 missing cells (kept: exactly 20% missing, imputed with row mean)
fid += 1
vals = [5.0e4 * (2.0 ** noise(0.20)) for j in range(10)]
vals[2] = None
vals[7] = None
rows.append(("MET_M%02d" % fid, vals))

# 1 feature with 3 missing cells (filtered: > 20% missing)
fid += 1
vals = [8.0e4 * (2.0 ** noise(0.20)) for j in range(10)]
vals[1] = None
vals[4] = None
vals[9] = None
rows.append(("MET_X%02d" % fid, vals))

out = ["feature_id," + ",".join(SAMPLES)]
for name, vals in rows:
    cells = ["" if v is None else "%.4f" % v for v in vals]
    out.append(name + "," + ",".join(cells))
open("features.csv", "w").write("\n".join(out) + "\n")
print("wrote features.csv:", len(rows), "features x", len(SAMPLES), "samples")
```

The table mimics a real quantification export: comma-separated, `%.4f` values, missing cells left empty. Blocks A and B are deliberately correlated *within* themselves so PC1 and PC2 both have a determined direction; the 8 noise features sit in a near-degenerate low-variance subspace.

## Acceptance criteria

Run `python3 make_test_data.py`, then `python3 pca.py features.csv -o scores.tsv --loadings loadings.tsv`. All of:

1. stdout (not stderr) prints exactly these three lines, fractions to 4 decimals:
   `kept 27 of 28 features (filtered: MET_X28)` · `PC1 variance fraction 0.9218` · `PC2 variance fraction 0.0719`
2. `MET_M27` is kept (2 missing of 10 = 20%, imputed); only `MET_X28` is filtered.
3. `scores.tsv` is **tab-separated** with header `sample\tPC1\tPC2`, 10 rows in input column order (`CTRL_1 … CTRL_5, EXP_1 … EXP_5`), values to 6 decimals.
4. `loadings.tsv` is tab-separated with header `feature\tPC1\tPC2`, exactly **27** rows in input row order (minus `MET_X28`), values to 6 decimals.
5. Variance fractions: PC1 = 0.9218 ± 0.002, PC2 = 0.0719 ± 0.002.
6. Sign and separation: `CTRL_1`'s PC1 score > 0, and **every** CTRL PC1 score exceeds **every** EXP PC1 score. Spot values ± 0.01: `CTRL_1` PC1 = 3.4354, `EXP_1` PC1 = −3.6524, `CTRL_2` PC2 = −1.7934.
7. Loadings: every `MET_S*` PC1 loading in [−0.35, −0.20]; every `MET_B*` PC2 loading in [+0.35, +0.45]; every `MET_N*` and `MET_M27` PC1 loading has |value| < 0.05.

## If something fails

Self-check λ or v wrong → re-read the kernel: `v` stays a unit vector, `lam` is `|Cv|`, deflation is `C − λ·v·vᵀ` (not `C − v·vᵀ`). Fractions off by ~11% → you divided the covariance by `n` instead of `n − 1`. One giant feature dominating PC1 → you skipped log2. PC1 right but PC2 wrong → missing/incorrect deflation, or you re-ran iteration on the original `C`. Separation flipped → apply the sign rule to scores and loadings *together*. Wrong feature filtered → the rule is ≥ 8 of 10 valid, checked before imputation. Crash on empty cells → skip them before `float()`.

## Optional

`--scale uv` flag for unit-variance (correlation) PCA. `--k 4` to emit more PCs with per-PC and cumulative variance fractions. A Procrustes/correlation comparison of your PC1–PC2 scores against another implementation's.
