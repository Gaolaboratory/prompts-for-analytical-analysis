# DDA database-search validation data (tier c)

## Source

Real DDA LC–MS/MS of a known sample: **Sigma UPS1 48-protein standard spiked at
50 fmol/µg into a Saccharomyces cerevisiae (yeast) whole-cell-lysate digest**
(highest spike level of the PXD001819 dilution series, replicate R1, original
raw file `OEMMA121101_61.raw`). Sample was reduced/alkylated with iodoacetamide
and trypsin-digested; acquired on a **Thermo LTQ Orbitrap Velos** (Dionex nanoRS
UHPLC, precursor in Orbitrap, fragment ions in the ion trap).

- ProteomeXchange/PRIDE project: **PXD001819** — "yeast-UPS1 standard LC-MS/MS
  dataset", Ramus et al., *Data in Brief* 6:286–294 (2016), PMID 26862574.
  Project page: https://www.ebi.ac.uk/pride/archive/projects/PXD001819
- Exact source file (archived Mascot result containing the searched MS2 peak
  lists; HTTP 200, direct download):
  https://ftp.pride.ebi.ac.uk/pride/data/archive/2015/12/PXD001819/WF1-4-5_UPS1_50000amol_R1.dat
  (494,083,568 bytes; its 41,639 `query` sections hold the Distiller-processed
  peak lists of every MS2 scan; its `parameters` section documents the original
  search: Trypsin/P, ≤2 missed cleavages, fixed Carbamidomethyl (C), variable
  Acetyl (protein N-term)/Oxidation (M), 5 ppm precursor, 0.8 Da fragment.)
- UPS protein sequences: compiled UPS1/UPS2 standard FASTA
  `UPS1_UPS2_Ecoli_469008_RefSeq.fasta` shipped inside
  https://ftp.pride.ebi.ac.uk/pride/data/archive/2013/12/PXD000602/LTQ_other_files.zip
  (PRIDE project PXD000602, "UPS1 and UPS2 proteins diluted in E. coli").
- Yeast sequences: UniProtKB reviewed *S. cerevisiae* (strain S288c) proteome
  **UP000002311**, downloaded 2026-08-26 via
  https://rest.uniprot.org/uniprotkb/stream?query=(proteome:UP000002311)%20AND%20(reviewed:true)&format=fasta
- Download date for all files: **2026-08-26**.
- Licenses: PXD001819 and PXD000602 are distributed under the standard
  **EMBL-EBI Terms of Use** (public; reuse permitted with citation of the
  dataset and paper — no further restrictions). UniProt data: **CC BY 4.0**.

## Contents

- `ups1_yeast_dda_first1200.mgf` — 8,877,301 bytes. MGF with the **first 1200
  MS2 spectra (queries 1–1200 of 41,639, i.e. the start of the run in
  acquisition order)** of `UPS1_50000amol_R1` / `OEMMA121101_61.raw`. Real
  instrument peak lists (the exact Mascot-searched "Ions" lists; mean 448
  peaks/spectrum, 538,202 peaks total; 1032 spectra CHARGE=2+, 168 CHARGE=1+).
  `SCANS=` is the Mascot query number; `TITLE=` keeps the original
  raw-file/scan title. MD5 `49ecc5db66f02b5af05448bfbfb380b2`.
- `yeast_pe1_plus_ups.fasta` — 1,986,408 bytes, 3,260 sequences:
  - 3,210 *S. cerevisiae* proteins (UniProt reviewed, headers `>sp|ACC|NAME`)
    that are **reported as identified in the archived Mascot result** (the
    `.dat` protein section lists 4,193 yeast hits; 3,474 map to today's
    reviewed proteome; PE=1 entries kept) — i.e. a proteome subset that
    provably contains proteins identified in this exact run;
  - the 50 human UPS standard entries (48 canonical UPS1 proteins plus 2
    variant/fragment entries in the compiled PXD000602 set), headers as in the
    source (`P02768ups|ALBU_HUMAN_UPS ...`).
  MD5 `fbbf2c74057b9b2a920d7e1234092ff9`.

