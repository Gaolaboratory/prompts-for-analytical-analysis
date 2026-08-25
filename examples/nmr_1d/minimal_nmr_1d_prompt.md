# 1D NMR processing from FID

Standard library only (no `numpy`, `scipy`, `nmrglue`). Write `nmr_1d.py`.

`nmr_1d.py` reads a single-channel (real) 1D FID from a CSV of `time_s,intensity` rows, applies exponential apodization, zero-fills, Fourier-transforms, applies a zero-order phase correction, builds the ppm axis, picks peaks, integrates each peak, and writes a tab-separated multiplet table sorted by ppm. CLI: `python3 nmr_1d.py fid.csv -o multiplets.tsv`. Print progress counts to stdout (see criteria). A deterministic generator for `fid.csv` is below; run it first.

## Fixed acquisition and processing parameters

These are binding constants — the CSV carries them as `#` comments, but do not parse them out:

- Spectrometer frequency `SFO1 = 400.0` MHz, carrier `CARRIER_PPM = -4.0`, spectral width `SW = 14.0` ppm → `SW_HZ = 14.0 × 400.0 = 5600.0` Hz.
- Dwell time `dt = 1/(2·SW_HZ) = 1/11200 s` (real sampling: usable band is 0…SW_HZ above the carrier).
- Line broadening `LB = 1.0` Hz; zero-order phase `PHI0 = 0.6` rad; reference signal at `0.50` ppm.

## The parts of FID processing you can't guess

- **CSV quirks.** Lines starting with `#` are comments; one header row `time_s,intensity` follows; data rows are comma-separated, times in seconds. Skip comments and the header.
- **Apodization.** Multiply every point by `exp(-π · LB · t)` with `LB = 1.0` Hz.
- **Zero-fill.** Append zeros to the next power of two ≥ N (10000 → 16384) before the FFT.
- **FFT.** Radix-2, decimation-in-time, with this exact sign convention — use verbatim:

```python
def fft(x):  # X_k = sum_n x_n * exp(-2j*pi*k*n/N), k = 0..N-1
    n = len(x)
    if n == 1:
        return list(x)
    ev = fft(x[0::2]); od = fft(x[1::2])
    out = [0j] * n
    for k in range(n // 2):
        t = cmath.exp(-2j * math.pi * k / n) * od[k]
        out[k] = ev[k] + t
        out[k + n // 2] = ev[k] - t
    return out
```

