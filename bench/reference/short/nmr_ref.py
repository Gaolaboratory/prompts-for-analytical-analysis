#!/usr/bin/env python3
"""Reference 1D 1H NMR processing for examples/nmr_1d/PROMPT.md.

The recipe pinned in data/nmr/README.md and implemented by the build-time
oracle `bench/reference/nmr_expected.py`: read the complex FID (real +
1j*imag), apodize `exp(-pi*LB*t)` at LB = 1.0 Hz, zero-fill to NFFT = 65536,
FFT, fftshift; ppm = CARRIER_PPM + f/SF with f = (arange(NFFT) - NFFT//2) *
SW_HZ/NFFT; take the magnitude spectrum; pick local maxima at or above 5% of
the spectrum maximum; integrate each picked peak over a valley-bounded
window (walk outward from the apex while the next bin is strictly lower,
capped at +/-0.10 ppm per side), baseline = mean of the two window-boundary
spectrum values; normalise every integral to the resonance nearest 0.000 ppm
(TSP/DSS), which becomes 1.000.

numpy only. Reads only the workspace's own fid_complex.csv -- this module
must agree with bench/reference/nmr_expected.py, which produced the table in
data/nmr/README.md's "## Expected results" section.
"""
import numpy as np

SF = 699.869954581      # MHz, pdata/1/procs SF
CARRIER_PPM = 4.76648   # pdata/1/procs OFFSET - SW_ppm/2
SW_HZ = 14005.6022      # acqus SW_h, full complex bandwidth
LB = 1.0                # Hz, exponential apodization
NFFT = 65536            # zero-fill target
VALLEY_CAP_PPM = 0.10   # max half-window for valley-bounded integration
PICK_FRAC = 0.05        # local-maxima threshold, fraction of spectrum max

REFERENCE_PPM = 0.000   # TSP/DSS: the resonance nearest this becomes 1.000


def _read_fid(csv_path):
    t, re, im = [], [], []
    with open(csv_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("time_s"):
                continue
            a, b, c = line.split(",")
            t.append(float(a))
            re.append(float(b))
            im.append(float(c))
    return np.array(t), np.array(re) + 1j * np.array(im)


def _valley_bound(spec, apex_idx, cap_bins):
    """Walk outward from apex_idx in each direction until the spectrum stops
    strictly falling, or the cap is reached."""
    n = len(spec)
    i = apex_idx
    while i > 0 and (apex_idx - i) < cap_bins and spec[i - 1] < spec[i]:
        i -= 1
    left = max(i, apex_idx - cap_bins, 0)
    j = apex_idx
    while j < n - 1 and (j - apex_idx) < cap_bins and spec[j + 1] < spec[j]:
        j += 1
    right = min(j, apex_idx + cap_bins, n - 1)
    return left, right


def _integrate_window(spec, dppm, left, right):
    window = spec[left:right + 1]
    baseline = 0.5 * (spec[left] + spec[right])
    return float(np.sum(window - baseline) * dppm)


def run(csv_path):
    t, z = _read_fid(csv_path)
    n_points = len(z)

    xw = z * np.exp(-np.pi * LB * t)
    spec_complex = np.fft.fftshift(np.fft.fft(xw, NFFT))
    f = (np.arange(NFFT) - NFFT // 2) * (SW_HZ / NFFT)
    ppm = CARRIER_PPM + f / SF
    spec = np.abs(spec_complex)
    dppm = abs(ppm[1] - ppm[0])
    cap_bins = int(round(VALLEY_CAP_PPM / dppm))

    smax = spec.max()
    is_max = np.zeros(NFFT, dtype=bool)
    is_max[1:-1] = (spec[1:-1] > spec[:-2]) & (spec[1:-1] > spec[2:])
    cand = np.where(is_max & (spec >= PICK_FRAC * smax))[0]

    peaks = []
    for idx in cand:
        left, right = _valley_bound(spec, idx, cap_bins)
        integral = _integrate_window(spec, dppm, left, right)
        peaks.append({"ppm_center": float(ppm[idx]), "integral_raw": integral})

    # Normalise to the picked peak nearest 0.000 ppm (TSP/DSS).
    ref_peak = min(peaks, key=lambda p: abs(p["ppm_center"] - REFERENCE_PPM))
    ref_integral = ref_peak["integral_raw"]
    for p in peaks:
        p["integral_rel"] = p["integral_raw"] / ref_integral
        del p["integral_raw"]

    peaks.sort(key=lambda p: p["ppm_center"])

    return {"points": int(n_points), "peaks": peaks,
            "reference_ppm": float(ref_peak["ppm_center"])}


if __name__ == "__main__":
    import sys
    r = run(sys.argv[1])
    print("points=%d peaks=%d reference_ppm=%.3f"
          % (r["points"], len(r["peaks"]), r["reference_ppm"]))
