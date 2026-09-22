# UV–Vis absorption band — λmax, molar absorptivity and width

Write `uvvis.py`. Run: `python3 uvvis.py 4-nitrophenol.csv -o bands.tsv`

Python standard library plus numpy, pandas and scipy only. No other third-party packages.

## Input

`4-nitrophenol.csv` is in the working directory: header `wavelength_nm,absorbance`,
576 rows, 225–800 nm. The second column is **molar absorptivity** (ε, M⁻¹ cm⁻¹), not
absorbance units, despite the header.

## Output

`bands.tsv`: a header line plus exactly one tab-separated data row per detected band,
LF endings:

```
lambda_max_nm	epsilon	fwhm_nm
```

One line on stdout: `points=<n> bands=<n> lambda_max=<x> epsilon=<x>`

## Method

- Analyse the **250–700 nm** window only.
- A band is a local maximum at or above **20% of the window maximum**. A lower
  threshold picks up a phantom band on the long-wavelength tail — that happened on
  this exact file.
- The baseline region above 400 nm carries genuinely **negative** values (down to
  −107.8 at 559 nm, ≈1.2% of the peak). That is ordinary spectrometer noise on an ε
  scale. Do not clip it to zero, do not treat it as an error, and do not
  baseline-subtract before finding the maximum.
- FWHM is the distance between the two half-maximum crossings, each found by
  **linear interpolation between the bracketing samples**, not by the nearest
  sampled wavelength — the grid is ~1 nm and rounding to it costs a nanometre.

## Acceptance criteria

1. bands.tsv: header + exactly one band row, columns in order, no CR.
2. lambda_max 317 +/- 3 nm.
3. epsilon within 2% of 9283.
4. fwhm within 2 nm of the reference recomputed from the input.
5. stdout reports points, bands, lambda_max and epsilon.
6. re-running uvvis.py on an absorbance-tilted input reproduces the reference
   lambda_max and epsilon for that input.

Do not tune a constant to make a number match; if a criterion fails, the analysis is
wrong.
