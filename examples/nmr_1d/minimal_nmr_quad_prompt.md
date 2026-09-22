# 1D NMR processing from a quadrature (complex) FID

Standard library only (no `numpy`, `scipy`, `nmrglue`). Write `nmr_quad.py`.

`nmr_quad.py` reads a **complex (quadrature-detected)** 1D FID from a CSV of `time_s,real,imag`
rows, applies exponential apodization, zero-fills, Fourier-transforms, rotates the spectrum so
the carrier sits at the centre, removes a known zero- and first-order phase, subtracts a
baseline, picks peaks against a noise-estimated threshold, integrates each peak over a
valley-bounded window, and writes a tab-separated multiplet table sorted by ppm.
CLI: `python3 nmr_quad.py fid_quad.csv -o multiplets.tsv`. Print progress counts to stdout
(see criteria).

> This is the quadrature counterpart of `minimal_nmr_1d_prompt.md`. That prompt models
> **single-channel real** detection, which every modern spectrometer stopped doing decades ago.
> Use this one for anything that came off a real instrument. The two are not interchangeable —
> the last section shows exactly what the real-channel model does to quadrature data.

## Dependencies

None — this is a base module. Other prompts depend on it.

## Data

Run `python3 make_fid_quad.py` (shipped beside this prompt) to write `fid_quad.csv`. It is the
oracle: the numbers below hold only for its exact output. Don't edit it and
don't generate the data any other way.

## Fixed acquisition and processing parameters

Binding constants — the CSV carries them as `#` comments, but do not parse them out:

- Spectrometer frequency `SFO1 = 400.0` MHz, carrier `CARRIER_PPM = 5.0`.
- Spectral width `SW_HZ = 8000.0` Hz. **This is the full quadrature width**, spanning
  `±SW_HZ/2` about the carrier, i.e. ±10.0 ppm → the axis runs −5.0 … 15.0 ppm.
- Complex dwell `dt = 1/SW_HZ = 1/8000 s`. Note there is **no factor of 2**: quadrature
  detection samples the full width at `1/SW_HZ`, unlike real detection at `1/(2·SW)`.
- Line broadening `LB = 1.0` Hz; baked-in phase `P0 = 30.0°`, `P1 = 20.0°`;
  integral reference signal at `1.20` ppm.

## The parts you can't guess

- **CSV quirks.** Lines starting with `#` are comments; one header row `time_s,real,imag`
  follows; data rows are comma-separated. Point `n` is the complex number `real + i·imag`.
- **Apodization.** Multiply every complex point by `exp(-π · LB · t)` with `LB = 1.0` Hz.
- **Zero-fill.** Append zeros to **twice** the next power of two ≥ N (8192 → 16384) before the
  FFT. `N_fft = 16384`.
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

- **Shift the carrier to the centre.** The raw transform puts the carrier at bin 0 and negative
  frequencies in the upper half. Rotate by `N_fft/2`: `Xs = X[N_fft//2:] + X[:N_fft//2]`.
  Now index `k` is frequency `f_k = (k − N_fft/2) · SW_HZ / N_fft`, running −4000 … +4000 Hz.
  **Keep every bin.** A quadrature FID distinguishes +ν from −ν, so there are no mirror images
  and nothing to discard — that is the entire point of quadrature detection.
- **ppm axis.** `ppm_k = CARRIER_PPM + f_k / SFO1_MHz`, running −5.0 … 15.0 ppm.
- **Phase correction.** The acquisition baked in `φ_k = P0 + P1 · k / N_fft` (degrees, `k` the
  index in the *shifted* array). Remove it: `Xs[k] ← Xs[k] · exp(−i·φ_k)` with `φ_k` in radians.
  The spectrum `s_k` is the **real part** of the result. Getting the sign of this rotation
  backwards inverts the strongest lines and is the single most destructive mistake here.
- **Baseline.** A real spectrum rolls: broad probe background and FID first-point error leave a
  slowly varying floor that makes integrals meaningless (and can make them negative). Split the
  spectrum into **256 equal segments**, take the **median** of each segment, place that median
  at the segment's centre index, linearly interpolate between centres, and subtract. Medians
  work because peaks occupy a small fraction of bins, so a segment's median tracks its floor.
- **Peak picking.** A bin `k` is a peak if `s[k] > s[k-1]`, `s[k] >= s[k+1]`, and
  `s[k] >= threshold`, where `threshold = max(20·σ, 0.01·max(s))`. Estimate σ robustly:
  `σ = 1.4826 · median(|s − median(s)|)`. A fixed fraction of the tallest peak does not work —
  in a real spectrum the reference line dwarfs everything of interest.
- **Integration.** From the apex walk outward in each direction while the signal keeps falling,
  stopping when it turns back up (a valley) or when 0.05 ppm is reached. Take the **smaller**
  of the two half-widths and use it on both sides, so one runaway tail cannot dominate. With
  window `[lo, hi]`, `baseline = (s[lo] + s[hi]) / 2` and
  `integral = Σ_{lo..hi} (s[k] − baseline) · Δf`, `Δf = SW_HZ / N_fft`.
  `relative_integral = integral / integral` of the peak nearest 1.20 ppm.

**Verify your FFT before continuing.** Two of these three checks pass under *either* sign
convention; only the third can catch a flipped exponent.

