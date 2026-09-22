#!/usr/bin/env python3
"""Writes sample.csv, a synthetic UV-Vis spectrum. Std-lib only, deterministic."""
import math

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

BANDS = [  # (lambda0 nm, true peak absorbance, sigma nm)
    (320.0, 0.90, 15.0),
    (420.0, 1.30, 25.0),   # quantitation band: epsilon 26000, l 1.0 cm -> 50.0 uM
    (540.0, 0.70, 30.0),
]

def baseline(lam):  # sloping + gently curved, like scatter from a real cuvette
    x = lam - 200.0
    return 0.02 + 6.0e-4 * x + 4.0e-7 * x * x

rnd = lcg(20260824)
lines = ["# UV-Vis export, mock instrument",
         "# cell path length: 1.0 cm",
         "wavelength_nm,absorbance"]
for lam in range(200, 801):
    a = baseline(float(lam))
    for mu, amp, sig in BANDS:
        a += amp * math.exp(-((lam - mu) ** 2) / (2.0 * sig * sig))
    a += (next(rnd) - 0.5) * 0.01
    lines.append("%d,%.6f" % (lam, a))
open("sample.csv", "w").write("\n".join(lines) + "\n")
print("wrote sample.csv")
