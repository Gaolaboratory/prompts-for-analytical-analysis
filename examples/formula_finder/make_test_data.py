#!/usr/bin/env python3
"""Deterministic generator for formula_finder test data. Std-lib only."""
# isotope table: element -> [(mass, abundance %), ...], monoisotopic first
ISO = {
 "C": [(12.000000, 98.93), (13.003355, 1.07)],
 "H": [(1.007825, 99.9885), (2.014102, 0.0115)],
 "N": [(14.003074, 99.636), (15.000109, 0.364)],
 "O": [(15.994915, 99.757), (16.999131, 0.038), (17.999160, 0.205)],
 "P": [(30.973762, 100.0)],
 "S": [(31.972071, 94.99), (32.971459, 0.75), (33.967867, 4.25)],
}
TRUE = [("CPD1", {"C":6,"H":12,"O":6}),            # glucose
        ("CPD2", {"C":8,"H":10,"N":4,"O":2}),      # caffeine
        ("CPD3", {"C":5,"H":11,"N":1,"O":2,"S":1})] # methionine

def pattern(counts):
    mass = sum(ISO[e][0][0]*n for e, n in counts.items())
    m1 = m2 = 0.0
    for e, n in counts.items():
        a = ISO[e]
        if len(a) > 1:
            r1 = a[1][1]/a[0][1]
            m1 += n*r1; m2 += n*(n-1)/2.0*r1*r1
        if len(a) > 2:
            m2 += n*a[2][1]/a[0][1]
    return mass, m1, m2

def lcg(state):
    while True:
        state = (1103515245*state + 12345) % 2147483648
        yield state/2147483648.0

rnd = lcg(20260824)
lines = ["id\tmass\tM1\tM2"]
for cid, counts in TRUE:
    m, m1, m2 = pattern(counts)
    m  += (2*next(rnd)-1) * 2.5*m/1e6       # +/-2.5 ppm mass error
    m1 *= 1 + (2*next(rnd)-1)*0.04          # +/-4% relative isotope noise
    m2 *= 1 + (2*next(rnd)-1)*0.04
    lines.append(f"{cid}\t{m:.4f}\t{m1:.6f}\t{m2:.6f}")
open("measured.tsv", "w").write("\n".join(lines) + "\n")
print("wrote measured.tsv")
