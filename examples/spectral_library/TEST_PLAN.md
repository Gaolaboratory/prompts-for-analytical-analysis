# TEST PLAN — MS/MS spectral library search

**Tier (a) executed 2026-08-24:** 7/7 criteria × 3 reps × 2 models (local Ornith-1.5-35B-A3B, remote
Qwen3.8-27B), external grader via the pi harness — see `/AC_BENCHMARK_REPORT.md`. Tiers (b)/(c)
remain plans. The reference
numbers in the prompt were produced by running a reference implementation against the
shipped generator (see "oracle verification" below).

## Oracle verification (done, pre-benchmark)

Before publishing the prompt, the generator and a reference `libsearch.py` were written
and executed under `/tmp`. Verified by execution:

- self-check core: query `[(100,100),(200,400),(300,900)]` vs reference
  `[(100,25),(200,100),(350,225)]` → score **0.127551**, 2 matched peaks
  (hand-check: `250² / (1400·350)`);
- q1 → caffeine 0.937281, 7/8 matched; runner-up acetaminophen 0.022093;
- q2 → acetaminophen 0.911280, 7/8; runner-up sulfamethoxazole 0.024659;
- q3 → sulfamethoxazole 0.958285, 8/8; runner-up acetaminophen 0.023126;
- q4 → all four entries score 0.0 → `NO_MATCH`.

Any benchmark failure on criteria 3–7 therefore implicates the generated code, not the oracle.

## Tier (a) — exact synthetic

In a clean workspace:

```
# prompt the agent with minimal_spectral_library_prompt.md; it must produce:
python3 make_test_data.py                                   # writes library.txt, queries.txt
python3 libsearch.py queries.txt library.txt -o results.tsv # the tool under test
python3 grade.py                                            # external grader, below
```

`grade.py` is a **separate program** (not the agent's self-report — tutorial.md §3). Sketch:

```python
import subprocess, sys
EXP = {  # (best_match, score_lo, score_hi, matched, total)
  "q1": ("caffeine",        0.9363, 0.9383, 7, 8),
  "q2": ("acetaminophen",   0.9103, 0.9123, 7, 8),
  "q3": ("sulfamethoxazole",0.9573, 0.9593, 8, 8),
  "q4": ("NO_MATCH",       -1e-9,   0.001,  None, None),
}
# criterion 1: run the CLI, assert stdout line == "queries: 4  called: 3  no_match: 1"
# criterion 2: parse results.tsv; assert header == the 5 specified columns joined by "\t",
#   exactly 4 rows sorted by query_id, file uses \t and \n only
# criteria 3-6: per row, match/lo<=score<=hi and (if given) matched_peaks/total_library_peaks
# criterion 7: recompute all 16 pairwise scores from library.txt/queries.txt with the grader's
#   own scorer; assert argmax and second-best < 0.03 for q1-q3
# print one PASS/FAIL line per numbered criterion; exit nonzero on any FAIL
```

The grader recomputes scores independently — it never trusts the tool's arithmetic.

## Tier (b) — robustness

Perturb generator knobs one at a time (edit the copy in the agent's workspace, recompute
expected values with the reference implementation before grading — never estimate them):

- **m/z jitter**: widen `(next(rnd) - 0.5) * 0.2` → `* 0.4` (still inside ±0.5) and `* 1.2`
  (half the peaks fall outside tolerance). Criteria 1–2 and the NO_MATCH call on q4 must
  still hold; scores/matched counts change and must be re-verified.
- **Intensity noise**: `0.75 + 0.5*rnd` → `0.5 + 1.0*rnd`. Same expectations.
- **Drop threshold**: `jint < 12.0` → `< 40.0` (aggressive centroiding). Ranking must survive.
- **Extra peaks**: add 6 noise peaks instead of 2, some deliberately within ±0.5 of library
  peaks of *other* entries. One-to-one matching keeps scores stable; check the call still wins.
- **Format quirks**: CRLF line endings, tabs as separator, a `>NAME` line with trailing
  spaces, an entry with zero peaks. Parser must not crash; zero-peak entries score 0.

Criterion 7 (runner-up separation) is the canary: if any perturbation collapses the gap,
the prompt's matching rule is under-specified, not the model.

## Tier (c) — real data

Source: **MassBank of North America / MassBank.eu** — public, downloadable small-molecule
MS/MS records: https://massbank.eu/MassBank/ (GitHub export: https://github.com/MassBank/MassBank-data).

Protocol: pick 5 records of known compounds (e.g. caffeine, sulfamethoxazole) from
`MassBank-data`, convert their `PK$PEAK` blocks to the prompt's text format as the library;
take a second record (different instrument/collision energy) of one of those compounds as
the query. Reference answer: the query record's own annotated compound name — a known true
positive. Cross-check against MassBank's web search (https://massbank.eu/MassBank/Search) or
NIST MS Search if available; the tool's top hit must equal the true compound and the score
must exceed the 0.5 threshold. A second query from a compound absent from the 5-record
library must return `NO_MATCH`.

## Benchmark protocol

- Run the prompt in a fresh agentic coding session, clean workspace, no pre-existing code.
- Record: model name + version, full prompt hash (SHA-256 of the prompt file), generated
  code hash, iteration count, wall-clock, per-criterion pass/fail **from the external
  grader only** (the agent's self-certification is not evidence).
- Require reproduction on at least one second model family; report the floor both ways
  (tutorial.md §6.1–6.2).
- Prompt size: the prompt is ~6.6 KB / 125 lines, well inside a 32 K-context local model
  budget; record context usage of the smallest model claimed (tutorial.md §9).
- Archive: workspace snapshot, stdout/stderr logs, `results.tsv`, grader output.
