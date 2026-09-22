#!/usr/bin/env python3
"""Deterministic generator for the spectral-library-search test data. Std-lib only."""

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

LIBRARY = [
    ("caffeine",        [(42.1, 15), (58.0, 100), (69.0, 20), (82.0, 35),
                         (109.1, 55), (138.1, 60), (163.1, 10), (195.1, 90)]),
    ("acetaminophen",   [(43.0, 40), (65.0, 20), (80.9, 10), (92.0, 15),
                         (93.0, 60), (109.0, 45), (110.0, 35), (152.1, 80)]),
    ("sulfamethoxazole",[(65.0, 30), (92.0, 70), (99.0, 25), (108.0, 85),
                         (124.0, 20), (156.0, 90), (188.0, 50), (254.1, 75)]),
    ("nicotine",        [(42.0, 35), (84.1, 100), (117.0, 15), (119.1, 20),
                         (130.1, 25), (132.1, 40), (133.0, 10), (163.1, 60)]),
]

def write_spectra(path, entries, comment):
    lines = [comment, ""]
    for name, peaks in entries:
        lines.append(">NAME %s" % name)
        for i, (mz, inten) in enumerate(peaks):
            sep = "  " if i == 0 else " "   # real files mix spacing
            lines.append("%.4f%s%s" % (mz, sep, inten))
        lines.append("")
    with open(path, "w") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")

write_spectra("library.txt", LIBRARY, "# minimal text spectral library")

rnd = lcg(20260824)
queries = []
for qid, (name, peaks) in zip(("q1", "q2", "q3"), LIBRARY[:3]):
    out = []
    for mz, inten in peaks:
        jmz = mz + (next(rnd) - 0.5) * 0.2
        jint = inten * (0.75 + 0.5 * next(rnd))
        if jint < 12.0:            # low-intensity peaks are dropped
            continue
        out.append((jmz, round(jint, 1)))
    for _ in range(2):             # noise peaks
        out.append((round(60.0 + next(rnd) * 340.0, 4), round(3.0 + next(rnd) * 8.0, 1)))
    out.sort()
    queries.append((qid, out))

queries.append(("q4", [(90.2, 50.0), (131.1, 30.0), (176.1, 80.0),
                       (220.2, 25.0), (300.1, 60.0)]))

write_spectra("queries.txt", queries, "# query spectra")
print("wrote library.txt, queries.txt")
