"""Independent raw-bit/TEXT-run and closed-form matrix oracles (original MIT).

No clinical data, downloads, FlowIO or NumPy. Run after JS release build.
"""
import argparse
import hashlib
import json
import math
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text_bytes(pairs, delimiter=b"|"):
    return delimiter + delimiter.join(
        value.encode().replace(delimiter, delimiter * 2) for pair in pairs for value in pair
    ) + delimiter


def decode(path):
    data = path.read_bytes()
    first, last = int(data[10:18]), int(data[18:26])
    text = data[first:last + 1]
    sep = text[:1]
    fields, field = [], b""
    # Independent run-length/parity interpretation of FCS delimiter escaping.
    for run in re.split(b"(" + re.escape(sep) + b"+)", text[1:]):
        if run.startswith(sep):
            field += sep * (len(run) // 2)
            if len(run) % 2:
                fields.append(field.decode())
                field = b""
        else:
            field += run
    assert not field and len(fields) % 2 == 0
    meta = dict(zip(fields[::2], fields[1::2]))
    begin, end = int(meta["$BEGINDATA"]), int(meta["$ENDDATA"])
    assert int(data[26:34]) == begin and int(data[34:42]) == end
    return meta, data[begin:end + 1], sep


def source(path, widths, rows, order, metadata=None):
    pairs = [
        ("$MODE", "L"), ("$DATATYPE", "I"),
        ("$BYTEORD", "1,2,3,4" if order == "little" else "4,3,2,1"),
        ("$PAR", str(len(widths))), ("$TOT", str(len(rows))),
        ("$BEGINSTEXT", "0"), ("$ENDSTEXT", "0"), ("$BEGINANALYSIS", "0"),
        ("$ENDANALYSIS", "0"), ("$NEXTDATA", "0"),
        ("$BEGINDATA", "0000000000"), ("$ENDDATA", "0000000000"),
    ]
    for c, width in enumerate(widths, 1):
        pairs += [(f"$P{c}N", f"C{c}"), (f"$P{c}B", str(width)),
                  (f"$P{c}R", str(1 << width)), (f"$P{c}E", "0,0")]
    pairs += list((metadata or {}).items())
    stream = "".join(f"{value:0{width}b}"[::-1] if order == "little" else f"{value:0{width}b}"
                     for row in rows for width, value in zip(widths, row))
    # Convert bit-address strings to independent complete-byte integers.
    stream = stream.ljust((len(stream) + 7) // 8 * 8, "0")
    raw = bytes(int(stream[i:i + 8][::-1] if order == "little" else stream[i:i + 8], 2)
                for i in range(0, len(stream), 8))
    begin = 256 + len(text_bytes(pairs))
    end = begin + len(raw) - 1
    pairs = [(k, f"{begin:010d}" if k == "$BEGINDATA" else f"{end:010d}" if k == "$ENDDATA" else v)
             for k, v in pairs]
    header = b"FCS3.1    " + b"".join(f"{x:8d}".encode() for x in [256, begin - 1, begin, end, 0, 0])
    path.write_bytes(header.ljust(256, b" ") + text_bytes(pairs) + raw)


def integers(meta, raw):
    widths = [int(meta[f"$P{i}B"]) for i in range(1, int(meta["$PAR"]) + 1)]
    little = meta["$BYTEORD"] == "1,2,3,4"
    aggregate = int.from_bytes(raw, "little" if little else "big")
    at = 0
    result = []
    for _ in range(int(meta["$TOT"])):
        row = []
        for width in widths:
            shift = at if little else len(raw) * 8 - at - width
            row.append((aggregate >> shift) & ((1 << width) - 1))
            at += width
        result.append(row)
    # Unused final bits must be zero in output.
    unused = len(raw) * 8 - at
    assert (aggregate >> at if little else aggregate & ((1 << unused) - 1)) == 0
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    args = p.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    out = args.directory.resolve()
    commands, cases = [], []

    def cli(command, *paths, options=None, code=0):
        argv = ["node", "tools/fcs.mjs", command, *map(str, paths)]
        if options is not None:
            cfg = out / f"options-{len(commands)}.json"
            cfg.write_text(json.dumps(options), encoding="utf-8")
            argv += ["--options", str(cfg)]
        run = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, code=run.returncode, stdout=run.stdout, stderr=run.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
        assert run.returncode == code, (command, run.stdout, run.stderr)
        if code:
            assert run.stderr and not run.stdout
            return run.stderr
        assert not run.stderr
        return json.loads(run.stdout)

    widths = [1, 10, 12, 14, 18, 20, 65]  # 140 bits/event: cross-event byte boundaries.
    rows = [[0] * 7, [(1 << w) - 1 for w in widths], [1, 513, 2049, 8193, 131073, 524289, (1 << 64) + 3]]
    notes = {"NOTE": "a\x1cb\x1cc", "PREFIX": "\x1cstarts", "UTF8": "中文|a|b"}
    for order in ["little", "big"]:
        path = out / f"packed-{order}.fcs"
        source(path, widths, rows, order, notes)
        expected = [[str(v) for v in row] for row in rows]
        assert cli("values", path, options={"count": 3}) == expected
        chosen = out / f"selected-{order}.fcs"
        cli("subset", path, chosen, options={"events": [2, 0], "channels": [6, 1, 0]})
        meta, raw, _ = decode(chosen)
        projected = [[rows[e][c] for c in [6, 1, 0]] for e in [2, 0]]
        assert integers(meta, raw) == projected
        assert [int(meta[f"$P{i}B"]) for i in [1, 2, 3]] == [65, 10, 1]
        assert [meta[f"$P{i}N"] for i in [1, 2, 3]] == ["C7", "C2", "C1"]
        assert all(meta[k] == v for k, v in notes.items())
        gate = [{"channel": 6, "lower": str(1 << 64), "upper": str((1 << 64) + 4)}]
        assert cli("gate", path, options={"integer_bounds": gate}) == [2]
        cases.append(dict(case="cross-event bits, exact gate and metadata", order=order, sourceValues=21, selectedValues=6))

    # Force printable delimiter; independently decode escaped keys and values.
    metadata = {f"CONTROL{i}": chr(i) + "x" for i in range(1, 32)}
    metadata["KEY WITH SPACE"] = "one two three"
    path = out / "printable-source.fcs"
    source(path, [10], [[511]], "little", metadata)
    rewritten = out / "printable-rewritten.fcs"
    cli("rewrite", path, rewritten)
    meta, raw, sep = decode(rewritten)
    assert sep == b" " and all(meta[k] == v for k, v in metadata.items())
    assert integers(meta, raw) == [[511]]
    cases.append(dict(case="all-control-prefix fallback; escaped keyword/value", delimiter=32))

    # Closed-form inverse: no duplicated elimination algorithm or shared oracle.
    for name, coefficients, expected in [
        ("large", [1e308, 1e308, 1e308, -1e308], [5e-309, 5e-309, 5e-309, -5e-309]),
        ("column-range", [1e308, 1e-308, 1e308, -1e-308], [5e-309, 5e-309, 5e307, -5e307]),
        ("row-range", [1e308, 1e308, 1e-308, -1e-308], [5e-309, 5e307, 5e-309, -5e307]),
    ]:
        path = out / f"matrix-{name}.fcs"
        cli("create", path, options={"names": ["A", "B"], "values": [1, 2], "double_precision": True,
                                    "spillover": {"channels": ["A", "B"], "coefficients": coefficients}})
        actual = cli("compensation", path)
        assert all(math.isclose(x, y, rel_tol=1e-12, abs_tol=0) for x, y in zip(actual, expected))
        cases.append(dict(case="finite extreme inverse", name=name, expected=expected, actual=actual))

    invalid = out / "invalid-matching.fcs"
    cli("create", invalid, options={"names": ["A", "B"], "values": [1, 2],
                                    "spillover": {"channels": ["A", "missing"], "coefficients": [1, .1, .2, 1]}}, code=1)
    assert not invalid.exists()
    singular = out / "singular.fcs"
    cli("create", singular, options={"names": ["A", "B"], "values": [1, 2],
                                    "spillover": {"channels": ["A", "B"], "coefficients": [1, 1, 1, 1]}})
    cli("values", singular, options={"compensated": True}, code=1)
    # Nonfinite spillover metadata is rejected, not confused with nonfinite DATA.
    malformed = out / "nonfinite-matrix.fcs"
    source(malformed, [10, 10], [[1, 2]], "little", {"$SPILLOVER": "2,C1,C2,1,NaN,0,1"})
    cli("validate", malformed, code=1)
    cli("subset", singular, out / "duplicate.fcs", options={"channels": [0, 0]}, code=1)
    cli("values", singular, options={"channels": [0.5]}, code=1)
    assert not (out / "duplicate.fcs").exists()
    cases.append(dict(case="channel mismatch, singular/nonfinite matrix, duplicate/fractional index errors", passed=True))
    raw = (out / "packed-little.fcs").read_bytes()
    nonfinite_data = out / "nonfinite-data.fcs"
    # Independent F/D source construction is not needed: modify a valid D
    # fixture's DATA only, leaving its offsets/shape intact.
    valid = (out / "matrix-large.fcs").read_bytes()
    begin = int(valid[26:34])
    nonfinite_data.write_bytes(valid[:begin] + struct.pack("<dd", float("nan"), 2.0))
    assert cli("values", nonfinite_data) == [["NaN", 2]]
    assert cli("stats", nonfinite_data)[0]["nonfinite"] == 1
    cases.append(dict(case="nonfinite measurement stays visible and counted, not JSON null", passed=True))
    files = ["parse.mbt", "text.mbt", "write.mbt", "compensation.mbt", "encoding.mbt", "events.mbt",
             "cmd/bridge/main.mbt", "tools/fcs.mjs", "tools/check-repair05.py", "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", cases=cases, commands=len(commands), oracle="independent bitstrings/aggregate ints/TEXT delimiter-run parity and closed-form inverse",
                  inputLicense="original MIT synthetic vectors", sourceSha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
