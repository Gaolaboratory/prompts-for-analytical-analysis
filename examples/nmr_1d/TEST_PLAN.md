# TEST_PLAN — 1D NMR processing from FID (`examples/nmr_1d/`)

**Tier (a) executed 2026-08-24:** 21/21 criteria × 3 reps × 2 models (local Ornith-1.5-35B-A3B, remote Qwen3.8-27B), external grader via the pi harness — see `/AC_BENCHMARK_REPORT.md`. Tiers (b)/(c) remain plans. Oracle verification (generator + reference implementation run by hand, "Oracle status" below) predates the benchmark.

Subject prompt: `minimal_nmr_1d_prompt.md` (≈6.7 KB — well inside a 32K-token context).

## Oracle status (already done, per tutorial §2)

- The generator embedded in the prompt was extracted and run; `fid.csv` is byte-identical across runs (MD5 `4e2158fa85b0385b8abe5391710aeeba`).
- A reference implementation produced the stated outputs: stdout lines `points read: 10000` / `zero-filled to: 16384` / `peaks found: 4`; ppm centers 0.4998 / 2.0994 / 3.7998 / 7.2502; integrals 24654.39 / 2768.91 / 5451.26 / 8166.71; relative integrals 1.0000 / 0.1123 / 0.2211 / 0.3312 (ideal 1 / 0.1111 / 0.2222 / 0.3333 — all within 0.002).
- FFT self-check outputs were computed by running the verbatim `fft`: 8-point cosine → `X[2] = (4-0j)`, `X[6] = (4+0j)`, all other `|X[k]| < 1e-15`; unit impulse → eight `(1+0j)`.

## Tier (a) — exact synthetic

In a clean workspace, paste the prompt to the agent, then:

```
python3 make_fid.py
python3 nmr_1d.py fid.csv -o multiplets.tsv > stdout.log 2> stderr.log
python3 grade_nmr_1d.py multiplets.tsv stdout.log stderr.log   # external grader, exit != 0 on any failure
```

Grading must be a separate program — never the agent's self-report (tutorial §3). Sketch of `grade_nmr_1d.py` (std-lib only):

```python
import sys, re
tsv, out, err = open(sys.argv[1]).read(), open(sys.argv[2]).read(), open(sys.argv[3]).read()
fails = []
def check(name, ok):
    if not ok: fails.append(name)

# 1: stdout lines exact, stderr silent on the counts
for line in ("points read: 10000", "zero-filled to: 16384", "peaks found: 4"):
    check(f"stdout {line!r}", line in out.splitlines())
# 2: structure
lines = tsv.split("\n")
check("header", lines[0] == "ppm_center\tintegral\trelative_integral")
rows = [l.split("\t") for l in lines[1:] if l]
check("4 rows", len(rows) == 4 and all(len(r) == 3 for r in rows))
check("tab-separated", "," not in tsv and "\r" not in tsv)
ppms = [float(r[0]) for r in rows]
check("sorted ascending", ppms == sorted(ppms))
check("decimals", all(re.fullmatch(r"-?\d+\.\d{4}", r[0]) and re.fullmatch(r"-?\d+\.\d{2}", r[1])
                      and re.fullmatch(r"-?\d+\.\d{4}", r[2]) for r in rows))
# 3/4/5: values
for r, (p, rel, integ) in zip(rows, [(0.50, 1.0, 24654.39), (2.10, 1/9, 2768.91),
                                     (3.80, 2/9, 5451.26), (7.25, 3/9, 8166.71)]):
    check(f"ppm {p}", abs(float(r[0]) - p) <= 0.02)
    check(f"rel {p}", abs(float(r[2]) - rel) <= 0.02)
    check(f"integral {p}", abs(float(r[1]) - integ) / integ <= 0.02)
# 6: FFT self-check — import the tool's fft and run it
sys.path.insert(0, ".")
import math
from nmr_1d import fft
X = fft([math.cos(2*math.pi*2*n/8) for n in range(8)])
check("fft cosine", abs(X[2] - 4) < 1e-9 and abs(X[6] - 4) < 1e-9
      and max(abs(X[k]) for k in range(8) if k not in (2, 6)) < 1e-9)
print("FAIL:", fails) if fails else print("PASS all")
sys.exit(1 if fails else 0)
```

