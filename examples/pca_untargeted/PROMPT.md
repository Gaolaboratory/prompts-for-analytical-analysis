# PCA of an untargeted metabolomics matrix

Write `pca.py`. Run: `python3 pca.py features.csv groups.csv -o scores.tsv`

Python standard library plus numpy, pandas and scipy only. No scikit-learn.

## Input

Both files are in the working directory.

- `features.csv` — first column `feature_id`, then one column per sample: 200 feature
  rows × 60 sample columns. **Empty cells are missing values** (signal below detection).
- `groups.csv` — header `sample,group`, 60 rows, two groups of 30.

## Output

`scores.tsv`, tab-separated, one row per sample in the order the columns appear in
`features.csv`:

```
sample	group	PC1	PC2
```

One line on stdout: `features_in=<n> features_kept=<n> pc1_var=<f> pc2_var=<f>`
with the variance fractions to 4 decimals.

## Method

- Keep a feature only if it has a value in **at least 80%** of samples (≥ 48 of 60).
- Impute each remaining empty cell with that feature's mean over its own valid values,
  **on the linear scale, before the log** — not with zero, and not with a sample mean.
- Then take `log2` of every value.
- Center each feature by subtracting its mean across samples. **Do not divide by the
  standard deviation**: this is covariance PCA, not correlation PCA.
- `features.csv` loads with features as rows and samples as columns: transpose it so each
  row is a sample before centering, giving the 60 × (kept features) matrix PCA needs.
  Skipping the transpose still yields correct variance fractions, so a plausible result is not evidence the orientation is right.
- A component's variance fraction is its eigenvalue divided by the sum of all
  eigenvalues.
- Component sign is arbitrary, so fix it: flip a component (scores and loadings
  together) so that the **first sample's score is positive**.

## Acceptance criteria

1. `scores.tsv` has the header above and exactly 60 tab-separated data rows, each
   sample's group taken from `groups.csv`.
2. The stdout line reports `features_in=200` and `features_kept=184`.
3. `pc1_var` = 0.1558 ± 0.01 and `pc2_var` = 0.1008 ± 0.01.
4. The reported PC1 scores correlate with a reference PC1 at |r| ≥ 0.999, and PC2
   likewise.
5. The first sample's PC1 and PC2 scores are both positive, per the sign rule.

This is real data: the two groups **overlap** on PC1. Do not tune the preprocessing to
separate them, and do not tune a constant to make a number match.
