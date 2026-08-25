# Task: Build a Minimal DDA Database Search Engine (Python, standard library only)

You are a coding agent. Build a **minimal but working** shotgun-proteomics DDA (data-dependent acquisition) database search engine in a single Python file `search.py`. It reads a protein FASTA file and an mzML file, identifies which peptide produced each MS/MS spectrum, and writes the results to a TSV file.

**Hard constraint:** use only the Python standard library (`csv`/`argparse`, `math`, etc.). Do **not** use `pyteomics`, `pymzml`, `numpy`, or any third-party package. All file parsing is already solved: this program **imports** `read_fasta` and `read_mzml` from the readers built in the MSTool task.

---

## Background (what a DDA search engine does)

1. Read protein sequences from a FASTA file.
2. Digest each protein **in silico** with trypsin into peptides.
3. For every peptide, compute its theoretical precursor mass and its theoretical b/y fragment-ion m/z values.
4. Read MS/MS spectra from an mzML file. Each MS/MS spectrum has a **precursor m/z**, a **charge state**, and a peak list (m/z + intensity arrays).
5. For each spectrum, find candidate peptides whose precursor mass matches the measured precursor m/z within a tolerance, then score each candidate by how many of its theoretical fragment ions appear in the measured peak list.
6. Report the best-scoring peptide per spectrum as a PSM (peptide-spectrum match).
7. Estimate confidence with a **target-decoy** strategy: append reversed protein sequences as decoys; a PSM matched to a decoy protein is a false match.

---

## Step 1 — Load the protein database

**Prerequisite:** you have already built `fasta_reader.py` and `mzml_reader.py` in the MSTool reader task. Use `read_fasta("mini.fasta")` → `[(record_id, sequence), ...]`; do **not** re-implement FASTA parsing here.

Test file `mini.fasta` (create it exactly like this):

```fasta
>sp|P00001|MINI1 Mini protein 1
MKTAYIAKQRQISFVKSHFSRQDILDLWQNLTTGPGR
>sp|P00002|MINI2 Mini protein 2
MAGDRSPGTWEQLKDAVEILRQNYVGAFW
```

`read_fasta` must return `[("sp|P00001|MINI1", "MKTAYIAKQRQISFVKSHFSRQDILDLWQNLTTGPGR"), ("sp|P00002|MINI2", "MAGDRSPGTWEQLKDAVEILRQNYVGAFW")]` (the reader already takes the first whitespace-delimited token of the header as the protein ID).

## Step 2 — In-silico tryptic digest

Trypsin cleaves **after** every `K` or `R`, **unless** the next residue is `P`. The cleaved peptide keeps the K/R at its C-terminus. Also generate decoy proteins first: for every target protein, add a decoy whose ID is prefixed `DECOY_` and whose sequence is the **reversed** target sequence, then digest targets and decoys together.

For the test data, the target digests must be exactly:

- `sp|P00001|MINI1` → `MK, TAYIAK, QR, QISFVK, SHFSR, QDILDLWQNLTTGPGR`
- `sp|P00002|MINI2` → `MAGDR, SPGTWEQLK, DAVEILR, QNYVGAFW`

Keep only peptides of length ≥ 5 as search candidates.

## Step 3 — Theoretical masses and fragment ions

Monoisotopic residue masses (use exactly these values):

| AA | mass | AA | mass |
|----|----------|----|----------|
| A | 71.03711 | L | 113.08406 |
| R | 156.10111 | K | 128.09496 |
| N | 114.04293 | M | 131.04049 |
| D | 115.02694 | F | 147.06841 |
| C | 103.00919 | P | 97.05276 |
| E | 129.04259 | S | 87.03203 |
| Q | 128.05858 | T | 101.04768 |
| G | 57.02146 | W | 186.07931 |
| H | 137.05891 | Y | 163.06333 |
| I | 113.08406 | V | 99.06841 |

Constants: `H2O = 18.01056`, `PROTON = 1.007276`.

- Peptide neutral mass = sum(residue masses) + H2O. Example: `QISFVK` → 720.417 Da.
- Precursor m/z for charge z = (neutral mass + z × PROTON) / z. Example: `QISFVK`, z=2 → 361.2158.
- **b-ion** for the prefix of length i: sum(first i residue masses) + PROTON (singly charged).
- **y-ion** for the suffix of length j: sum(last j residue masses) + H2O + PROTON (singly charged).
- Generate b1..b(n-1) and y1..y(n-1) for each candidate peptide (an n-residue peptide yields 2(n−1) fragments).

