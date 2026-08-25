# Task: Build a Minimal MS1 Feature Extraction Program (Python, standard library only)

You are a coding agent. Build a **minimal but working** mass-spectrometry MS1 feature detection program in a single Python file `features.py`. It reads an mzML file containing a series of MS1 scans from an LC-MS run, groups peaks into chromatographic traces, detects chromatographic peaks, groups isotope envelopes, determines charge states, and writes the detected features to a TSV file.

**Hard constraint:** use only the Python standard library (`argparse`, `math`, etc.). Do **not** use `pyteomics`, `pymzml`, `numpy`, `scipy`, or any third-party package. mzML parsing is already solved: this program **imports** `read_mzml` from the reader built in the MSTool task.

---

## Background (what MS1 feature extraction does)

In an LC-MS run, the mass spectrometer records one MS1 spectrum every ~1 second while peptides elute from the chromatography column. A single analyte (a "feature") appears as:

- a peak at roughly the **same m/z** in many consecutive scans, rising and falling in intensity over time — an **extracted-ion chromatogram (EIC)** with a chromatographic peak shape;
- a set of **isotope peaks** (M, M+1, M+2, ...) separated by `1.003355 / z` Da, where `z` is the charge state and 1.003355 Da is the neutron mass (¹³C−¹²C difference).

Feature detection = (1) connect peaks across scans into m/z traces, (2) find the chromatographic peak (apex, boundaries, area) in each trace, (3) group traces that form an isotope envelope and infer the charge. The output is a list of features: monoisotopic m/z, charge, retention time, and intensity (area).

---

## Step 1 — Load the MS1 scans

**Prerequisite:** you have already built `mzml_reader.py` in the MSTool reader task. Use `read_mzml("mini_ms1.mzml")` → a list of dicts with keys `id, ms_level, rt, precursor_mz, precursor_charge, mz, intensity`. Keep only spectra with `ms_level == 1`; each one is a single scan of the LC run with its retention time `rt` (seconds) and a centroided peak list (`mz` / `intensity`). Do **not** re-implement mzML parsing here — if parsing looks wrong, fix the reader, not this program.

