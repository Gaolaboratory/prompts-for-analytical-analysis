# TEST PLAN — Weighted calibration with internal standards

**Tier (a) executed 2026-08-24:** 6/6 criteria × 3 reps × 2 models (local Ornith-1.5-35B-A3B, remote
Qwen3.8-27B), external grader via the pi harness — see `/AC_BENCHMARK_REPORT.md`. Tiers (b)/(c)
remain plans. Every oracle number in
`minimal_calibration_prompt.md` was produced by running a reference implementation against the
shipped generator (`slope 2.502458, intercept 0.027564, r2 0.999766, sigma 0.004578, LOD 0.006037,
LOQ 0.018293; biases +0.43 / −0.33 / +0.49%`).

## Tier (a) — exact synthetic

Commands (in a clean workspace):

```
python3 make_cal_data.py
python3 calibrate.py standards.csv unknowns.csv -o results.tsv > stdout.txt
python3 grade.py stdout.txt results.tsv
```

External grader sketch (`grade.py`, a separate program — grading is never the agent's self-report):

```python
#!/usr/bin/env python3
"""grade.py stdout.txt results.tsv — checks each acceptance criterion, exits 1 on any failure."""
import sys

out = open(sys.argv[1]).read().splitlines()
lines = out
checks = []

# 1. exactly six name<TAB>value lines, in order
names = [l.split("\t")[0] for l in lines]
checks.append(("c1 six stdout lines in order",
    len(lines) == 6 and names == ["slope", "intercept", "r2", "sigma", "LOD", "LOQ"]))
vals = dict(l.split("\t") for l in lines)

def close(k, want, tol):
    return abs(float(vals[k]) - want) <= tol

# 2-3. line statistics and limits
checks.append(("c2 slope/intercept/r2", close("slope", 2.5025, 0.02)
    and close("intercept", 0.0276, 0.005) and close("r2", 0.9998, 0.0005)))
checks.append(("c3 sigma/LOD/LOQ", close("sigma", 0.0046, 0.0005)
    and close("LOD", 0.0060, 0.0007) and close("LOQ", 0.0183, 0.0020)))

# 4-5. results.tsv structure and recoveries
rows = [l.split("\t") for l in open(sys.argv[2]).read().splitlines()]
checks.append(("c4 header + 3 rows in order", rows[0] ==
    ["sample_id", "ratio", "calc_conc_ug_mL", "true_conc_ug_mL", "bias_pct"]
    and [r[0] for r in rows[1:]] == ["UNK_1", "UNK_2", "UNK_3"]))
checks.append(("c5 |bias| <= 5%", len(rows) == 4
    and all(abs(float(r[4])) <= 5.0 for r in rows[1:])))
# c6 (wls self-check) is graded by inspecting the agent's session transcript for the
# executed self-check output 2.0250 / 0.0571 — it cannot be re-derived from the artifacts.

for name, ok in checks:
    print(("PASS" if ok else "FAIL"), name)
sys.exit(0 if all(ok for _, ok in checks) else 1)
```

## Tier (b) — robustness

Perturb the generator knobs one at a time and re-run tier (a). All structural criteria (c1, c4)
must hold under every perturbation; numeric criteria are re-derived by running the reference
implementation on the perturbed data, never estimated.

- **Noise scale** — multiply the `0.012` / `0.0012` noise terms by 3: recoveries must still be
  |bias| ≤ 15%, r2 ≥ 0.995, and the weighted slope must stay closer to 2.5 than the unweighted one.
- **Intercept drift** — set `INTERCEPT = 0.10`: intercept recovery within ±0.02; LOD/LOQ shift must
  follow the reference implementation.
- **Level count / spacing** — drop to 4 levels or add a 10.0 level: σ definition still uses the two
  lowest levels present; all criteria re-derived.
- **Replicates** — change triplicate to duplicate or quadruplicate: m in σ changes accordingly.
- **Missing rows** — delete one replicate at a mid level: fit must not crash; row counts re-derived.
- **Format perturbation** — reorder CSV columns, add a `#` comment line at the end, or remove the
  blank-line/comment tolerance: parser must still read the file (header-driven parsing).
- **Extra unknowns** — add UNK_4 at 0.08 (near LOQ): output gains a row in input order; bias
  tolerance for sub-LOQ points is reported but not gated.

## Tier (c) — real data

- **NIST StRD `Norris` linear-regression dataset** — NIST's own ozone-monitor calibration study,
  36 observations, data at <https://www.itl.nist.gov/div898/strd/lls/data/Norris.dat>, certified
  values at <https://www.itl.nist.gov/div898/strd/lls/data/LINKS/v-Norris.shtml>: slope
  1.00211681802045, intercept −0.262323073774029, residual SD 0.884796396144373, R²
  0.999993745883712. It is unweighted, so it certifies the least-squares kernel only: run the
  tool's fitter with w = 1 on the Norris data and compare against the certified values to ~8
  significant digits.
- For the full IS workflow, take any published calibration table from a validated LC–MS/MS methods
  paper (concentration, analyte area, IS area) and compare against **R `lm(ratio ~ conc, weights =
  1/conc^2)`** as the reference implementation — the tool's slope/intercept should match R to
  machine precision, and LOD/LOQ should match the paper's reported values within the paper's own
  rounding.

## Benchmark protocol

1. Run the prompt in a fresh agentic coding session in a clean workspace (only the prompt file is
   provided; the agent writes `make_cal_data.py` and `calibrate.py` itself).
2. Record: model name + exact version, hash of the full prompt text, hash of the generated code,
   iteration count, wall-clock time, and per-criterion pass/fail **from the external grader** —
   the agent's own summary is not evidence (tutorial.md §3).
3. Require cross-model reproduction: at least two models of different families must pass tier (a)
   before the prompt is claimed reproducible; report the capability floor for any model that fails,
   including the failure mode (tutorial.md §6.1).
4. The prompt must fit the context budget of the smallest model claimed (it is ~6 KB, well under a
   32 K context even with data files and iteration; tutorial.md §9).
5. Report per checklist item 11 of tutorial.md: model+version, full prompt, code hash, benchmark
   data, pass criteria, iteration count, cross-model reproduction.
