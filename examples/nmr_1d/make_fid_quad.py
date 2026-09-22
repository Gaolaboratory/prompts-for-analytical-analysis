#!/usr/bin/env python3
"""Synthetic quadrature (complex) 1H FID. Std-lib only, deterministic."""
import math, cmath

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

SFO1_MHZ    = 400.0
CARRIER_PPM = 5.0
SW_HZ       = 8000.0                 # full quadrature width = 20.0 ppm
DT          = 1.0 / SW_HZ            # complex dwell
N           = 8192
P0_DEG      = 30.0                   # zero-order phase baked into the data
P1_DEG      = 20.0                   # first-order phase, across the full sweep
T2          = 0.40                   # identical for every signal -> integral ~ amplitude
# (ppm, amplitude proportional to proton count) -- two below the carrier, two above
SIGNALS = [(1.20, 9.0), (3.50, 2.0), (7.20, 3.0), (8.50, 1.0)]
# broad probe/first-point background -> the baseline roll a real spectrum has
BROAD   = [(5.60, 30.0, 0.0005)]     # (ppm, amplitude, T2_s)
NOISE   = 0.02

rnd = lcg(20260827)
p0 = math.radians(P0_DEG)
p1 = math.radians(P1_DEG)

with open("fid_quad.csv", "w") as f:
    f.write("# synthetic 1H FID, quadrature (complex) detection\n")
    f.write("# spectrometer_frequency_MHz=400.0 carrier_ppm=5.0 spectral_width_hz=8000.0\n")
    f.write("time_s,real,imag\n")
    for i in range(N):
        t = i * DT
        z = 0j
        for ppm, a in SIGNALS:
            nu = (ppm - CARRIER_PPM) * SFO1_MHZ          # Hz from carrier, signed
            phi = p0 + p1 * (nu / SW_HZ + 0.5)           # phase at this frequency
            z += a * math.exp(-t / T2) * cmath.exp(1j * (2.0 * math.pi * nu * t + phi))
        for ppm, a, t2 in BROAD:
            nu = (ppm - CARRIER_PPM) * SFO1_MHZ
            phi = p0 + p1 * (nu / SW_HZ + 0.5)
            z += a * math.exp(-t / t2) * cmath.exp(1j * (2.0 * math.pi * nu * t + phi))
        z += complex((next(rnd) - 0.5) * 2.0 * NOISE, (next(rnd) - 0.5) * 2.0 * NOISE)
        f.write("%.8f,%.6f,%.6f\n" % (t, z.real, z.imag))
print("wrote fid_quad.csv")
