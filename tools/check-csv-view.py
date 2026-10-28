"""Calibrated population FCS to CSV: independent values and view receipts.

Original MIT synthetic inputs. Python stdlib only; build the JS bridge first.
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
    commands = []

    def cli(command, *paths, options):
        cfg = out / f"options-{len(commands)}.json"
        cfg.write_text(json.dumps(options), encoding="utf-8")
        argv = ["node", "tools/fcs.mjs", command, *map(str, paths), "--options", str(cfg)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, code=result.returncode, stdout=result.stdout, stderr=result.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8")
        assert result.returncode == 0 and not result.stderr, (argv, result.stdout, result.stderr)
        return json.loads(result.stdout)

    original_rows = [[4, 12], [8, 24], [12, 36]]
    src = out / "calibrated.fcs"
    source.write_source(src, ["A", "B"], [16, 16], [65536, 65536], "I", "L", 3,
                        struct.pack("<6H", *(v for row in original_rows for v in row)),
                        extra={"$P1G": "2", "$P2G": "4", "$SPILLOVER": "2,A,B,1,0.5,0,1"})
    source_hash = hashlib.sha256(src.read_bytes()).hexdigest()
    plan = {"gates": [{"id": "selected", "bounds": [["A", 5, 13]]}]}
    groups = cli("populations", src, options=plan)
    assert len(groups) == 1 and groups[0]["event_indices"] == [1, 2]
    assert groups[0]["count"] == 2 and groups[0]["parent_count"] == groups[0]["total_count"] == 3
    selected = out / "selected.fcs"
    cli("subset", src, selected, options=dict(plan, population="selected"))
    selected_rows = [original_rows[i] for i in [1, 2]]
    meta, raw, _ = source.oracle.decode(selected)
    assert meta["$TOT"] == "2" and [meta["$P1N"], meta["$P2N"]] == ["A", "B"]
    assert raw == struct.pack("<4H", *(v for row in selected_rows for v in row))
    assert [meta["$P1G"], meta["$P2G"]] == ["2", "4"]
    spillover = meta["$SPILLOVER"].split(",")
    assert spillover[:3] == ["2", "A", "B"]
    assert list(map(Fraction, spillover[3:])) == [1, Fraction(1, 2), 0, 1]
    # Closed-form truth, independent of MoonBit value/compensation queries:
    # linear=(rawA/2,rawB/4), S^-1=[[1,-1/2],[0,1]].
    linear = [[Fraction(a, 2), Fraction(b, 4)] for a, b in selected_rows]
    compensated = [[a, b - a / 2] for a, b in linear]
    views = [
        ("raw", {}, selected_rows, False, False),
        ("linear", {"scaled": True}, linear, True, False),
        ("compensated", {"compensated": True}, compensated, True, True),
        ("compensated-explicit-false", {"compensated": True, "scaled": False}, compensated, True, True),
        ("compensated-both-true", {"compensated": True, "scaled": True}, compensated, True, True),
        ("empty-compensated", {"compensated": True, "scaled": False, "start": 2, "count": 0}, [], True, True),
    ]
    cases = []
    for label, options, expected, scaled, comp in views:
        dst = out / (label + ".csv")
        receipt = cli("csv", selected, dst, options=options)
        # Actual downstream consumer parses delivered CSV, not a values query.
        with dst.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["A", "B"]
        actual = [[Fraction(cell) for cell in row] for row in rows[1:]]
        assert actual == expected, (label, actual, expected)
        assert receipt["written"] == str(dst) and receipt["events"] == len(expected)
        assert receipt["scaled"] is scaled and receipt["compensated"] is comp
        cases.append(dict(case=label, rows=len(actual), exactValues=[[str(v) for v in row] for row in actual],
                          scaled=receipt["scaled"], compensated=receipt["compensated"],
                          csvSha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
    assert hashlib.sha256(src.read_bytes()).hexdigest() == source_hash
    pinned = ["tools/fcs.mjs", "tools/check-csv-view.py", "tools/check-repair06.py", "tools/check-repair05.py",
              "events.mbt", "compensation.mbt", "cmd/bridge/main.mbt", "pkg.generated.mbti",
              "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", commands=len(commands), sourceEventIndices=[1, 2],
                  selectedRawBytesVerified=len(raw), cases=cases,
                  oracle="Python struct source projection, Fraction gain and closed-form row-vector inverse, csv consumer",
                  inputLicense="original MIT synthetic inputs", inputUnchanged=True,
                  scope="CSV receipt only; numerical output, core, bridge and public API unchanged",
                  sourceSha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in pinned})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "commands": len(commands), "sourceEventIndices": [1, 2], "cases": cases}))


if __name__ == "__main__":
    main()
