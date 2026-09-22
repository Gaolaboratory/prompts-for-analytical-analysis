# Real MS/MS test data — tier (c) for the spectral-library-search prompt

`library.txt` (5 entries) and `queries.txt` (4 queries) are converted from real MassBank
MS/MS records, in the prompt's text format (`>NAME <id>` header, one `m/z intensity`
pair per line, blank line between spectra, first line a `#` comment). Reference truth for
each query is the compound annotated by MassBank in the query record itself.

## Source

All records fetched from the MassBank REST API (MassBank v2025.12.1) on **2026-08-26**:

- API base: `https://massbank.eu/MassBank-api`
- Record endpoint: `https://massbank.eu/MassBank-api/records/<accession>` (JSON)
- Record search used for selection: `https://massbank.eu/MassBank-api/records?compound_name=<name>&ms_type=MS2`
- Record pages: `https://massbank.eu/MassBank/RecordDisplay?id=<accession>`

Values cross-checked against the raw record text in the GitHub export
(https://github.com/MassBank/MassBank-data, branch `dev`, e.g.
`https://raw.githubusercontent.com/MassBank/MassBank-data/dev/BAFG/MSBNK-BAFG-CSL2311094657.txt`):
m/z and relative intensities are identical.

MassBank data is open access; each record carries its own license, reproduced per record
below (CC BY / CC BY-SA / dl-de/by-2.0). Attribution: the MassBank contributors listed in
each record's `AUTHORS` field (Eawag, Athens University, ACES_SU, BAF).

## Contents

Library — one record per compound, entry id = lowercase compound name
(`acetaminophen` is a CH$NAME synonym in its record, whose title compound is "Paracetamol"):

| entry              | accession                 | compound (MassBank title) | instrument (type)                     | CE            | license      |
|--------------------|---------------------------|---------------------------|---------------------------------------|---------------|--------------|
| caffeine           | MSBNK-Eawag-EA030313      | Caffeine                  | LTQ Orbitrap XL (LC-ESI-ITFT)         | 90 % (nom.)   | CC BY        |
| acetaminophen      | MSBNK-Eawag-EA024307      | Paracetamol = Acetaminophen | LTQ Orbitrap XL (LC-ESI-ITFT)       | 90 % (nom.)   | CC BY        |
| sulfamethoxazole   | MSBNK-Athens_Univ-AU101802| Sulfamethoxazole          | Bruker maXis Impact (LC-ESI-QTOF)     | 20 eV         | CC BY-SA     |
| ketamine           | MSBNK-Athens_Univ-AU158602| Ketamine                  | Bruker maXis Impact (LC-ESI-QTOF)     | 20 eV         | CC BY        |
| nicotine           | MSBNK-Eawag-EQ300803      | Nicotine                  | Q Exactive Orbitrap (LC-ESI-QFT)      | 45 (nom.)     | CC BY        |

Queries — q1–q3 are *different records* (different contributor and/or instrument and/or
collision energy) of compounds that ARE in the library; q4 is a compound NOT in the library:

| query | accession                 | true compound (MassBank annotation) | instrument (type)                  | CE                 | vs library entry      |
|-------|---------------------------|-------------------------------------|------------------------------------|--------------------|-----------------------|
| q1    | MSBNK-BAFG-CSL2311094657  | Caffeine                            | SCIEX TripleTOF 5600 (LC-ESI-QTOF) | 40 V               | caffeine: other instrument + CE |
| q2    | MSBNK-Athens_Univ-AU101803| Sulfamethoxazole                    | Bruker maXis Impact (LC-ESI-QTOF)  | 30 eV              | sulfamethoxazole: same instrument, other CE |
| q3    | MSBNK-ACES_SU-AS000192    | Nicotine                            | Q Exactive HF-X (LC-ESI-QFT)       | ramp 20–70 % (nom.)| nicotine: other instrument + CE |
| q4    | MSBNK-BAFG-CSL23111011381 | Theophylline (not in library)       | SCIEX TripleTOF 5600 (LC-ESI-QTOF) | 50 V               | —                     |

## Expected results

Computed with the prompt's exact algorithm (greedy one-to-one matching, |Δm/z| ≤ 0.5,
sqrt-intensity cosine `score = (Σ_matched √(Iq·Il))² / (Σ Iq · Σ Il)`), run directly on
these two files. The data is real, so same-compound/different-CE scores are looser than
the synthetic tier-(a) values (0.9+): 0.67–0.87 here, as expected for real cross-CE
spectra. These are exact deterministic values — a correct implementation reproduces them
to 4 decimals.

| query | best_match       | score  | matched_peaks | total_library_peaks | runner-up (score)          |
|-------|------------------|--------|---------------|---------------------|----------------------------|
| q1    | caffeine         | 0.7473 | 6             | 7                   | acetaminophen (0.0837)     |
| q2    | sulfamethoxazole | 0.6669 | 4             | 6                   | caffeine (0.0000)          |
| q3    | nicotine         | 0.8706 | 6             | 8                   | ketamine (0.0137)          |
| q4    | NO_MATCH         | 0.0138 | 2             | 6                   | (top entry: acetaminophen) |

- q1–q3: top hit = the query record's own annotated compound, score > 0.5 → called.
- q4: theophylline shares no fragment within ±0.5 Da of any library entry except two
  low-intensity coincidences (65.0136→65.0386 and 92.0249→92.0495 of acetaminophen);
  best score 0.0138 < 0.5 → `NO_MATCH` (score/matched columns still describe the top entry).
- Summary stdout line: `queries: 4  called: 3  no_match: 1`.

## How obtained

1. Selected 5 compounds with ≥2 MS2 records each via the API search above (caffeine,
   acetaminophen, sulfamethoxazole, ketamine, nicotine) plus theophylline (many records,
   verified absent from the 5 library compounds) for q4.
2. For each chosen record, took the published `PK$PEAK` block (API fields
   `peak.peak.values[]` = m/z, `rel` = published `rel.int.` column; `peak.annotation`
   m/z strings = the published m/z, used where present and verified aligned).
   **No rescaling, no reweighting**: m/z and relative intensity are as published
   (MassBank `rel.int.` scales differ per record — e.g. base peak 999 for Eawag/BAFG
   records — which is harmless because the prompt's score is scale-invariant).
3. Dropped peaks with relative intensity < 5 % of the record's base peak
   (`100 * rel / max(rel) < 5`); every kept entry/query has ≥ 6 peaks.
   Peak counts before → after: caffeine 14→7, acetaminophen 12→6, sulfamethoxazole
   19→6, ketamine 49→18, nicotine 17→8, q1 21→8, q2 22→6, q3 9→6, q4 16→16.
4. Sorted peaks ascending by m/z; m/z written with 4 decimals (trailing zeros are
   formatting only — e.g. published 69.049 is written 69.0490); intensity written as the
   published integer `rel.int.`
5. Verification scores in "Expected results" were computed by an independent reference
   implementation of the prompt's matcher/scorer run against these exact files.
