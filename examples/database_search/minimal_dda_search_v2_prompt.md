# DDA database search with FDR control

Standard library only. Write `search.py`.

`python3 search.py bench.fasta bench.mgf -o psms.tsv` — search every MS2 spectrum against a
tryptic peptide database, score the candidates, estimate a false-discovery rate from reversed
decoys, and write one row per spectrum:

```
scan	precursor_mz	charge	peptide	protein	decoy	matched_fragments	total_fragments	score	q_value
```


> This supersedes `minimal_dda_search_prompt.md`, which reports an unqualified best hit for
> every spectrum. That is safe only when every spectrum's peptide is guaranteed to be in the
> database. It is not safe on real data, and the generator is built so that it is not
> safe here either: **20 of the 60 spectra come from proteins deliberately left out of the
> FASTA.** Those spectra have no correct answer. A search engine that always names a peptide
> will name a wrong one for all 20 of them, and roughly half of those will be decoys.

## Dependencies

| module | provides | build from |
|---|---|---|
| `fasta_reader.py` | `read_fasta(path) -> [(id, sequence), ...]` | `examples/mass_reader/minimal_readers_prompt.md` |
| `mgf_reader.py` | `read_mgf(path) -> [spectrum dict, ...]` | `examples/mass_reader/minimal_readers_prompt.md` |

Check the working directory for each module before writing any code. If it is
there, import it — do not re-implement it and do not edit it. If it is missing,
build it from the prompt named above, verify that prompt's acceptance criteria,
then come back here.

## Data

Run `python3 make_search_data.py` (shipped beside this prompt) to write `bench.fasta` and `bench.mgf`. It is the
oracle: the numbers below hold only for its exact output. Don't edit it and
don't generate the data any other way.

## Pipeline

1. **Decoys** — for each target protein add a `DECOY_`-prefixed protein whose sequence is
   reversed. Digest targets and decoys together, and keep the flag.
2. **Digest** — trypsin: cleave after K/R except before P; the peptide keeps its C-terminal
   K/R. Keep peptides of length **6 to 18**.
3. **Masses** — standard monoisotopic residue masses, `H2O = 18.010565`,
   `PROTON = 1.0072765`. Neutral = Σresidues + H2O. Singly-charged fragments:
   **b** = Σprefix + PROTON, **y** = Σsuffix + H2O + PROTON. Generate b1..b(n−1) and
   y1..y(n−1), i.e. 2(n−1) fragments.

   **`b_i` is the first `i` residues; `y_i` is the last `i` residues.** They are
   independent series, not one loop run in reverse. For `QISFVK`: `b1` is `Q` alone
   (129.0659) and `y1` is `K` alone (147.1128) — `y1` **must include the C-terminal
   residue**. Writing the y loop as a mirror image of the b loop is the classic way
   to drop that residue and shift the entire y series.
4. **Index the database by mass.** Build one list of `(neutral_mass, peptide, protein, decoy)`
   **sorted by mass**, and select candidates with `bisect`. Do not rescan the peptide list for
   every spectrum: that is `O(spectra × peptides)` and on a real-sized database it is the
   difference between one second and ninety minutes.
5. **Candidates** — peptides whose neutral mass is within `0.02 × z` Da of the spectrum's
   measured neutral mass, `neutral_obs = pmz·z − z·PROTON`.
6. **Filter the peaks before matching.** Keep only the **12 most intense peaks in each 100 Da
   window** of the spectrum, and drop peaks within 2 Da of the precursor m/z. A raw scan
   carries hundreds of noise peaks; at ±0.5 Da tolerance those alone will match a large
   fraction of any peptide's fragments.
7. **Score** — a fragment matches if a kept peak lies within **±0.5 Da**. Score = number of
   matched fragments, tie-broken by summed matched intensity. Report the best candidate;
   `decoy=1` if its protein starts with `DECOY_`.
8. **FDR** — sort all best hits by descending score. Walking down that list, let `T` and `D` be
   the running counts of target and decoy hits; the FDR estimate at each position is `D/T`.
   The **q-value** of a PSM is the smallest FDR estimate at or below its position — compute it
   by sweeping from the bottom of the list upward, carrying a running minimum, so q-values are
   monotone. Write the q-value in every row.
9. **Run the whole search a second time with peak filtering switched off** (step 6 skipped,
   every peak kept) and report that run's `q ≤ 0.01` count alongside the first. Only the
   filtered run is written to `psms.tsv`. This is not a diagnostic afterthought: it is the
   only evidence that your filtering step does anything, and criterion 6 grades it.

Print to stdout: the target and decoy peptide counts, the number of spectra read, the number
with at least one candidate, the number of best hits and how many of them are decoys, the
number of target PSMs at `q ≤ 0.01`, and the same count from the unfiltered run of step 9.

## Why the q-value is not optional

