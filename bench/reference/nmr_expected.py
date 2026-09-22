"""Recompute the nmr expected-results oracle for data/nmr/fid_complex.csv.

Magnitude-mode spectrum, valley-bounded peak integration, TSP/DSS-normalised.
numpy only (no nmrglue) — runs under the pinned .venv-bench:

    .venv-bench/bin/python3 bench/reference/nmr_expected.py

Reads only data/nmr/fid_complex.csv; does not touch the raw Bruker source or
regenerate the FID.

All six resonances' ppm positions are graded (+/-0.05 ppm each). Only the
four metabolite integrals (acetate, citrate, creatinine CH3, creatinine CH2)
are graded on intensity, against TSP/DSS = 1.000 by definition. Water's
integral is reported for information only and is not graded — see
data/nmr/README.md for why (a presaturated water line is broad and its
integral is window-sensitive; water was tried as the normalisation reference
in an earlier round and rejected for exactly this reason).

Sensitivity check (does not change the default behaviour or output above):

    .venv-bench/bin/python3 bench/reference/nmr_expected.py --sensitivity

Recomputes the four graded integrals under ambiguous-but-defensible readings
of the same written recipe (peak-picking threshold, window cap, baseline
estimator, valley-test strictness) and reports the relative change from the
default (pinned) value for each, plus the single worst deviation observed
among the four graded integrals. Of these four axes only three are genuine
ambiguities in the written recipe (threshold, baseline estimator, valley
strictness); the window cap is pinned at +/-0.10 ppm by the written recipe,
not ambiguous, so its variants are reported for diagnostic completeness but
are not evidence for or against the bound.
"""
import sys
import numpy as np

CSV = 'data/nmr/fid_complex.csv'
SF = 699.869954581      # MHz, pdata/1/procs SF
CARRIER_PPM = 4.76648   # pdata/1/procs OFFSET - SW_ppm/2
SW_HZ = 14005.6022      # acqus SW_h, full complex bandwidth
LB = 1.0                # Hz, exponential apodization
NFFT = 65536            # zero-fill target
VALLEY_CAP_PPM = 0.10   # max half-window for valley-bounded integration (pinned)
PICK_FRAC = 0.05        # local-maxima threshold, fraction of spectrum max (pinned)
MATCH_WINDOW_PPM = 0.05 # search window around each nominal ppm for its apex
BASELINE_MODE = 'mean'  # pinned: mean of the two window-boundary spectrum values
VALLEY_STRICT = False   # pinned: non-strict stop test, spec[neighbor] >= spec[i] stops
                        # (equivalently: continue only while spec[neighbor] < spec[i];
                        #  a flat point immediately stops the walk — it does not wait
                        #  for an actual rise before stopping)

TARGETS = {
    'TSP/DSS': 0.000,
    'acetate': 1.921,
    'citrate': 2.549,
    'creatinine CH3': 3.048,
    'creatinine CH2': 4.058,
    'water': 4.767,
}

REFERENCE_NAME = 'TSP/DSS'   # resonance nearest 0.000 ppm; rel_integral = 1.000 by definition
GRADED_INTEGRAL_NAMES = ('acetate', 'citrate', 'creatinine CH3', 'creatinine CH2')
UNGRADED_INTEGRAL_NAMES = ('water',)  # position still graded; integral reported, not graded


