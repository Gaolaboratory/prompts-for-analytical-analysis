# Example data & expected results — pca_untargeted

**Dataset:** the published MetaboLights **MTBLS1** human-urine ¹H-NMR bucket matrix (Salek et
al. 2007, diabetes vs control), subset harness-side to a balanced 30+30 samples × top-200
variable buckets with below-detection zeros written as empty cells
(`data/pca/features.csv`, `data/pca/groups.csv`). Provenance, subsetting rule (seed 20260826),
and license: `data/pca/README.md`.

**Run:** `python3 pca.py features.csv -o scores.tsv --loadings loadings.tsv` (`groups.csv` is
context only; the tool does not read it).

**Expected results (sklearn PCA on exactly the prompt's pipeline — ≥80% filter, linear row-mean
imputation, log2, mean-center, covariance):**

| anchor | value |
|---|---|
| features kept | 184 of 200 |
| PC1 variance fraction | 0.1558 (±0.01) |
| PC2 variance fraction | 0.1008 (±0.01) |
| sample scores | \|r\| > 0.999 vs reference (sign-normalized) |

Note: unlike the synthetic data, the two groups **overlap** on PC1 in this real study (a
directional shift exists; group means ±1.71) — the tier (a) separation criterion does not apply.

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/pca/local/tierc/`, 20 iterations): kept 184 of 200 (identical filtered-bucket list),
PC1 0.1558, PC2 0.1008, PC1/PC2 sample-score correlations vs an independent numpy reference
|r| = 1.000000 both — **PASS**, exact.