## Expected results — v1 rules (minimal_dda_search_prompt.md)

Harness-side reference, computed by re-implementing the prompt's rules exactly
(trypsin after K/R not before P, **0 missed cleavages**, length ≥ 5, no
modifications; candidates within **0.02 Da** of the measured precursor m/z at
the spectrum's charge; singly-charged b1..b(n−1)/y1..y(n−1), peak within
**±0.5 Da**; score = matched-fragment count, tie-broken by summed matched
intensity):

| Quantity (for the 1200-spectrum subset vs `yeast_pe1_plus_ups.fasta`) | Value |
| --- | --- |
| **N** — spectra with ≥ 1 candidate peptide within 0.02 Da | **1028 / 1200 (85.7%)** |
| proteins with ≥ 1 best-hit spectrum | 398 |
| **M** — proteins with ≥ 2 best-hit spectra | **189** |
| UPS1 (human standard) proteins with ≥ 2 best-hit spectra | 2 — `NQO1_HUMAN_UPS` (8 spectra), `GELS_HUMAN_UPS` (3) |

Top-hit proteins are dominated by abundant yeast background proteins (e.g.
PSK1_YEAST 28 spectra, TOG1_YEAST 20, OTC_YEAST 18, VATA_YEAST 17, SNT2_YEAST
17, ITPA_YEAST 16), with the known UPS1 standard proteins above also appearing
— the qualitative expectation for a yeast lysate spiked with 50 fmol/µg UPS1.

Supplementary: the sample carries fixed carbamidomethyl-C (+57.021464), which
the prompt's modification-blind engine does not model. Adding CAM-C peptide
variants to the candidate space changes N (unchanged, 1028) and M (190) — so
the strict numbers above are a mild under-count of the true chemically-correct
ones, i.e. conservative.

Published identification list for the exact file: the same `.dat`'s protein
section (= the submitter's archived Mascot result for
`UPS1_50000amol_R1`) reports 4,193 yeast proteins for this run and **no UPS1
proteins** (the search's reported hits are yeast-only, although `DB2=UPS1_2`
was configured); peptide/protein-level published results for the full dataset
are in Ramus et al. 2016 (Data in Brief) Supplementary Table 1. Consequently
the UPS1 protein claims above come from the harness-side reference, not from
the archived search.

## How obtained

```sh
# 1) archived Mascot result for the exact run (contains the MS2 peak lists)
curl -sL -o WF1-4-5_UPS1_50000amol_R1.dat \
  "https://ftp.pride.ebi.ac.uk/pride/data/archive/2015/12/PXD001819/WF1-4-5_UPS1_50000amol_R1.dat"
# (one connection drop at ~85% occurred; resumed with `curl -C -`)

# 2) UPS standard sequences + published protein-level ID list for this run
curl -sL -o LTQ_other_files.zip \
  "https://ftp.pride.ebi.ac.uk/pride/data/archive/2013/12/PXD000602/LTQ_other_files.zip"
curl -sL -o yeast_reviewed.fasta \
  "https://rest.uniprot.org/uniprotkb/stream?query=(proteome:UP000002311)%20AND%20(reviewed:true)&format=fasta"
```

MGF extraction (Python 3 std lib only): the `.dat` is MIME-multipart; queries
1–1200 were read from their `name="queryN"` sections (`title=`, and the peak
list from the `Ions…=` lines, plain `mz:intensity` pairs), with measured
precursor m/z and charge from the `summary` section's `qexp{N}=mz,z+` entries;
written as standard MGF `BEGIN IONS/…/END IONS` blocks with `SCANS=` = query
number. FASTA construction: accessions parsed from the `.dat` protein section
values (`sp|ACC|NAME`), intersected with the reviewed yeast proteome, PE=1
kept, plus the 50 UPS entries copied verbatim. Reference numbers computed with
the same digest/mass/fragment/scoring rules as the prompt (script in the tier-c
scratch; parameters reproduced in the table above). No LLM or endpoint calls.

## Expected results — v2 rules (examples/database_search/PROMPT.md)