Test file `mini_ms1.mzml` (create it exactly like this): 24 MS1 scans, RT 60.0–83.0 s in 1.0 s steps. It contains **two analytes** with Gaussian elution profiles plus low-intensity random noise peaks in every scan:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0">
  <run id="mini_ms1_run">
    <spectrumList count="24">
      <spectrum index="0" id="scan=1" defaultArrayLength="10">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="60.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>5BQdyeVPbUA9m1Wfq0N+QGEyVTAqaX5Aw2SqYFREf0DTTWIQWFR/QNJvXwdObIFAnKIjufxjh0CQoPgxZlOQQFJJnYCmFZJA8kHPZlU/lUA=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>zczMzMzsWECamZmZmQlmQJqZmZmZqWhAZmZmZmaKgUAAAAAAABBsQDMzMzMzc1pAMzMzMzOzTEBmZmZmZkZnQGZmZmZmZmtAzczMzMzsUUA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="1" id="scan=2" defaultArrayLength="10">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="61.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>07zjFB0JdEDOqs/VVkR/QCfChqdXVH9AdQKaCJsShEBz1xLywaCFQIPAyqHFCIxA9ihcj0J+k0BL6gQ0EYWTQPVKWYb4VpRAXrpJDIKRlkA=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>zczMzMyMUkCamZmZmSWVQGZmZmZm6oBAmpmZmZk5VkAAAAAAAIBnQM3MzMzMVHJAAAAAAAAQbEDNzMzMzAxtQM3MzMzMHGlAMzMzMzPDYEA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="2" id="scan=3" defaultArrayLength="10">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="62.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>lrIMcaz7ckCZKhiV1LR0QOcdp+hIBH9AejarPldEf0BR2ht8YVR/QM07TtGRGIFA/mX35OFJhUDsL7snjwmQQDBMpgrGb5FATDeJQeCglEA=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>zczMzMwMW0AAAAAAAOBdQDMzMzMzk15AzczMzMy4pUBmZmZmZmCRQDMzMzMzw3FAmpmZmZmZWUBmZmZmZqZhQAAAAAAAwE5AmpmZmZlJaEA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="3" id="scan=4" defaultArrayLength="10">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="63.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>rfpcbcXGeUCh+DHmrmd6QJYhjnVxpH1AMzMzMzMcf0DDZKpgVER/QFHaG3xhVH9AwcqhRbYQg0BfKcsQR+CMQK5H4XrUPpRAmN2Th4U5l0A=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>zczMzMwcYkCamZmZmQltQDMzMzMz23FAAAAAAAAATUAAAAAAgAOzQAAAAAAAbJ5AmpmZmZk5XUBmZmZmZqZrQAAAAAAAgG5AAAAAAABAakA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="4" id="scan=5" defaultArrayLength="10">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="64.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>TRWMSuric0DTTWIQWER/QDxO0ZFcVH9ARPrt68ACgUDRkVz+w3mGQFMFo5I6Do1AWMoyxLH/jUCjI7n8R3CQQOQUHcmls5VAGXPXEjJjl0A=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>ZmZmZmbmTkAAAAAAgF28QDMzMzMzsaZAzczMzMzsW0AzMzMzMzNaQM3MzMzM7FxAAAAAAAAocUDNzMzMzJxiQGZmZmZmlmRAzczMzMwsZkA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="5" id="scan=6" defaultArrayLength="10">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="65.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>pN++DpzdakBMN4lBYKlxQOcdp+hIkHVA8WPMXUtEf0D+ZffkYVR/QME5I0r7FoFAoBov3eT4kEAwKqkT0DaTQA1xrIub2ZZAb/CFydRbl0A=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>ZmZmZmbGbEDNzMzMzCxiQGZmZmZm1mNAmpmZmZkHwkAAAAAAANmsQGZmZmZmRmpAZmZmZmYGZ0AAAAAAAHBjQDMzMzMzk3BAmpmZmZnJZkA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="6" id="scan=7" defaultArrayLength="10">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="66.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>bxKDwMoXaUBfB84ZUUR/QL99HThnVH9AlIeFWtNfgkCU9gZfGJaKQMKGp1dK/Y5AkxgEVg6dkkANcayL2/CSQDhnRGlv6pRAYTJVMKqplUA=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>AAAAAABgYEAAAAAAAIjDQAAAAAAAQK9AZmZmZmY2akDNzMzMzKxXQM3MzMzMDFZAmpmZmZkZZ0AzMzMzM9NmQDMzMzMz81xAmpmZmZm5cEA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="7" id="scan=8" defaultArrayLength="10">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="67.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>W7G/7J4fckA730+Nl3VzQOzAOSNKRH9AE/JBz2ZUf0Djx5i7lgSBQPkx5q4lvoJA5fIf0u+OiUDOqs/VVq6SQGZmZmam9ZRA3pOHhVr5lEA=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>ZmZmZmYGbkAAAAAAAHBlQJqZmZmZB8JAAAAAAADZrECamZmZmcFwQAAAAAAAIFBAAAAAAABwZ0BmZmZmZoZUQDMzMzMz63FAZmZmZmYecEA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="8" id="scan=9" defaultArrayLength="10">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="68.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>LbKd76dEckDZzvdT41R2QMBbIEHx13xAAwmKH2Myf0Cze/KwUER/QIofY+5aVH9AuY0G8Bb8g0DgnBGlPQyIQHEbDeCtKIxAiGNd3MZWl0A=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>mpmZmZn5aUDNzMzMzIxaQJqZmZmZ+V9AZmZmZmZGWkAAAAAAgF28QDMzMzMzsaZAMzMzMzOjaEDNzMzMzGxmQAAAAAAAEG1AAAAAAACQakA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="9" id="scan=10" defaultArrayLength="12">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="69.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>CRueXilgdEC2hHzQszN8QEjhehSuO3xAio7k8h/ofUBPHhZqTUR/QGZmZmZmVH9A0SLb+X7Wf0CcM6K0N3WHQDXvOEXHc4lAWMoyxDHvkUAvbqMB/IaTQIGVQ4usIJZA</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>mpmZmZm5Y0BmZmZmZtZjQM3MzMzMzFdAZmZmZmbGVEAAAAAAgAOzQAAAAAAAbJ5AZmZmZmYma0CamZmZmdlkQGZmZmZmxm5AmpmZmZlJa0BmZmZmZmZYQJqZmZmZGWhA</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="10" id="scan=11" defaultArrayLength="13">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="70.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>sb/snjyccECWsgxxrDN8QARWDi2yO3xAnRGlvcFDfECFfNCzWUR/QCxlGeJYVH9Ax7q4jQZagECaCBue3pCBQIQNT6+UeYhA6Gor9lcblEDmriXkA5+UQNZW7C/74JVA4zYawBvxlUA=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>zczMzMy8ckCamZmZmRF8QGZmZmZm1nBAMzMzMzNzVkDNzMzMzLilQGZmZmZmYJFAZmZmZmZmWEAAAAAAACBcQAAAAAAAcGNAMzMzMzNDckAzMzMzM3NnQJqZmZmZGWRAMzMzMzNjcEA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="11" id="scan=12" defaultArrayLength="13">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="71.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>BhIUP8YTeUDf4AuTqTN8QAn5oGezO3xAD5wzorRDfED3Bl+YTER/QPMf0m9fVH9AJzEIrBwGgUCP5PIfUqWFQDY8vVIWvIhAmSoYldRGjED1udqK/dOMQHlYqDUNkpZAFvvL7knNlkA=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>zczMzMwMX0DNzMzMzOqQQM3MzMzMTIRAAAAAAAAQa0CamZmZmSWVQGZmZmZm6oBAAAAAAADAbkDNzMzMzIRyQJqZmZmZeWNAAAAAAACgbUAzMzMzM7NsQGZmZmZmrnJAmpmZmZlZaEA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="12" id="scan=13" defaultArrayLength="13">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="72.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>HcnlP6Q9dkCwA+eMKJl7QEjhehSuM3xAKcsQx7o7fEDByqFFtkN8QJhMFYxKRH9ApU5AE2FUf0BxPQrXo0CAQNV46SYx9o1AIbByaJFpj0CKH2PuGteQQKHWNO94HJZAuK8D5wyklkA=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>mpmZmZkJcUCamZmZmdloQJqZmZmZYKFAZmZmZmbalEBmZmZmZs57QGZmZmZmioFAAAAAAAAQbEAzMzMzM9NoQGZmZmZmlmZAmpmZmZlZY0AzMzMzMzNbQGZmZmZmRllAAAAAAACAUUA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="13" id="scan=14" defaultArrayLength="13">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="73.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>N4lBYOVkckA7cM6I0nNyQJayDHGsM3xAcvkP6bc7fEDLEMe6uEN8QMgHPZtVRH9ANqs+V1tUf0DdJAaBFQaBQGPuWkI+GINAW9O84xRDhUBjf9k9eQ+UQE7RkVx+BJVAgnNGlPZnl0A=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>MzMzMzOTZEAzMzMzM9NZQAAAAAAAbK5AzczMzMxAokBmZmZmZlaIQM3MzMzMzGhAmpmZmZnZU0DNzMzMzLRxQAAAAAAAwG1AmpmZmZlZVkDNzMzMzDxsQM3MzMzM3HBAAAAAAACwckA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="14" id="scan=15" defaultArrayLength="12">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="74.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>2PD0SlkydUAawFsgQWl3QBQ/xty1M3xAxm00gLc7fEC2hHzQs0N8QGpN845TRH9A/kP67WtQgUDWVuwvuxiKQGlv8IUJApBARpT2Bp+ZkEAHX5hMlbORQOqVsgzxuJNA</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>mpmZmZmJZ0CamZmZmblTQDMzMzMzsbZAAAAAAAA7q0AzMzMzMyeSQGZmZmZm5k1AZmZmZmYmaUDNzMzMzERxQAAAAAAAAF1AMzMzMzPLcUCamZmZmTlZQDMzMzMzM19A</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="15" id="scan=16" defaultArrayLength="11">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="75.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>IGPuWkKSakC2hHzQszN8QEjhehSuO3xAfT81XrpDfEDIBz2bVeSAQDlFR3J5fYFAmnecoiNqjEDl0CLbeamMQMPTK2UZ6o1AuB6F69HJkkC/fR04JxCVQA==</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>MzMzMzMzUUBmZmZm5ti8QAAAAAAAT7FAAAAAAAAUl0CamZmZmWltQDMzMzMzc0lAmpmZmZkpcEDNzMzMzJxjQAAAAAAAwFVAmpmZmZkpakAAAAAAAEBxQA==</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="16" id="scan=17" defaultArrayLength="11">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="76.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>aLPqc7UOeUAtsp3vpzN8QFjKMsSxO3xA9ihcj8JDfECk374OHGOAQL7BFyZTwoZAtFn1uZr4kkB1kxgE1kuTQGRd3EYDmJNASFD8GPOvlEDFILByaGKVQA==</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>AAAAAACocUAAAAAAAEC/QAAAAAAAwLJAAAAAAAAAmUDNzMzMzOxSQGZmZmZmpmlAAAAAAADwcEAzMzMzM5NwQGZmZmZm5nBAmpmZmZlhckAAAAAAAKBZQA==</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="17" id="scan=18" defaultArrayLength="11">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="77.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>r5RliGNIdUB7gy9MpjN8QMsQx7q4O3xAeJyiI7lDfEDwFkhQ/P1+QAu1pnnHFoFAGlHaG/ylgkDr4jYaQLaTQE2EDU+vkJRA6Ugu/yGtlEB4CyQoPgiWQA==</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>AAAAAADAcEBmZmZm5ti8QAAAAAAAT7FAAAAAAAAUl0AzMzMzM/NLQJqZmZmZ2W5AmpmZmZkZb0AzMzMzM6NkQGZmZmZmZlpAZmZmZmaWb0AzMzMzM1NvQA==</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="18" id="scan=19" defaultArrayLength="11">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="78.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>WYY41sVOdUAyVTAqqTN8QARWDi2yO3xAnRGlvcFDfEAkufyHtCeQQGKh1jRv7JFAOpLLfwg0lkCbVZ+rLa2WQBE2PL3Sw5ZAB1+YTBXWlkBoImx4+g2XQA==</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>MzMzMzPTY0AzMzMzM7G2QAAAAAAAO6tAMzMzMzMnkkDNzMzMzLxiQM3MzMzMDGBAMzMzMzOzU0CamZmZmRldQDMzMzMz811AZmZmZmamV0AzMzMzMwNnQA==</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="19" id="scan=20" defaultArrayLength="11">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="79.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>+n5qvHQvckD5D+m3rzN8QLsnDwu1O3xA0LNZ9blDfECuR+F6FKqDQLx0kxiErI1AP8bctUS/kECM22gAr4WRQKjGSzcJvZFAXf5D+q1ZlEDgnBGl/eyVQA==</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>MzMzMzMDa0AAAAAAAGyuQM3MzMzMQKJAZmZmZmZWiEAAAAAAABBgQM3MzMzMbFxAMzMzMzOjYUAzMzMzMzNJQAAAAAAAcG1AzczMzMy8bEAzMzMzMxNnQA==</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="20" id="scan=21" defaultArrayLength="11">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="80.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>LUMc6+IQaUCKsOHpldd2QOSDns2qM3xAWMoyxLE7fEB9PzVeukN8QM6I0t7geYJAWDm0yPaYhkBLWYY41raHQEi/fR14bJBA48eYu5Z2lUAy5q4l5DmWQA==</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>zczMzMxsXkAzMzMzM2NjQJqZmZmZYKFAZmZmZmbalEBmZmZmZs57QAAAAAAAYGdAmpmZmZn5XkAAAAAAAGBoQGZmZmZmxmRAzczMzMx8aUCamZmZmWlrQA==</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="21" id="scan=22" defaultArrayLength="11">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="81.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>arx0kxj4bECEDU+vlEl6QO/Jw0KtM3xAppvEILA7fEDWVuwvu0N8QJ2AJsKGwH5ApgpGJfXdg0DPZtXnao2JQAn5oGezMItApSxDHOthkkBcIEHxI26VQA==</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>zczMzMzMW0DNzMzMzMxRQM3MzMzM6pBAzczMzMxMhEAAAAAAABBrQDMzMzMz81hAMzMzMzPTb0BmZmZmZmZwQGZmZmZmBmpAZmZmZmZGa0AAAAAAACBvQA==</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="22" id="scan=23" defaultArrayLength="11">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="82.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>vHSTGAQpdUCWIY51ccp6QNSa5h2nM3xACfmgZ7M7fECNKO0NvkN8QG40gLdATHxA3+ALk6lfgEBuowG8hVWKQMzuycPCSotArIvbaIBzkEDmriXkA2GSQA==</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>mpmZmZmJY0AAAAAAABhyQJqZmZmZEXxAZmZmZmbWcEAzMzMzM3NWQDMzMzMzA2xAmpmZmZlhcEAAAAAAAMBbQM3MzMzMTE9AMzMzMzOzSUAAAAAAAFBuQA==</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
      <spectrum index="23" id="scan=24" defaultArrayLength="10">
        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="83.0" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000514" name="m/z array" value="" unitCvRef="MS" unitAccession="MS:1000040" unitName="m/z"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>78nDQq0zfEDQs1n1uTt8QBueXilLS4BAqoJRSZ2IiUBiEFg5tHCOQIEmwoZnr5BAOUVHcjm8kUA+eVio9f6TQGEyVTBqO5VArBxaZHtZlUA=</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value="" unitCvRef="MS" unitAccession="MS:1000105" unitName="number of detector counts"/>
            <cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>
            <cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>
            <binary>ZmZmZmbWY0DNzMzMzMxXQM3MzMzMLGpAMzMzMzOzXEAAAAAAAPhxQAAAAAAAkHJAZmZmZmYGZkAAAAAAAGBnQGZmZmZmZmlAzczMzMx8bUA=</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
    </spectrumList>
  </run>