Pass = grader exits 0. Report per-criterion pass/fail, not just the aggregate.

## Tier (b) — robustness

Perturb generator knobs one at a time, **recompute the oracle with the reference implementation before grading** (tutorial §2 — never grade against numbers you didn't re-run):

- **Noise**: `NOISE` 0.05 → 0.5 (10×). Criteria 2–5 must still hold; ppm tolerance may widen to ±0.05 if verified against the re-run oracle.
- **Baseline drift**: add a slow drift term (e.g. `+ 0.3*math.sin(2*math.pi*t/0.4)` — period shorter than the acquisition, so it lands near 2.8 Hz ≈ DC in the spectrum). The flanking-band baseline subtraction exists precisely for this; relative integrals must stay within ±0.02 of the re-run oracle.
- **Extra peak**: add a 5th signal, e.g. `(5.50, 4.0, 0.30)`. Expect exactly 5 rows, all original ppm/relative-integral criteria unchanged.
- **Missing peak**: drop the `(2.10, ...)` signal. Expect exactly 3 rows; the remaining three criteria unchanged.
- **Sampling density**: `N` 10000 → 20000 (zero-fill 32768). Same ppm centers within ±0.02; relative integrals within ±0.02 of the re-run oracle.
- **Phase**: `PHI0` 0.6 → 1.2. Peak count and ppm unchanged; relative integrals within ±0.02 — catches implementations that integrate before phasing.

## Tier (c) — real data

Dataset: **MetaboLights MTBLS1** — Salek et al. 2007, human urine 1H NMR (Bruker), public: <https://www.ebi.ac.uk/metabolights/MTBLS1>. Raw Bruker FIDs are in the study's file tree (`.zip` of per-sample `fid` + `acqus`).

Honest caveat to record in the run notes: real Bruker FIDs are complex quadrature with the carrier mid-spectrum and DSP group-delay artifacts, while `nmr_1d.py` specifies single-channel real detection. So convert one FID to the tool's input model: read with nmrglue (`ng.bruker.read`), remove the digital filter (`ng.bruker.remove_digital_filter`), take the real channel, and write `time_s,intensity` CSV using `SW`/`O1` from `acqus`. Then:

- Run `nmr_1d.py` on that CSV (overriding the constants to the `acqus` values) and compare against a **reference processing** of the same FID in nmrglue — `em` (lb=1) → `zf_auto` → `fft` → `ps(p0=...)` — following the published template <https://nmrglue.readthedocs.io/en/latest/examples/proc_bruker_1d.html>.
- Acceptance: the major picked resonances agree in ppm within ±0.05; relative integrals of the 3–5 strongest peaks agree within ±20% (real-data phasing and baseline differences make a tighter bound unrealistic for a minimal tool). This tier validates the pipeline, not exact equality.

## Benchmark protocol

1. Fresh agentic coding session, clean workspace, no access to this repo's reference implementation or scratch files — the agent sees only the prompt file.
2. Record: model name + exact version, prompt SHA-256, SHA-256 of every file the agent writes, iteration count (agent turns), wall-clock time, token/context usage if available.
3. Grade with the external `grade_nmr_1d.py` only; record per-criterion pass/fail. The agent's own summary is not evidence.
4. Require cross-model reproduction: at least two models (one local, one remote) before claiming the prompt "works". Report the floor: if a model fails, report which model and the failure mode (tutorial §6.1) — do not quietly drop it.
5. Prompt budget: ≈6.7 KB / 98 lines — comfortably inside a 32K-token context; state the smallest model it was actually validated on (tutorial §9–11).