- **Index → frequency.** `Δf = 1/(N_fft · dt)`. Bin `k ≤ N/2` is `f_k = k·Δf` Hz above the carrier; bins `k > N/2` are negative frequencies. A **real** FID gives a Hermitian spectrum (mirror peaks at ±ν) — keep bins 0…N/2 only, or every peak appears twice.
- **ppm axis.** `ppm_k = CARRIER_PPM + f_k / SFO1_MHz`. Bin 0 is the carrier (−4.0 ppm), the last kept bin is −4.0 + 14.0 = 10.0 ppm.
- **Phase correction.** Multiply every `X_k` by `exp(-i·PHI0)` with `PHI0 = 0.6` rad; the spectrum `s_k` is the **real part** of the rotated value.
- **Mirror-tail background.** Real detection leaves weak dispersive tails from the negative-frequency mirrors, a slowly varying background under the spectrum. Integrate against a local baseline or relative integrals drift high (worst for the strongest signal's mirror).
- **Peak picking.** A peak is a bin with `s[k] > s[k-1]`, `s[k] >= s[k+1]`, and `s[k] >= 0.05 · max(s)`. `ppm_center` is the ppm of that bin.
- **Integration.** Window = bins within ±0.10 ppm of `ppm_center`. Baseline = mean of `s` over the two flanking bands 0.15–0.25 ppm on either side of `ppm_center`. `integral = Σ (s[k] − baseline) · Δf`. `relative_integral = integral / integral` of the peak whose center is nearest 0.50 ppm.

**Verify your FFT before continuing** — run it on the 8-point cosine `x_n = cos(2π·2n/8)`, `n = 0..7`. Correct output: `X[2] = (4-0j)`, `X[6] = (4+0j)` (imaginary parts ~1e-16), every other `|X[k]| < 1e-9`. And `fft([1.0, 0, 0, 0, 0, 0, 0, 0])` must return eight copies of `(1+0j)`. Fix the transform before writing any NMR code.

## Test data generator — `make_fid.py`

```python
#!/usr/bin/env python3
"""Synthetic 1H FID: 4 damped cosines + LCG noise. Std-lib only, deterministic."""
import math

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

SFO1_MHZ = 400.0
CARRIER_PPM = -4.0
SW_PPM = 14.0
DT = 1.0 / (2.0 * SW_PPM * SFO1_MHZ)   # 1/11200 s
N = 10000
PHI0 = 0.6
# (ppm, amplitude, T2_s); amplitudes are proportional to proton counts 9:1:2:3
SIGNALS = [(0.50, 9.0, 0.30), (2.10, 1.0, 0.40), (3.80, 2.0, 0.25), (7.25, 3.0, 0.20)]
NOISE = 0.05

rnd = lcg(20260824)
with open("fid.csv", "w") as f:
    f.write("# synthetic 1H FID, single-channel real detection\n")
    f.write("# spectrometer_frequency_MHz=400.0 carrier_ppm=-4.0 spectral_width_ppm=14.0\n")
    f.write("time_s,intensity\n")
    for i in range(N):
        t = i * DT
        x = sum(a * math.exp(-t / t2) * math.cos(2.0 * math.pi * (ppm - CARRIER_PPM) * SFO1_MHZ * t + PHI0)
                for ppm, a, t2 in SIGNALS)
        x += (next(rnd) - 0.5) * 2.0 * NOISE
        f.write(f"{t:.8f},{x:.6f}\n")
print("wrote fid.csv")
```

## Acceptance criteria

Run `python3 make_fid.py`, then `python3 nmr_1d.py fid.csv -o multiplets.tsv`, and check all of:

1. Stdout (not stderr) carries these exact lines: `points read: 10000`, `zero-filled to: 16384`, `peaks found: 4`.
2. `multiplets.tsv` is **tab**-separated with Unix newlines, header row `ppm_center	integral	relative_integral`, exactly **4** data rows, sorted by `ppm_center` ascending.
3. `ppm_center` values (4 decimals) are 0.50, 2.10, 3.80, 7.25, each within ±0.02. (Verified: 0.4998, 2.0994, 3.7998, 7.2502.)
4. `relative_integral` values (4 decimals) are 1.0000 for the 0.50 ppm reference row, and 0.111, 0.222, 0.333 within ±0.02. (Verified: 0.1123, 0.2211, 0.3312.)
5. `integral` values (2 decimals) within 2% of 24654.39, 2768.91, 5451.26, 8166.71.
6. The FFT self-check above passes when run against your `fft` function.

## If something fails

Every peak doubled, or 8 peaks → you kept bins above N/2 (mirror images). All ppm shifted by a constant → carrier sign or `Δf = 1/(N_fft·dt)` wrong (e.g. you used N_acq instead of N_fft). `zero-filled to: 8192` → next power of two ≥ 10000 is 16384. Peaks found ≠ 4 → threshold or local-maximum test, or you picked peaks on the unphased spectrum. Relative integrals drift high, worst at high amplitude → you skipped the local-baseline subtraction (mirror tails). Relative integrals systematically ~5–10% low → you integrated the spectrum before phase correction, mixing in dispersion. Self-check gives `X[2] = X[6] = 2` → stray factor of 2 in the recursion; phases on the wrong bins → wrong sign in the twiddle factor.

## Optional

First-order phase correction `φ(f) = PHI0 + PHI1·(f − f_carrier)/SW_HZ`; peak picking with a noise-estimated threshold (median absolute deviation of peak-free bins) instead of 5%; doublet detection — report J in Hz for two peaks within 5–20 Hz whose integrals agree within 10%; Lorentzian fit of each peak for sub-bin `ppm_center`.
