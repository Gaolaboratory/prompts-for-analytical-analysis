#!/usr/bin/env python3
"""Coarse reference MS1 feature analysis for tier (c) validation.

Documented reference method (deliberately simple and robust):

1. Keep MS1 scans only; one RT "slice" per MS1 scan (native cycle time).
2. Build m/z windows by greedy clustering of centroid sticks sorted by m/z
   (join the last window if |mz - running window mean| <= 0.01 Da and that
   window has no stick from the same scan; else start a new window).
   Keep windows observed in >= 5 distinct scans.
3. Take the top K = 200 windows by maximum stick intensity.
4. Per window, build the extracted-ion chromatogram (EIC): intensity at each
   MS1 scan (0 when the window has no stick in that scan).
5. Robust noise threshold per EIC: T = median(x) + 5 * MAD(x) with
   median/MAD taken over the window's observed (nonzero) intensities
   (absent scans are structural zeros, not noise, and would drive MAD to 0);
   windows with MAD == 0 are skipped.
6. Chromatographic peak event = maximal run of consecutive scans with
   x >= T, merging single-scan dips below T; a run counts if it spans
   >= 3 scans. Apex = max-intensity scan in the run; feature m/z =
   intensity-weighted mean of the window's sticks over the run; feature
   RT = scan start time of the apex.
7. Reference feature count N = total events over the K windows.
"""
import sys
import numpy as np
from pyteomics import mzml

MZ_TOL = 0.01     # Da, window clustering tolerance (same as the prompt's trace builder)
K = 200           # number of top-intensity m/z windows to analyse
MIN_SCANS = 5     # min distinct scans a window must appear in
K_MAD = 5         # robust noise threshold = median + K_MAD * MAD
MIN_LEN = 3       # min run length (scans) for a chromatographic peak event


def main(path):
    scans = []
    with mzml.read(path) as reader:
        for s in reader:
            if s.get('ms level') != 1:
                continue
            rt = float(s['scanList']['scan'][0]['scan start time'])
            scans.append((rt, np.asarray(s['m/z array']), np.asarray(s['intensity array'])))
    scans.sort(key=lambda t: t[0])
    rts = np.array([t[0] for t in scans])
    cycles = np.diff(rts)
    print(f"MS1 scans: {len(scans)}  RT: {rts[0]:.2f}..{rts[-1]:.2f} s  "
          f"median cycle {np.median(cycles):.2f} s")

    mz_all = np.concatenate([t[1] for t in scans])
    int_all = np.concatenate([t[2] for t in scans])
    scan_all = np.concatenate([np.full(len(t[1]), i, dtype=int) for i, t in enumerate(scans)])
    print(f"centroid sticks total: {mz_all.size}  "
          f"m/z range {mz_all.min():.3f}-{mz_all.max():.3f}")

    # --- greedy m/z-window clustering, sticks processed in m/z order --------
    order = np.argsort(mz_all, kind='stable')
    windows = []          # each: [sum_mz, n, max_int, {scan: (inten, mz)}]
    for idx in order:
        mz, inten, si = float(mz_all[idx]), float(int_all[idx]), int(scan_all[idx])
        if windows:
            w = windows[-1]
            if mz - w[0] / w[1] <= MZ_TOL and si not in w[3]:
                w[0] += mz
                w[1] += 1
                if inten > w[2]:
                    w[2] = inten
                w[3][si] = (inten, mz)
                continue
        windows.append([mz, 1, inten, {si: (inten, mz)}])

    keep = [w for w in windows if len(w[3]) >= MIN_SCANS]
    print(f"m/z windows (>= {MIN_SCANS} scans): {len(keep)}")
    top = sorted(keep, key=lambda w: -w[2])[:K]

    # --- EIC peak counting ----------------------------------------------------
    events = []
    skipped_mad0 = 0
    for w in top:
        x = np.zeros(len(scans))
        for si, (inten, _mz) in w[3].items():
            x[si] = inten
        observed = x[x > 0]
        med = float(np.median(observed))
        mad = float(np.median(np.abs(observed - med)))
        if mad == 0:
            skipped_mad0 += 1
            continue
        T = med + K_MAD * mad
        above = x >= T
        # merge single-scan dips: a False with True neighbours is inside a peak
        merged = above.copy()
        for i in range(1, len(above) - 1):
            if not merged[i] and merged[i - 1] and above[i + 1]:
                merged[i] = True
        i = 0
        while i < len(merged):
            if merged[i]:
                j = i
                while j + 1 < len(merged) and merged[j + 1]:
                    j += 1
                if j - i + 1 >= MIN_LEN:
                    seg = x[i:j + 1]
                    apex = i + int(np.argmax(seg))
                    num = den = 0.0
                    for si in range(i, j + 1):
                        if si in w[3]:
                            iv, mv = w[3][si]
                            num += iv * mv
                            den += iv
                    events.append({'mz': num / den if den else w[0] / w[1],
                                   'rt': float(rts[apex]),
                                   'intensity': float(x[apex]),
                                   'width': j - i + 1})
                i = j + 1
            else:
                i += 1

    print(f"windows analysed: {len(top) - skipped_mad0} (skipped MAD==0: {skipped_mad0})")
    print(f"REFERENCE FEATURE COUNT N = {len(events)} "
          f"(chromatographic peak events over the top {K} m/z windows)")
    events.sort(key=lambda e: -e['intensity'])
    widths = [e['width'] for e in events]
    if widths:
        print(f"event width (scans): median {int(np.median(widths))}, "
              f"range {min(widths)}-{max(widths)}")
    print("\nTop 10 events by apex intensity:")
    print("rank  m/z          RT_apex(s)  apex intensity   width(scans)")
    for i, e in enumerate(events[:10], 1):
        print(f"{i:4d}  {e['mz']:12.4f}  {e['rt']:10.2f}  {e['intensity']:15.6g}  {e['width']:4d}")


if __name__ == '__main__':
    main(sys.argv[1])
