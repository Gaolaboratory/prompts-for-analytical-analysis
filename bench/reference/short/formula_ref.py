#!/usr/bin/env python3
"""Reference molecular-formula assignment for examples/formula_finder/PROMPT.md.

Enumerates elemental compositions (C 0-30, H 0-60, N 0-10, O 0-10, P 0-2, S
0-2) by brute force -- pruned with a branch-and-bound that breaks a loop as
soon as its running total, with every remaining element at zero, already
exceeds the window's upper bound (every element's mass is positive, so more
of it only makes things worse) -- keeps candidates within an INCLUSIVE 5 ppm
window of the measured mass, scores them against the measured M1/M2 isotope
intensities, and ranks ascending by score.

The isotope table and the first-order pattern model are copied verbatim from
examples/formula_finder/minimal_formula_finder_prompt.md -- it is data, not
exposition, and the module-level self-check below reproduces that prompt's
own CO2/CH4 oracle rows exactly.
"""
import csv

# Isotope table -- verbatim from
# examples/formula_finder/minimal_formula_finder_prompt.md. Do not add
# elements or isotopes beyond this table (36S at 0.01% is deliberately
# omitted there).
ISOTOPES = {
    "H": [(1.007825, 99.9885), (2.014102, 0.0115)],
    "C": [(12.000000, 98.93), (13.003355, 1.07)],
    "N": [(14.003074, 99.636), (15.000109, 0.364)],
    "O": [(15.994915, 99.757), (16.999131, 0.038), (17.999160, 0.205)],
    "P": [(30.973762, 100.0)],
    "S": [(31.972071, 94.99), (32.971459, 0.75), (33.967867, 4.25)],
}

MONO_MASS = {e: iso[0][0] for e, iso in ISOTOPES.items()}

# Hill order for this table: C first (if present), then H, then the rest
# alphabetically -- which for {C, H, N, O, P, S} is identical to plain
# alphabetical order, since H already sorts second.
HILL_ORDER = ["C", "H", "N", "O", "P", "S"]

BOUNDS = {"C": 30, "H": 60, "N": 10, "O": 10, "P": 2, "S": 2}
PPM_WINDOW = 5.0


def pattern(counts):
    """(mass, M1, M2) for an element-count dict, using the prompt's
    first-order isotope-pattern approximation: M1 = sum(n_e * r1_e); M2 =
    sum(n_e * r2_e) + sum(n_e*(n_e-1)/2 * r1_e**2) -- first order in the rare
    isotopes plus the same-element pair term, cross-element second-order
    terms neglected."""
    mass = 0.0
    m1 = 0.0
    m2 = 0.0
    for e, n in counts.items():
        if n == 0:
            continue
        iso = ISOTOPES[e]
        a0 = iso[0][1]
        mass += iso[0][0] * n
        r1 = (iso[1][1] / a0) if len(iso) > 1 else 0.0
        m1 += n * r1
        m2 += n * (n - 1) / 2.0 * r1 * r1
        if len(iso) > 2:
            m2 += n * (iso[2][1] / a0)
    return mass, m1, m2


def _self_check():
    """Verify pattern() against the prompt's own CO2/CH4 oracle rows before
    trusting anything downstream (rounded to 6 decimal places: the exact
    float for CH4's M2 pair term is ~7.9e-08, not 0.0, which only agrees with
    the oracle's "0.000000" at that precision)."""
    oracle = [
        ({"C": 1, "O": 2}, (43.989830, 0.011578, 0.004110)),
        ({"C": 1, "H": 4}, (16.031300, 0.011276, 0.000000)),
    ]
    for counts, want in oracle:
        got = tuple(round(v, 6) for v in pattern(counts))
        assert got == want, (
            "formula_ref.pattern self-check failed for %r: got %r, want %r -- "
            "the isotope model has drifted from the prompt's CO2/CH4 oracle"
            % (counts, got, want))


_self_check()


def formula_str(counts):
    parts = []
    for e in HILL_ORDER:
        n = counts.get(e, 0)
        if n == 0:
            continue
        parts.append(e if n == 1 else "%s%d" % (e, n))
    return "".join(parts)


def enumerate_candidates(measured, m1_meas, m2_meas):
    """All (formula, calc_mass, error_ppm, score) candidates within an
    inclusive 5 ppm window of `measured`, brute force over BOUNDS, pruned by
    branch-and-bound (see module docstring) rather than by skipping any
    composition the full enumeration would keep."""
    window = measured * PPM_WINDOW * 1e-6
    low = measured - window
    high = measured + window
    mC, mH, mN, mO, mP, mS = (MONO_MASS[e] for e in HILL_ORDER)
    out = []
    for c in range(BOUNDS["C"] + 1):
        mc = c * mC
        if mc > high:
            break
        for h in range(BOUNDS["H"] + 1):
            mh = mc + h * mH
            if mh > high:
                break
            for n in range(BOUNDS["N"] + 1):
                mn = mh + n * mN
                if mn > high:
                    break
                for o in range(BOUNDS["O"] + 1):
                    mo = mn + o * mO
                    if mo > high:
                        break
                    for p in range(BOUNDS["P"] + 1):
                        mp = mo + p * mP
                        if mp > high:
                            break
                        for s in range(BOUNDS["S"] + 1):
                            m = mp + s * mS
                            if m > high:
                                break
                            if m >= low:
                                counts = {"C": c, "H": h, "N": n,
                                          "O": o, "P": p, "S": s}
                                mass, m1c, m2c = pattern(counts)
                                err_ppm = (mass - measured) / measured * 1e6
                                score = (abs(err_ppm)
                                         + 100.0 * abs(m1_meas - m1c)
                                         + 100.0 * abs(m2_meas - m2c))
                                out.append({
                                    "formula": formula_str(counts),
                                    "calc_mass": mass,
                                    "error_ppm": err_ppm,
                                    "score": score,
                                })
    return out


def run(tsv_path):
    """id -> [{"rank", "formula", "calc_mass", "error_ppm", "score"}, ...],
    plus "blocks" (number of input rows) and "candidates" (total candidate
    rows summed across every block)."""
    with open(tsv_path, newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))

    result = {}
    total_candidates = 0
    for row in rows:
        cid = row["id"]
        measured = float(row["mass"])
        m1_meas = float(row["M1"])
        m2_meas = float(row["M2"])
        candidates = enumerate_candidates(measured, m1_meas, m2_meas)
        candidates.sort(key=lambda c: (c["score"], c["formula"]))
        total_candidates += len(candidates)
        result[cid] = [
            {"rank": i, "formula": c["formula"], "calc_mass": c["calc_mass"],
             "error_ppm": c["error_ppm"], "score": c["score"]}
            for i, c in enumerate(candidates, start=1)
        ]
    result["blocks"] = len(rows)
    result["candidates"] = total_candidates
    return result


if __name__ == "__main__":
    import sys
    r = run(sys.argv[1])
    ids = [k for k in r if k not in ("blocks", "candidates")]
    for cid in ids:
        block = r[cid]
        top = block[0]
        runner_up = block[1]["score"] if len(block) > 1 else float("nan")
        print("%s: rank1=%s calc_mass=%.6f error_ppm=%+.3f score=%.4f "
              "candidates=%d runner_up_score=%.2f"
              % (cid, top["formula"], top["calc_mass"], top["error_ppm"],
                 top["score"], len(block), runner_up))
    print("blocks=%d candidates=%d" % (r["blocks"], r["candidates"]))