With a 1:1 target:decoy database, a spectrum whose true peptide is absent scores its random
best hit against targets and decoys with equal probability. **The decoy fraction among your
best hits therefore measures the fraction of your output that is noise** — it needs no ground
truth to compute, which is exactly why it is the criterion below. Reporting one best hit per
spectrum with no q-value is not a simplification; it is an unfalsifiable result. On a real
UPS1-in-yeast run (PRIDE PXD001819, 1200 LTQ Orbitrap Velos MS2 spectra against 3,260
proteins) the previous prompt's rules assign a peptide to 997 spectra of which **40.2% are
decoys**, and only **1** survives a 1% FDR threshold.

## Verify your masses before searching

Use standard monoisotopic residue masses from memory; any reasonable precision works, since the
0.02 Da precursor window is far wider than last-digit differences.

`QISFVK` neutral mass = 720.417 Da, precursor m/z at z=2 = 361.2158. If that is off, your table
has a real error. (The classic traps are that I and L are isobaric, and that K and Q differ by
only ~0.036 Da.)

**Then check the fragments, which the precursor mass cannot catch.** For `QISFVK`:

```
b1..b5  129.0659  242.1499  329.1819  476.2504  575.3188
y1..y5  147.1128  246.1812  393.2496  480.2817  593.3657
```

A y series starting at 246.1812 instead of 147.1128 means you dropped the C-terminal residue —
see step 3. This error still produces plausible output: it *raises* the number of matched
fragments, because a wrong series still hits peaks by chance at ±0.5 Da tolerance, and it makes
every summary statistic look better (fewer decoys, more accepted PSMs). Nothing downstream will
tell you. Print this table and compare it before you search.

**Check these by running code, never by reasoning through the strings by hand.** Reversing
sequences or summing residue masses mentally wastes the budget and is error-prone.


`bench.mgf` is MGF, not mzML: `BEGIN IONS` … `END IONS` blocks, `PEPMASS=` (an m/z, not a
neutral mass), `CHARGE=2+`, `SCANS=`, then `m/z intensity` pairs one per line.

## If a number below does not match, do not tune for it

Every constant in the pipeline is pinned: 0.02 × z precursor window, ±0.5 Da fragment
tolerance, 12 peaks per 100 Da window, length 6–18. A mismatch means a **bug upstream**,
not a parameter that needs adjusting. Do not sweep tolerances, peak budgets, window sizes
or score cut-offs to move a count toward the target — that search does not converge, and a
run that reaches the right number by tuning is wrong in a way the criteria cannot see. Print
the digest of one protein and the fragment table of one peptide, compare them against the
values above, and fix what is actually broken.

## Acceptance criteria

Run `python3 make_search_data.py`, then
`python3 search.py bench.fasta bench.mgf -o psms.tsv`, and check all of:

1. Runs with no third-party packages, and finishes in **under 60 seconds**. (The mass-sorted
   index version of this search takes about 0.13 s; a per-spectrum linear rescan of the
   database will not make the limit.)
2. Stdout reports **16,853 target and 16,735 decoy** peptides indexed, **60** spectra read, and
   **59** spectra with at least one candidate.
3. Stdout reports **59 best hits, 9 of them decoys (15.3%)**. Do not try to drive this to zero:
   20 of the 60 spectra have no correct answer, and ~half their random best hits landing on
   decoys is the expected and correct behaviour.
4. Stdout reports **31 target PSMs at q ≤ 0.01**.
5. `psms.tsv` is tab-separated with the exact 10-column header above and **59** data rows,
   with a `q_value` column that is non-decreasing when the rows are sorted by descending score.
6. The unfiltered run from pipeline step 9 reports **18** target PSMs at q ≤ 0.01, against
   **31** for the filtered run, with the decoy count unchanged at 9. Both numbers must appear
   on stdout. This is the check that your peak-filtering step exists and does something.
7. `scan=1` → `EHHSESNHWK`, `sp|SYN0146|SYN0146_TEST`, `decoy=0`, 9 of 18 fragments matched.

## If something fails

No candidates anywhere → mass bug (see the QISFVK check), or you treated `PEPMASS` as a neutral
mass instead of an m/z. Search takes minutes → you are rescanning all peptides per spectrum;
build the sorted index and use `bisect`. Decoy fraction near 50% → your score is not
discriminating at all; check that fragments are matched against *kept* peaks and that b ions
carry no H2O. Decoy fraction 0% → you never digested the decoys, or you filtered them out
before choosing the best hit; they must compete on equal terms or the FDR is meaningless.
q-values not monotone → you assigned `D/T` directly instead of sweeping a running minimum from
the bottom of the score-sorted list. Criterion 6 shows no change → your peak filter is
computing a filtered list and then matching against the unfiltered one. Wrong peptide wins →
digest bug: print the digest of one protein and check that cleavage is *after* K/R, not before.

## Optional

ppm precursor tolerance; fixed carbamidomethyl-C (+57.021464) and variable oxidised M; one or
two missed cleavages; 2+ fragment charges when the precursor charge is ≥ 3; a hyperscore
(`log(N_b! · N_y! · ΣI_b · ΣI_y)`) in place of the plain count; protein-level rollup with its
own FDR. On the real PXD001819 data, peak filtering plus a hyperscore cut the decoy fraction
from 40.2% to 26.0% and raised the 1%-FDR yield from 1 PSM to 54 — worth having, but far less
than what the q-value itself buys you.
