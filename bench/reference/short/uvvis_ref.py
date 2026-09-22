#!/usr/bin/env python3
"""Reference UV-Vis band analysis for examples/uvvis_spectrum/PROMPT.md.

The recipe pinned in data/uvvis/README.md: restrict to the 250-700 nm analysis
window, take the band maximum as the global maximum in that window, find FWHM
by linear interpolation of the half-maximum crossings on each side, and count
bands as local maxima at or above 20% of the window maximum. The 20% floor
matters on this exact file: a lower threshold picks up a phantom band on the
long-wavelength tail (see the README's tier-(c) validation note).
"""
import numpy as np
import pandas as pd

WINDOW_LO, WINDOW_HI = 250.0, 700.0
BAND_FRACTION = 0.20


def run(csv_path):
    d = pd.read_csv(csv_path)
    w_all = d["wavelength_nm"].to_numpy(dtype=float)
    a_all = d["absorbance"].to_numpy(dtype=float)
    points = int(len(w_all))

    mask = (w_all >= WINDOW_LO) & (w_all <= WINDOW_HI)
    w = w_all[mask]
    a = a_all[mask]

    imax = int(np.argmax(a))
    lambda_max = float(w[imax])
    epsilon = float(a[imax])
    half = epsilon / 2.0

    # Left half-max crossing: walk left from the peak until the trace drops
    # below half-max, then interpolate linearly between the bracketing points.
    i = imax
    while i > 0 and a[i] >= half:
        i -= 1
    if i == imax:
        left = w[imax]
    else:
        x0, x1 = w[i], w[i + 1]
        y0, y1 = a[i], a[i + 1]
        left = x0 + (half - y0) * (x1 - x0) / (y1 - y0)

    # Right half-max crossing, symmetric to the left.
    j = imax
    n = len(a)
    while j < n - 1 and a[j] >= half:
        j += 1
    if j == imax:
        right = w[imax]
    else:
        x0, x1 = w[j - 1], w[j]
        y0, y1 = a[j - 1], a[j]
        right = x0 + (half - y0) * (x1 - x0) / (y1 - y0)

    fwhm = float(right - left)

    threshold = BAND_FRACTION * epsilon
    bands = 0
    for k in range(1, n - 1):
        if a[k] > a[k - 1] and a[k] >= a[k + 1] and a[k] >= threshold:
            bands += 1

    return {"points": points, "lambda_max": lambda_max, "epsilon": epsilon,
            "fwhm": fwhm, "bands": int(bands)}


if __name__ == "__main__":
    import sys
    r = run(sys.argv[1])
    print("points=%d bands=%d lambda_max=%.3f epsilon=%.2f fwhm=%.3f"
          % (r["points"], r["bands"], r["lambda_max"], r["epsilon"], r["fwhm"]))
