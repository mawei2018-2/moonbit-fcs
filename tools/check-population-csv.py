"""Direct population CSV integration with struct/Fraction/csv consumers.

Original MIT synthetic inputs; standard-library development check only.
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
    raw_rows = [[4, 12, base], [8, 40, base + 1], [12, 36, base + 2],
                [16, 80, base + 3], [20, 60, base + 4], [24, 120, base + 5]]
    src = out / "source.fcs"
    source.write_source(src, ["A", "B", "ID"], [16, 16, 64], [65536, 65536, 1 << 64],
                        "I", "L", 6, b"".join(struct.pack(">HHQ", *row) for row in raw_rows), "big",
                        {"$P1G": "2", "$P2G": "4", "$SPILLOVER": "2,A,B,1,0.5,0,1"})
    source_hash = hashlib.sha256(src.read_bytes()).hexdigest()
    linear = [[Fraction(a, 2), Fraction(b, 4)] for a, b, uid in raw_rows]
    corrected = [[a, b - a / 2] for a, b in linear]
    members = [i for i, row in enumerate(corrected) if 0 <= row[1] < 11]
    assert members == [0, 1, 2, 4]
    plan = {"gates": [{"id": "band", "compensated": True, "bounds": [["B", 0, 11]]}], "population": "band"}

    def check(label, options, ids, names, expected, input_file=src, population_count=4):
        dst = out / (label + ".csv")
        receipt = cli(input_file, dst, options)
        with dst.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0] == names
        assert [[Fraction(cell) for cell in row] for row in rows[1:]] == expected, label
        assert receipt["events"] == len(expected)
        assert receipt["population"] == options["population"]
        assert receipt["population_events"] == population_count
        assert receipt["source_event_indices"] == ids
        assert receipt["scaled"] is (bool(options.get("scaled")) or bool(options.get("compensated")))
        assert receipt["compensated"] is bool(options.get("compensated"))
        cases.append(dict(case=label, rows=len(expected), sourceIndices=ids))

    check("raw", dict(plan, channels=["ID", "B", "A"]), members, ["ID", "B", "A"],
          [[raw_rows[e][2], raw_rows[e][1], raw_rows[e][0]] for e in members])
    check("compensated-output", dict(plan, channels=["A", "B"], compensated=True), members,
          ["A", "B"], [corrected[e] for e in members])
    check("scaled-output", dict(plan, channels=["A", "B"], scaled=True), members,
          ["A", "B"], [linear[e] for e in members])
    for label, start, count, ids in [("slice-middle", 1, 2, [1, 2]), ("slice-after-gap", 3, 1, [4]),
                                    ("empty-at-end", 4, 0, [])]:
        check(label, dict(plan, channels=["ID"], start=start, count=count), ids, ["ID"],
              [[raw_rows[e][2]] for e in ids])
    empty = {"gates": [{"id": "none", "compensated": True, "bounds": [["B", 100, 200]]}], "population": "none"}
    check("empty-population", dict(empty, channels=["ID"]), [], ["ID"], [], population_count=0)

    # CSV does not rewrite FCS, so valid source ANALYSIS remains untouched.
    meta, raw, _ = source.oracle.decode(src)
    offsets = {"$BEGINDATA", "$ENDDATA", "$BEGINANALYSIS", "$ENDANALYSIS"}
    pairs = [(k, "0000000000" if k in offsets else v) for k, v in meta.items()]
    analysis = source.oracle.text_bytes([("RESULT", "retained-source-analysis")])
    begin = 256 + len(source.oracle.text_bytes(pairs))
    end = begin + len(raw) - 1
    values = {"$BEGINDATA": begin, "$ENDDATA": end, "$BEGINANALYSIS": end + 1, "$ENDANALYSIS": end + len(analysis)}
    pairs = [(k, f"{values[k]:010d}" if k in offsets else v) for k, v in pairs]
    text = source.oracle.text_bytes(pairs)
    header = b"FCS3.1    " + b"".join(f"{v:8d}".encode() for v in [256, begin - 1, begin, end, end + 1, end + len(analysis)])
    with_analysis = out / "with-analysis.fcs"
    with_analysis.write_bytes(header.ljust(256, b" ") + text + raw + analysis)
    analysis_hash = hashlib.sha256(with_analysis.read_bytes()).hexdigest()
    check("source-analysis-retained", dict(plan, channels=["ID"]), members, ["ID"],
          [[raw_rows[e][2]] for e in members], input_file=with_analysis)
    assert hashlib.sha256(with_analysis.read_bytes()).hexdigest() == analysis_hash

    bad = [
        ("unknown-population", dict(plan, population="missing")),
        ("missing-population", {"gates": plan["gates"]}),
        ("missing-gates", {"population": "band"}),
        ("cycle", {"gates": [{"id": "band", "parent": "band", "bounds": [["A", 0, 100]]}], "population": "band"}),
        ("unknown-column", dict(plan, channels=["missing"])),
        ("past-population", dict(plan, start=5, count=0)),
        ("too-many-members", dict(plan, count=5)),
        ("selector-conflict", dict(plan, events=[0])),
    ]
    for label, options in bad:
        dst = out / (label + ".csv")
        cli(src, dst, options, code=1)
        assert not dst.exists(), label
        cases.append(dict(case=label, rejectedBeforeOutput=True))
    # The affected default loop still slices source events without a population.
    default_csv = out / "default-source-slice.csv"
    receipt = cli(src, default_csv, {"channels": ["ID"], "start": 3, "count": 1})
    with default_csv.open(encoding="utf-8", newline="") as f:
        assert list(csv.reader(f)) == [["ID"], [str(base + 3)]]
    assert receipt["events"] == 1 and "population" not in receipt and "source_event_indices" not in receipt
    existing = out / "existing.csv"
    existing.write_bytes(b"keep-existing")
    cli(src, existing, plan, code=1)
    assert existing.read_bytes() == b"keep-existing"
    cases.append(dict(case="default source slice and no-overwrite preserved"))

    # 128 columns make the cell budget 781 rows, then a two-row final chunk.
    wide = out / "wide.fcs"
    n, cols = 783, 128
    labels = [f"C{c:03d}" for c in range(cols)]
    wide_raw = b"".join(struct.pack("<128d", *(r + c / 256 for c in range(cols))) for r in range(n))
    source.write_source(wide, labels, [64] * cols, [262144] * cols, "D", "L", n, wide_raw)
    wide_csv = out / "wide.csv"
    receipt = cli(wide, wide_csv, {"gates": [{"id": "all", "bounds": [["C000", 0, n]]}], "population": "all"})
    assert receipt["events"] == n and receipt["source_event_indices"] == list(range(n))
    with wide_csv.open(encoding="utf-8", newline="") as f:
        table = csv.reader(f)
        assert next(table) == labels
        count = 0
        for r, row in enumerate(table):
            assert len(row) == cols
            assert [Fraction(cell) for cell in row] == [Fraction(r) + Fraction(c, 256) for c in range(cols)]
            count += 1
        assert count == n
    cases.append(dict(case="population spans cross cell-budget boundary", rows=n, columns=cols,
                      valuesVerified=n * cols, chunkRows=100000 // cols))
    assert hashlib.sha256(src.read_bytes()).hexdigest() == source_hash
    pinned = ["tools/fcs.mjs", "tools/check-population-csv.py", "tools/check-repair06.py", "tools/check-repair05.py",
              "gating.mbt", "cmd/bridge/main.mbt", "pkg.generated.mbti", "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", commands=len(commands), cases=cases,
                  inputLicense="original MIT synthetic inputs", oracle="struct/Fraction/csv consumers; explicit source-member positions",
                  inputUnchanged=True, sourceSha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in pinned})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "commands": len(commands), "cases": len(cases), "wideValuesVerified": n * cols}))


if __name__ == "__main__":
    main()
