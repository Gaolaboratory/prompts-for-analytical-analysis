# TEST_PLAN — formula_finder

**Tier (a) executed 2026-08-24:** 18/18 criteria × 3 reps × 2 models (local Ornith-1.5-35B-A3B,
remote Qwen3.8-27B), external grader via the pi harness — see `/AC_BENCHMARK_REPORT.md`. Tiers
(b)/(c) remain plans. The oracle numbers in
`minimal_formula_finder_prompt.md` were verified by running a reference implementation at
authoring time (counts 7/10/2, top-hit scores 1.2763 / 2.1369 / 2.5581).

## Tier (a) — exact synthetic

In a clean workspace, hand the agent `minimal_formula_finder_prompt.md` verbatim, then:

```
python3 make_test_data.py
python3 formula_finder.py measured.tsv -o ranked.tsv
python3 grade.py measured.tsv ranked.tsv
```

Grading must be an external program, never the agent's self-report. Sketch of `grade.py`
(std-lib only, expectations hardcoded — the agent never sees this file):

```python
#!/usr/bin/env python3
import re, sys
meas = {r[0]: tuple(map(float, r[1:]))
        for r in (l.split("\t") for l in open(sys.argv[1]).read().splitlines()[1:])}
lines = open(sys.argv[2], "rb").read().decode().split("\n")
checks = []
def chk(name, ok): checks.append((name, bool(ok))); print(("PASS" if ok else "FAIL"), name)

chk("unix newlines, no CR", "\r" not in open(sys.argv[2], "rb").read().decode())
hdr = "id\tformula\tcalc_mass\terror_ppm\tM1_calc\tM2_calc\tscore"
chk("tab-separated header, exact column order", lines[0] == hdr)
rows = [l.split("\t") for l in lines[1:] if l]
chk("19 data rows", len(rows) == 19)
counts = {"CPD1": 7, "CPD2": 10, "CPD3": 2}
seq = [cid for cid in counts for _ in range(counts[cid])]
chk("blocks in input order with exact counts", [r[0] for r in rows] == seq)
for cid, formula, mass, score in [("CPD1","C6H12O6",180.063390,1.2763),
                                  ("CPD2","C8H10N4O2",194.080376,2.1369),
                                  ("CPD3","C5H11NO2S",149.051050,2.5581)]:
    top = next(r for r in rows if r[0] == cid)
    chk(f"{cid} top hit is {formula}", top[1] == formula)
    chk(f"{cid} calc_mass/score", abs(float(top[2])-mass) < 1e-6
        and abs(float(top[6])-score) < 1e-3)
    mm, m1m, m2m = meas[cid]
    chk(f"{cid} within tolerances", abs(float(top[3])) <= 5.0
        and abs(float(top[4])-m1m) <= 0.005 and abs(float(top[5])-m2m) <= 0.005)
    blk = [float(r[6]) for r in rows if r[0] == cid]
    chk(f"{cid} sorted by score asc", blk == sorted(blk))
fmt = re.compile(r"^-?\d+\.\d{6}\t[+-]\d+\.\d{3}\t-?\d+\.\d{6}\t-?\d+\.\d{6}\t\d+\.\d{4}$")
chk("column formats (6/±3/6/6/4 decimals)",
    all(fmt.search("\t".join(r[2:])) for r in rows))
sys.exit(0 if all(ok for _, ok in checks) else 1)
```

Expected result for a correct run: all checks PASS. Candidate-count lines on stdout
(`CPD1: 7 candidates` …) are checked by capturing stdout during the run and comparing
against the prompt's criterion 2 — do this in the harness, not by asking the agent.

## Tier (b) — robustness

Perturb the generator knobs, regenerate, and re-grade. The grader's expected counts/scores
must be recomputed from the perturbed generator with the same reference enumeration before
each run (the grader never hardcodes perturbed expectations by hand).

- **Noise level**: mass error from ±2.5 ppm up to ±4.5 ppm and isotope noise from ±4% up to
  ±10% relative. Must still hold: true formula ranked first; criterion 5 tolerances.
- **Tolerance**: rerun the tool logic at 3 ppm and 10 ppm. Must hold: candidate counts change
  in the direction and by the amount the reference enumeration predicts; top hit unchanged.
- **Compound set**: drop CPD3 (the sulfur compound) or add a fourth true formula. Must hold:
  counts and block order track the input rows exactly.
- **Adversarial near-tie**: place a true formula whose mass sits < 1 ppm from a wrong
  candidate's mass. Must hold: the isotope terms break the tie in favor of the true formula.

Not applicable to this tool: baseline drift, sampling density, missing/extra peaks (no
spectrum is parsed; input is a peak-summary table).

## Tier (c) — real data

MassBank record **MSBNK-Eawag-EA030313** (caffeine, LTQ Orbitrap XL, R=30000):
<https://massbank.eu/MassBank/RecordDisplay?id=MSBNK-Eawag-EA030313> — machine-readable via
<https://massbank.eu/MassBank-api/records/MSBNK-Eawag-EA030313>. Verified 2026-08: the record
carries `CH$FORMULA: C8H10N4O2` and `CH$EXACT_MASS: 194.0804` (neutral monoisotopic mass, so
no adduct correction is needed).

Protocol: feed the tool `CAFFEINE	194.0804	<M1>	<M2>` with M1/M2 computed from the prompt's
own isotope table (0.103051 / 0.007466 — an MS2 record carries no usable isotope
intensities, so this tests mass-plus-pattern assignment, not real measured isotope ratios).
**Reference answer**: the annotated `CH$FORMULA` — the tool must rank `C8H10N4O2` first with
`error_ppm` ≈ 0 and `score` ≈ 0. Optional cross-check of the isotope simulation itself against
an independent calculator (e.g. enviPat or pyOpenMS `IsotopeDistribution`, run by the
grader, not the agent).

## Benchmark protocol

- Run the prompt in a **fresh agentic coding session in a clean workspace**; nothing from
  this repo except the prompt file itself.
- Record: model name + version, SHA-256 of the prompt file, SHA-256 of the generated
  `formula_finder.py`, iteration count (agent turns), wall-clock time, and per-criterion
  pass/fail **from the external grader** — the agent's own summary table is not evidence.
- Require cross-model reproduction: at least two different models (or providers) must pass
  tier (a) before the prompt is called validated, and report the floor — the models that
  fail — not just the ones that pass.
- The prompt must fit the context budget of the smallest model claimed; state that budget.
  Current prompt size: ~7 KB.
