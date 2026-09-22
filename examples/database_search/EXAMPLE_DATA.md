# Example data & expected results — database_search

**Dataset:** real UPS1-in-yeast DDA run — 1,200 MS2 spectra (MGF, extracted from the archived
Mascot results of PRIDE **PXD001819**, Ramus et al. 2016, LTQ Orbitrap Velos) + a 3,260-protein
FASTA (3,210 run-identified yeast PE=1 entries + the 48 UPS standards) —
`data/database_search/`. Provenance, extraction method, and licenses:
`data/database_search/README.md`.

**Run:** `python3 search.py ups1_yeast_dda_first1200.mgf yeast_pe1_plus_ups.fasta -o psms.tsv`
(the MGF needs a small reader — the spectra are peak lists with PEPMASS (m/z) and CHARGE
headers).

**Expected results (harness-side reference implementing the prompt's own rules — 0 missed
cleavages, 0.02 Da precursor, ±0.5 Da b/y fragments):**

| anchor | reference |
|---|---|
| N — spectra with ≥1 precursor candidate | 1028 of 1200 |
| M — proteins with ≥2 best-hit spectra | 189 |
| UPS1 ground truths among hits | NQO1 ×8, Gelsolin ×3 |

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/database_search/local/tierc/`, 38 iterations; the runner's 2700 s timeout was
raised to 5400 s for this cell — the densest prompt × largest real input). Verdict: **PARTIAL**:

- N: 1038 spectra assigned (target or decoy best hit) — within 1% of the reference 1028 ✓
- ground truth: both reference UPS1 proteins recovered — NQO1 ×6, Gelsolin ×1 ✓
- M: 109 target proteins with ≥2 hits vs reference 189 ✗, and 499 of 1038 assignments went to
  *decoys* (~48%) — on real ion-trap MS2 at the prompt's ±0.5 Da fragment tolerance, the
  matched-fragment-count score does not separate target from decoy nearly as cleanly as on the
  synthetic spectra (where decoys rarely tie). The engine, digestion, and mass arithmetic are
  correct (the agent independently diagnosed PEPMASS-as-m/z and matched the candidate window);
  the limitation is the *scoring rule's* discrimination on real data — a prompt-level finding,
  recorded here rather than hidden.
