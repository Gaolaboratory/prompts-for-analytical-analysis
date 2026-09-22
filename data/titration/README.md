# Titration of acetic acid with NaOH — published teaching dataset

## Source

- **Page:** "15.7 Acid-Base Titrations", Table 15.7.1 (*pH Values in the Titrations of a Strong
  Acid with a Strong Base and of a Weak Acid with a Strong Base*), weak-acid column
  (0.100 M CH3CO2H), *Chemistry Fundamentals* (Maricopa Open Digital Press / UCF Pressbooks,
  adapted from OpenStax *Chemistry 2e* via Lumen "Chemistry for Majors").
- **URL:** https://open.maricopa.edu/chemistryfundamentals/chapter/acid-base-titrations-2/
- **Downloaded:** 2026-08-26
- **License:** CC BY 4.0 (Attribution). The page's "Licenses and Attributions" section states:
  "Chemistry 2e. Provided by: OpenStax. License: CC BY: Attribution." (It is CC BY, not
  CC BY-NC-SA.) Source content: OpenStax, https://openstax.org/books/chemistry-2e/.

## Contents

- `acetic_acid_naoh.csv` — 19 rows, header `titrant_volume_mL,pH`, LF line endings. Volume of
  0.100 M NaOH titrant added (mL) vs solution pH.
- **Experiment:** 25.00 mL of 0.100 M acetic acid (CH3CO2H, weak monoprotic acid) titrated with
  0.100 M NaOH (strong base) at 25 °C. Volume grid: 5 mL steps across the buffer region,
  0.1–0.5 mL steps around the equivalence point.
- The source table lists volume to 1 decimal and pH to 2 decimals; the CSV pads these to
  2 and 3 decimals respectively (trailing zeros only, values verbatim) to match the format
  consumed by `titration.py`.

## Expected results

For a tier-(c) run of `titration.py` on this CSV with the constants set to `C_b = 0.100 M`
and `V0 = 25.00 mL`:

- **Equivalence volume:** Veq = 25.0 ± 0.5 mL (published equivalence point is 25.0 mL,
  equivalence pH 8.72). Manual cross-checks: first-derivative maximum with parabolic
  refinement on the table gives Veq = 25.00 mL; a Gran plot (V·10^−pH vs V, 5.0–24.9 mL)
  gives 24.98 mL.
- **pKa:** 4.74 ± 0.10 (the page's own worked example uses Ka = 1.8 × 10⁻⁵, pKa = 4.74, and
  computes pH = 4.74 at the 12.50 mL half-equivalence point; the coarse 5 mL grid in the
  buffer region limits half-equivalence interpolation, hence the wide tolerance).
- **Equivalence pH:** 8.72 at 25.0 mL per the table (acetate hydrolysis; theory with
  Ka = 1.8 × 10⁻⁵ gives 8.72).
- **Analyte concentration:** 0.100 M ± 5% (recovered as C_a = C_b·Veq/V0 with
  C_b = 0.100 M, V0 = 25.00 mL).

## How obtained

Manual transcription of Table 15.7.1 (weak-acid column) from the page above on 2026-08-26.
The weak-acid column was identified unambiguously — it starts at pH 2.87 (0.100 M acetic acid)
and has equivalence pH 8.72 at 25.0 mL, whereas the strong-acid (HCl) column starts at pH 1.00
with equivalence pH 7.00.

**Verification method:** the page was retrieved twice through independent channels
(server-side reader and direct `curl` of the raw HTML) and the 19 rows from both extractions
agree digit-for-digit. Each transcribed pH was then checked against an exact equilibrium
calculation (charge balance `h + cb = Kw/h + ca·Ka/(Ka + h)` solved by bisection at each
volume, with Ka = 1.8 × 10⁻⁵, Kw = 1.0 × 10⁻¹⁴): all 19 published values agree with theory
to within 0.005 pH. Full details in `.superpowers/tierc/titration-report.md`.