## Step 4 — Load the MS/MS spectra

Use `read_mzml("mini.mzml")` from the MSTool reader task — do **not** re-implement mzML parsing here. It returns a list of dicts with keys `id, ms_level, rt, precursor_mz, precursor_charge, mz, intensity`. Keep only spectra with `ms_level == 2`; `precursor_mz` / `precursor_charge` are what you match candidate peptides against, and `mz` / `intensity` are the measured fragment peak lists.

Test file `mini.mzml` (create it exactly like this; it contains two MS/MS spectra, `scan=1` and `scan=2`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0">
  <run id="mini_run">
    <spectrumList count="2">
      <spectrum index="0" id="scan=1" defaultArrayLength="25">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="2"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="101.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <precursorList count="1">
          <precursor>
            <selectedIonList count="1">
              <selectedIon>
                <cvParam cvRef="MS" accession="MS:1000744" name="selected ion m/z" value="361.2158" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
                <cvParam cvRef="MS" accession="MS:1000041" name="charge state" value="2"/>
              </selectedIon>
            </selectedIonList>
          </precursor>
        </precursorList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>VTAqqRMiYEBdbcX+ssNhQGiz6nO1Y2JAJuSDns1EbkCrz9VW7MVuQBe30QDeB3RAy6FFtvOSdEA4+MJkquR2QL6fGi/dk3hAdnEbDeDDfUBsCfmgZwR+QCSX/5B+in9Anzws1BrrgEAN4C2QoPqBQE7RkVz+ioJAcoqO5PJlhkC+MJkqGCKHQFOWIY51/YhAKe0NvjDWiUBwzojS3j2KQMHKoUU2U5JAuycPCzXxk0DZX3ZP3hSUQGlv8IUJhZZAio7k8t9il0A=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>AAAAAACWt0DNzMzMzCxwQJqZmZmZjLlAAAAAAICOuECamZmZmYOVQGZmZmZmZkxAzczMzMzIv0DNzMzMzNxjQDMzMzMzJa1AZmZmZmYvwEAzMzMzM+e1QGZmZmZmZlRAmpmZmZkpY0BmZmZmZunCQGZmZmbmRrRAmpmZmZnRekBmZmZmZuZlQJqZmZmZwXVAmpmZmZkhdUAzMzMzMzNTQGZmZmZmxmxAAAAAAAAId0DNzMzMzPxrQM3MzMzM9HpAmpmZmZkhf0A=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="1" id="scan=2" defaultArrayLength="31">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="2"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="102.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <precursorList count="1">
          <precursor>
            <selectedIonList count="1">
              <selectedIon>
                <cvParam cvRef="MS" accession="MS:1000744" name="selected ion m/z" value="523.2693" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
                <cvParam cvRef="MS" accession="MS:1000041" name="charge state" value="2"/>
              </selectedIon>
            </selectedIonList>
          </precursor>
        </precursorList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>yXa+nxoDVkCWIY51cSViQPp+arx0Y2JAf/s6cM4YZUDmP6TfviJnQE8eFmpN62tAJ6CJsOFDbkBKe4MvTENwQCbkg57NsXJAUWuad5xydUCHp1fKMkR4QLFQa5r3IYBAGXPXEnIqgECmCkYl9YmAQCntDb6wy4BAS1mGONavgkDiWBe3UXqDQC9uowE8koRAmG4Sg8AJhUA1XrpJDPuFQCbkg57NkohAY3/ZPXkjiUAcfGEyVUaJQEhQ/Bjz4opAarx0k5jrikC7uI0GcBuMQM9m1efq841AGsBbIAEqkEA8vVKWIUqQQARWDi0ynJVAtoR80PNxlkA=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>mpmZmZmuoUDNzMzMzCR9QAAAAABAxcJAzczMzMwUckCamZmZmUqgQGZmZmZmJn9AZmZmZmYbqEDNzMzMzNC3QGZmZmZmVnpAZmZmZmZWwkBmZmZmZmW4QAAAAAAA4HNAAAAAAACiuEAAAAAAAHCWQAAAAAAAGHlAmpmZmZmJbkAzMzMzM4NzQGZmZmZmLqVAZmZmZma2dUDNzMzMTDHCQJqZmZmZHb9AMzMzMzNGrkDNzMzMzKxxQDMzMzMzo25AzczMzMwOsEBmZmZm5m65QJqZmZnZgcNAmpmZmZmpYEAzMzMzM/txQJqZmZmZiWdAZmZmZmZudUA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
    </spectrumList>
  </run>
</mzML>
```

Sanity checks for your reader: `scan=1` must decode to 25 peaks with precursor m/z 361.2158, charge 2; `scan=2` to 31 peaks with precursor m/z 523.2693, charge 2. m/z arrays are sorted ascending.

## Step 5 — Match and score

For each MS/MS spectrum:

1. **Candidate selection**: keep candidate peptides where `abs(theoretical_precursor_mz − measured_precursor_mz) ≤ 0.02 Da` (compute the theoretical m/z at the spectrum's charge state).
2. **Fragment matching**: a theoretical fragment m/z matches the spectrum if any measured peak is within **±0.5 Da** of it.
3. **Score** = number of matched b/y fragments. Tie-break: higher summed intensity of matched peaks wins.
4. Report the best candidate as the PSM, with a column `decoy` = 1 if the protein ID starts with `DECOY_`, else 0.

## Step 6 — Output

CLI: `python3 search.py mini.fasta mini.mzml -o psms.tsv`

Write a TSV with header:

```
scan	precursor_mz	charge	peptide	protein	decoy	matched_fragments	total_fragments	score
```

(one row per MS/MS spectrum; `score` = matched_fragments, kept as a separate column so the scoring function can be upgraded later.)

---

## How to test (acceptance criteria)

Run the exact command above against the two embedded files. **All** of these must hold:

1. The program runs with no third-party packages and no errors.
2. `psms.tsv` has exactly 2 PSM rows.
3. `scan=1` → peptide `QISFVK`, protein `sp|P00001|MINI1`, `decoy=0`, `matched_fragments=10`, `total_fragments=10`.
4. `scan=2` → peptide `SPGTWEQLK`, protein `sp|P00002|MINI2`, `decoy=0`, `matched_fragments=16`, `total_fragments=16`.
5. The decoy database was actually searched: print (to stdout) the total candidate counts, which must be 8 target candidates and 8 decoy candidates for this data.

Note on criterion 5: the correct answers come out as targets only if target scores beat decoy scores; verify this by also printing the best decoy hit per spectrum for inspection.

## If a test fails — debugging checklist

Work through these in order; fix the first thing that is wrong, then re-run:

1. **0 spectra found or wrong peak counts (not 25 / 31)** → the bug is in `mzml_reader.py`, not here. Go back to the MSTool reader task acceptance criteria and fix the reader; do not patch parsing inside `search.py`.
2. **No candidates pass the precursor filter** → mass bug. Print your computed precursor m/z for `QISFVK` at z=2; it must be ≈ 361.2158 within 0.02. Common causes: forgot +H2O on the neutral mass, used average instead of monoisotopic masses, or a typo in the mass table (check I/L = 113.08406, K = 128.09496, Q = 128.05858).
3. **Wrong peptide wins** → digest bug. Print the digest of both proteins and compare against the exact lists in Step 2. Common causes: splitting before K/R instead of after, or mis-handling the `P` exception (no KP/RP occurs in this data, but implement the rule anyway).
4. **Right peptide, wrong fragment count** → b/y formula bug. b-ion = prefix sum + PROTON (no H2O); y-ion = suffix sum + H2O + PROTON. With ±0.5 Da tolerance and this clean data, the true peptide must match all 2(n−1) fragments; print unmatched theoretical m/z values to see which series is off.
5. **Decoy count is 0** → you reversed but forgot to digest the decoy proteins, or you filtered them out when reporting.

## Optional stretch goals (only after all acceptance criteria pass)

- Precursor tolerance in ppm instead of Da.
- Charge-state fragment matching (consider 2+ fragments when precursor charge ≥ 3).
- Simple q-value: sort PSMs by score descending, q = (#decoys so far) / (#targets so far).
- An `assert`-based `test_search.py` that runs the acceptance criteria automatically.
