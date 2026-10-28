"""ASCII-to-I range/calibration counterexamples and actual gate/CSV consumer.

Original MIT synthetic input; independent ASCII/bit/struct/Fraction truth.
"""
import argparse
import csv
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source06", ROOT / "tools/check-repair06.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--section", choices=["all", "calibration"], default="all", help="calibration resumes after already-checked range vectors")
    args = parser.parse_args()
    out = args.directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands, cases = [], []

    def cli(command, *paths, options=None, code=0):
        cfg = out / f"options-{len(commands)}.json"
        cfg.write_text(json.dumps(options or {}), encoding="utf-8")
        argv = ["node", "tools/fcs.mjs", command, *map(str, paths), "--options", str(cfg)]
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, expectedCode=code, code=r.returncode, stdout=r.stdout, stderr=r.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8")
        assert r.returncode == code, (argv, r.stdout, r.stderr)
        if code:
            assert r.stderr and not r.stdout
            return None
        assert not r.stderr
        return json.loads(r.stdout)

    def ascii_file(name, values, value_range, width=0, label="Signal", extra=None):
        path = out / (name + ".fcs")
        data = (" ".join(map(str, values)) if width == 0 else "".join(f"{value:>{width}}" for value in values)).encode("ascii")
        extras = dict(extra or {})
        amplifier = extras.pop("$P1E", "0,0")
        source.write_source(path, [label], ["*" if width == 0 else width], [value_range], "A", "L", len(values), data, extra=extras)
        if amplifier != "0,0":
            encoded = bytearray(path.read_bytes())
            _, _, delimiter = source.oracle.decode(path)
            needle = delimiter + b"$P1E" + delimiter
            at = encoded.index(needle) + len(needle)
            stop = encoded.index(delimiter, at)
            replacement = amplifier.encode("ascii")
            assert stop - at == len(replacement)  # Test amplifiers keep the byte layout unchanged.
            encoded[at:stop] = replacement
            path.write_bytes(encoded)
        return path

    if args.section != "calibration":
        sources = {}
        for width in [0, 4]:
            src = ascii_file(f"source-{width}", [20, 21, 5], 10, width, extra={"$P1G": "2"})
            sources[width] = src
            for big in [False, True]:
                label = f"w{width}-{'big' if big else 'little'}"
                dst = out / (label + ".fcs")
                cli("rewrite", src, dst, options={"encoding": {"datatype": "I", "widths": [16], "big_endian": big}})
                meta, raw, _ = source.oracle.decode(dst)
                assert meta["$P1R"] == "22" and meta["$P1G"] == "2"
                assert list(struct.unpack((">" if big else "<") + "3H", raw)) == [20, 21, 5]
                mask = (1 << (int(meta["$P1R"]) - 1).bit_length()) - 1
                assert all((value & mask) == value for value in [20, 21, 5])
                assert cli("values", dst, options={"count": 3}) == [["20"], ["21"], ["5"]]
                assert cli("gate", dst, options={"bounds": [[0, 19, 22]]}) == [0, 1]
                scaled = width != 0 or big
                csv_path = out / (label + ".csv")
                cli("csv", dst, csv_path, options={"scaled": scaled})
                with csv_path.open(encoding="utf-8", newline="") as f:
                    rows = list(csv.reader(f))
                assert rows[0] == ["Signal"]
                expected = [Fraction(value, 2 if scaled else 1) for value in [20, 21, 5]]
                assert [Fraction(row[0]) for row in rows[1:]] == expected
                cases.append(dict(case="actual raw/scaled gate and CSV consumer", sourceWidth=width, bigEndian=big,
                                  outputRange=22, csvScaled=scaled, exactValues=[str(v) for v in expected]))

        for label, indices in [("selected-low", [2]), ("empty", [])]:
            dst = out / (label + ".fcs")
            cli("rewrite", sources[0], dst, options={"events": indices, "encoding": {"datatype": "I", "widths": [8]}})
            meta, raw, _ = source.oracle.decode(dst)
            assert meta["$P1R"] == "10" and list(raw) == ([5] if indices else [])
            if indices:
                assert cli("values", dst) == [["5"]]
            else:
                csv_path = out / "empty.csv"
                cli("csv", dst, csv_path)
                with csv_path.open(encoding="utf-8", newline="") as f:
                    assert list(csv.reader(f)) == [["Signal"]]
            cases.append(dict(case="only exported values determine range", selection=indices, outputRange=10))

        one = ascii_file("range-one", [0, 1], 1)
        one_out = out / "range-one-I.fcs"
        cli("rewrite", one, one_out, options={"encoding": {"datatype": "I", "widths": [1]}})
        assert source.oracle.decode(one_out)[0]["$P1R"] == "2"
        assert cli("values", one_out) == [["0"], ["1"]]
        cases.append(dict(case="range1 and one-bit output", outputRange=2))

    log_bad = ascii_file("log-unrepresentable", [20], 10, extra={"$P1E": "2,1"})
    assert cli("values", log_bad, options={"scaled": True}) == [[10000]]
    log_bad_out = out / "log-rejected.fcs"
    cli("rewrite", log_bad, log_bad_out, options={"encoding": {"datatype": "I", "widths": [16]}}, code=1)
    assert not log_bad_out.exists()
    log_ok = ascii_file("log-covered", [20], 17, extra={"$P1E": "2,1"})
    log_out = out / "log-covered-I.fcs"
    cli("rewrite", log_ok, log_out, options={"encoding": {"datatype": "I", "widths": [8]}})
    meta, raw, _ = source.oracle.decode(log_out)
    assert meta["$P1R"] == "17" and meta["$P1E"] == "2,1" and raw == bytes([20])
    measured = cli("values", log_out, options={"scaled": True})[0][0]
    assert math.isclose(measured, 10 ** (40 / 17), rel_tol=1e-12)
    cases.append(dict(case="log range preserved if mask already covers value; otherwise no output", coveredRange=17))

    for label, value in [("too-wide", 300), ("negative", -1)]:
        src = ascii_file(label, [value], 10)
        dst = out / (label + "-rejected.fcs")
        cli("rewrite", src, dst, options={"encoding": {"datatype": "I", "widths": [8]}}, code=1)
        assert not dst.exists()
        cases.append(dict(case="existing unrepresentable storage failure", value=value))

    time = ascii_file("time", [20], 10, label="TiMe", extra={"$P1E": "2,1", "$TIMESTEP": "0.25"})
    time_out = out / "time-I.fcs"
    cli("rewrite", time, time_out, options={"encoding": {"datatype": "I", "widths": [8]}})
    assert source.oracle.decode(time_out)[0]["$P1R"] == "21"
    time_csv = out / "time.csv"
    cli("csv", time_out, time_csv, options={"scaled": True})
    with time_csv.open(encoding="utf-8", newline="") as f:
        assert list(csv.reader(f)) == [["TiMe"], ["5"]]
    cases.append(dict(case="Time tick calibration does not depend on PnR", raw=20, scaled=5))

    value = (1 << 128) + 3
    wide = ascii_file("wide", [value], 10)
    wide_out = out / "wide-I.fcs"
    cli("rewrite", wide, wide_out, options={"encoding": {"datatype": "I", "widths": [129], "big_endian": True}})
    meta, raw, _ = source.oracle.decode(wide_out)
    assert int(meta["$P1R"]) == value + 1
    assert int("".join(f"{byte:08b}" for byte in raw)[:129], 2) == value
    assert cli("values", wide_out) == [[str(value)]]
    wide_csv = out / "wide.csv"
    cli("csv", wide_out, wide_csv)
    with wide_csv.open(encoding="utf-8", newline="") as f:
        assert list(csv.reader(f)) == [["Signal"], [str(value)]]
    cases.append(dict(case="BigInt range expansion", bits=129, outputRange=str(value + 1)))
    pinned = ["write.mbt", "ascii_range23_wbtest.mbt", "tools/check-ascii-to-integer.py", "tools/check-repair06.py",
              "tools/check-repair05.py", "tools/fcs.mjs", "pkg.generated.mbti", "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", section=args.section, commands=len(commands), cases=cases, inputLicense="original MIT synthetic inputs",
                  oracle="independent ASCII/struct/bit/PnR masks, Fraction linear scaling, log formula and actual CSV/gate consumers",
                  sourceSha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in pinned})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "commands": len(commands), "cases": len(cases)}))


if __name__ == "__main__":
    main()
