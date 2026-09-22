# 1D 1H NMR — FID to spectrum, peak picking and integration

Write `nmr.py`. Run: `python3 nmr.py fid_complex.csv -o multiplets.tsv`

Python standard library plus numpy, pandas and scipy only. No other third-party packages.

## Input

`fid_complex.csv` is in the working directory: a couple of `#` comment lines, then
header `time_s,real,imag`, 32,697 complex points from a 700 MHz urine spectrum. Keep
these as named constants at the top of the file: `SF = 699.869954581` MHz,
`CARRIER_PPM = 4.76648`, `SW_HZ = 14005.6022`, `LB = 1.0` Hz, `NFFT = 65536`.

## Output

`multiplets.tsv`: a header line plus one tab-separated data row per picked peak, LF
endings:

```
ppm_center	integral_rel
```

Sorted by ascending `ppm_center`.

One line on stdout: `points=<n> peaks=<n> reference_ppm=<x>`

## Method

- The `real` and `imag` columns are the two channels of **one complex signal** — combine
  them as `real + 1j*imag` before the transform. Treating `real` alone as the signal
  folds every resonance below the carrier onto a mirror image at
  `2*CARRIER_PPM - ppm`, which looks like a plausible spectrum but has the wrong peaks
  in it.
- Apodise with `exp(-pi * LB * t)` before zero-filling to `NFFT`.
- ppm axis: `CARRIER_PPM + f/SF`, with `f = (arange(NFFT) - NFFT//2) * SW_HZ/NFFT`, after
  `fftshift(fft(...))`.
- Take the **magnitude** spectrum (`abs`, not a phased real part). This needs no phase
  constants and is not sensitive to the sign of a phase-correction convention.
- Pick local maxima at or above **5%** of the spectrum maximum.
- Integrate each picked peak over a **valley-bounded** window: from the apex, step
  outward one bin at a time in each direction for as long as the next bin is strictly
  lower than the current one; stop the moment that is no longer true (a flat run stops
  the walk immediately), capped at **+/-0.10 ppm** per side either way. Take the local
  baseline as the mean of the spectrum values at the two resulting window-boundary bins,
  subtract it, and sum over the window. A fixed-width window with a distant flanking
  baseline puts a neighbouring multiplet's own intensity into the baseline estimate and
  can drive an integral negative — citrate's two AB multiplets near 2.549 and 2.656 ppm
  do exactly that on this data.
- Normalise every integral to the picked peak nearest **0.000 ppm** — TSP/DSS, the
  sample's internal chemical-shift standard — which becomes the reference row at
  **1.000**. Do not normalise to water: this is a presaturation experiment, so the
  water line is broad and attenuated, and its integral is window-sensitive enough to
  move the whole table. Water's row is still written to `multiplets.tsv` with its
  position, but its integral is not part of any acceptance criterion below.
- The six assigned resonances, at their nominal ppm on this true (non-mirrored) axis:
  TSP/DSS 0.000, acetate 1.921, citrate 2.549, creatinine CH3 3.048, creatinine CH2
  4.058, water 4.767.

## Acceptance criteria

1. multiplets.tsv: header + rows sorted by ppm_center, columns in order.
2. all six assigned resonances within 0.05 ppm on the true axis.
3. TSP is the reference row at 1.000 and the four metabolite integrals match the
   reference within 20%.
4. no mirrored peak near 9.53 ppm (real-channel processing).
5. stdout reports points, peaks and reference_ppm=0.000.

Do not tune a constant to make a number match; if a criterion fails, the processing is
wrong.
