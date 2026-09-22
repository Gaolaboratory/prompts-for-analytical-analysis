# Real measured-mass inputs for formula_finder (tier c)

## Source

MassBank high-quality MS/MS records, fetched from the MassBank REST API on **2026-08-26**
(each record's `CH$EXACT_MASS` neutral monoisotopic mass and `CH$FORMULA`, returned by the API
as `compound.mass` / `compound.formula`):

| id | Accession | Record title | API URL |
|---|---|---|---|
| CAFFEINE | MSBNK-Eawag-EA030313 | Caffeine; LC-ESI-ITFT; MS2; CE: 90%; R=30000; [M+H]+ | https://massbank.eu/MassBank-api/records/MSBNK-Eawag-EA030313 |
| ACETAMINOPHEN | MSBNK-UFZ-UF409101 | Acetaminophen / paracetamol; LC-ESI-ITFT; MS2; CE: 55; R=15000; [M+H]+ | https://massbank.eu/MassBank-api/records/MSBNK-UFZ-UF409101 |
| SULFAMETHOXAZOLE | MSBNK-Eawag-EA029804 | Sulfamethoxazole; LC-ESI-ITFT; MS2; CE: 45%; R=7500; [M+H]+ | https://massbank.eu/MassBank-api/records/MSBNK-Eawag-EA029804 |
| AMPA | MSBNK-Keio_Univ-KO000308 | (Aminomethyl)phosphonic acid; LC-ESI-QQ; MS2; CE:40 V; [M-H]- | https://massbank.eu/MassBank-api/records/MSBNK-Keio_Univ-KO000308 |

**License:** per the `license` field returned by the API — CC BY for MSBNK-Eawag-EA030313,
MSBNK-UFZ-UF409101 and MSBNK-Eawag-EA029804; CC BY-NC-SA (4.0) for MSBNK-Keio_Univ-KO000308.
(Not the blanket CC BY-NC-SA 4.0: three of the four records state CC BY.)
`CH$EXACT_MASS` is the **neutral** monoisotopic mass in every record, so the values need no
adduct/proton correction and are valid inputs for the prompt's neutral-mass contract even
though the records were acquired as [M+H]+ or [M-H]-.

## Contents

`measured_caffeine.tsv` — tab-separated, LF newlines, header `id	mass	M1	M2`, 4 data rows.
The file is named for its lead compound but carries all four rows.

- `id` — compound label (uppercase).
- `mass` — the record's published `CH$EXACT_MASS`, precision **as published**: 4 decimal places
  for the first three rows; the Keio AMPA record publishes 5 decimals (`111.00853`), kept
  verbatim rather than rounded.
- `M1`, `M2` — **not measured intensities.** These MS2 records carry no usable isotope
  intensities, so M1/M2 are *computed* from each record's own `CH$FORMULA` using the exact
  first-order isotope approximation specified in
  `examples/formula_finder/minimal_formula_finder_prompt.md`: with r1 = a1/a0 and r2 = a2/a0
  (abundance ratios within one element from the prompt's 13-isotope table),
  `M1 = Σ n_e·r1_e` and `M2 = Σ n_e·r2_e + Σ n_e(n_e−1)/2·r1_e²`.
  This makes the test a mass-plus-pattern assignment check against a known ground-truth
  composition, not a claim about measured isotope ratios.

Values (6 dp, std-lib Python, self-checked against the prompt's own `CO2`/`CH4` oracle):

| id | formula | M1 | M2 |
|---|---|---|---|
| CAFFEINE | C8H10N4O2 | 0.103051 | 0.007466 |
| ACETAMINOPHEN | C8H9NO2 | 0.091976 | 0.007386 |
| SULFAMETHOXAZOLE | C10H11N3O3S | 0.129421 | 0.056212 |
| AMPA | CH6NO3P | 0.016302 | 0.006166 |

## Expected results

For `python3 formula_finder.py measured.tsv -o ranked.tsv` run on this input: in each block the
record's own `CH$FORMULA` must be the **rank-1 row**, with `|error_ppm| ≤ 0.2` (the entire
residual error is the records' 4/5-dp mass rounding — far inside the ~2.1 ppm worst case for
4-dp rounding, and inside the 5 ppm window) and isotope terms contributing exactly 0 to the
score, so `score = |error_ppm|` to 4 decimals:

| id | expected rank-1 formula | calc_mass | error_ppm | score | candidates in block | runner-up |
|---|---|---|---|---|---|---|
| CAFFEINE | C8H10N4O2 | 194.080376 | −0.124 | 0.1237 | 9 | C4H13N5O2P (score 5.66) |
| ACETAMINOPHEN | C8H9NO2 | 151.063329 | +0.192 | 0.1920 | 6 | C4H12N2O2P (score 6.43) |
| SULFAMETHOXAZOLE | C10H11N3O3S | 253.052113 | +0.051 | 0.0514 | 18 | C6H14N4O3PS (score 5.55) |
| AMPA | CH6NO3P | 111.008531 | +0.009 | 0.0091 | 2 | C5H3O3 (score 6.84) |

Acceptance thresholds suggested for tier (c): rank-1 formula matches the table above in all
four blocks; `|error_ppm| ≤ 2.0` for every rank-1 row; score ≤ 0.5 for every rank-1 row;
the rank-1 row of each block beats its runner-up by ≥ 5 score units. Candidate counts and
runner-up formulae are informational cross-checks: they were produced by an independent
reference implementation of the prompt's enumeration (C 0–30, H 0–60, N 0–10, O 0–10,
P 0–2, S 0–2, inclusive 5 ppm window); a conforming implementation reproduces them exactly,
but only the rank-1 formula, its error and its score should be treated as pass/fail.

The four rows deliberately span all six elements of the prompt's isotope table — N-rich
(caffeine), CHO-only (acetaminophen), S-bearing (sulfamethoxazole, whose M2 is dominated by
the 34S term) and P-bearing with a C-free-capable mass region (AMPA) — so a single run
exercises every element branch of the pattern model.

## How obtained

1. Fetched each accession's JSON from `https://massbank.eu/MassBank-api/records/{accession}`
   with `curl` on 2026-08-26; read `accession`, `title`, `license`, `compound.formula`,
   `compound.mass` (= the record's CH$FORMULA / CH$EXACT_MASS fields).
2. Accessions for the three non-caffeine compounds were located by full-text search of the
   official MassBank record mirror (github.com/MassBank/MassBank-data), then each candidate
   was fetched and confirmed from the live API (no values taken from the mirror).
3. Recomputed M1/M2 from each `CH$FORMULA` with std-lib Python using the prompt's isotope
   table and first-order model, after verifying the implementation against the prompt's own
   `CO2` (43.989830 / 0.011578 / 0.004110) and `CH4` (16.031300 / 0.011276 / 0.000000)
   oracle rows.
4. Validated the expected ranking by running an independent implementation of the prompt's
   enumeration and scoring (same isotope table, same first-order pattern, same 5 ppm
   inclusive window, same score weights 1/100/100) over the exact `mass` values in the tsv.
