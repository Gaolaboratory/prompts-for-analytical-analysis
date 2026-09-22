#!/usr/bin/env python3
"""Reference MS/MS spectral library search for examples/spectral_library/PROMPT.md.

Parses the prompt's text format (`#` comments, `>NAME <name>` record headers,
then `m/z intensity` pairs, blank lines separating records), scores every
query against every library entry with greedy one-to-one peak matching at
|delta m/z| <= 0.5 and the sqrt-intensity cosine, and reports the best-scoring
library entry per query -- `NO_MATCH` (name only; score/matched_peaks/
total_library_peaks still describe the top entry) below the 0.5 call
threshold.
"""
import math


def parse_spectra(path):
    """[(name, [(mz, intensity), ...]), ...] in file order."""
    records = []
    name, peaks = None, []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(">NAME"):
                if name is not None:
                    records.append((name, peaks))
                name, peaks = line.split()[1], []
            else:
                mz_s, inten_s = line.split()
                peaks.append((float(mz_s), float(inten_s)))
    if name is not None:
        records.append((name, peaks))
    return records


def score_pair(qpeaks, lpeaks):
    """(score, matched_peaks) for one query spectrum against one library
    spectrum: greedy one-to-one matching, pairing candidate peaks in
    descending order of the product of their square-rooted intensities so
    that the strongest, most diagnostic peaks are matched first, each peak
    used at most once."""
    candidates = []
    for qi, (qmz, qint) in enumerate(qpeaks):
        for li, (lmz, lint) in enumerate(lpeaks):
            if abs(qmz - lmz) <= 0.5:
                weight = math.sqrt(qint * lint)
                candidates.append((weight, qi, li))
    candidates.sort(key=lambda c: c[0], reverse=True)

    q_used = [False] * len(qpeaks)
    l_used = [False] * len(lpeaks)
    numerator = 0.0
    matched = 0
    for weight, qi, li in candidates:
        if q_used[qi] or l_used[li]:
            continue
        q_used[qi] = True
        l_used[li] = True
        numerator += weight
        matched += 1

    sum_q = sum(i for _, i in qpeaks)
    sum_l = sum(i for _, i in lpeaks)
    denom = sum_q * sum_l
    score = (numerator * numerator) / denom if denom > 0 else 0.0
    return score, matched


def run(queries_path, library_path, call_threshold=0.5):
    """list[dict] with keys query, best_match, score, matched_peaks,
    total_library_peaks, in query order."""
    queries = parse_spectra(queries_path)
    library = parse_spectra(library_path)

    rows = []
    for qname, qpeaks in queries:
        best = None  # (score, matched, total_library_peaks, lib_name)
        for lname, lpeaks in library:
            s, m = score_pair(qpeaks, lpeaks)
            if best is None or s > best[0]:
                best = (s, m, len(lpeaks), lname)
        score, matched, total_lib, lib_name = best
        called = score >= call_threshold
        rows.append({
            "query": qname,
            "best_match": lib_name if called else "NO_MATCH",
            "score": score,
            "matched_peaks": matched,
            "total_library_peaks": total_lib,
        })
    return rows


if __name__ == "__main__":
    import sys
    rows = run(sys.argv[1], sys.argv[2])
    for r in rows:
        print("%s\t%s\t%.4f\t%d\t%d"
              % (r["query"], r["best_match"], r["score"],
                 r["matched_peaks"], r["total_library_peaks"]))
    called = sum(1 for r in rows if r["best_match"] != "NO_MATCH")
    print("queries: %d  called: %d  no_match: %d"
          % (len(rows), called, len(rows) - called))
