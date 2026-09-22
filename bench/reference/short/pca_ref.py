#!/usr/bin/env python3
"""Reference PCA for examples/pca_untargeted/PROMPT.md.

The recipe pinned in data/pca/README.md: >=80% valid filter, linear-scale row-mean
imputation, log2, per-feature mean centering, no scaling, covariance PCA, sign fixed
so the first sample's score is positive. numpy only (sklearn is not allowed here);
the README records that sklearn and numpy.linalg agree to 1e-16 on this matrix.
"""
import numpy as np
import pandas as pd

MIN_VALID_FRACTION = 0.80


def run(features_csv, groups_csv):
    feats = pd.read_csv(features_csv, index_col=0)
    samples = list(feats.columns)
    n = len(samples)
    keep = feats.notna().sum(axis=1) >= MIN_VALID_FRACTION * n
    kept = feats[keep]
    filled = kept.apply(lambda row: row.fillna(row.mean()), axis=1)
    x = np.log2(filled.to_numpy(dtype=float)).T            # samples x features
    x = x - x.mean(axis=0, keepdims=True)
    cov = x.T @ x / (x.shape[0] - 1)
    evals = np.linalg.eigvalsh(cov)[::-1]
    _, _, vt = np.linalg.svd(x, full_matrices=False)
    scores = x @ vt[:2].T
    for j in range(2):                                     # sign rule
        if scores[0, j] < 0:
            scores[:, j] = -scores[:, j]
    total = evals.sum()
    grp = pd.read_csv(groups_csv).set_index("sample")["group"]
    return {"samples": samples, "groups": [grp[s] for s in samples],
            "features_in": int(feats.shape[0]), "features_kept": int(keep.sum()),
            "pc1_var": float(evals[0] / total), "pc2_var": float(evals[1] / total),
            "scores": scores}


if __name__ == "__main__":
    import sys
    r = run(sys.argv[1], sys.argv[2])
    print("features_in=%d features_kept=%d pc1_var=%.4f pc2_var=%.4f"
          % (r["features_in"], r["features_kept"], r["pc1_var"], r["pc2_var"]))
