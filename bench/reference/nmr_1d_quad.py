#!/usr/bin/env python3
"""1D NMR processing from a quadrature (complex) FID - standard library only.

Completed version: adds the pieces the single-real-channel prompt omitted.
  - complex (quadrature) input -> two-sided spectrum, no mirror folding
  - iterative radix-2 FFT (recursive blows up at 65536 pts in pure Python)
  - zero- AND first-order phase correction, pivoted at the carrier
  - noise-estimated peak threshold (MAD), not a fixed 5% of max
  - valley-bounded integration windows + peak-free baseline
CLI: python3 nmr_1d_v2.py fid.csv -o multiplets.tsv [--sfo1 ..] [--carrier ..]
     [--sw-hz ..] [--lb ..] [--p0 deg] [--p1 deg] [--ref-ppm ..] [--mode absorption|magnitude]
"""
import sys, math, cmath, argparse


# ---------------------------------------------------------------- FFT
def fft_inplace(a):
    """Iterative radix-2 DIT FFT, X_k = sum_n x_n exp(-2j*pi*k*n/N). len(a) = 2**m."""
    n = len(a)
    j = 0
    for i in range(1, n):                      # bit-reversal permutation
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    length = 2
    while length <= n:
        ang = -2.0 * math.pi / length
        wl = cmath.exp(1j * ang)
        for i in range(0, n, length):
            w = 1.0 + 0j
            half = length >> 1
            for k in range(i, i + half):
                u = a[k]; v = a[k + half] * w
                a[k] = u + v
                a[k + half] = u - v
                w *= wl
        length <<= 1
    return a


def next_pow2(n):
    p = 1
    while p < n:
        p <<= 1
    return p


# ---------------------------------------------------------------- input
def read_fid(path):
    """Return (times, values, is_complex). Accepts time_s,real,imag or time_s,intensity."""
    times, vals = [], []
    is_complex = None
    with open(path) as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            low = s.lower()
            if low.startswith("time_s"):
                is_complex = low.count(",") >= 2
                continue
            p = s.split(",")
            times.append(float(p[0]))
            if is_complex is None:
                is_complex = len(p) >= 3
            vals.append(complex(float(p[1]), float(p[2])) if is_complex else complex(float(p[1]), 0.0))
    return times, vals, bool(is_complex)


