"""Reported statistic columns after full compensation: original MIT consumers.

No old main/suite or RepOD runs. Inputs use independent packed bits/struct;
statistics use Fraction truth and closed-form triangular compensation.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stats_oracle25", ROOT / "tools/check-population-stats.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    out = parser.parse_args().directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands, cases, inputs = [], [], {}
    env = os.environ.copy()
    env.update(NODE_COMPILE_CACHE=str(out / "node-cache"), PYTHONDONTWRITEBYTECODE="1")

    def cli(path, options, code=0):
        cfg = out / f"options-{len(commands)}.json"
        cfg.write_text(json.dumps(options), encoding="utf-8")
        argv = ["node", "tools/fcs.mjs", "population-stats", str(path), "--options", str(cfg)]
        p = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, expectedCode=code, code=p.returncode, stdout=p.stdout, stderr=p.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8")
        assert p.returncode == code, commands[-1]
        if code:
            assert p.stderr and not p.stdout
            return None
        assert not p.stderr
        return json.loads(p.stdout)

    def check(label, path, options, members, names, columns, all_rows):
        result = cli(path, options)
        wanted_keys = {"population", "population_events", "source_event_indices", "channel_names", "scaled", "compensated", "statistics"}
        if columns is not None:
            wanted_keys.add("channel_indices")
            assert result["channel_indices"] == columns
        else:
            columns = list(range(len(names)))
        assert set(result) == wanted_keys, result
        assert result["population"] == options["population"]
        assert result["source_event_indices"] == members and result["population_events"] == len(members)
        assert result["channel_names"] == [names[c] for c in columns]
        assert len(result["statistics"]) == len(columns)
        assert result["scaled"] == bool(options.get("scaled") or options.get("compensated"))
        assert result["compensated"] == bool(options.get("compensated"))
        oracle.verify_stats(result["statistics"], [[row[c] for c in columns] for row in all_rows])
        cases.append(dict(case=label, members=members, reportedChannels=columns))
        return result

    high = 1 << 64
    names = ["Driver", "Target", "ID"]
    rows = [[8, 24, high + 1], [20, 100, high + 6], [12, 20, high + 2],
            [4, 8, high + 3], [40, 400, high + 9]]
    source = out / "new-source-with-analysis.fcs"
    oracle.source(source, names, [16, 16, 65], rows, analysis=True,
                  extra={"$P1G": "2", "$P2G": "4", "$SPILLOVER": "2,Driver,Target,1,0.5,0,1"})
    inputs[str(source)] = digest(source)
    plan = {"gates": [
        {"id": "p", "integer_bounds": [{"channel": "ID", "lower": str(high + 1), "upper": str(high + 4)}]},
        {"id": "empty", "parent": "p", "bounds": [["Driver", -1, 0]]},
    ], "population": "p"}
    members = [0, 2, 3]
    raw_rows = [[float(v) for v in rows[e]] for e in members]
    scaled_rows = [[rows[e][0] / 2, rows[e][1] / 4, float(rows[e][2])] for e in members]
    comp_rows = [[rows[e][0] / 2, (rows[e][1] - rows[e][0]) / 4, float(rows[e][2])] for e in members]
    default = check("unchanged default on new input", source, plan, members, names, None, raw_rows)
    null = check("null retains default format", source, dict(plan, channels=None), members, names, None, raw_rows)
    assert default == null
    check("one raw report channel", source, dict(plan, channels=["Target"]), members, names, [1], raw_rows)
    check("one scaled report channel", source, dict(plan, channels=[1], scaled=True), members, names, [1], scaled_rows)
    result = check("unreported Driver still contributes to Target compensation", source,
                   dict(plan, channels=["Target"], scaled=False, compensated=True), members, names, [1], comp_rows)
    assert result["statistics"][0]["mean"] != sum(row[1] for row in scaled_rows) / len(scaled_rows)
    check("mixed order and repeated report channel", source, dict(plan, channels=["Target", 0, "Target"], compensated=True),
          members, names, [1, 0, 1], comp_rows)
    check("empty report columns keep membership and view", source, dict(plan, channels=[], compensated=True), members, names, [], comp_rows)
    check("empty population retains requested column identity", source, dict(plan, population="empty", channels=["Target"], compensated=True), [], names, [1], [])
    cli(source, dict(plan, population="empty", channels=["missing"]), code=1)
    invalid = [["missing"], [3], [-1], [0.5], ["1"], "Target", {"column": 1}]
    for channels in invalid:
        cli(source, dict(plan, channels=channels), code=1)
    cases.append(dict(case="bad names, indices and shapes including empty population", expectedFailures=len(invalid) + 1))

    duplicate = out / "duplicate-names.fcs"
    oracle.source(duplicate, ["Twin", "Twin"], [64, 64], [[3, 10], [7, 20], [11, 30]], kind="D")
    inputs[str(duplicate)] = digest(duplicate)
    duplicate_plan = {"gates": [{"id": "p", "bounds": [[0, 0, 10]]}], "population": "p"}
    check("numeric positions retain duplicate source labels", duplicate, dict(duplicate_plan, channels=[1, 0]),
          [0, 1], ["Twin", "Twin"], [1, 0], [[3, 10], [7, 20]])
    cli(duplicate, dict(duplicate_plan, channels=["Twin"]), code=1)
    cases.append(dict(case="ambiguous source label rejected without guessing"))

    first = out / "first.fcs"
    oracle.source(first, ["Other"], [64], [[99]], kind="D")
    data = first.read_bytes()
    marker = b"|$NEXTDATA|0000000000|"
    assert data.count(marker) == 1
    chain = out / "chained.fcs"
    chain.write_bytes(data.replace(marker, b"|$NEXTDATA|" + f"{len(data):010d}".encode() + b"|") + source.read_bytes())
    inputs[str(chain)] = digest(chain)
    check("report channel indices belong to selected dataset", chain, dict(plan, dataset=1, channels=["Target", 0], compensated=True),
          members, names, [1, 0], comp_rows)

    # Retain the exact original round25 source/request, now an additive success.
    retained_rows = [[2, 12, high], [4, 8, high + 1], [6, 20, high + 2],
                     [8, 16, high + 3], [10, 28, high + 4], [12, 24, high + 5]]
    retained = out / "retained-round25-channel-request.fcs"
    oracle.source(retained, ["X", "Y", "ID"], [16, 16, 65], retained_rows, analysis=True,
                  extra={"$P1G": "2", "$P2G": "4", "$SPILLOVER": "2,X,Y,1,0.5,0,1"})
    inputs[str(retained)] = digest(retained)
    retained_plan = {"gates": [
        {"id": "selected", "parent": "ids", "bounds": [["Y", 19, 29]]},
        {"id": "ids", "integer_bounds": [{"channel": "ID", "lower": str(high + 1), "upper": str(high + 6)}]},
        {"id": "empty", "parent": "selected", "bounds": [["X", -1, 0]]},
        {"id": "single", "parent": "selected", "bounds": [["X", 10, 11]]},
    ], "population": "selected", "channels": [0]}
    check("round25 unsupported-channel input preserved as new supported request", retained, retained_plan,
          [2, 4, 5], ["X", "Y", "ID"], [0], [retained_rows[e] for e in [2, 4, 5]])

    example_data = json.loads((ROOT / "examples/gate-plan-events.json").read_text(encoding="utf-8"))
    example_names = example_data["names"]
    flat = list(map(int, example_data["integer_values"]))
    example_rows = [flat[i:i + len(example_names)] for i in range(0, len(flat), len(example_names))]
    example = out / "portable-example.fcs"
    oracle.source(example, example_names, example_data["encoding"]["widths"], example_rows)
    inputs[str(example)] = digest(example)
    example_options = json.loads((ROOT / "examples/population-stat-channels.json").read_text(encoding="utf-8"))
    check("portable report-channel example", example, example_options, [2, 5], example_names, [2, 0, 2], [example_rows[e] for e in [2, 5]])

    assert all(digest(Path(path)) == value for path, value in inputs.items())
    assert b"source analysis remains unchanged" in source.read_bytes()
    report = dict(status="passed", commands=len(commands), cases=cases,
                  expectedFailureCommands=sum(c["expectedCode"] == 1 for c in commands), inputLicense="original MIT synthetic inputs",
                  sourceFilesUnchanged=True, inputsSha256=inputs, defaultAndNullReportEqual=True,
                  fullMatrixUnreportedDependencyVerified=True, retainedRound25InputSha256=digest(retained),
                  noOldSuiteOrRepodRun=True,
                  oracle="independent packed bits/struct inputs, Fraction statistics, explicit source indices and closed-form triangular compensation",
                  sourceSha256={name: digest(ROOT / name) for name in ["tools/fcs.mjs", "tools/check-population-stat-channels.py", "tools/check-population-stats.py", "tools/check-repair05.py", "examples/population-stat-channels.json", "events.mbt", "write.mbt", "cmd/bridge/main.mbt", "pkg.generated.mbti", "_build/js/release/build/cmd/bridge/bridge.js"]})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(status="passed", commands=len(commands), cases=len(cases), expectedFailures=report["expectedFailureCommands"])))


if __name__ == "__main__":
    main()
