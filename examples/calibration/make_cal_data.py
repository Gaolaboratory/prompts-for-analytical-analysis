#!/usr/bin/env python3
"""Deterministic generator: 6 levels x 3 replicates, heteroscedastic noise, 3 unknowns."""
import math

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

def gauss(rnd):
    u1 = max(next(rnd), 1e-12)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * next(rnd))

SLOPE, INTERCEPT = 2.5, 0.03
LEVELS = [0.05, 0.20, 0.50, 1.00, 2.50, 5.00]
UNKNOWNS = [("UNK_1", 0.15), ("UNK_2", 1.20), ("UNK_3", 3.80)]

rnd = lcg(20260824)

def one_point(x):
    ratio = SLOPE * x + INTERCEPT
    is_area = 50000.0 * (1.0 + 0.04 * gauss(rnd))
    noise = gauss(rnd) * (0.012 * ratio + 0.0012)   # noise grows with level
    return is_area * (ratio + noise), is_area

lines = ["# calibration standards, generated synthetic", "# conc in ug/mL",
         "conc_ug_mL,analyte_area,is_area"]
for x in LEVELS:
    for rep in range(3):
        a, s = one_point(x)
        lines.append(f"{x:.2f},{a:.1f},{s:.1f}")
open("standards.csv", "w").write("\n".join(lines) + "\n")

lines = ["# unknown samples", "sample_id,analyte_area,is_area,true_conc_ug_mL"]
for sid, x in UNKNOWNS:
    a, s = one_point(x)
    lines.append(f"{sid},{a:.1f},{s:.1f},{x:.2f}")
open("unknowns.csv", "w").write("\n".join(lines) + "\n")
print("wrote standards.csv, unknowns.csv")
