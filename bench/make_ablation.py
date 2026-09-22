#!/usr/bin/env python3
"""Build Experiment A's specification ladder (L0-L3) from each shipped PROMPT.md.

The ladder is built by DELETION from the real prompt, never by re-authoring it.
That choice is the experiment's main defence against the obvious objection --
that L0 is a straw man the authors wrote to lose. L0 is the authors' own opening
lines; every level above it restores one of the prompt's own sections, in the
prompt's own words and the prompt's own order:

    L0  preamble only            task contract + dependency prohibitions
    L1  + ## Input               data contract
    L2  + ## Method              domain constraints
    L3  + ## Output              output contract
    L4  = PROMPT.md verbatim     + ## Acceptance criteria

Two consequences worth stating in the manuscript. First, nesting is guaranteed
by construction and checked here: the line sequence of L(k) is a subsequence of
L(k+1), so no level can accidentally say something a higher level does not.
Second, the prompt's own sectioning IS the operational definition of the six
template blocks -- not a taxonomy imposed afterwards. Where a Method section
carries something a purist would call an output detail, the ladder inherits that
choice rather than silently correcting it.

The preamble carries the program name, the exact run command and the dependency
prohibitions at every level. That is deliberate: it is held constant so it never
confounds the ladder, and it keeps every level runnable by the pinned command,
so a low level fails on its specification rather than on being unrunnable.
`## Dependencies` (database_search only) stays in the preamble for the same
reason -- it declares which modules exist, which is task contract, not method.
"""
import hashlib, json, os, re, sys

BENCH = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BENCH)
sys.path.insert(0, BENCH)
from specs import SPECS

LADDER_TOOLS = ["calibration_s", "titration_s", "uvvis_s",
                "pca_s", "chrom_s", "dda_s"]
# Sections restored at each level, cumulative. Order of the keys is the ladder;
# the emitted file keeps the PROMPT's own section order regardless.
LEVELS = {"L0": (),
          "L1": ("Input",),
          "L2": ("Input", "Method"),
          "L3": ("Input", "Method", "Output")}
PREAMBLE_SECTIONS = ("Dependencies",)   # kept at every level, see docstring


def split_sections(text):
    """(preamble_lines, [(heading, lines), ...]) split on '## ' headings."""
    lines = text.splitlines()
    idx = [i for i, l in enumerate(lines) if l.startswith("## ")]
    if not idx:
        return lines, []
    pre = lines[:idx[0]]
    out = []
    for n, start in enumerate(idx):
        end = idx[n + 1] if n + 1 < len(idx) else len(lines)
        out.append((lines[start][3:].strip(), lines[start:end]))
    return pre, out


def is_subsequence(small, big):
    it = iter(big)
    return all(any(x == y for y in it) for x in small)


def build(tool):
    spec = SPECS[tool]
    src = spec["prompt"]
    text = open(src).read()
    pre, sections = split_sections(text)
    names = [h for h, _ in sections]
    for needed in ("Input", "Output", "Method", "Acceptance criteria"):
        if needed not in names:
            raise SystemExit("%s: PROMPT.md has no '## %s' section (has %s)"
                             % (tool, needed, names))
    outdir = os.path.join(os.path.dirname(src), "ablation")
    os.makedirs(outdir, exist_ok=True)

    emitted, manifest = {}, {}
    for level, keep in LEVELS.items():
        body = list(pre)
        for heading, lines in sections:
            if heading in PREAMBLE_SECTIONS or heading in keep:
                body += lines
        while body and not body[-1].strip():
            body.pop()
        out = "\n".join(body) + "\n"
        path = os.path.join(outdir, level + ".md")
        open(path, "w").write(out)
        emitted[level] = out.splitlines()
        manifest[level] = {"path": os.path.relpath(path, REPO),
                           "lines": len(out.splitlines()),
                           "chars": len(out),
                           "sha256": hashlib.sha256(out.encode()).hexdigest(),
                           "sections": list(PREAMBLE_SECTIONS_present(names)) + list(keep)}
    emitted["L4"] = text.splitlines()
    manifest["L4"] = {"path": os.path.relpath(src, REPO),
                      "lines": len(text.splitlines()), "chars": len(text),
                      "sha256": hashlib.sha256(text.encode()).hexdigest(),
                      "sections": names}

    order = ["L0", "L1", "L2", "L3", "L4"]
    for lo, hi in zip(order, order[1:]):
        if not is_subsequence(emitted[lo], emitted[hi]):
            raise SystemExit("%s: %s is not a subsequence of %s -- the ladder is "
                             "not nested and the experiment would be invalid"
                             % (tool, lo, hi))
    return manifest


def PREAMBLE_SECTIONS_present(names):
    return [s for s in PREAMBLE_SECTIONS if s in names]


def main():
    tools = sys.argv[1:] or LADDER_TOOLS
    all_manifest = {}
    for tool in tools:
        m = build(tool)
        all_manifest[tool] = m
        print("%-16s " % tool + "  ".join(
            "%s=%d lines" % (lv, m[lv]["lines"]) for lv in ("L0", "L1", "L2", "L3", "L4")))
    path = os.path.join(BENCH, "ablation_manifest.json")
    json.dump(all_manifest, open(path, "w"), indent=1)
    print("\nnesting verified for every tool; manifest -> %s"
          % os.path.relpath(path, REPO))


if __name__ == "__main__":
    main()
