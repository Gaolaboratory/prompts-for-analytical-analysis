# Data index

Real test data shipped with the prompts. Each directory's `README.md` documents the dataset's
source, URL, license, download date, and any conversion; expected results and their provenance
are recorded in `examples/<tool>/EXAMPLE_DATA.md`.

| Directory | Tool | Dataset | Oracle |
|---|---|---|---|
| `calibration/` | `calibrate.py` | NIST StRD Norris (36 points, `norris.csv`) | NIST certified coefficients, ≤1e-9 relative |
| `titration/` | `titration.py` | Published acetic acid–NaOH teaching curve | Published Veq/p*K*a*; recomputed reference |
| `uvvis_spectrum/` | `uvvis.py` | Published teaching spectrum | Published λmax/ε; recomputed reference |
| `chrom/` | `chrom_integrate.py` | Real chromatogram | Recomputed reference (apexes, areas) |
| `pca/` | `pca.py` | Public metabolomics feature matrix + groups | NumPy/scikit-learn reference |
| `mass_stats/` | `stats.py` | Real feature table (CTRL/EXP) | Recomputed reference |
| `mass_reader/` | `fasta_reader.py`, `mzml_reader.py` | Real mzML, MGF, FASTA files | pyteomics reference |
| `feature_extraction/` | `features.py` | Real LC–MS run (`BSA1_F1.mzML`) | OpenMS comparison (agreement) |
| `database_search/` | `search.py` | UPS1-in-yeast DDA MGF + FASTA | Target–decoy FDR; recomputed reference |
| `formula/` | `formula_finder.py` | MassBank-derived candidate set | MassBank annotations |
| `spectral/` | `libsearch.py` | MassBank library + query spectra | MassBank annotations |
| `nmr/` | `nmr.py` | MetaboLights MTBLS1 FID | nmrglue reference; published resonances |
