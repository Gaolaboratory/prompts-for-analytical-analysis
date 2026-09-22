#!/usr/bin/env python3
"""Spec-exact reference for examples/nmr_1d/minimal_nmr_quad_prompt.md.

Distinct from nmr_1d_quad.py, which is the parameterised research tool used for the
2026-08-27 ablation study and whose defaults (zero-fill, extra valley stop condition)
do NOT match the prompt. This file implements the prompt literally and is the source
of its pinned criteria-3/4/5 numbers. Verified insensitive to every ambiguous reading
of the spec except the segment count, which the prompt pins at 256.

CLI matches the prompt: python3 nmr_quad.py fid_quad.csv -o multiplets.tsv
"""
import argparse, cmath, math

SFO1, CARRIER, SW_HZ, LB, P0, P1, REF_PPM = 400.0, 5.0, 8000.0, 1.0, 30.0, 20.0, 1.20
NSEG, MAX_HALFWIDTH_PPM, SIGMA_MULT, MIN_REL_HEIGHT = 256, 0.05, 20.0, 0.01


def fft(x):  # X_k = sum_n x_n * exp(-2j*pi*k*n/N), k = 0..N-1
    n = len(x)
    if n == 1:
        return list(x)
    ev = fft(x[0::2]); od = fft(x[1::2])
    out = [0j] * n
    for k in range(n // 2):
        t = cmath.exp(-2j * math.pi * k / n) * od[k]
        out[k] = ev[k] + t
        out[k + n // 2] = ev[k] - t
    return out


def median(v):
    s = sorted(v); n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def read_fid(path):
    ts, zs = [], []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("time_s"):
            continue
        a, b, c = line.split(",")
        ts.append(float(a)); zs.append(complex(float(b), float(c)))
    return ts, zs


def process(ts, zs):
    n = len(zs)
    zs = [z * math.exp(-math.pi * LB * t) for z, t in zip(zs, ts)]
    p = 1
    while p < n:
        p *= 2
    nfft = 2 * p                                    # twice the next power of two
    zs = zs + [0j] * (nfft - n)

    xs = fft(zs)
    xs = xs[nfft // 2:] + xs[:nfft // 2]            # carrier to centre

    d_f = SW_HZ / nfft
    ppm = [CARRIER + ((k - nfft / 2) * d_f) / SFO1 for k in range(nfft)]
    spec = [(xs[k] * cmath.exp(-1j * math.radians(P0 + P1 * k / nfft))).real
            for k in range(nfft)]

    seg = nfft // NSEG                              # segment-median baseline
    cx = [(i * seg + (i + 1) * seg - 1) / 2.0 for i in range(NSEG)]
    cy = [median(spec[i * seg:(i + 1) * seg]) for i in range(NSEG)]
    j = 0
    for k in range(nfft):
        while j < len(cx) - 2 and k > cx[j + 1]:
            j += 1
        spec[k] -= cy[j] + (cy[j + 1] - cy[j]) * (k - cx[j]) / (cx[j + 1] - cx[j])

    med = median(spec)
    sigma = 1.4826 * median([abs(s - med) for s in spec])
    thresh = max(SIGMA_MULT * sigma, MIN_REL_HEIGHT * max(spec))
    peaks = [k for k in range(1, nfft - 1)
             if spec[k] > spec[k - 1] and spec[k] >= spec[k + 1] and spec[k] >= thresh]

    maxbins = int(MAX_HALFWIDTH_PPM / (d_f / SFO1))
    rows = []
    for k in peaks:
        halves = []
        for step in (-1, 1):
            i, count = k, 0
            while count < maxbins:
                nxt = i + step
                if nxt < 0 or nxt >= nfft or spec[nxt] > spec[i]:
                    break
                i = nxt; count += 1
            halves.append(count)
        half = min(halves)
        lo, hi = k - half, k + half
        base = (spec[lo] + spec[hi]) / 2.0
        rows.append((ppm[k], sum(spec[i] - base for i in range(lo, hi + 1)) * d_f))
    rows.sort()
    return n, nfft, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fid")
    ap.add_argument("-o", "--out", default="multiplets.tsv")
    a = ap.parse_args()

    ts, zs = read_fid(a.fid)
    n, nfft, rows = process(ts, zs)
    print("points read: %d" % n)
    print("zero-filled to: %d" % nfft)
    print("peaks found: %d" % len(rows))

    ref = min(rows, key=lambda r: abs(r[0] - REF_PPM))[1] if rows else 1.0
    with open(a.out, "w", newline="") as fh:
        fh.write("ppm_center\tintegral\trelative_integral\n")
        for p, integ in rows:
            fh.write("%.4f\t%.4e\t%.4f\n" % (p, integ, integ / ref))


if __name__ == "__main__":
    main()
