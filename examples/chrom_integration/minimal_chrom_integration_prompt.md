# Chromatographic peak integration and USP system-suitability QC

Python 3 standard library only — **no `numpy`, `scipy`, `pandas`**. Write `chrom_integrate.py`.

The tool reads a chromatogram CSV (columns `time_s,signal`, uniform 1 s sampling, `#` comment lines and one header row), detects peaks on a lightly smoothed trace, integrates each peak against a straight-line baseline, and writes a tab-separated peak table with USP system-suitability parameters (resolution, tailing factor, plate count, S/N against a user-specified noise region). Noise region bounds are given in seconds on the command line.

`python3 chrom_integrate.py chrom.csv --noise 0 25 -o peaks.tsv`

## The parts you can't guess

- **USP vs. EP conventions differ — use USP here.** Resolution `Rs = 2(tR2 − tR1)/(w1 + w2)` with **baseline widths** `w = rt_end − rt_start` (the EP half-height variant carries a 1.18 factor — do not mix them). Plate count `N = 16·(tR/w)²` with the same baseline width (the half-height variant is `5.54·(tR/w½)²` — do not mix).
- **Tailing factor is measured at 5% of peak height** (USP): `Tf = W0.05 / (2a)`, where `W0.05` is the full width at 5% height above baseline and `a` is the front segment, apex-to-left-crossing. The 10%-height quantity is the *asymmetry factor* `As = b/a` — a different statistic; do not report it here.
- **S/N is pinned to `height / σ_noise`**, where `σ_noise` is the sample standard deviation (n−1) of the **raw** signal inside `--noise LO HI`. Real USP S/N uses `2H/h` over a peak-width-wide noise band; we deliberately simplify — do not "correct" this.
- **A tailing peak is an exponentially modified Gaussian (EMG)**, used by the generator. Verbatim:

```python
def emg(t, mu, sig, lam, A):          # area A, exponential tail constant 1/lam
    x = (lam / 2.0) * (2 * mu + lam * sig * sig - 2 * t)
    z = (mu + lam * sig * sig - t) / (sig * math.sqrt(2.0))
    if x > 600:
        return 0.0
    return (A * lam / 2.0) * math.exp(x) * math.erfc(z)
```

  Note: an EMG's apex sits **right of `mu`** (by roughly `lam·sig²` here); a measured apex of 244 s for `mu = 240` is correct, not a bug.

## Test data generator — `make_chrom_data.py`, exactly this script

Three peaks (two Gaussians, one tailing EMG), linear baseline drift `50 + 0.10·t`, Gaussian noise (σ = 5) from a seeded LCG via Box–Muller, 300 points at 1 s spacing. Never use the `random` module. The first line is a `#` comment and the second is the header, mimicking exported instrument files.

```python
#!/usr/bin/env python3
"""Deterministic chromatogram generator. Std-lib only."""
import math

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

def gauss(t, mu, sig, h):
    return h * math.exp(-((t - mu) ** 2) / (2 * sig * sig))

def emg(t, mu, sig, lam, A):
    x = (lam / 2.0) * (2 * mu + lam * sig * sig - 2 * t)
    z = (mu + lam * sig * sig - t) / (sig * math.sqrt(2.0))
    if x > 600:
        return 0.0
    return (A * lam / 2.0) * math.exp(x) * math.erfc(z)

PEAKS = [(60.0, 4.0, 800.0), (150.0, 5.0, 1200.0)]   # mu, sigma, height
EMG = (240.0, 4.5, 0.15, 12000.0)                    # mu, sigma, lambda, area
NOISE_SD = 5.0

rnd = lcg(20260824)
lines = ["# MiniLC-100 export, channel=UV254, method=DEFAULT", "time_s,signal"]
for i in range(300):
    t = float(i)
    s = 50.0 + 0.10 * t
    for mu, sig, h in PEAKS:
        s += gauss(t, mu, sig, h)
    s += emg(t, *EMG)
    u1 = max(next(rnd), 1e-12); u2 = next(rnd)
    s += NOISE_SD * math.sqrt(-2.0 * math.log(u1)) * math.cos(2 * math.pi * u2)
    lines.append(f"{t:.1f},{s:.4f}")
open("chrom.csv", "w").write("\n".join(lines) + "\n")
print("wrote chrom.csv")
```

## Algorithm

Let `y` be the raw signal, `sm` the smoothed signal, `m`/`σ` the noise-region mean/sd, `H = sm[apex] − m`.

