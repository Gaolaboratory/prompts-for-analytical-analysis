#!/usr/bin/env python3
import math

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

rnd = lcg(20260824)

SAMPLES = ["CTRL_%d" % i for i in range(1, 6)] + ["EXP_%d" % i for i in range(1, 6)]
GROUP = [-1.0] * 5 + [1.0] * 5

# shared per-sample jitter (within-group structure): drives the PC2 block
delta = [(next(rnd) + next(rnd) + next(rnd) - 1.5) for _ in SAMPLES]

rows = []  # (feature_id, [10 values or None])
fid = 0

def noise(amp):
    return amp * (next(rnd) + next(rnd) - 1.0)

# block A: 12 group-signal features, up in EXP, correlated via the shared group term
for _ in range(12):
    fid += 1
    base = 1.0e4 * (10.0 ** (next(rnd) * 2.0))          # 1e4..1e6
    loading = 0.8 + 0.6 * next(rnd)                      # 0.8..1.4
    vals = [base * (2.0 ** (loading * GROUP[j] + 0.1 * delta[j] + noise(0.10)))
            for j in range(10)]
    rows.append(("MET_S%02d" % fid, vals))

# block B: 6 features tracking the shared per-sample jitter (within-group structure)
for _ in range(6):
    fid += 1
    base = 1.0e4 * (10.0 ** (next(rnd) * 2.0))
    vals = [base * (2.0 ** (1.2 * delta[j] + noise(0.10))) for j in range(10)]
    rows.append(("MET_B%02d" % fid, vals))

# 8 pure-noise features
for _ in range(8):
    fid += 1
    base = 1.0e4 * (10.0 ** (next(rnd) * 2.0))
    rows.append(("MET_N%02d" % fid, [base * (2.0 ** noise(0.30)) for j in range(10)]))

# 1 feature with 2 missing cells (kept: exactly 20% missing, imputed with row mean)
fid += 1
vals = [5.0e4 * (2.0 ** noise(0.20)) for j in range(10)]
vals[2] = None
vals[7] = None
rows.append(("MET_M%02d" % fid, vals))

# 1 feature with 3 missing cells (filtered: > 20% missing)
fid += 1
vals = [8.0e4 * (2.0 ** noise(0.20)) for j in range(10)]
vals[1] = None
vals[4] = None
vals[9] = None
rows.append(("MET_X%02d" % fid, vals))

out = ["feature_id," + ",".join(SAMPLES)]
for name, vals in rows:
    cells = ["" if v is None else "%.4f" % v for v in vals]
    out.append(name + "," + ",".join(cells))
open("features.csv", "w").write("\n".join(out) + "\n")
print("wrote features.csv:", len(rows), "features x", len(SAMPLES), "samples")
