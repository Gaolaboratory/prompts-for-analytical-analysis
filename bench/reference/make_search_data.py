#!/usr/bin/env python3
"""Synthetic DDA benchmark. Std-lib only, deterministic.

Writes bench.fasta (1600 proteins) and bench.mgf (60 MS2 spectra).
20 of the 60 spectra come from 400 proteins that are deliberately NOT in the
FASTA: those spectra have no correct answer, exactly like real spectra whose
peptide carries an unmodelled modification. A search engine must not pretend
to identify them.
"""
import math

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

RES = {'G':57.02146,'A':71.03711,'S':87.03203,'P':97.05276,'V':99.06841,
       'T':101.04768,'C':103.00919,'L':113.08406,'I':113.08406,'N':114.04293,
       'D':115.02694,'Q':128.05858,'K':128.09496,'E':129.04259,'M':131.04049,
       'H':137.05891,'F':147.06841,'R':156.10111,'Y':163.06333,'W':186.07931}
H2O, PROTON = 18.010565, 1.0072765
ALPHA = "ADEFGHILNPQSTVWY"
N_IN, N_OUT = 1600, 400          # in the FASTA / held out
N_HIT, N_MISS = 40, 20           # spectra from present / absent proteins
NOISE_PEAKS = 200

rnd = lcg(20260827)

def digest(seq, lo=6, hi=18):
    peps, start, n = [], 0, len(seq)
    for i, r in enumerate(seq):
        if r in 'KR' and not (i + 1 < n and seq[i+1] == 'P'):
            peps.append(seq[start:i+1]); start = i + 1
    if start < n: peps.append(seq[start:])
    return [p for p in peps if lo <= len(p) <= hi]

proteins = []
for i in range(N_IN + N_OUT):
    L = 160 + int(next(rnd) * 140)
    s = []
    for _ in range(L):
        s.append('K' if next(rnd) < 0.055 else 'R' if next(rnd) < 0.055 else
                 ALPHA[int(next(rnd) * len(ALPHA))])
    proteins.append(("sp|SYN%04d|SYN%04d_TEST" % (i + 1, i + 1), "".join(s)))

with open("bench.fasta", "w") as f:                 # only the first N_IN are searchable
    for h, s in proteins[:N_IN]:
        f.write(">%s\n" % h)
        for j in range(0, len(s), 60): f.write(s[j:j+60] + "\n")

def pool_of(subset):
    out = []
    for h, s in subset:
        for p in digest(s): out.append((p, h))
    out.sort()
    return out

pool_in, pool_out = pool_of(proteins[:N_IN]), pool_of(proteins[N_IN:])
chosen, seen = [], set()
for pool, count in ((pool_in, N_HIT), (pool_out, N_MISS)):
    n = 0
    while n < count:
        p, h = pool[int(next(rnd) * len(pool))]
        if p in seen: continue
        seen.add(p); chosen.append((p, h)); n += 1

def frags(pep):
    b, y, pre, suf = [], [], 0.0, 0.0
    for i in range(len(pep) - 1):
        pre += RES[pep[i]]; b.append(pre + PROTON)
    for i in range(len(pep) - 1, 0, -1):
        suf += RES[pep[i-1]]; y.append(suf + H2O + PROTON)
    return b, y

order = sorted(range(len(chosen)), key=lambda i: next(rnd))   # interleave hit/miss scans
with open("bench.mgf", "w") as f:
    for k, idx in enumerate(order):
        pep, prot = chosen[idx]
        z = 2
        pmz = (sum(RES[c] for c in pep) + H2O + z * PROTON) / z
        b, y = frags(pep)
        peaks = []
        for mz in b + y:
            if next(rnd) < 0.25: continue
            peaks.append((mz + (next(rnd) - 0.5) * 0.4, 200.0 + next(rnd) * 1800.0))
        for _ in range(NOISE_PEAKS):
            peaks.append((100.0 + next(rnd) * 1400.0, 50.0 + next(rnd) * 900.0))
        peaks.sort()
        f.write("BEGIN IONS\nTITLE=synthetic scan %d\nSCANS=%d\n" % (k + 1, k + 1))
        f.write("PEPMASS=%.4f\nCHARGE=%d+\n" % (pmz, z))
        for mz, it in peaks: f.write("%.4f %.1f\n" % (mz, it))
        f.write("END IONS\n")

print("wrote bench.fasta (%d proteins) and bench.mgf (%d spectra)"
      % (N_IN, N_HIT + N_MISS))
