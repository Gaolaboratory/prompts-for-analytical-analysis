#!/usr/bin/env python3
"""Reference MS1 feature detection for examples/feature_extraction/PROMPT.md.

The recipe pinned in data/feature_extraction/README.md, expressed in the prompt's
terms. Uses the tested std-lib reader in bench/reference/lib so the reference does not
depend on an agent's module.
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lib"))
from mzml_reader import read_mzml                       # noqa: E402

# data/feature_extraction/README.md, "Top 10 events by apex intensity" (m/z, RT s)
REFERENCE_TOP10 = [
    (395.2392, 1943.80), (487.7323, 1848.68), (395.7405, 1941.74),
    (325.4912, 1850.10), (488.2334, 1848.68), (388.2539, 1977.38),
    (443.7112, 1749.73), (722.3250, 1788.01), (738.3110, 1900.27),
    (344.2280, 1827.04),
]


def detect(path, top_k=200, min_scans=5, min_run=3, mz_tol=0.01, k_mad=5.0):
    ms1 = [s for s in read_mzml(path) if s["ms_level"] == 1]
    rts = [s["rt"] for s in ms1]
    sticks = sorted(((mz, i, inten)
                     for i, s in enumerate(ms1)
                     for mz, inten in zip(s["mz"], s["intensity"])),
                    key=lambda t: t[0])
    windows, cur, cur_scans, cur_sum = [], [], set(), 0.0
    for mz, i, inten in sticks:
        if cur and abs(mz - cur_sum / len(cur)) <= mz_tol and i not in cur_scans:
            cur.append((mz, i, inten)); cur_scans.add(i); cur_sum += mz
        else:
            if len(cur_scans) >= min_scans:
                windows.append(cur)
            cur, cur_scans, cur_sum = [(mz, i, inten)], {i}, mz
    if len(cur_scans) >= min_scans:
        windows.append(cur)
    windows.sort(key=lambda w: max(t[2] for t in w), reverse=True)
    kept = windows[:top_k]

    features = []
    for w in kept:
        eic = np.zeros(len(ms1))
        for mz, i, inten in w:
            eic[i] += inten
        nz = eic[eic > 0]
        thr = np.median(nz) + k_mad * np.median(np.abs(nz - np.median(nz)))
        above = eic >= thr
        for j in range(1, len(above) - 1):          # bridge single-scan dips
            if not above[j] and above[j - 1] and above[j + 1]:
                above[j] = True
        j = 0
        while j < len(above):
            if not above[j]:
                j += 1
                continue
            k = j
            while k + 1 < len(above) and above[k + 1]:
                k += 1
            if k - j + 1 >= min_run:
                inrun = [(mz, i, inten) for mz, i, inten in w if j <= i <= k]
                tot = sum(t[2] for t in inrun) or 1.0
                apex = int(j + np.argmax(eic[j:k + 1]))
                features.append({
                    "mz": sum(t[0] * t[2] for t in inrun) / tot,
                    "rt_apex": rts[apex], "rt_start": rts[j], "rt_end": rts[k],
                    "apex_intensity": float(eic[apex]), "n_scans": k - j + 1})
            j = k + 1
    features.sort(key=lambda f: f["apex_intensity"], reverse=True)
    return {"ms1_scans": len(ms1), "windows": len(kept), "features": features}


if __name__ == "__main__":
    r = detect(sys.argv[1])
    print("ms1_scans=%d windows=%d features=%d"
          % (r["ms1_scans"], r["windows"], len(r["features"])))
