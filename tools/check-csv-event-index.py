"""Optional source-index CSV column with actual DictReader consumers.

Original MIT synthetic inputs. Python stdlib development check only.
"""
import argparse
import csv
from fractions import Fraction
import hashlib
import importlib.util
import json
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
    args = parser.parse_args()
    out = args.directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands, cases = [], []

    def cli(src, dst, options, code=0):
        cfg = out / f"options-{len(commands)}.json"
        cfg.write_text(json.dumps(options), encoding="utf-8")
        argv = ["node", "tools/fcs.mjs", "csv", str(src), str(dst), "--options", str(cfg)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, code=result.returncode, stdout=result.stdout, stderr=result.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8")
        assert result.returncode == code, (argv, result.stdout, result.stderr)
        if code:
            assert result.stderr and not result.stdout
            return None
        assert not result.stderr
        return json.loads(result.stdout)

    base = 1 << 53
    rows = [[10, base], [40, base + 1], [20, base + 2], [50, base + 3], [30, base + 4]]
    src = out / "source.fcs"
    source.write_source(src, ["Signal", "ID"], [16, 64], [65536, 1 << 64], "I", "L", 5,
                        b"".join(struct.pack(">HQ", *row) for row in rows), "big", {"$P1G": "2"})
    original_hash = hashlib.sha256(src.read_bytes()).hexdigest()
    plan = {"gates": [{"id": "band", "bounds": [["Signal", 15, 45]]}], "population": "band"}
    members = [1, 2, 4]

    def check(label, options, expected_indices, names, expected, population=True):
        dst = out / (label + ".csv")
        receipt = cli(src, dst, options)
        index_name = options["event_index_column"]
        with dst.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == [index_name] + names
            table = list(reader)
        assert [int(row[index_name]) for row in table] == expected_indices
        assert [[Fraction(row[name]) for name in names] for row in table] == expected
        # Downstream row sorting must retain the source association in the CSV
        # itself; this consumer does not join a positional JSON receipt.
        by_index = {index: values for index, values in zip(expected_indices, expected)}
        for row in reversed(table):
            assert [Fraction(row[name]) for name in names] == by_index[int(row[index_name])]
        assert receipt["event_index_column"] == index_name and receipt["events"] == len(expected)
        if population:
            assert receipt["source_event_indices"] == expected_indices
        else:
            assert "source_event_indices" not in receipt
        cases.append(dict(case=label, sourceIndices=expected_indices, rows=len(table)))

    options = dict(plan, channels=["ID", "Signal"], event_index_column="source_row")
    expected = [[rows[e][1], rows[e][0]] for e in members]
    check("noncontiguous-population", options, members, ["ID", "Signal"], expected)
    check("population-slice", dict(options, start=1, count=2), [2, 4], ["ID", "Signal"], expected[1:])
    quoted = 'row,"源"\nindex'
    check("escaped-header", dict(options, event_index_column=quoted), members, ["ID", "Signal"], expected)
    check("ordinary-source-range", {"channels": ["ID"], "start": 2, "count": 2, "event_index_column": "row"},
          [2, 3], ["ID"], [[rows[e][1]] for e in [2, 3]], population=False)
    check("index-is-not-compensated", dict(plan, channels=["Signal"], compensated=True, event_index_column="row"),
          members, ["Signal"], [[Fraction(rows[e][0], 2)] for e in members])
    empty = {"gates": [{"id": "none", "bounds": [["Signal", 90, 100]]}], "population": "none",
             "channels": ["ID"], "event_index_column": "row"}
    check("empty-population", empty, [], ["ID"], [])
    # Collision is about actual output fields, not unselected source channels.
    check("unselected-name-allowed", dict(plan, channels=["ID"], event_index_column="Signal"),
          members, ["ID"], [[rows[e][1]] for e in members])
    default = out / "null-default.csv"
    receipt = cli(src, default, {"channels": ["ID"], "event_index_column": None})
    with default.open(encoding="utf-8", newline="") as f:
        assert list(csv.reader(f)) == [["ID"]] + [[str(row[1])] for row in rows]
    assert "event_index_column" not in receipt
    cases.append(dict(case="null keeps original CSV schema", rows=5))
    for label, name in [("empty-name", ""), ("numeric-name", 7), ("array-name", []),
                        ("boolean-name", True), ("selected-name-collision", "Signal")]:
        dst = out / (label + ".csv")
        cli(src, dst, dict(plan, event_index_column=name), code=1)
        assert not dst.exists()
        cases.append(dict(case=label, rejectedBeforeOutput=True))

    # With 127 data columns plus the index, the cell budget is 781 rows.
    # Check every index across the block reset and two scientific sentinels;
    # the unchanged full scientific block suite is intentionally not rerun.
    n, cols = 783, 127
    names = [f"C{c:03d}" for c in range(cols)]
    wide = out / "wide.fcs"
    raw = b"".join(struct.pack("<127d", *(r + c / 256 for c in range(cols))) for r in range(n))
    source.write_source(wide, names, [64] * cols, [262144] * cols, "D", "L", n, raw)
    wide_csv = out / "wide.csv"
    receipt = cli(wide, wide_csv, {"start": 1, "event_index_column": "row"})
    assert receipt["events"] == n - 1 and receipt["event_index_column"] == "row"
    with wide_csv.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ["row"] + names
        count = 0
        for expected_index, row in enumerate(reader, 1):
            assert len(row) == cols + 1 and int(row["row"]) == expected_index
            assert Fraction(row[names[0]]) == expected_index
            assert Fraction(row[names[-1]]) == expected_index + Fraction(cols - 1, 256)
            count += 1
        assert count == n - 1
    cases.append(dict(case="index crosses CSV block boundary", indexValuesVerified=n - 1,
                      scientificSentinelsVerified=2 * (n - 1), chunkRows=100000 // (cols + 1)))
    assert hashlib.sha256(src.read_bytes()).hexdigest() == original_hash
    pinned = ["tools/fcs.mjs", "tools/check-csv-event-index.py", "tools/check-repair06.py", "tools/check-repair05.py",
              "cmd/bridge/main.mbt", "pkg.generated.mbti", "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", commands=len(commands), cases=cases, inputUnchanged=True,
                  inputLicense="original MIT synthetic inputs",
                  oracle="independent struct rows, Fraction calibration and actual DictReader/reordered-row consumer",
                  sourceSha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in pinned})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "commands": len(commands), "cases": len(cases),
                      "crossBlockIndicesVerified": n - 1, "scientificSentinelsVerified": 2 * (n - 1)}))


if __name__ == "__main__":
    main()
