# TEST PLAN — acid–base titration curve analysis

**Tier (a) executed 2026-08-24:** 10/10 criteria × 3 reps × 2 models (local Ornith-1.5-35B-A3B,
remote Qwen3.8-27B), external grader via the pi harness — see `/AC_BENCHMARK_REPORT.md`. Tiers
(b)/(c) remain plans. The numbers quoted
below are oracle values produced by running the shipped generator and a reference implementation
during prompt authoring (see `minimal_titration_prompt.md` acceptance criteria).

## Tier (a) — exact synthetic

In a clean workspace, hand the agent only `minimal_titration_prompt.md`. Expected session:

```
python3 make_test_data.py                       # writes titration.csv (50 points, seed 20260824)
python3 titration.py titration.csv -o results.tsv
python3 grade.py .                              # external grader, written by the benchmark author
```

`grade.py` is a **separate program** — never the agent's self-report. Sketch (std-lib only):

```python
#!/usr/bin/env python3
"""Grades a titration run in the directory given as argv[1]. Prints one PASS/FAIL line
per criterion and exits non-zero on any failure."""
import csv, sys, os

d = sys.argv[1]
results = []

def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS" if ok else "FAIL"), name)

# 1. generator output shape and edge rows
rows = [l for l in open(os.path.join(d, "titration.csv")).read().splitlines()]
data = [l for l in rows if l and not l.startswith("#") and not l.startswith("titrant_volume")]
check("csv: comment+header+50 rows", rows[0].startswith("#") and rows[1] == "titrant_volume_mL,pH" and len(data) == 50)
check("csv: first row 0.00,2.892", data[0] == "0.00,2.892")
check("csv: last row 75.00,12.283", data[-1] == "75.00,12.283")

# 2-3. results.tsv: tab-separated, header + exactly one data row, columns in order
tsv = open(os.path.join(d, "results.tsv")).read()
check("tsv: LF only, no CR", "\r" not in tsv)
lines = [l for l in tsv.split("\n") if l]
check("tsv: header + 1 row", len(lines) == 2)
hdr = lines[0].split("\t")
check("tsv: 4 tab-separated columns in order",
      hdr == ["equivalence_volume_mL", "equivalence_volume_d2_mL", "pKa", "analyte_concentration_M"])
v1, v2, pka, ca = map(float, lines[1].split("\t"))

# 4-7. numeric oracle (true Veq = 50.00 mL, pKa = 4.76, C = 0.1000 M)
check("Veq within 0.50 mL of 50.00", abs(v1 - 50.00) <= 0.50)
check("d1/d2 agree within 0.20 mL", abs(v1 - v2) <= 0.20)
check("pKa within 0.05 of 4.76", abs(pka - 4.76) <= 0.05)
check("concentration recovery within 2%", abs(ca - 0.1000) <= 0.0020)

sys.exit(0 if all(ok for _, ok in results) else 1)
```

Reference tool output on the unmodified generated data (authoring run, last digit may differ
across correct implementations): `Veq = 50.245`, `Veq_d2 = 50.245`, `pKa = 4.761`,
`conc = 0.10049`. Tolerances in the grader carry ≥ 2× margin over these.

## Tier (b) — robustness

Perturb the generator knobs; re-run tool + grader after each. Criteria that must still hold:

| Perturbation | Must hold |
|---|---|
| LCG seed: any (e.g. 1, 7, 999) at default noise ±0.02 | all tier-(a) numeric criteria |
| Noise amplitude up to ±0.03 pH | Veq ±1.0 mL (relaxed), pKa ±0.05, d1/d2 agreement 0.20 mL |
| Noise amplitude ±0.05 and above | Veq ±1.0 mL, pKa ±0.05; d1/d2 agreement may degrade — record, don't require |
| Sampling density 35–70 points over the same 0–75 mL | all numeric criteria (verified at 35 and 65 points) |
| One interior point dropped (except within ±3 mL of Veq) | Veq ±1.0 mL, pKa ±0.05 |
| Small volume jitter (±0.02 mL on the grid, kept sorted) | all numeric criteria |
| File-format quirks: CRLF endings, trailing blank line, extra `#` comment lines | parsing criteria; numeric criteria unchanged |

Authoring measurements behind the relaxed rows: at ±0.03 pH noise across seeds 1/7/999/20260824
Veq ranged 49.675–50.599 mL with d1/d2 agreeing to 0.001 mL in every case; at ±0.05 the two
derivative methods diverged to 1.9 mL, which is why the agreement criterion is waived there.

## Tier (c) — real data

Dataset: the published teaching titration **Table 15.7.1** in "15.7 Acid-Base Titrations",
Chemistry Fundamentals (OpenStax-derived), Maricopa Open Digital Press:
https://open.maricopa.edu/chemistryfundamentals/chapter/acid-base-titrations-2/
— 19 (volume, pH) pairs for 25.00 mL of 0.100 M CH3CO2H titrated with 0.100 M NaOH
(spacing 5 mL in the buffer region, 0.1–0.5 mL around the equivalence point).

Procedure: transcribe the table to CSV (or a lab's own pH-electrode log of the same titration),
run the tool with the constants set to `C_b = 0.100 M`, `V0 = 25.00 mL`. Reference answers: the
published table itself (equivalence pH 8.72 at 25.0 mL) and the accepted pKa of acetic acid,
4.76 (the table's own worked example uses Ka = 1.8e-5, pKa 4.74). Expect `Veq = 25.0 ± 0.5 mL`,
`pKa = 4.74 ± 0.10` (the 5 mL grid in the buffer region limits half-equivalence interpolation),
`conc = 0.100 ± 5%`. Cross-check Veq against a manual Gran plot (`V·10^(−pH)` vs `V`, x-intercept)
or a spreadsheet first-derivative analysis — this is a comparison against published reference
values, not a graded pass/fail tier.

## Benchmark protocol

1. Run the prompt in a **fresh agentic coding session** in a clean, empty workspace; paste the
   prompt verbatim, no hints.
2. Record: model name + exact version, SHA-256 of the prompt file, SHA-256 of the generated
   `titration.py` and `make_test_data.py`, iteration count (agent turns), wall-clock time,
   and per-criterion pass/fail **from `grade.py` only** — the agent's own summary is not evidence.
3. Require cross-model reproduction: at least one frontier API model and one local model; report
   the capability floor honestly, including failed runs.
4. The prompt (~6.5 KB) must fit the context budget of the smallest model claimed, with headroom
   for tool output and iteration; measure and record peak context use.
5. Archive raw tool output (`results.tsv`, stdout) alongside the grader verdict.