1. **Parse** — skip blank lines, lines starting with `#`, and the `time_s,signal` header; split the rest on commas.
2. **Smooth** — 5-point centered moving average; at the two points nearest each end, average only the samples that exist (truncated window, not zero-padded).
3. **Noise** — `m` = mean and `σ` = sample sd (n−1) of raw `y` with `LO ≤ t ≤ HI`.
4. **Apexes** — indices `i` with `sm[i] > sm[i-1]` and `sm[i] >= sm[i+1]` and `sm[i] >= m + 10σ`.
5. **Bounds** — walk down from the apex on the **smoothed** trace; stop at the 2%-of-apex level or at a valley (signal rising again), exactly:

```python
l = apex
while l > 0 and sm[l-1] < sm[l] and sm[l-1] - m >= 0.02 * H: l -= 1
r = apex
while r < len(sm)-1 and sm[r+1] < sm[r] and sm[r+1] - m >= 0.02 * H: r += 1
```

6. **Baseline** — straight line between the **raw** values `y[l]` and `y[r]`.
7. **Integrate on raw signal** — `height` = max of `y − baseline` within `[l, r]`; `rt_apex` = time of that maximum; `area` = trapezoid of `y − baseline` over `[l, r]`; `width = t[r] − t[l]`.
8. **QC per peak** — `N = 16·(rt_apex/width)²`; `Tf` from the 5%-height crossings of `y − baseline`, located by **linear interpolation between adjacent samples**; `sn = height/σ`; `rs_to_previous = 2·(tR − tR_prev)/(width + width_prev)` (`-` for peak 1).

## Verify your core before continuing

Hand-checkable on a symmetric triangle with zero baseline: `t = [0,1,2,3,4]`, `y = [0,1,2,1,0]`, bounds `l=0, r=4` must give exactly:

| quantity | area | height | rt_apex | 5% crossings | Tf | N |
|---|---|---|---|---|---|---|
| expected | 4.000 | 2.000 | 2.000 | 0.100 / 3.900 | 1.000 | 4.000 |

## Acceptance criteria

Run `python3 make_chrom_data.py`, then `python3 chrom_integrate.py chrom.csv --noise 0 25 -o peaks.tsv`:

1. Self-check above passes exactly.
2. Stdout (not stderr) prints the noise statistics — `n=26, mean=51.076, sd=4.291` (±0.001) — and the line `peaks detected: 3`.
3. `peaks.tsv` is **tab-separated** with Unix newlines, header exactly `peak_id	rt_apex	rt_start	rt_end	height	area	width	N	tf	sn	rs_to_previous`, then exactly **3 rows** sorted by `rt_apex` ascending; all numeric fields printed with 3 decimals; `rs_to_previous` is `-` for peak 1.
4. `rt_apex` = 60.0, 150.0, 244.0 (±1.0).
5. `area` = 7822, 14920, 12032 (±5%); `height` = 786, 1199, 725 (±5%).
6. Peaks 1–2 are symmetric: `tf` = 0.99 ± 0.10. Peak 3 tails: `tf` = 1.34 ± 0.10.
7. `N` = 100, 331, 315 (±15%); `rs_to_previous` = 3.158 and 2.136 (±0.15); `sn` = 183, 279, 169 (±10%).

Reference rows (last digit may differ): `1 60.000 48.000 72.000 786.254 7821.509 24.000 100.000 0.993 183.245 -` · `2 150.000 135.000 168.000 1198.618 14920.273 33.000 330.579 0.988 279.350 3.158` · `3 244.000 225.000 280.000 725.128 12032.407 55.000 314.901 1.339 168.999 2.136`.

## If something fails

0 peaks or a parse crash → comment/header lines not skipped. 4+ peaks → apexes must be tested on the **smoothed** trace with the 10σ threshold. Peak 3 apex ≠ 240 → expected; EMG apexes shift right of `mu`. Peak-1 area ~2.5% below the analytic 8021 → per spec: bounds truncate at 2% of apex height. Tf < 1 on every peak → you computed the asymmetry factor (10% height) or swapped front/back. N wildly large → you mixed conventions (half-height width with the 16· formula). `sn` off by 2× → you implemented textbook USP `2H/h` instead of the pinned `height/σ`.

## Optional

Also report EP half-height plate count and 10% asymmetry factor as extra columns; shoulder detection via sign changes of the smoothed second difference; batch mode over a directory of CSVs with a summary table.
