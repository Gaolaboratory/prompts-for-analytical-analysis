#!/usr/bin/env python3
"""Synthetic 1H FID: 4 damped cosines + LCG noise. Std-lib only, deterministic."""
import math

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

SFO1_MHZ = 400.0
CARRIER_PPM = -4.0
SW_PPM = 14.0
DT = 1.0 / (2.0 * SW_PPM * SFO1_MHZ)   # 1/11200 s
N = 10000
PHI0 = 0.6
# (ppm, amplitude, T2_s); amplitudes are proportional to proton counts 9:1:2:3
SIGNALS = [(0.50, 9.0, 0.30), (2.10, 1.0, 0.40), (3.80, 2.0, 0.25), (7.25, 3.0, 0.20)]
NOISE = 0.05

rnd = lcg(20260824)
with open("fid.csv", "w") as f:
    f.write("# synthetic 1H FID, single-channel real detection\n")
    f.write("# spectrometer_frequency_MHz=400.0 carrier_ppm=-4.0 spectral_width_ppm=14.0\n")
    f.write("time_s,intensity\n")
    for i in range(N):
        t = i * DT
        x = sum(a * math.exp(-t / t2) * math.cos(2.0 * math.pi * (ppm - CARRIER_PPM) * SFO1_MHZ * t + PHI0)
                for ppm, a, t2 in SIGNALS)
        x += (next(rnd) - 0.5) * 2.0 * NOISE
        f.write(f"{t:.8f},{x:.6f}\n")
print("wrote fid.csv")
