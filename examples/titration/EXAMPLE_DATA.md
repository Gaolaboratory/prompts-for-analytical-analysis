# Example data & expected results — titration

**Dataset:** published teaching titration table (19 volume–pH pairs): 25.00 mL of 0.100 M acetic
acid titrated with 0.100 M NaOH (`data/titration/acetic_acid_naoh.csv`). Full provenance and
license: `data/titration/README.md`.

**Run:** `python3 titration.py acetic_acid_naoh.csv -o results.tsv` with constants
C_b = 0.100 M, V0 = 25.00 mL.

**Expected results (from the published table and its own worked example):**

| quantity | expected |
|---|---|
| equivalence volume | 25.0 ± 0.5 mL |
| pKa | 4.74 ± 0.10 (table's worked example uses Ka = 1.8e-5) |
| equivalence pH | 8.72 at 25.0 mL (for reference) |
| analyte concentration | 0.100 M ± 5% |

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/titration/local/tierc/`, 14 iterations): Veq = 24.999 mL (d1) / 24.998 mL (d2), pKa
4.745, C_a = 0.10000 M — **PASS**, all four criteria inside bounds with >10× margin on volume
and pKa.
