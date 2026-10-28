"""Compare preflight regression with list-event and histogram consumers.

Original MIT synthetic FCS inputs, independently packed with Python struct.
Only the standard library is required; build the MoonBit JS bridge first.
"""
import argparse
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

    def cli(command, *paths, options=None, code=0):
        argv = ["node", "tools/fcs.mjs", command, *map(str, paths)]
        if options is not None:
            cfg = out / f"options-{len(commands)}.json"
            cfg.write_text(json.dumps(options), encoding="utf-8")
            argv += ["--options", str(cfg)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, expectedCode=code, code=result.returncode,
                             stdout=result.stdout, stderr=result.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8")
        assert result.returncode == code and not result.stderr, (argv, result.stdout, result.stderr)
        return json.loads(result.stdout)

    profiles = [
        ("L1", "L", 2, [0, 1, 1, 0], "little"),
        ("L2", "L", 3, [0, 1, 1, 0, 1, 1], "big"),
        ("C1", "C", 10, [1, 2, 3, 4], "little"),
        ("C2", "C", 20, [2, 4, 6, 8], "big"),
        ("U1", "U", 3, [1, 2, 1, 2], "little"),
        ("U2", "U", 5, [2, 3, 1, 4], "big"),
    ]
    mode_names = {"L": "ListMode", "C": "Correlated", "U": "Uncorrelated"}
    fixtures, reports = {}, {}
    for name, mode, total, values, order in profiles:
        path = out / f"{name}.fcs"
        raw = struct.pack(("<" if order == "little" else ">") + "H" * len(values), *values)
        source.write_source(path, ["A", "B"], [16, 16], [2, 2], "I", mode, total, raw, order)
        fixtures[name] = path
        report = cli("inspect", path)
        assert report["mode"] == mode_names[mode] and int(report["events"]) == total
        assert report["byte_order"] == ("LittleEndian" if order == "little" else "BigEndian")
        assert report["warnings"] == []
        reports[name] = report
    # The fields compared before this fix are identical, although the DATA
    # meanings and operation domains differ. Counts and byte order may differ.
    for report in reports.values():
        for key in ["channels", "datatype", "timestep", "spillover"]:
            assert report[key] == reports["L1"][key]

    for left, right in [("L1", "C1"), ("C1", "L1"), ("L1", "U1"),
                        ("U1", "L1"), ("C1", "U1"), ("U1", "C1")]:
        rows = cli("compare", fixtures[left], fixtures[right], code=2)
        assert [row["compatible"] for row in rows] == [True, False]
        assert [row["mode"] for row in rows] == [reports[left]["mode"], reports[right]["mode"]]
        assert all(row["warnings"] == [] for row in rows)
    cases.append(dict(case="all ordered cross-mode pairs reject compatibility", comparisons=6,
                      modes=list(mode_names.values()), exitCode=2, validJson=True))

    consumers = []
    for mode in ["L", "C", "U"]:
        names = [mode + "1", mode + "2"]
        rows = cli("compare", *(fixtures[name] for name in names))
        assert all(row["compatible"] and row["mode"] == mode_names[mode] for row in rows)
        assert [row["events"] for row in rows] == [reports[name]["events"] for name in names]
        # A caller can use compare as preflight for one operation domain.
        # Consume both accepted files, including the big-endian input, with
        # expectations derived from the explicit source rows/frequencies.
        for name in names:
            if mode == "L":
                groups = cli("populations", fixtures[name], options={
                    "gates": [{"id": "A-is-one", "bounds": [[0, 1, 2]]}]})
                expected = [1] if name == "L1" else [1, 2]
                assert len(groups) == 1
                group = groups[0]
                assert group["id"] == "A-is-one" and group["event_indices"] == expected
                assert group["count"] == len(expected)
                assert group["parent_count"] == group["total_count"] == reports[name]["events"]
                assert group["parent_fraction"] == group["total_fraction"] == len(expected) / reports[name]["events"]
                consumers.append(dict(file=name, operation="populations", sourceEventIndices=expected))
            else:
                expected = {"C1": [4, 6], "C2": [8, 12], "U1": [1, 2], "U2": [2, 3]}[name]
                axis = cli("histogram-axis", fixtures[name], options={"channel": 0})
                assert axis == list(map(str, expected))
                consumers.append(dict(file=name, operation="histogram-axis", exactFrequencies=axis))
    cases.append(dict(case="same-mode counts/data/byte-order differences remain compatible",
                      comparisons=3, acceptedConsumerCalls=6, consumers=consumers))

    rows = cli("compare", *(fixtures[name] for name in ["L1", "L2", "C1", "U1"]), code=2)
    assert [row["compatible"] for row in rows] == [True, True, False, False]
    assert [row["mode"] for row in rows] == ["ListMode", "ListMode", "Correlated", "Uncorrelated"]
    renamed = out / "renamed.fcs"
    source.write_source(renamed, ["Other", "B"], [16, 16], [2, 2], "I", "L", 2,
                        struct.pack("<HHHH", 0, 1, 1, 0))
    rows = cli("compare", fixtures["L1"], renamed, code=2)
    assert [row["compatible"] for row in rows] == [True, False]
    assert all(row["mode"] == "ListMode" for row in rows)
    cases.append(dict(case="multi-file baseline and existing channel mismatch criterion retained"))

    pinned = ["tools/fcs.mjs", "tools/check-compare-mode.py", "tools/check-repair06.py",
              "tools/check-repair05.py", "cmd/bridge/main.mbt", "pkg.generated.mbti",
              "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", commands=len(commands), cases=cases,
                  inputLicense="original MIT synthetic inputs",
                  oracle="Python struct DATA, explicit source event indices and exact histogram sums",
                  scope="Node compare preflight only; no new MoonBit core or public API",
                  sourceSha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in pinned})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "commands": len(commands), "cases": cases}))


if __name__ == "__main__":
    main()
