# Acid–base titration curve analysis

Write `titration.py`. Run: `python3 titration.py acetic_acid_naoh.csv -o results.tsv`

Python standard library plus numpy, pandas and scipy only. No other third-party packages.

## Input

`acetic_acid_naoh.csv` is in the working directory: header `titrant_volume_mL,pH`,
19 rows, a weak monoprotic acid titrated with a strong base. The flask held
**25.00 mL** of analyte and the titrant is **0.1000 M** — keep both as named
constants at the top of the file.

## Output

`results.tsv`: a header line plus exactly one tab-separated data row, LF endings:

```
equivalence_volume_mL	pKa	analyte_concentration_M
```

One line on stdout: `points=<n> Veq=<x> pKa=<x> conc=<x>`

## Method

- A weak acid's equivalence point is **not** at pH 7 — here it is near pH 8.7. Never
  search for a pH target; take the maximum of dpH/dV.
- Differentiate the **smoothed** curve, not the raw one: a centered moving average of
  width 5, truncated at the edges. Place each derivative value at the midpoint of its
  volume pair.
- The volume grid is uneven — 5 mL steps through the buffer region, 0.1 mL steps near
  the equivalence point — so divide by the actual ΔV of each pair, never by a constant
  step.
- Refine the maximum: fit a parabola to the three derivative points around it and take
  its vertex, so the answer is not pinned to a sampled volume.
- pKa is the pH at **Veq/2**, interpolated on the raw curve. It is not the pH at half
  the last volume.
- `analyte_concentration_M = C_titrant · Veq / V0`, in that order.

## Acceptance criteria

1. `results.tsv` has the header above plus exactly one tab-separated data row, columns
   in that order, and contains no CR characters.
2. `equivalence_volume_mL` = 25.0 ± 0.5 (the published equivalence point is 25.0 mL).
3. `pKa` = 4.74 ± 0.10 (acetic acid, Ka = 1.8 × 10⁻⁵).
4. `analyte_concentration_M` = 0.100 ± 5%.
5. The stdout line is printed with all four fields.
6. The reported values come from actually reading `acetic_acid_naoh.csv`: re-running
   `titration.py` on a modified copy of that file must shift the three output values
   correspondingly, not reproduce the same numbers.

Do not tune a constant to make a number match; if a criterion fails, the analysis is wrong.
