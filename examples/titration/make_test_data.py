#!/usr/bin/env python3
"""Deterministic weak-acid/strong-base titration curve generator. Std-lib only."""
import math

KA = 10.0 ** (-4.76)   # pKa = 4.76 (acetic-acid-like)
KW = 1.0e-14
CA = 0.1000            # mol/L analyte in the flask
V0 = 50.00             # mL analyte
CB = 0.1000            # mol/L strong-base titrant

def ph_at(v_ml):
    V  = V0 + v_ml
    ca = CA * V0 / V
    cb = CB * v_ml / V
    def f(h):                      # charge balance, root in h
        return h + cb - KW / h - ca * KA / (KA + h)
    lo, hi = 1e-14, 1.0
    for _ in range(200):
        mid = math.sqrt(lo * hi)   # geometric bisection, h spans 14 decades
        if f(mid) > 0.0: hi = mid
        else:            lo = mid
    return -math.log10(math.sqrt(lo * hi))

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

rnd = lcg(20260824)
N = 50
lines = ["# pH titration log, electrode E-201, 25.0 C",
         "titrant_volume_mL,pH"]
for i in range(N):
    v = round(75.0 * i / (N - 1), 2)
    noise = (next(rnd) - 0.5) * 0.04        # ±0.02 pH
    lines.append(f"{v:.2f},{ph_at(v) + noise:.3f}")
open("titration.csv", "w").write("\n".join(lines) + "\n")
print("wrote titration.csv: 50 points, Veq = 50.00 mL")
