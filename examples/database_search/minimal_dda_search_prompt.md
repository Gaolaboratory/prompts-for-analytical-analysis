# Task 2/4 — Minimal DDA database search engine

Standard library only. Write `search.py`.

**Reuse task 1:** `from fasta_reader import read_fasta` and `from mzml_reader import read_mzml`; run `python3 make_test_data.py` for `mini.fasta` / `mini.mzml`. Do not re-implement parsing or re-create the test files. (If those files are missing, build task 1 first.)

## What to build

`python3 search.py mini.fasta mini.mzml -o psms.tsv` — for each MS2 spectrum, identify the best-matching tryptic peptide and write one row:

```
scan	precursor_mz	charge	peptide	protein	decoy	matched_fragments	total_fragments	score
```

Pipeline, using standard proteomics definitions:

1. **Decoys** — for each target protein add a `DECOY_`-prefixed protein whose sequence is reversed. Digest targets and decoys together.
2. **Digest** — trypsin: cleave after K/R except before P; the peptide keeps its C-terminal K/R. Keep peptides of length ≥ 5.
3. **Masses** — standard monoisotopic residue masses, `H2O = 18.01056`, `PROTON = 1.007276`. Neutral = Σresidues + H2O; precursor m/z at charge z = (neutral + z·PROTON)/z. Singly-charged fragments: **b** = Σprefix + PROTON, **y** = Σsuffix + H2O + PROTON. Generate b1..b(n−1) and y1..y(n−1), i.e. 2(n−1) fragments.
4. **Search** — candidates are peptides within **0.02 Da** of the measured precursor m/z at the spectrum's charge. A fragment matches if some peak is within **±0.5 Da**. Score = number of matched fragments, tie-broken by summed matched intensity. Report the best candidate; `decoy=1` if its protein starts with `DECOY_`.

Print to stdout the target and decoy candidate counts, and the best decoy hit per spectrum (or "no decoy hit" when no decoy passes the precursor filter).

## Verify your masses before searching

Use standard monoisotopic residue masses from memory; any reasonable precision works, since the 0.02 Da precursor window is far wider than last-digit differences. Do not stall reconciling decimal places — just check the result:

`QISFVK` neutral mass = 720.417 Da, precursor m/z at z=2 = 361.2158. If that is off, your table has a real error. (The classic traps are that I and L are isobaric, and that K and Q differ by only ~0.036 Da.)

**Check these by running code, never by reasoning through the strings by hand.** Write `search.py` first, then
print the digests and counts and compare. Reversing sequences or summing residue masses mentally wastes the
budget and is error-prone.

## Acceptance criteria

1. Runs with no third-party packages; `psms.tsv` has exactly 2 rows.
2. `scan=1` → `QISFVK`, `sp|P00001|MINI1`, `decoy=0`, 10 of 10 fragments matched.
3. `scan=2` → `SPGTWEQLK`, `sp|P00002|MINI2`, `decoy=0`, 16 of 16 fragments matched.
4. Digests are exactly `MK, TAYIAK, QR, QISFVK, SHFSR, QDILDLWQNLTTGPGR` and `MAGDR, SPGTWEQLK, DAVEILR, QNYVGAFW`.
5. Stdout reports **8 target and 7 decoy** candidates, plus the best decoy hit per spectrum. With this data no decoy falls inside the 0.02 Da precursor window, so the correct output is **"no decoy hit"** for both spectra — print that, don't invent one.

> The 8/7 asymmetry is correct, not a bug: reversing moves the C-terminal K/R to the N-terminus, so a reversed protein does not digest into the same number of peptides. Do not force the counts equal.

## If something fails

No candidates → mass bug (see the QISFVK check). Wrong peptide wins → digest bug: print both digests and compare with criterion 4; the usual cause is cleaving before K/R instead of after. Right peptide but missing fragments → b/y formula (b has no H2O). Decoy count 0 → you reversed but never digested the decoys. Wrong peak counts → fix `mzml_reader.py` in task 1, not here.

## Optional

ppm precursor tolerance; 2+ fragment charges when precursor charge ≥ 3; q-value = decoys/targets over score-sorted PSMs.