Harness-side reference (`bench/reference/short/dda_ref.py`), implementing the v2
rules: reversed-sequence decoys, tryptic peptides of length 6-18, a mass-sorted
index selected with bisect, a 0.02 x z Da precursor window on the neutral mass,
12 peaks per 100 Da window with peaks within 2 Da of the precursor dropped,
score = matched-fragment count at +/-0.5 Da tie-broken by summed matched
intensity, and monotone, **tie-grouped** q-values: because score is an integer
matched-fragment count, hundreds of best hits share one score (238/221/216/165
on this data), so every PSM in a score group receives the FDR evaluated once at
the end of that group, not at its own arbitrary position within it -- see
`docs/design/2026-09-12-dda-fdr-tie-fix.md`.

| Quantity | Value |
| --- | --- |
| target peptides / decoy peptides | 87060 / 87188 |
| spectra read | 1200 |
| spectra with >= 1 candidate | 1025 |
| best hits / of which decoy | 1025 / 341 |
| decoy fraction among best hits | 0.333 |
| target PSMs at q <= 0.01 (filtered) | 18 |
| target PSMs at q <= 0.01 (unfiltered, step 9) | 0 |
| UPS1 proteins with >= 2 best-hit spectra | 7 |

Reference wall clock: 2.17 s. Reproduce with:
`python3 bench/reference/short/dda_ref.py data/database_search/yeast_pe1_plus_ups.fasta data/database_search/ups1_yeast_dda_first1200.mgf`

(Superseded value: before the tie-grouped q-value fix, this same reference
implementation reported **26** filtered / **1** unfiltered here -- a number
that depended on the arbitrary order equal-score PSMs happened to land in
when sorted, and swung 18-26 across 8 reorderings of the identical PSM set.
The 18/0 pair above is the tie-order-invariant, corrected value.)

The v1 block above is a different quantity, not a disagreement: v1 keeps peptides
of length >= 5 and windows candidates at 0.02 Da against the measured precursor
m/z, so the two rule sets search different candidate spaces.

**The 7 UPS1 proteins are not the same set v1 recorded, and that is expected.**
v1 has no peak-filtering step at all, so its "best hit" is effectively this
reference's *unfiltered* run. Under v2's filtered rules, `GELS_HUMAN_UPS`
carries over (2 best-hit spectra, matching v1), but `NQO1_HUMAN_UPS` — v1's
other qualifying protein, with 8 spectra — drops out entirely (0 best-hit
spectra). Traced to source: in v1/unfiltered mode, scans 814-820 all pick
`NQO1_HUMAN_UPS`'s tryptic peptide `EAAAAALK` with a perfect 14/14 fragment
match, because that spectrum's 459 raw peaks span m/z 112-759 (density
~0.71/Da over that observed span) and an 8-residue peptide's 14 fragments
almost always land within +/-0.5 Da of *some* peak by chance at that density.
The matches themselves show the coincidental signature directly: all 14 sit
0.003-0.41 Da off their predicted m/z (near the edge of the +/-0.5 Da window,
not clustered near 0), and their matched intensities run 1,000-20,300 while
the spectrum's own dominant peaks reach 913,400 — none of the spectrum's
intense peaks correspond to a predicted fragment at all. Filtering scan 814
to its 12-most-intense-per-100-Da peaks (84 of 459 survive) drops
`EAAAAALK`'s match to 3/14, and a different candidate — a decoy,
`DECOY_sp|P38922|HRB1_YEAST` scoring 6/10 — wins instead. This is peak
filtering working as documented, not a bug: it removes exactly the kind of
noise-driven "perfect" match that produced v1's NQO1 identification, and its
replacement being a decoy is the correct, informative outcome for a spectrum
whose true peptide is not a strong candidate. In v2's own *unfiltered*
run (step 9), `NQO1_HUMAN_UPS` reappears with 7 best-hit spectra (`EAAAAALK`,
score 14 each) — consistent with v1's un-filtered engine, and with why v2's
peak-filtering criterion exists at all. New prompts and graders built on this
file must not assume `NQO1_HUMAN_UPS` (or any specific named protein) survives
v2's filtered pipeline; the pinned quantities are the counts in the table
above, not this protein list.
