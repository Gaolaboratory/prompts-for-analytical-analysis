#!/usr/bin/env python3
"""Reference titration analysis for examples/titration/PROMPT.md.

Exactly the prompt's recipe, in numpy/pandas: smooth width 5, midpoint
derivative on the real dV, parabolic vertex, pKa interpolated at Veq/2 on the
raw curve. Used to build the grader's conformant fixture.
"""
import numpy as np
import pandas as pd

C_TITRANT = 0.1000
V0 = 25.00


def _smooth(y, w=5):
    half = w // 2
    return np.array([y[max(0, i - half):i + half + 1].mean() for i in range(len(y))])


def analyse(path, c_titrant=C_TITRANT, v0=V0):
    df = pd.read_csv(path)
    v = df["titrant_volume_mL"].to_numpy(dtype=float)
    ph = df["pH"].to_numpy(dtype=float)
    sm = _smooth(ph)
    d1 = np.diff(sm) / np.diff(v)
    x = (v[:-1] + v[1:]) / 2.0
    k = int(np.argmax(d1))
    if 0 < k < len(d1) - 1:
        x3 = x[k - 1:k + 2]
        y3 = d1[k - 1:k + 2]
        a, b, c = np.polyfit(x3, y3, 2)
        veq = -b / (2 * a) if a else x[k]
    else:
        veq = x[k]
    pka = float(np.interp(veq / 2.0, v, ph))
    return {"points": len(v), "veq": float(veq), "pka": pka,
            "conc": float(c_titrant * veq / v0)}


if __name__ == "__main__":
    import sys
    r = analyse(sys.argv[1])
    print("points=%d Veq=%.3f pKa=%.3f conc=%.5f"
          % (r["points"], r["veq"], r["pka"], r["conc"]))
