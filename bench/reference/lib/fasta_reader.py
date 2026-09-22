#!/usr/bin/env python3
"""read_fasta(path) -> [(record_id, sequence), ...]; id = first whitespace token."""


def read_fasta(path):
    records, rid, seq = [], None, []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if rid is not None:
                records.append((rid, "".join(seq)))
            rid, seq = line[1:].split()[0] if line[1:].split() else "", []
        elif rid is not None:
            seq.append(line.upper())
    if rid is not None:
        records.append((rid, "".join(seq)))
    return records


if __name__ == "__main__":
    import sys
    for rid, seq in read_fasta(sys.argv[1]):
        print("%s  %d aa" % (rid, len(seq)))
