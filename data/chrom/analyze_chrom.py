#!/usr/bin/env python3
"""Harness-side reference analysis for data/chrom/chrom.csv (tier c, chrom_integration).

This is the DOCUMENTED method the LLM tool run will be judged against.
Std-lib only. Run: python3 analyze_chrom.py [chrom.csv]

Method (frozen 2026-08-26 — do not change without re-deriving the reference):
  1. Read time_s,signal; signal is in mAU at 220 nm.
  2. baseline b   = median of the FIRST 100 raw points (t = 0.12..39.72 s, verified flat:
                    no local maximum exceeds b + 3*sigma anywhere before t = 320 s).
  3. robust sd    = 1.4826 * MAD of the first 100 raw points (about their median).
  4. smooth       = 5-point centered moving average (truncated at the ends).
  5. apex i       = sm[i] > sm[i-1] AND sm[i] >= sm[i+1] AND sm[i] > b + 10*sd.
  6. apexes within 5 points of each other are one peak (keep the tallest).
Reference: 10 peaks. Grading of a tool run: every reference apex must appear in the
tool's peak table within +/-5% of its time (and no extra peak above b + 10*sd may be
reported that the reference method did not find).
"""
import csv
import statistics as st
import sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "chrom.csv"
    rows = list(csv.reader(open(path)))
    assert rows[0] == ["time_s", "signal"], rows[0]
    t = [float(r[0]) for r in rows[1:]]
    y = [float(r[1]) for r in rows[1:]]
    n = len(y)

    sm = [sum(y[max(0, i - 2):i + 3]) / len(y[max(0, i - 2):i + 3]) for i in range(n)]
    b = st.median(y[:100])
    sigma = 1.4826 * st.median([abs(v - b) for v in y[:100]])
    thr = b + 10 * sigma

    cands = [i for i in range(1, n - 1)
             if sm[i] > sm[i - 1] and sm[i] >= sm[i + 1] and sm[i] > thr]
    groups = []
    for i in cands:
        if groups and i - groups[-1][-1] <= 5:
            groups[-1].append(i)
        else:
            groups.append([i])

    gi = max(range(n), key=lambda i: y[i])
    print(f"# points={n}  t=[{t[0]:.2f},{t[-1]:.2f}] s  dt={t[1]-t[0]:.2f} s")
    print(f"# baseline(median first100) = {b:.4f} mAU   robust sd = {sigma:.4f} mAU   "
          f"threshold = {thr:.4f} mAU")
    print(f"# GLOBAL MAX: {y[gi]:.3f} mAU at t = {t[gi]:.2f} s ({t[gi]/60:.3f} min)")
    print(f"# N peaks = {len(groups)}")
    print("# apex_s     apex_min   height_mAU  above_base")
    for g in groups:
        k = max(g, key=lambda i: sm[i])
        print(f"  {t[k]:8.2f}   {t[k]/60:7.3f}   {y[k]:9.2f}  {y[k]-b:+9.2f}")


if __name__ == "__main__":
    main()