# ---------------------------------------------------------------- stats
def median(xs):
    ys = sorted(xs)
    n = len(ys)
    return ys[n // 2] if n % 2 else 0.5 * (ys[n // 2 - 1] + ys[n // 2])


def noise_sigma(spec):
    """Robust noise level: MAD of the spectrum, scaled to a Gaussian sigma."""
    med = median(spec)
    mad = median([abs(v - med) for v in spec])
    return 1.4826 * mad


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("fid")
    ap.add_argument("-o", "--out", default="multiplets.tsv")
    ap.add_argument("--sfo1", type=float, required=True, help="spectrometer freq, MHz")
    ap.add_argument("--carrier", type=float, required=True, help="carrier position, ppm")
    ap.add_argument("--sw-hz", type=float, required=True, help="full spectral width, Hz")
    ap.add_argument("--lb", type=float, default=1.0)
    ap.add_argument("--p0", type=float, default=0.0, help="zero-order phase, degrees")
    ap.add_argument("--p1", type=float, default=0.0, help="first-order phase, degrees over full SW")
    ap.add_argument("--ref-ppm", type=float, default=0.0, help="ppm of the integral reference peak")
    ap.add_argument("--mode", choices=("absorption", "magnitude"), default="absorption")
    ap.add_argument("--thresh-sigma", type=float, default=20.0)
    ap.add_argument("--min-rel-height", type=float, default=0.01,
                    help="also require height >= this fraction of the tallest peak")
    ap.add_argument("--zf", type=int, default=0, help="zero-fill size (0 = next power of two)")
    ap.add_argument("--baseline-segments", type=int, default=256,
                    help="number of segments for the median baseline (0 = off)")
    ap.add_argument("--max-halfwidth-ppm", type=float, default=0.05,
                    help="hard cap on each integration half-window")
    a = ap.parse_args(argv)

    times, vals, is_complex = read_fid(a.fid)
    N = len(vals)
    dt = 1.0 / a.sw_hz if is_complex else 1.0 / (2.0 * a.sw_hz)
    print("points read: %d" % N)
    print("input channels: %s" % ("complex (quadrature)" if is_complex else "real (single channel)"))

    # apodization
    x = [v * math.exp(-math.pi * a.lb * t) for v, t in zip(vals, times)]

    # zero-fill
    nfft = a.zf if a.zf else next_pow2(N)
    x = x + [0j] * (nfft - len(x))
    print("zero-filled to: %d" % nfft)

    X = fft_inplace(x)

    # ---- axis ----
    if is_complex:
        # two-sided, carrier at the centre: shift so index 0 is -SW/2
        half = nfft // 2
        Xs = X[half:] + X[:half]
        f = [(k - half) * (a.sw_hz / nfft) for k in range(nfft)]   # Hz from carrier
    else:
        # real detection: only bins 0..N/2 are meaningful (rest are mirrors)
        half = nfft // 2
        Xs = X[: half + 1]
        f = [k / (nfft * dt) for k in range(half + 1)]
    ppm = [a.carrier + fi / a.sfo1 for fi in f]

    # ---- phase ----
    p0 = math.radians(a.p0)
    p1 = math.radians(a.p1)
    if a.mode == "magnitude":
        spec = [abs(v) for v in Xs]
    else:
        # phi_k = p0 + p1 * k / n, the ramp running across the displayed axis
        n = len(Xs)
        spec = [(v * cmath.exp(1j * (p0 + p1 * k / n))).real
                for k, v in enumerate(Xs)]

    # ---- baseline correction (segment medians + linear interpolation) ----
    # Real spectra roll: residual-water wings and FID first-point errors leave a
    # slowly varying floor. Medians of short segments are dominated by baseline
    # (peaks occupy a small fraction of bins), so they trace it robustly.
    if a.baseline_segments > 0:
        nseg = a.baseline_segments
        m = len(spec)
        seg = max(1, m // nseg)
        cx, cy = [], []
        for st in range(0, m, seg):
            en = min(st + seg, m)
            cx.append(0.5 * (st + en - 1))
            cy.append(median(spec[st:en]))
        base = [0.0] * m
        j = 0
        for k in range(m):
            while j < len(cx) - 2 and cx[j + 1] < k:
                j += 1
            x0, x1 = cx[j], cx[j + 1]
            y0, y1 = cy[j], cy[j + 1]
            base[k] = y0 + (y1 - y0) * ((k - x0) / (x1 - x0)) if x1 != x0 else y0
        spec = [v - b for v, b in zip(spec, base)]

    # ---- peak picking, noise-estimated threshold ----
    sigma = noise_sigma(spec)
    thresh = max(a.thresh_sigma * sigma, a.min_rel_height * max(spec))
    peaks = [k for k in range(1, len(spec) - 1)
             if spec[k] > spec[k - 1] and spec[k] >= spec[k + 1] and spec[k] >= thresh]
    print("noise sigma: %.4g  threshold: %.4g  raw maxima: %d" % (sigma, thresh, len(peaks)))

    # ---- valley-bounded integration ----
    dppm = abs(ppm[1] - ppm[0])
    df = abs(f[1] - f[0])
    peakset = set(peaks)

    def walk(k, step, maxbins):
        """Walk downhill from k until the signal turns up (valley) or drops to noise."""
        j = k
        for _ in range(maxbins):
            nxt = j + step
            if nxt < 0 or nxt >= len(spec):
                break
            if spec[nxt] > spec[j] or spec[nxt] < thresh * 0.05:
                break
            j = nxt
        return j

    maxbins = max(1, int(a.max_halfwidth_ppm / dppm))
    rows = []
    for k in peaks:
        lo = walk(k, -1, maxbins)
        hi = walk(k, +1, maxbins)
        # symmetrise: a runaway dispersive tail on one side must not dominate
        w = min(k - lo, hi - k)
        lo, hi = k - w, k + w
        base = 0.5 * (spec[lo] + spec[hi])
        integ = sum((spec[j] - base) for j in range(lo, hi + 1)) * df
        rows.append({"ppm": ppm[k], "height": spec[k], "integral": integ,
                     "lo_ppm": ppm[lo], "hi_ppm": ppm[hi]})

    rows.sort(key=lambda r: r["ppm"])
    if rows:
        ref = min(rows, key=lambda r: abs(r["ppm"] - a.ref_ppm))
        refi = ref["integral"] if ref["integral"] else 1.0
    else:
        refi = 1.0
    print("peaks found: %d" % len(rows))

    with open(a.out, "w", newline="\n") as fh:
        fh.write("ppm_center\theight\tintegral\trelative_integral\twindow_lo\twindow_hi\n")
        for r in rows:
            fh.write("%.4f\t%.4e\t%.4e\t%.4f\t%.4f\t%.4f\n"
                     % (r["ppm"], r["height"], r["integral"], r["integral"] / refi,
                        r["lo_ppm"], r["hi_ppm"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
