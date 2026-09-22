#!/usr/bin/env python3
"""Reference peak detection for examples/chrom_integration/PROMPT.md.

The recipe pinned in data/chrom/README.md and frozen, verbatim, in the answer
file data/chrom/analyze_chrom.py: baseline = median of the first 100 raw
points; robust sigma = 1.4826 * MAD of those same points; 5-point centered
moving-average smoothing (window truncated at the ends, so the first/last two
points average over fewer neighbours); a peak is a local maximum of the
SMOOTHED trace with sm[i] > sm[i-1] and sm[i] >= sm[i+1] and
sm[i] > baseline + 10*sigma; local maxima within 5 points of each other
collapse into one peak, the tallest (by smoothed value) winning. Reported
`height` comes from the RAW trace at the winning index.

Areas are also computed here (trapezoidal, between the half-height-crossing
bounds around each apex) so the output has an area column, but NO criterion
in grade_chrom_s.py grades area: data/chrom/README.md is explicit that peaks
7-10 ride a baseline that wanders roughly -7 to +5 mAU, so their areas are
sensitive to the baseline model used and pinning a number would fail a
correct implementation that chose a different (equally defensible) baseline
convention for integration. The area here is only good enough to populate the
column, not a certified quantity.
"""
import numpy as np
import pandas as pd

WINDOW_HALF = 2      # 5-point centered moving average (window_half*2 + 1)
MERGE_GAP = 5         # local maxima within this many samples merge
THRESHOLD_SIGMA = 10  # peak must exceed baseline + THRESHOLD_SIGMA * sigma
BASELINE_N = 100      # first N raw points anchor baseline and sigma


def _smooth(y):
    n = len(y)
    return np.array([y[max(0, i - WINDOW_HALF):i + WINDOW_HALF + 1].mean()
                      for i in range(n)])


def _half_height_bounds(y, baseline, k, half_thresh):
    """Indices bracketing the apex at k where the raw trace last stood above
    half_thresh, walking outward in each direction. Used only for the
    ungraded area column."""
    n = len(y)
    left = k
    while left > 0 and y[left - 1] > half_thresh:
        left -= 1
    right = k
    while right < n - 1 and y[right + 1] > half_thresh:
        right += 1
    return left, right


def run(csv_path):
    d = pd.read_csv(csv_path)
    t = d["time_s"].to_numpy(dtype=float)
    y = d["signal"].to_numpy(dtype=float)
    n = len(y)

    baseline = float(np.median(y[:BASELINE_N]))
    sigma = float(1.4826 * np.median(np.abs(y[:BASELINE_N] - baseline)))
    sm = _smooth(y)
    thr = baseline + THRESHOLD_SIGMA * sigma

    cands = [i for i in range(1, n - 1)
              if sm[i] > sm[i - 1] and sm[i] >= sm[i + 1] and sm[i] > thr]
    groups = []
    for i in cands:
        if groups and i - groups[-1][-1] <= MERGE_GAP:
            groups[-1].append(i)
        else:
            groups.append([i])

    peaks = []
    for g in groups:
        k = max(g, key=lambda i: sm[i])
        height = float(y[k])
        half_thresh = baseline + (height - baseline) / 2.0
        left, right = _half_height_bounds(y, baseline, k, half_thresh)
        area = float(np.trapezoid(y[left:right + 1] - baseline, t[left:right + 1]))
        peaks.append({"rt_apex_s": float(t[k]), "height": height, "area": area})

    peaks.sort(key=lambda p: p["rt_apex_s"])
    return {"points": int(n), "baseline": baseline, "sigma": sigma, "peaks": peaks}


if __name__ == "__main__":
    import sys
    r = run(sys.argv[1] if len(sys.argv) > 1 else "chrom.csv")
    print("points=%d baseline=%.3f sigma=%.3f peaks=%d"
          % (r["points"], r["baseline"], r["sigma"], len(r["peaks"])))
    for p in r["peaks"]:
        print("  rt_apex_s=%.2f height=%.2f area=%.3f"
              % (p["rt_apex_s"], p["height"], p["area"]))
