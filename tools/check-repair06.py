"""Original MIT synthetic time/histogram/statistics semantic counterexamples.

Uses Python struct and exact Fraction truth; no downloads or external data.
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
spec = importlib.util.spec_from_file_location("fcs_oracle05", ROOT / "tools/check-repair05.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def write_source(path, names, widths, ranges, kind, mode, total, raw, order="little", extra=None):
    pairs = [("$MODE", mode), ("$DATATYPE", kind), ("$PAR", str(len(names))), ("$TOT", str(total)),
             ("$BYTEORD", "1,2,3,4" if order == "little" else "4,3,2,1"),
             ("$BEGINSTEXT", "0"), ("$ENDSTEXT", "0"), ("$BEGINANALYSIS", "0"),
             ("$ENDANALYSIS", "0"), ("$NEXTDATA", "0"),
             ("$BEGINDATA", "0000000000"), ("$ENDDATA", "0000000000")]
    for c, (name, width, value_range) in enumerate(zip(names, widths, ranges), 1):
        pairs += [(f"$P{c}N", name), (f"$P{c}B", str(width)), (f"$P{c}R", str(value_range)), (f"$P{c}E", "0,0")]
    pairs += list((extra or {}).items())
    first = 256 + len(oracle.text_bytes(pairs))
    last = first + len(raw) - 1
    pairs = [(k, f"{first:010d}" if k == "$BEGINDATA" else f"{last:010d}" if k == "$ENDDATA" else v) for k, v in pairs]
    header = b"FCS3.1    " + b"".join(f"{x:8d}".encode() for x in [256, first - 1, first, last, 0, 0])
    path.write_bytes(header.ljust(256, b" ") + oracle.text_bytes(pairs) + raw)


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
            config = out / f"options-{len(commands)}.json"
            config.write_text(json.dumps(options), encoding="utf-8")
            argv += ["--options", str(config)]
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, code=r.returncode, stdout=r.stdout, stderr=r.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
        assert r.returncode == code, (command, r.stdout, r.stderr)
        if code:
            assert r.stderr and not r.stdout
            return None
        assert not r.stderr
        return json.loads(r.stdout)

    # A calibrated detector must be normalized, whereas Time keeps raw ticks:
    # independently defined input rows Time=[1,2], ADC=[2,4], gainADC=2.
    for kind, order, step in [("F", "little", "0.5"), ("F", "big", "2"),
                              ("D", "little", "2"), ("D", "big", "0.5")]:
        source = out / f"time-{kind}-{order}.fcs"
        raw = struct.pack(("<" if order == "little" else ">") + ("f" if kind == "F" else "d") * 4, 1, 2, 2, 4)
        write_source(source, ["TIME", "ADC"], [32 if kind == "F" else 64] * 2, [262144] * 2,
                     kind, "L", 2, raw, order, {"$TIMESTEP": step, "$P2G": "2"})
        expected_scaled = [[float(step), 1], [2 * float(step), 2]]
        assert cli("values", source, options={"count": 2, "scaled": True}) == expected_scaled
        csv_path = out / f"list-{kind}-{order}.csv"
        cli("csv", source, csv_path, options={"scaled": True})
        with csv_path.open(encoding="utf-8", newline="") as f:
            table = list(csv.reader(f))
        assert table[0] == ["TIME", "ADC"]
        assert [list(map(float, row)) for row in table[1:]] == expected_scaled
        for target in ["I", "A"]:
            destination = out / f"time-{kind}-{order}-to-{target}.fcs"
            cli("rewrite", source, destination, options={"encoding": {"datatype": target, "widths": [10, 10] if target == "I" else [4, 4], "big_endian": order == "little"}})
            meta, payload, _ = oracle.decode(destination)
            if target == "I":
                raw_values = oracle.integers(meta, payload)
            else:
                flat = [int(payload[i:i + 4]) for i in range(0, len(payload), 4)]
                raw_values = [flat[:2], flat[2:]]
            assert raw_values == [[1, 1], [2, 2]]
            assert meta["$TIMESTEP"] == step and meta["$P2G"] == "1"
            assert cli("values", destination, options={"count": 2, "scaled": True}) == expected_scaled
            assert cli("gate", destination, options={"bounds": [[0, 0, 1.5 * float(step)]], "scaled": True}) == [0]
            cases.append(dict(case="Time raw ticks and detector gain", source=kind, order=order, timestep=step, target=target, raw=raw_values, scaled=expected_scaled))

    for mode, values, total, expected_axis in [("C", [1, 2, 3, 4], 10, [4, 6]), ("U", [1, 2, 1, 2], 3, [1, 2])]:
        source = out / f"histogram-{mode}.fcs"
        write_source(source, ["A", "B"], [8, 8], [2, 2], "I", mode, total, bytes(values))
        assert cli("histogram-axis", source, options={"channel": 0}) == list(map(str, expected_axis))
        cli("stats", source, code=1)
        cli("values", source, code=1)
        cli("gate", source, code=1)
        cli("gate", source, options={"bounds": [[0, 0, 2]]}, code=1)
        cli("gate", source, options={"x": 0, "y": 1, "vertices": [[0, 0], [2, 0], [0, 2]]}, code=1)
        csv_path = out / f"histogram-{mode}.csv"
        cli("csv", source, csv_path, options={"count": 0}, code=1)
        assert not csv_path.exists()
        assert cli("histogram", source)["frequencies"] == list(map(str, values))
        cases.append(dict(case="C/U retain histogram APIs and reject event-only analysis", mode=mode))

    groups = [[1e308, -1e308], [1e154, -1e154, 0, 0], [1e154, -1e154, 0, 0, 0],
              [1, 2, 3, 4], [0, 0, 0], [float("nan"), 1e154, -1e154, 0, 0, float("inf")], [1e308], []]
    for index, values in enumerate(groups):
        source = out / f"statistics-{index}.fcs"
        write_source(source, ["A"], [64], [262144], "D", "L", len(values),
                     b"".join(struct.pack("<d", v) for v in values))
        finite = [Fraction.from_float(float(v)) for v in values if math.isfinite(v)]
        mean = sum(finite, Fraction(0)) / len(finite) if finite else None
        variance = sum(((v - mean) ** 2 for v in finite), Fraction(0)) / (len(finite) - 1) if len(finite) > 1 else None
        try:
            expected_variance = float(variance) if variance is not None else None
        except OverflowError:
            expected_variance = None
        result = cli("stats", source)[0]
        assert result["count"] == len(finite) and result["nonfinite"] == len(values) - len(finite)
        if mean is None:
            assert result.get("mean") is None
        else:
            assert math.isclose(result["mean"], float(mean), rel_tol=1e-12, abs_tol=0)
        if expected_variance is None:
            assert result.get("variance") is None
        else:
            assert math.isclose(result["variance"], expected_variance, rel_tol=1e-12, abs_tol=0)
        cases.append(dict(case="exact Fraction statistics", group=index, expectedMean=float(mean) if mean is not None else None,
                          expectedVariance=expected_variance, actualMean=result.get("mean"), actualVariance=result.get("variance")))
    names = ["write.mbt", "events.mbt", "pkg.generated.mbti", "tools/fcs.mjs", "tools/check-repair05.py", "tools/check-repair06.py",
             "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", cases=cases, commands=len(commands), oracle="independent struct ticks/gains; exact Fraction mean/sample variance; documented list-vs-histogram mode",
                  inputLicense="original MIT synthetic inputs", sourceSha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
