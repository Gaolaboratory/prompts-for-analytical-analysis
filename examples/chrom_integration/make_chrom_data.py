#!/usr/bin/env python3
"""Deterministic chromatogram generator. Std-lib only."""
import math

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

def gauss(t, mu, sig, h):
    return h * math.exp(-((t - mu) ** 2) / (2 * sig * sig))

def emg(t, mu, sig, lam, A):
    x = (lam / 2.0) * (2 * mu + lam * sig * sig - 2 * t)
    z = (mu + lam * sig * sig - t) / (sig * math.sqrt(2.0))
    if x > 600:
        return 0.0
    return (A * lam / 2.0) * math.exp(x) * math.erfc(z)

PEAKS = [(60.0, 4.0, 800.0), (150.0, 5.0, 1200.0)]   # mu, sigma, height
EMG = (240.0, 4.5, 0.15, 12000.0)                    # mu, sigma, lambda, area
NOISE_SD = 5.0

rnd = lcg(20260824)
lines = ["# MiniLC-100 export, channel=UV254, method=DEFAULT", "time_s,signal"]
for i in range(300):
    t = float(i)
    s = 50.0 + 0.10 * t
    for mu, sig, h in PEAKS:
        s += gauss(t, mu, sig, h)
    s += emg(t, *EMG)
    u1 = max(next(rnd), 1e-12); u2 = next(rnd)
    s += NOISE_SD * math.sqrt(-2.0 * math.log(u1)) * math.cos(2 * math.pi * u2)
    lines.append(f"{t:.1f},{s:.4f}")
open("chrom.csv", "w").write("\n".join(lines) + "\n")
print("wrote chrom.csv")
