# Task: Build Minimal mzML and FASTA Readers (Python, standard library only)

You are a coding agent. Build two small, correct file readers in Python:

1. `mzml_reader.py` — reads an mzML mass-spectrometry file into a list of spectra.
2. `fasta_reader.py` — reads a protein FASTA file into a list of (id, sequence) records.

**Hard constraint:** use only the Python standard library (`xml.etree.ElementTree`, `base64`, `struct`, `zlib`, `argparse`). Do **not** use `pyteomics`, `pymzml`, `numpy`, or any third-party package. Everything you need to parse both formats is specified below.

---

## Role in the mini-tool series

This is the **foundation task** of a five-part series. The downstream tasks — MS1 feature detection (MSFeature), DDA database search (MSSearch), differential stats (MSStats), and the combined analysis pipeline — all **import `read_mzml` / `read_fasta` from these two files** instead of re-parsing anything. Keep the two function signatures and return formats exactly as specified below; the other tasks depend on them.

---

## Part 1 — FASTA reader

FASTA format: a header line starting with `>`, followed by one or more sequence lines (uppercase letters). Concatenate sequence lines until the next header. Use the first whitespace-delimited token of the header as the record ID.

Required API in `fasta_reader.py`:

```python
def read_fasta(path: str) -> list[tuple[str, str]]:
    """Return [(record_id, sequence), ...] in file order."""
```

Test file `mini.fasta` (create it exactly like this):

```fasta
>sp|P00001|MINI1 Mini protein 1
MKTAYIAKQRQISFVKSHFSRQDILDLWQNLTTGPGR
>sp|P00002|MINI2 Mini protein 2
MAGDRSPGTWEQLKDAVEILRQNYVGAFW
```

Expected result: `[("sp|P00001|MINI1", "MKTAYIAKQRQISFVKSHFSRQDILDLWQNLTTGPGR"), ("sp|P00002|MINI2", "MAGDRSPGTWEQLKDAVEILRQNYVGAFW")]`.

Also handle these edge cases correctly (add them to your own test file to verify): blank lines between records, sequences wrapped over multiple lines, and lowercase letters (convert to uppercase).

## Part 2 — mzML reader

mzML is an XML format standardised by HUPO-PSI (schema: `http://psi.hupo.org/ms/mzml`; the controlled-vocabulary accessions below are from the PSI-MS CV, https://raw.githubusercontent.com/HUPO-PSI/psi-ms-CV/master/psi-ms.obo). Parse it with `xml.etree.ElementTree`. The file uses a default XML namespace — either iterate with the qualified tag name `{http://psi.hupo.org/ms/mzml}spectrum` or strip namespaces before searching.

For each `<spectrum>` element, extract:

- **id**: the `id` attribute (e.g. `scan=1`).
- **ms_level**: cvParam `MS:1000511` (`"1"` = MS1 survey scan, `"2"` = MS/MS scan).
- **rt**: retention time in seconds — cvParam `MS:1000016` ("scan start time") inside `scanList/scan`.
- **precursor_mz / precursor_charge** (MS2 only): inside `precursorList/precursor/selectedIonList/selectedIon`, cvParams `MS:1000744` ("selected ion m/z") and `MS:1000041` ("charge state"). Set to `None` for MS1 spectra.
- **mz / intensity arrays**: inside `binaryDataArrayList`, each `<binaryDataArray>` is one array. cvParam `MS:1000514` marks the m/z array, `MS:1000515` the intensity array. The `<binary>` text is **base64-encoded binary**:
  - cvParam `MS:1000523` = 64-bit float, `MS:1000521` = 32-bit float. Decode with `base64.b64decode` then `struct.unpack('<%dd' % n, raw)` for 64-bit (little-endian; use `<%df` for 32-bit).
  - cvParam `MS:1000576` = no compression, `MS:1000574` = zlib compression (call `zlib.decompress` on the decoded bytes first). The test data uses no compression, but check the accession so your reader is correct in general.
  - The two arrays are parallel: `mz[i]` pairs with `intensity[i]`.

Required API in `mzml_reader.py`:

```python
def read_mzml(path: str) -> list[dict]:
    """Return one dict per spectrum with keys:
    id, ms_level, rt, precursor_mz, precursor_charge, mz (list[float]), intensity (list[float]).
    """
```

Test file `mini.mzml` (create it exactly like this; two MS/MS spectra):

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

## Part 3 — Demo CLI

Add a `main` to each reader (or a shared `demo.py`) so these commands print a short human-readable summary:

```
python3 fasta_reader.py mini.fasta
python3 mzml_reader.py mini.mzml
```

Example expected summary for the mzML file: 2 spectra, both MS2, with per-spectrum id, RT, precursor m/z, charge, and peak count.

---

## How to test (acceptance criteria)

All of these must hold:

1. Both readers run with no third-party packages and no errors.
2. `read_fasta("mini.fasta")` returns exactly 2 records with the IDs and sequences listed in Part 1; the multi-line/blank-line/lowercase edge cases also parse correctly.
3. `read_mzml("mini.mzml")` returns exactly 2 spectra.
4. `scan=1`: `ms_level=2`, `rt=101.0`, `precursor_mz=361.2158`, `precursor_charge=2`, **25 peaks**, first m/z ≈ 129.0649, last m/z ≈ 1496.7187, max intensity ≈ 9682.8, intensity sum ≈ 64705.3.
5. `scan=2`: `ms_level=2`, `rt=102.0`, `precursor_mz=523.2693`, `precursor_charge=2`, **31 peaks**, first m/z ≈ 88.0485, last m/z ≈ 1436.4881, max intensity ≈ 9987.7, intensity sum ≈ 95772.6.
6. In every spectrum the m/z array is sorted ascending and `len(mz) == len(intensity)`.

## If a test fails — debugging checklist

Work through these in order; fix the first thing that is wrong, then re-run:

1. **0 spectra found** → XML namespace bug. Use `{http://psi.hupo.org/ms/mzml}`-qualified tags or strip namespaces before searching.
2. **Wrong peak counts (not 25 / 31)** → base64/struct decoding bug. Format string must be little-endian `'<%dd' % n` with `n = len(raw_bytes) // 8`. Print the first 3 decoded m/z values and check they are ascending.
3. **Values garbled but count right** → wrong float width (`<df` vs `<%dd`) or big-endian format character. mzML binary is always little-endian.
4. **precursor fields are None** → you searched for the cvParams at the wrong XML depth; they live under `precursorList/precursor/selectedIonList/selectedIon`, not directly under `spectrum`.
5. **rt is None or a string** → cvParam `MS:1000016` sits inside `scanList/scan`; convert the `value` attribute (always a string in XML) with `float()`.
6. **FASTA sequence contains header text or spaces** → strip each line, skip blank lines, and treat only lines starting with `>` as headers; take `header[1:].split()[0]` as the ID.

## Optional stretch goals (only after all acceptance criteria pass)

- A generator-based `iter_mzml(path)` that yields spectra one at a time using `xml.etree.ElementTree.iterparse` (streaming, constant memory).
- Support zlib-compressed arrays and verify against a file you compress yourself.
- `read_fasta` support for a `DECOY_` prefix helper that returns reversed sequences.
