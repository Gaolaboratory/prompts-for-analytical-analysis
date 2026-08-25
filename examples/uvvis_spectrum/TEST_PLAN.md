# TEST PLAN — UV-Vis spectrum processing

**Tier (a) executed 2026-08-24:** 9/9 criteria × 3 reps × 2 models (local Ornith-1.5-35B-A3B, remote
Qwen3.8-27B), external grader via the pi harness — see `/AC_BENCHMARK_REPORT.md`. Tiers (b)/(c)
remain plans. The oracle numbers in
`minimal_uvvis_prompt.md` were verified by running a reference implementation.

## Tier (a) — exact synthetic

Commands, in a clean workspace containing only the prompt:

```sh
# 1. Agent session: paste minimal_uvvis_prompt.md verbatim into a fresh agentic coding session.
#    The agent must produce make_uvvis_data.py and uvvis.py.
python3 make_uvvis_data.py
python3 uvvis.py sample.csv -o peaks.tsv > stdout.txt 2> stderr.txt
python3 grade.py peaks.tsv stdout.txt stderr.txt
```

External grader sketch (`grade.py`, a separate program — the agent's self-report is not
evidence, tutorial.md §3). Each acceptance criterion maps to one check returning PASS/FAIL:

```python
import sys
peaks, out, err = sys.argv[1:4]
lines = open(peaks).read().splitlines()
stdout = open(out).read()

def check(name, ok): print(("PASS" if ok else "FAIL"), name)

check("header+tabs", lines[0] == "band\tlambda_max_nm\ta_max")
rows = [l.split("\t") for l in lines[1:]]
check("3 rows", len(rows) == 3 and all(len(r) == 3 for r in rows))
lams = [int(r[1]) for r in rows]
amaxs = [float(r[2]) for r in rows]
check("sorted", lams == sorted(lams))
check("lambda within 2nm", all(abs(a-b) <= 2 for a, b in zip(lams, [320, 420, 540])))
check("a_max within 0.02", all(abs(a-b) <= 0.02 for a, b in zip(amaxs, [0.8803, 1.2677, 0.6691])))
check("a_max %.4f format", all(r[2] == "%.4f" % float(r[2]) for r in rows))
check("stdout bands line", "bands: 3" in stdout.splitlines())
conc = float(next(l.split(":")[1] for l in stdout.splitlines()
                  if l.startswith("concentration_uM:")))
check("conc within 5% of 50.0", abs(conc - 50.0) <= 2.5)
check("no 4th band near 481", all(abs(l - 481) > 5 for l in lams))
```

Also confirm `make_uvvis_data.py` is byte-reproducible: run it twice, `diff` the two
`sample.csv` files.

## Tier (b) — robustness

Perturb the generator knobs (edit `make_uvvis_data.py`, re-run, re-grade). The prompt's
algorithm spec must survive all of:

| Knob | Perturbation | Must still hold |
|---|---|---|
| noise amplitude | `0.01` → `0.02`, then `0.04` | band count 3; lambda within ±2 nm; a_max tolerance widens to ±0.05 |
| baseline curvature | `4.0e-7` → `8.0e-7` | band count 3; lambda within ±2 nm; a_max tolerance widens to ±0.06; concentration within 10% |
| baseline slope | `6.0e-4` → `1.2e-3` | band count 3; lambda within ±2 nm |
| missing peak | drop the 540 nm band from `BANDS` | exactly 2 rows; no phantom band reported anywhere |
| extra small peak | add `(650.0, 0.15, 20.0)` (below the 0.20 floor) | still exactly 3 rows |
| sampling density | `range(200, 801)` → 2 nm steps (`lam/2`, adjust loop) | band count 3; lambda within ±4 nm (grid is coarser) |
| seed | change `lcg(20260824)` | band count 3; lambda within ±2 nm |

For each perturbed file, recompute the reference answer with the reference implementation before
grading — never grade against the tier (a) numbers on perturbed data.

## Tier (c) — real data

Source: **AIST Spectral Database for Organic Compounds (SDBS)**, https://sdbs.db.aist.go.jp —
free, includes solution UV/Vis spectra. Concrete target: the UV/Vis spectrum of
**4-nitrophenol** (SDBS lists λmax; literature value ≈ 317 nm in neutral solution).

Procedure: transcribe or digitize the published trace into the tool's CSV format (or take any
exported CSV the source offers), run `uvvis.py`, and compare the reported lambda_max against the
database/literature value. Record: agreement within ±3 nm on lambda_max for the main band; if the
entry also gives ε, check the concentration identity is arithmetically consistent
(`c = A/(ε·l)` for the stated path length). Reference answer: the λmax/ε stated in the SDBS
entry itself, plus a manual read of the peak apex from the published figure as an independent
check. A failure here that does not occur in tier (a) is a finding (real-format quirks the
generator missed), not necessarily a model error — record which.

## Benchmark protocol

- Run the prompt in a **fresh agentic coding session in a clean workspace** (no reference
  implementation, no scratch files).
- Record: model name and exact version, full prompt text, **prompt hash** (e.g.
  `shasum -a 256 minimal_uvvis_prompt.md`), **generated code hash**, iteration count (agent
  turns until the agent declares done), wall-clock time, and per-criterion PASS/FAIL **from the
  external grader** — never from the agent's own summary (tutorial.md §3: models rubber-stamp
  criteria their own output contradicts).
- Cross-model reproduction: repeat on at least two models of different size/origin and report
  both. A capability floor is a property of a model, not of the task (tutorial.md §6.1–6.2) —
  record the floor per model, in both directions.
- Context budget: the prompt is ~5.4 KB and must fit the context budget of the smallest model
  claimed, with room for the generator, the tool, and agentic iteration (tutorial.md §9). Verify
  the run completes without context overflow on that model before claiming support.
