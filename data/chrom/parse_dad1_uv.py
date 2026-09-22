#!/usr/bin/env python3
"""Minimal parser for Agilent ChemStation DAD .uv files.

Python port of chromConverter::read_chemstation_uv / decode_uv_delta
(R package chromConverter, (c) Ethan Bass, GPL-3), itself adapted from the
rainbow project's Agilent .uv parser (Evan Shi, GPL-3).
https://github.com/ethanbass/chromConverter  (R/read_chemstation_uv.R,
R/agilent_utility_functions.R at master, retrieved 2026-08-26)

Supports file versions "31" and "131" (both LC and OpenLab "OL" type codes).
Writes the FIRST wavelength channel to CSV as time_s,signal.

Usage: python3 parse_dad1_uv.py <input.uv> <output.csv> [ref_csv] [channel_nm]

The default exported channel is 220 nm. It is NOT the first channel in the
file (200 nm); 220 nm is chosen because chromConverter's own test suite
(tests/testthat/test-read_chroms.R) ships a reference export of exactly this
channel (testdata/dad1.csv), which allows exact numeric validation.
"""
import csv
import struct
import sys


def read_cstrs(buf, off, count):
    """Read `count` NUL-terminated strings sequentially (R readBin 'character')."""
    out = []
    for _ in range(count):
        end = buf.index(b"\x00", off)
        out.append(buf[off:end])
        off = end + 1
    return out


def get_agilent_offsets(version):
    # From chromConverter R/agilent_utility_functions.R::get_agilent_offsets
    if version in ("131_LC", "131_OL"):
        return {"num_times": 278, "scaling_factor": 3085, "data_start": 4096}
    if version == "31":
        return {"num_times": 278, "scaling_factor": 318, "data_start": 512}
    raise ValueError(f"unsupported .uv version: {version}")


def parse_uv(path):
    buf = open(path, "rb").read()

    # File version string at offset 0: 1-byte length + that many chars.
    n = buf[0]
    version = buf[1 : 1 + n].decode("ascii", "replace")
    if version == "131":
        # File type code at byte 348: two NUL-terminated 1-char strings,
        # pasted together -> "LC" (ChemStation LC) or "OL" (OpenLab).
        code = b"".join(read_cstrs(buf, 348, 2)).decode("ascii", "replace")
        version = f"{version}_{code}"
    if version not in ("131_LC", "131_OL", "31"):
        raise ValueError(f"unsupported .uv version: {version}")

    off = get_agilent_offsets(version)

    # Number of data points: big-endian signed int32.
    nval = struct.unpack_from(">i", buf, off["num_times"])[0]

    # Scaling factor: big-endian 64-bit double.
    scaling = struct.unpack_from(">d", buf, off["scaling_factor"])[0]

    # Wavelength block at data_start+8: three little-endian int16, value/20 = nm.
    w1, w2, w3 = struct.unpack_from("<3h", buf, off["data_start"] + 0x8)
    lam_start, lam_end, lam_step = w1 // 20, w2 // 20, w3 // 20
    lambdas = list(range(lam_start, lam_end + lam_step, lam_step))
    n_lam = len(lambdas)

    # Body: per record -> 4 bytes discard, int32 time (LE, in milliseconds),
    # 14 bytes discard, then per-wavelength delta-coded values.
    pos = off["data_start"]
    times_ms = []
    traces = [[0] * n_lam for _ in range(nval)]
    for i in range(nval):
        pos += 4  # discard
        (t,) = struct.unpack_from("<i", buf, pos)
        pos += 4
        times_ms.append(t)
        pos += 14  # discard
        running = 0  # ONE accumulator carried across wavelengths, reset per record
        for j in range(n_lam):
            (v,) = struct.unpack_from("<h", buf, pos)
            pos += 2
            if v == -0x8000:  # -32768 sentinel: next 4 bytes are absolute int32
                (running,) = struct.unpack_from("<i", buf, pos)
                pos += 4
            else:
                running += v
            traces[i][j] = running

    # Time: raw value is 1/60000 min == 1 ms (chromConverter: times/60000 -> min).
    time_s = [t / 1000.0 for t in times_ms]
    # Intensity: raw * scaling factor -> mAU.
    signals = [[v * scaling for v in row] for row in traces]
    return version, nval, scaling, lambdas, time_s, signals


def main():
    src, dst = sys.argv[1], sys.argv[2]
    ref = sys.argv[3] if len(sys.argv) > 3 else None
    channel = int(sys.argv[4]) if len(sys.argv) > 4 else 220
    version, nval, scaling, lambdas, time_s, signals = parse_uv(src)

    j = lambdas.index(channel)
    with open(dst, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "signal"])
        for i in range(nval):
            w.writerow([f"{time_s[i]:.4f}", f"{signals[i][j]:.8f}"])

    print(f"file_version      : {version}")
    print(f"n_points          : {nval}")
    print(f"scaling_factor    : {scaling}")
    print(f"wavelengths (nm)  : {lambdas[0]}..{lambdas[-1]} step {lambdas[1]-lambdas[0]} ({n_lam} channels)" if (n_lam := len(lambdas)) else "")
    print(f"time_span (s)     : {time_s[0]:.3f} .. {time_s[-1]:.3f}")
    dts = [round(time_s[i+1]-time_s[i], 9) for i in range(len(time_s)-1)]
    print(f"sampling interval : min {min(dts):.4f} max {max(dts):.4f} s (uniform={len(set(dts))==1})")
    print(f"wrote channel {lambdas[j]} nm -> {dst}")

    # Optional validation against a reference CSV (UTF-16 chemstation_csv export).
    if ref:
        with open(ref, "rb") as f:
            raw = f.read()
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError:
            text = raw.decode("utf-16-le", "replace")
        rows = [r for r in text.splitlines() if r.strip()][1:]  # drop header line
        ref_t, ref_y = [], []
        for r in rows:
            a, b = r.split(",")
            ref_t.append(float(a.strip().strip("\x00")))
            ref_y.append(float(b.strip().strip("\x00")))
        n = min(len(ref_t), nval)
        dt_max = max(abs(time_s[i] - ref_t[i] * 60.0) for i in range(n))
        dy_max = max(abs(signals[i][j] - ref_y[i]) for i in range(n))
        dy_rel = max(abs(signals[i][j] - ref_y[i]) / max(abs(ref_y[i]), 1e-9) for i in range(n))
        print(f"reference compare : {n} points, max|dt|={dt_max:.3e} s, "
              f"max|dy|={dy_max:.3e} mAU, max rel|dy|={dy_rel:.3e}")


if __name__ == "__main__":
    main()
