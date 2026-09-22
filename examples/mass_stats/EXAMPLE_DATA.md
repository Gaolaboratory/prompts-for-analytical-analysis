# Example data & expected results — mass_stats

**Dataset:** real two-condition LC-MS quantification matrix from MetaboLights **MTBLS14397**
(*V. dahliae* wild type vs knockout, 3+3 replicates, 618 named metabolites, raw peak areas) —
`data/mass_stats/quant_mtbls14397_pos.csv` + `groups.tsv` (+ a full 618-row scipy reference
table `expected_stats.tsv`). Provenance (CC0) and exact reference recipe:
`data/mass_stats/README.md`.

**Run:** the tool's pinned command on the provided matrix and group labels (the tool
log2-transforms raw areas itself per the spec).

**Expected results (scipy Welch + BH reference; top 3 by p-value):**

| feature | p | log2FC |
|---|---|---|
| MET_235 3'-Dephosphocoenzyme A | 9.81e-07 | −7.08 |
| MET_433 Myrmicacin | 1.18e-06 | −5.65 |
| MET_410 2,3-Dinor-8-epi-PGF2 | 1.31e-06 | −5.53 |

618 features tested, 253 significant at the spec's threshold; tolerance t/p within 1e-6
relative, same adjusted-p ordering (BH plateau at 1.26076e-04 in the top 8 — order by p).

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/mass_stats/local/tierc/`, 27 iterations): `real_results.tsv` top rows MET_235
(p 9.8097e-07, log2FC −7.0798), MET_433 (1.1821e-06, −5.6520), MET_410 (1.3053e-06, −5.5257) —
same ordering, values match the scipy reference to rounding — **PASS**. (The agent also
re-validated on its synthetic generator before touching the real data — its `results.tsv` holds
that synthetic check.)
