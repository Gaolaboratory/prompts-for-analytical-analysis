#!/usr/bin/env python3
"""Reference differential statistics for examples/mass_stats/PROMPT.md.

Pipeline pinned in data/mass_stats/README.md: keep a feature with >= 3 valid
values per condition; log2 transform; Welch t-test via
scipy.stats.ttest_ind(equal_var=False); Welch-Satterthwaite fractional df
(computed by hand, not rounded); log2FC = mean(log2 EXP) - mean(log2 CTRL);
Benjamini-Hochberg across tested features (ranks from 1, monotone sweep from
the largest rank down, capped at 1); significant iff q < 0.05 and
|log2FC| >= 1.
"""
import numpy as np
import pandas as pd
from scipy import stats

MIN_VALID_PER_CONDITION = 3


def _welch_satterthwaite_df(a, b):
    va, vb = a.var(ddof=1), b.var(ddof=1)
    na, nb = len(a), len(b)
    num = (va / na + vb / nb) ** 2
    den = (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
    return float(num / den)


def _bh_qvalues(pvals):
    """Benjamini-Hochberg q-values: ranks from 1, monotone sweep from the
    largest rank down, capped at 1."""
    m = len(pvals)
    order = np.argsort(pvals)               # ascending p -> rank 1..m
    ranked_p = np.asarray(pvals)[order]
    q_sorted = ranked_p * m / (np.arange(m) + 1)
    for i in range(m - 2, -1, -1):
        q_sorted[i] = min(q_sorted[i], q_sorted[i + 1])
    q_sorted = np.minimum(q_sorted, 1.0)
    q = np.empty(m)
    q[order] = q_sorted
    return q


def run(quant_csv, groups_tsv):
    quant = pd.read_csv(quant_csv, index_col=0)
    groups = pd.read_csv(groups_tsv, sep="\t").set_index("pinned_column")["group"]
    ctrl_cols = [c for c in quant.columns if groups.get(c) == "CTRL"]
    exp_cols = [c for c in quant.columns if groups.get(c) == "EXP"]

    filtered = 0
    kept_ids = []
    log2fc_list = []
    t_list = []
    df_list = []
    p_list = []

    for feature_id, row in quant.iterrows():
        ctrl = row[ctrl_cols].astype(float)
        exp = row[exp_cols].astype(float)
        ctrl_valid = ctrl.dropna()
        exp_valid = exp.dropna()
        if len(ctrl_valid) < MIN_VALID_PER_CONDITION or len(exp_valid) < MIN_VALID_PER_CONDITION:
            filtered += 1
            continue
        log_ctrl = np.log2(ctrl_valid.to_numpy(dtype=float))
        log_exp = np.log2(exp_valid.to_numpy(dtype=float))
        t_stat, p_val = stats.ttest_ind(log_exp, log_ctrl, equal_var=False)
        df = _welch_satterthwaite_df(log_exp, log_ctrl)
        log2fc = float(log_exp.mean() - log_ctrl.mean())

        kept_ids.append(feature_id)
        log2fc_list.append(log2fc)
        t_list.append(float(t_stat))
        df_list.append(df)
        p_list.append(float(p_val))

    tested = len(kept_ids)
    q_list = _bh_qvalues(np.asarray(p_list)) if tested else np.array([])

    rows = []
    significant = 0
    for feature_id, log2fc, t_stat, df, p_val, q_val in zip(
            kept_ids, log2fc_list, t_list, df_list, p_list, q_list):
        sig = bool(q_val < 0.05 and abs(log2fc) >= 1.0)
        significant += int(sig)
        rows.append({
            "feature_id": feature_id,
            "log2fc": log2fc,
            "t": t_stat,
            "df": df,
            "p_value": p_val,
            "q_value": float(q_val),
            "significant": int(sig),
        })

    rows.sort(key=lambda r: r["p_value"])

    return {"tested": tested, "filtered": filtered, "significant": significant,
            "rows": rows}


if __name__ == "__main__":
    import sys
    r = run(sys.argv[1], sys.argv[2])
    print("tested=%d filtered=%d significant=%d"
          % (r["tested"], r["filtered"], r["significant"]))