- `fft([1.0, 0, 0, 0, 0, 0, 0, 0])` → eight copies of `(1+0j)`. Checks scaling.
- `x_n = cos(2π·2n/8)`, `n = 0..7` → `|X[2]| = |X[6]| = 4`, every other `|X[k]| < 1e-9`.
  Checks bin placement. A real, even input has a symmetric transform, so this passes
  whichever sign you used — it is not evidence that your convention is right.
- `x_n = exp(+2πi·2n/8)`, `n = 0..7` → **`X[2] = 8`**, every other `|X[k]| < 1e-9`.
  Getting `X[6] = 8` instead means your exponent sign is flipped and every resonance will
  land on the wrong side of the carrier. Only a complex input exposes this.

Fix the transform before writing any NMR code.


Note `phi = p0 + p1 * (nu / SW_HZ + 0.5)`: since `k / N_fft = nu / SW_HZ + 0.5` on the shifted
axis, this is the same ramp the correction step removes.

## Acceptance criteria

Run `python3 make_fid_quad.py`, then `python3 nmr_quad.py fid_quad.csv -o multiplets.tsv`,
and check all of:

1. Stdout (not stderr) carries these exact lines: `points read: 8192`,
   `zero-filled to: 16384`, `peaks found: 4`.
2. `multiplets.tsv` is **tab**-separated with Unix newlines, header row
   `ppm_center	integral	relative_integral`, exactly **4** data rows, sorted by
   `ppm_center` ascending.
3. `ppm_center` values (4 decimals) are 1.20, 3.50, 7.20, 8.50, each within ±0.01.
   (Verified: 1.2000, 3.4998, 7.1997, 8.4998.)
4. `relative_integral` values (4 decimals) are 1.0000 for the 1.20 ppm reference row, and
   0.2222, 0.3333, 0.1111 (the 9:2:3:1 proton ratios) each within ±0.02.
   (Verified: 1.0000, 0.2245, 0.3360, 0.1110.)
5. `integral` values within 3% of 3.2215e4, 7.2307e3, 1.0825e4, 3.5749e3.
6. All three FFT self-checks above pass against your `fft` function — including the
   complex-exponential one, which must give `X[2] = 8` and not `X[6] = 8`.
7. **No peak is reported between 5.4 and 5.9 ppm.** The generator puts a broad background
   component at 5.60 ppm; if your baseline step works it is flattened away, and if it does not
   you will report several spurious maxima there.

## If something fails

Peaks at 6.50 and 8.80 instead of 3.50 and 1.20 → you built a real-valued spectrum (took only
the `real` column, or kept bins 0…N/2 as for real detection). Everything below the carrier
folded to `10.0 − ppm_true`. Read the last section.
All ppm shifted by a constant → you forgot the `N_fft/2` rotation, or used `dt = 1/(2·SW_HZ)`.
Axis spans 5.0…15.0 instead of −5.0…15.0 → you discarded the negative-frequency half.
`zero-filled to: 8192` → the rule is *twice* the next power of two.
Strongest peak negative, or `peaks found` far below 4 → phase rotation sign is backwards; use
`exp(−i·φ_k)`, not `exp(+i·φ_k)`.
Several peaks reported near 5.6 ppm → baseline step missing or too few segments.
Integrals negative, or the reference integral far smaller than its peak height → baseline step
missing; a rolling floor drags the sum below zero.
`peaks found` in the hundreds → you used only the σ threshold without the `0.01·max(s)` floor,
or you ran the picker before baseline subtraction.
Relative integrals all ≈ 1 → you normalised by the wrong row; the reference is the peak nearest
1.20 ppm, not the tallest and not the first.

## Why the real-channel model is not an option

Feed the **real column alone** of this same `fid_quad.csv` to a single-real-channel tool
(carrier 5.0 ppm, real spectral width 4000 Hz, bins 0…N/2 kept). Verified output:

| true ppm | reported ppm | true relative integral | reported |
|---|---|---|---|
| 3.50 | 6.4978 | 0.222 | 1.0000 |
| 7.20 | 7.1997 | 0.333 | 6.5740 |
| 8.50 | 8.4998 | 0.111 | 1.9644 |
| 1.20 | 8.7988 | 1.000 | 1.0057 |

Every resonance below the carrier is reflected to `2·CARRIER_PPM − ppm_true`, the four lines
collapse into a 2.3 ppm window, and the integrals are unrelated to the 9:2:3:1 proton counts.
On a real 700 MHz urine FID (MetaboLights MTBLS1) the same failure moved four of five
resonances by up to 0.5 ppm and put three of five relative integrals 150–560% out — while a
complex-input tool placed all seven assigned resonances (TSP, acetate, both citrate lines, both
creatinine lines, water) within **0.002 ppm** of their published values.

## Optional

Automatic phase determination by minimising spectral entropy (then `P0`/`P1` need not be given);
magnitude-mode processing `|X_k|`, which needs no phase at all and on the MTBLS1 data landed
within 10% of the phased integrals; solvent-region exclusion around the carrier; multiplet
grouping with J in Hz for components 5–20 Hz apart; Lorentzian fitting for sub-bin centres;
a polynomial or asymmetric-least-squares baseline instead of segment medians.