def read_fid(path):
    t, re, im = [], [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('time_s'):
                continue
            a, b, c = line.split(',')
            t.append(float(a))
            re.append(float(b))
            im.append(float(c))
    return np.array(t), np.array(re) + 1j * np.array(im)


def build_spectrum(t, z):
    xw = z * np.exp(-np.pi * LB * t)
    X = np.fft.fftshift(np.fft.fft(xw, NFFT))
    f = (np.arange(NFFT) - NFFT // 2) * (SW_HZ / NFFT)
    ppm = CARRIER_PPM + f / SF
    spec = np.abs(X)
    return ppm, spec


def valley_bound(spec, apex_idx, cap_bins, strict=VALLEY_STRICT):
    """Walk outward from apex_idx in each direction until the spectrum stops
    falling (a local minimum) or the cap is reached.

    strict=False (pinned/default): the walk stops as soon as the neighbour is
      not strictly lower than the current point (spec[neighbor] >= spec[i]) —
      a flat point stops the walk immediately.
    strict=True (sensitivity variant): the walk stops only once the neighbour
      is strictly higher than the current point (spec[neighbor] > spec[i]) —
      a flat region is walked through and does not by itself stop the walk.
    """
    n = len(spec)
    i = apex_idx
    if strict:
        while i > 0 and (apex_idx - i) < cap_bins and spec[i - 1] <= spec[i]:
            i -= 1
    else:
        while i > 0 and (apex_idx - i) < cap_bins and spec[i - 1] < spec[i]:
            i -= 1
    left = max(i, apex_idx - cap_bins, 0)
    j = apex_idx
    if strict:
        while j < n - 1 and (j - apex_idx) < cap_bins and spec[j + 1] <= spec[j]:
            j += 1
    else:
        while j < n - 1 and (j - apex_idx) < cap_bins and spec[j + 1] < spec[j]:
            j += 1
    right = min(j, apex_idx + cap_bins, n - 1)
    return left, right


def integrate_window(spec, dppm, left, right, mode=BASELINE_MODE):
    window = spec[left:right + 1]
    if mode == 'mean':
        baseline = 0.5 * (spec[left] + spec[right])
        return float(np.sum(window - baseline) * dppm)
    elif mode == 'min':
        baseline = float(np.min(window))
        return float(np.sum(window - baseline) * dppm)
    elif mode == 'linear':
        baseline = np.linspace(spec[left], spec[right], len(window))
        return float(np.sum(window - baseline) * dppm)
    raise ValueError('unknown baseline mode: %r' % mode)


def compute(ppm, spec, dppm, pick_frac=PICK_FRAC, cap_ppm=VALLEY_CAP_PPM,
            baseline_mode=BASELINE_MODE, valley_strict=VALLEY_STRICT):
    """Run the full recipe (peak pick -> apex match -> valley-bound -> integrate
    -> TSP/DSS-normalise) for one choice of the four parameters."""
    n = len(spec)
    cap_bins = int(round(cap_ppm / dppm))
    smax = spec.max()

    is_max = np.zeros(n, dtype=bool)
    is_max[1:-1] = (spec[1:-1] > spec[:-2]) & (spec[1:-1] > spec[2:])
    cand = np.where(is_max & (spec >= pick_frac * smax))[0]

    results = {}
    for name, nominal in TARGETS.items():
        in_window = cand[np.abs(ppm[cand] - nominal) <= MATCH_WINDOW_PPM]
        if len(in_window) == 0:
            idxs = np.where(np.abs(ppm - nominal) <= MATCH_WINDOW_PPM)[0]
            apex = idxs[np.argmax(spec[idxs])]
        else:
            apex = in_window[np.argmax(spec[in_window])]
        left, right = valley_bound(spec, apex, cap_bins, strict=valley_strict)
        integral = integrate_window(spec, dppm, left, right, mode=baseline_mode)
        results[name] = dict(nominal=nominal, apex_ppm=float(ppm[apex]),
                              left_ppm=float(ppm[left]), right_ppm=float(ppm[right]),
                              integral=integral)

    ref_integral = results[REFERENCE_NAME]['integral']
    for name in results:
        results[name]['rel_integral'] = results[name]['integral'] / ref_integral
    return results, len(cand)


def main():
    t, z = read_fid(CSV)
    N = len(z)
    dt = t[1] - t[0]

    ppm, spec = build_spectrum(t, z)
    dppm = abs(ppm[1] - ppm[0])
    cap_bins = int(round(VALLEY_CAP_PPM / dppm))

    print("N=%d dt=%.6e SW_h=%.4f SF=%.9f carrier=%.5f NFFT=%d LB=%.3f cap_bins=%d dppm=%.6e"
          % (N, dt, SW_HZ, SF, CARRIER_PPM, NFFT, LB, cap_bins, dppm))

    results, n_cand = compute(ppm, spec, dppm)
    print("total local maxima >= %.0f%% of spectrum max: %d" % (PICK_FRAC * 100, n_cand))

    print("\nmagnitude-mode reference peaks (valley-bounded integration, TSP/DSS-normalised):")
    print("  %-16s %9s %9s %9s %20s %14s  %s" %
          ("resonance", "nominal", "apex", "delta", "window(ppm)", "rel_integral", "graded?"))
    for name, nominal in TARGETS.items():
        r = results[name]
        delta = abs(r['apex_ppm'] - nominal)
        if name == REFERENCE_NAME:
            graded = "position only (reference, =1.000 by definition)"
        elif name in GRADED_INTEGRAL_NAMES:
            graded = "position + integral"
        else:
            graded = "position only (integral informational)"
        print("  %-16s %9.3f %9.4f %9.4f  [%8.4f,%8.4f] %14.4f  %s"
              % (name, nominal, r['apex_ppm'], delta, r['left_ppm'], r['right_ppm'],
                 r['rel_integral'], graded))

    print("\nall relative integrals positive:", all(results[n]['integral'] > 0 for n in results))
    print("max apex delta (ppm):", max(abs(results[n]['apex_ppm'] - results[n]['nominal']) for n in results))


def run_sensitivity():
    t, z = read_fid(CSV)
    ppm, spec = build_spectrum(t, z)
    dppm = abs(ppm[1] - ppm[0])

    baseline_result, _ = compute(ppm, spec, dppm)
    baseline_rel = {name: baseline_result[name]['rel_integral'] for name in TARGETS}

    print("Baseline (pinned) relative integrals (TSP/DSS = 1.000 by definition):")
    for name in TARGETS:
        tag = " [GRADED]" if name in GRADED_INTEGRAL_NAMES else ""
        print("  %-16s %10.4f%s" % (name, baseline_rel[name], tag))

    variants = [
        ('pick_frac=0.03 (vs pinned 0.05) [ambiguous]', dict(pick_frac=0.03)),
        ('pick_frac=0.08 (vs pinned 0.05) [ambiguous]', dict(pick_frac=0.08)),
        ('cap=0.05 ppm (vs pinned 0.10) [NOT ambiguous - cap is pinned; diagnostic only]', dict(cap_ppm=0.05)),
        ('cap=0.15 ppm (vs pinned 0.10) [NOT ambiguous - cap is pinned; diagnostic only]', dict(cap_ppm=0.15)),
        ('baseline=min-in-window (vs pinned mean-of-boundary) [ambiguous]', dict(baseline_mode='min')),
        ('baseline=linear-interp (vs pinned mean-of-boundary) [ambiguous]', dict(baseline_mode='linear')),
        ('valley_strict=True (vs pinned False) [ambiguous]', dict(valley_strict=True)),
    ]

    worst_graded = (None, None, 0.0)       # worst among GRADED_INTEGRAL_NAMES, any variant
    worst_graded_ambiguous = (None, None, 0.0)  # worst among GRADED_INTEGRAL_NAMES, ambiguous variants only
    print("\nSensitivity: relative change in rel_integral vs baseline, per variant per resonance")
    print("(relative change = (variant - baseline) / baseline)\n")
    for label, kwargs in variants:
        is_ambiguous = 'NOT ambiguous' not in label
        result, _ = compute(ppm, spec, dppm, **kwargs)
        print(label + ":")
        for name in TARGETS:
            v = result[name]['rel_integral']
            b = baseline_rel[name]
            rel_change = (v - b) / b if b != 0 else float('nan')
            tag = " [GRADED]" if name in GRADED_INTEGRAL_NAMES else ""
            print("    %-16s baseline %10.4f  variant %10.4f  rel_change %+8.2f%%%s"
                  % (name, b, v, rel_change * 100, tag))
            if name in GRADED_INTEGRAL_NAMES:
                if abs(rel_change) > abs(worst_graded[2]):
                    worst_graded = (label, name, rel_change)
                if is_ambiguous and abs(rel_change) > abs(worst_graded_ambiguous[2]):
                    worst_graded_ambiguous = (label, name, rel_change)
        print()

    print("WORST relative change among the four GRADED integrals, across ALL variants "
          "(including the non-ambiguous cap diagnostic):")
    print("  variant=%r resonance=%r rel_change=%+.2f%% (%.4f)"
          % (worst_graded[0], worst_graded[1], worst_graded[2] * 100, worst_graded[2]))
    print("  within +/-20%% bound: %s" % (abs(worst_graded[2]) <= 0.20))

    print("\nWORST relative change among the four GRADED integrals, "
          "genuinely AMBIGUOUS axes only (threshold, baseline estimator, valley strictness):")
    print("  variant=%r resonance=%r rel_change=%+.2f%% (%.4f)"
          % (worst_graded_ambiguous[0], worst_graded_ambiguous[1],
             worst_graded_ambiguous[2] * 100, worst_graded_ambiguous[2]))
    print("  within +/-20%% bound: %s" % (abs(worst_graded_ambiguous[2]) <= 0.20))


if __name__ == '__main__':
    if '--sensitivity' in sys.argv:
        run_sensitivity()
    else:
        main()
