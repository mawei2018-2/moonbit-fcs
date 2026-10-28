"""Original MIT sparse-compensation vectors with independent closed-form truth.

Python struct creates source DATA; no downloads or external packages.
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
spec = importlib.util.spec_from_file_location("fcs_oracle06", ROOT / "tools/check-repair06.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


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

    def json_number(v):
        return "NaN" if math.isnan(v) else ("Infinity" if v > 0 else "-Infinity") if math.isinf(v) else v

    raw_rows = [(2., float("nan"), 5.), (3., float("inf"), 7.), (4., -float("inf"), 9.)]
    # Explicit algebraic expressions for these three known matrices. We do not
    # implement a second generic floating matrix inverse or copy the product sum.
    vectors = [
        ("identity", [1, 0, 0, 0, 1, 0, 0, 0, 1], lambda a, b, c: [a, b, c]),
        ("independent-block", [1, 0, 0, 0, 1, 0, .5, 0, 1], lambda a, b, c: [a - c / 2, b, c]),
        ("dependent-block", [1, 0, 0, 1, 1, 0, 0, 0, 1], lambda a, b, c: [a - b, b, c]),
    ]
    for kind in ["F", "D"]:
        for order in ["little", "big"]:
            fmt = ("<" if order == "little" else ">") + ("fff" if kind == "F" else "ddd")
            raw = b"".join(struct.pack(fmt, *row) for row in raw_rows)
            for name, matrix, formula in vectors:
                src = out / f"{kind}-{order}-{name}.fcs"
                source.write_source(src, ["A", "B", "C"], [32 if kind == "F" else 64] * 3,
                                    [100] * 3, kind, "L", 3, raw, order,
                                    {"$SPILLOVER": "3,A,B,C," + ",".join(map(str, matrix))})
                expected = [formula(*row) for row in raw_rows]
                assert cli("values", src) == [[json_number(v) for v in row] for row in raw_rows]
                assert cli("values", src, options={"compensated": True}) == [[json_number(v) for v in row] for row in expected]
                stats = cli("stats", src, options={"compensated": True})
                for c, actual in enumerate(stats):
                    finite = [Fraction.from_float(row[c]) for row in expected if math.isfinite(row[c])]
                    assert actual["count"] == len(finite) and actual["nonfinite"] == 3 - len(finite)
                    mean = sum(finite, Fraction(0)) / len(finite) if finite else None
                    variance = sum(((v - mean) ** 2 for v in finite), Fraction(0)) / (len(finite) - 1) if len(finite) > 1 else None
                    for key, value in [("minimum", min(finite) if finite else None), ("maximum", max(finite) if finite else None),
                                       ("mean", mean), ("variance", variance)]:
                        assert actual.get(key) == (float(value) if value is not None else None), (name, c, key, actual)
                indices = [] if name == "dependent-block" else [0, 1] if name == "identity" else [0, 1, 2]
                assert cli("gate", src, options={"compensated": True, "bounds": [[0, -1, 3.5]]}) == indices
                assert cli("gate", src, options={"compensated": True, "x": 0, "y": 2,
                    "vertices": [[-1, 4], [5, 4], [5, 10], [-1, 10]]}) == ([] if name == "dependent-block" else [0, 1, 2])
                cases.append(dict(case=name, source=kind, order=order, expected=[[json_number(v) for v in row] for row in expected],
                                  rectangle=indices, dependency="A unaffected by B" if name != "dependent-block" else "B contributes to A"))

    # Real file consumers of the corrected value/statistics/gate behavior.
    identity = out / "D-little-identity.fcs"
    subset = out / "selected.fcs"
    cli("subset", identity, subset, options={"compensated": True, "bounds": [[0, -1, 3.5]]})
    meta, payload, _ = source.oracle.decode(subset)
    assert meta["$TOT"] == "2"
    original = source.oracle.decode(identity)[1]
    assert payload == original[:2 * 3 * 8], "write must retain original uncompensated DATA bytes"
    assert cli("values", subset, options={"channels": [0, 2], "compensated": True}) == [[2, 5], [3, 7]]
    csv_path = out / "independent-channels.csv"
    cli("csv", identity, csv_path, options={"channels": [0, 2], "compensated": True})
    with csv_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    assert rows == [["A", "C"], ["2", "5"], ["3", "7"], ["4", "9"]]
    # A gate that truly depends on the nonfinite channel still selects nothing.
    dep = out / "D-little-dependent-block.fcs"
    empty = out / "dependent-selection.fcs"
    cli("subset", dep, empty, options={"compensated": True, "bounds": [[0, -1, 3.5]]})
    assert source.oracle.decode(empty)[0]["$TOT"] == "0"
    cases.append(dict(case="subset and CSV consumers preserve independence and raw DATA", selectedEvents=2))
    pinned = ["compensation.mbt", "isolation08_wbtest.mbt", "events.mbt", "write.mbt", "pkg.generated.mbti",
              "tools/fcs.mjs", "tools/check-repair05.py", "tools/check-repair06.py", "tools/check-repair08.py",
              "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", cases=cases, commands=len(commands), inputLicense="original MIT synthetic inputs",
                  oracle="struct source bytes; explicit closed-form identity/triangular-block expressions; exact Fraction statistics",
                  sourceSha256={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in pinned})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "commands": len(commands), "semanticCases": len(cases)}))


if __name__ == "__main__":
    main()