</mzML>
```

Sanity checks for your reader: exactly **24 MS1 scans**; scan 1 has RT 60.0 s and 10 peaks; scan 24 has RT 83.0 s; m/z arrays are sorted ascending.

## Step 2 — Collect peaks above the noise threshold

From every MS1 scan, keep only peaks with **intensity ≥ 500** (the noise in this data stays below 300). Collect them as tuples `(mz, scan_index, rt, intensity)`. Sanity check: you must collect exactly **53 peaks** from this file.

## Step 3 — Cluster peaks into m/z traces (EICs)

1. Sort all collected peaks by m/z.
2. Greedily assign each peak to an existing trace if `abs(peak_mz − trace_mean_mz) ≤ 0.01` **and** the trace does not already contain a peak from the same scan; otherwise start a new trace. Update the trace mean as you add peaks.
3. Keep only traces with peaks in **≥ 5 distinct scans**.

Sanity check: you must get exactly **5 traces**.

## Step 4 — Chromatographic peak shape per trace

For each trace (points sorted by scan index):

- **Apex**: the point with maximum intensity.
- **Boundaries**: walk left and right from the apex; stop extending when the next point's intensity is < 5% of the apex intensity or the scan indices are not consecutive (gap in the trace).
- **m/z**: intensity-weighted mean of the peak m/z values in the trace.
- **Area**: trapezoid integration of intensity over RT between the boundaries: `sum((rt[i+1]−rt[i]) × (int[i]+int[i+1]) / 2)`.

Sanity check (values from a reference implementation):

| trace m/z | apex RT | RT start | RT end | area |
|-----------|---------|----------|--------|------|
| 451.2297 | 76.0 | 71.0 | 81.0 | ≈ 47708 |
| 451.7315 | 76.0 | 71.0 | 81.0 | ≈ 28625 |
| 452.2333 | 76.0 | 73.0 | 79.0 | ≈ 7656 |
| 500.2697 | 66.0 | 60.0 | 72.0 | ≈ 61549 |
| 501.2738 | 66.0 | 61.0 | 71.0 | ≈ 23854 |

(m/z and area may differ in the last digit — that's fine.)

## Step 5 — Isotope grouping and charge determination

Constant: `NEUTRON = 1.003355` Da. Process traces sorted by m/z, lowest first; each trace may belong to only one group.

For each ungrouped trace `t0` (the candidate monoisotope):

1. **Charge**: find the nearest ungrouped trace above `t0` whose apex RT is within **1.0 s** of `t0`'s and whose m/z gap `d` satisfies `0.2 < d ≤ 1.01 + 0.01`. If found, `z = round(NEUTRON / d)`; accept it only if `1 ≤ z ≤ 3` and `abs(d − NEUTRON/z) ≤ 0.01`. If none found, `z = 1` (singly charged, no visible isotopes).
2. **Isotopes**: for `k = 1, 2, 3, ...`, look for an ungrouped trace at `mz(t0) + k × NEUTRON / z` (±0.01) with apex RT within 1.0 s; add it to the group; stop at the first missing isotope.
3. Emit one feature: monoisotopic m/z and area from `t0`, charge `z`, isotope count = group size.

Sanity check: the trace at 451.7315 is 0.5018 above 451.2297 → `z = round(1.003355/0.5018) = 2`; the trace at 501.2738 is 1.0041 above 500.2697 → `z = 1`.

## Step 6 — Output

CLI: `python3 features.py mini_ms1.mzml -o features.tsv`

Write a TSV, one row per feature, sorted by m/z, with header:

```
feature_id	mono_mz	charge	rt_apex	rt_start	rt_end	area	n_isotopes
```

---

## How to test (acceptance criteria)

Run the exact command above against the embedded file. **All** of these must hold:

1. The program runs with no third-party packages and no errors.
2. Exactly **24 MS1 scans** parsed, **53 peaks** above threshold, **5 traces** (print these counts to stdout).
3. `features.tsv` has exactly **2 feature rows**.
4. Feature 1: `mono_mz` = 451.23 ± 0.01, `charge` = 2, `rt_apex` = 76.0 ± 1.0, `n_isotopes` = 3.
5. Feature 2: `mono_mz` = 500.27 ± 0.01, `charge` = 1, `rt_apex` = 66.0 ± 1.0, `n_isotopes` = 2.
6. For each feature, the monoisotopic trace area is larger than each of its isotope traces' areas, and all areas are > 0.

## If a test fails — debugging checklist

Work through these in order; fix the first thing that is wrong, then re-run:

1. **0 spectra parsed or wrong per-scan peak counts** → the bug is in `mzml_reader.py`, not here. Go back to the MSTool reader task acceptance criteria and fix the reader; do not patch parsing inside `features.py`.
2. **53 ≠ collected peaks** → threshold bug (peaks must be `>= 500`, noise max is 300), or you included MS2 logic — this file is MS1-only; also make sure you keep `ms_level == 1`, not `2`.
3. **Trace count ≠ 5** → clustering bug. Common causes: tolerance applied to the first peak of the trace instead of the running mean (noise jitter accumulates); allowing two peaks from the same scan into one trace; forgetting the ≥ 5 scans filter (without it you get extra singleton traces). Print each trace's m/z and scan count.
4. **Apex RT or boundaries wrong** → check boundary rule order: stop when intensity < 5% of apex OR scan indices non-consecutive. Area must use RT values from the file, not scan indices.
5. **Wrong charge (e.g. z=1 for the 451.23 feature)** → you paired the monoisotope with the +1.0034 Da trace (the M+2 of a z=2 envelope) instead of the *nearest* trace above it (+0.5018). Always use the smallest qualifying gap to compute `z = round(1.003355/d)`.
6. **Isotope count wrong** → isotope target is `mono + k × 1.003355 / z` (divide by z!), and grouping must respect the apex-RT gate of 1.0 s.

## Optional stretch goals (only after all acceptance criteria pass)

- ppm-based m/z tolerance instead of Da.
- Smooth each EIC with a 3-point moving average before apex/boundary detection.
- Report an isotope-pattern score: correlation between measured isotope areas and the ratios 1.0 / 0.6 / 0.2 (z=2 envelope) or 1.0 / 0.4 (z=1 envelope) — a toy stand-in for an averagine model.
- An `assert`-based `test_features.py` that runs the acceptance criteria automatically.
