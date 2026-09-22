#!/usr/bin/env python3
"""Reference linear calibration for examples/calibration/PROMPT.md.

The recipe pinned in data/calibration/README.md: unweighted OLS of y on x
(NIST StRD Norris), residual SD on n-2 df, R^2, and LOD/LOQ at the
3.3*s/m and 10*s/m convention.
"""
import numpy as np
import pandas as pd


def run(csv_path):
    d = pd.read_csv(csv_path)
    x = d["x"].to_numpy(dtype=float)
    y = d["y"].to_numpy(dtype=float)
    n = len(x)
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    ss_res = float((resid ** 2).sum())
    residual_sd = float(np.sqrt(ss_res / (n - 2)))
    r_squared = float(1.0 - ss_res / float(((y - y.mean()) ** 2).sum()))
    return {"n": int(n), "slope": float(slope), "intercept": float(intercept),
            "residual_sd": residual_sd, "r_squared": r_squared,
            "lod": 3.3 * residual_sd / float(slope),
            "loq": 10.0 * residual_sd / float(slope)}


if __name__ == "__main__":
    import sys
    r = run(sys.argv[1])
    print("n=%d slope=%.12f intercept=%.12f residual_sd=%.12f r_squared=%.12f "
          "lod=%.6f loq=%.6f"
          % (r["n"], r["slope"], r["intercept"], r["residual_sd"], r["r_squared"],
             r["lod"], r["loq"]))
