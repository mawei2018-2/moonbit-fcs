"""Original MIT name-resolution/count0 vectors; independent raw integer truth."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

source = load("source06", "tools/check-repair06.py")
bits = load("gate09", "tools/check-gate-plan.py")
BASE = 1 << 64
NAMES = ["FSC-A", "SSC-A", "ID", "0"]
ROWS = [[10, 100, BASE, 7], [20, 10, BASE + 1, 8], [30, 200, BASE + 2, 9], [40, 150, BASE + 3, 10]]
PLAN = {"gates": [
    {"id": "window", "bounds": [["FSC-A", 15, 35]]},
    {"id": "shape", "parent": "window", "x": "FSC-A", "y": "SSC-A", "vertices": [[15, 0], [35, 0], [35, 250], [15, 250]]},
    {"id": "exact", "parent": "shape", "integer_bounds": [{"channel": "ID", "lower": str(BASE + 2), "upper": str(BASE + 4)}]},
]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    out = parser.parse_args().directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands, cases = [], []

    def cli(command, *paths, options=None, code=0):
        argv = ["node", "tools/fcs.mjs", command, *map(str, paths)]
        if options is not None:
            cfg = out / f"options-{len(commands)}.json"
            cfg.write_text(json.dumps(options), encoding="utf-8")
            argv += ["--options", str(cfg)]
        r = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, encoding="utf-8")
        commands.append(dict(argv=argv, code=r.returncode, stdout=r.stdout, stderr=r.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
        assert r.returncode == code, (argv, r.stdout, r.stderr)
        if code:
            assert r.stderr and not r.stdout
            return None
        assert not r.stderr
        return json.loads(r.stdout)

    original = None
    for kind, order, permutation in [("I", "little", [0,1,2,3]), ("I", "big", [0,1,2,3]),
                                     ("I", "little", [2,3,1,0]), ("I", "big", [2,3,1,0]),
                                     ("A", "little", [2,3,1,0]), ("D", "big", [2,3,1,0])]:
        label = f"{kind}-{order}-" + "".join(map(str, permutation))
        src = out / f"{label}.fcs"
        names = [NAMES[c] for c in permutation]
        rows = [[row[c] for c in permutation] for row in ROWS]
        widths = [[8,8,65,8][c] for c in permutation]
        ranges = [[256,256,1 << 65,256][c] for c in permutation]
        if kind == "I":
            raw = bits.packed(rows, widths, order)
        elif kind == "A":
            widths = ["*"] * 4
            raw = " ".join(str(v) for row in rows for v in row).encode()
        else:
            widths, ranges = [64] * 4, [256] * 4
            raw = struct.pack(">16d", *[v for row in rows for v in row])
        source.write_source(src, names, widths, ranges, kind, "L", 4, raw, order)
        if original is None:
            original = src
        plan = PLAN if kind != "D" else {"gates": PLAN["gates"][:2]}
        populations = cli("populations", src, options=plan)
        assert [p["event_indices"] for p in populations] == ([[1,2],[1,2],[2]] if kind != "D" else [[1,2],[1,2]])
        mixed = cli("values", src, options={"count": 1, "channels": ["0", 0]})
        if kind == "D":
            # JSON may spell a large Double as an integral decimal token.
            assert [[float(v) for v in row] for row in mixed] == [[7.0, float(rows[0][0])]]
        else:
            assert mixed == [[str(rows[0][names.index("0")]), str(rows[0][0])]]
        target = "exact" if kind != "D" else "shape"
        expected = [2] if kind != "D" else [1,2]
        selected_names = ["ID", "FSC-A"] if kind != "D" else ["SSC-A", "FSC-A"]
        selection = dict(plan, population=target, channels=selected_names)
        assert cli("gate", src, options=selection) == expected
        dst = out / f"selected-{label}.fcs"
        cli("subset", src, dst, options=selection)
        meta, payload, _ = source.oracle.decode(dst)
        assert [meta["$P1N"], meta["$P2N"]] == selected_names
        selected_truth = [[ROWS[e][NAMES.index(name)] for name in selected_names] for e in expected]
        if kind == "I":
            assert source.oracle.integers(meta, payload) == selected_truth
        elif kind == "A":
            assert list(map(int, payload.split())) == [v for row in selected_truth for v in row]
        else:
            assert list(struct.unpack(">" + "d" * (2 * len(expected)), payload)) == [v for row in selected_truth for v in row]
        csv_path = out / f"{label}.csv"
        cli("csv", src, csv_path, options={"channels": ["0", "FSC-A"]})
        with csv_path.open(encoding="utf-8", newline="") as f:
            table = list(csv.reader(f))
        assert table == [["0", "FSC-A"]] + [[str(row[3]), str(row[0])] for row in ROWS]
        rewritten = out / f"rewritten-{label}.fcs"
        cli("rewrite", src, rewritten, options={"channels": selected_names})
        rm, _, _ = source.oracle.decode(rewritten)
        assert [rm["$P1N"], rm["$P2N"]] == selected_names and rm["$TOT"] == "4"
        cases.append(dict(case="same named plan survives column reordering", kind=kind, order=order, permutation=permutation))

    assert cli("values", original, options={"count": 0, "channels": ["FSC-A"]}) == []
    assert cli("values", original, options={"count": 0, "channels": [0]}) == []
    for channels in [[99], [-1], [0.5], ["missing"], ["fsc-a"], [" FSC-A"], [False], [None], []]:
        cli("values", original, options={"count": 0, "channels": channels}, code=1)
    cli("values", original, options={"count": 0, "channels": None}, code=1)
    # Preserve the existing nullable transform/CSV defaults, distinct from values.
    null_output = out / "null-columns.fcs"
    cli("rewrite", original, null_output, options={"channels": None})
    assert source.oracle.decode(null_output)[0]["$PAR"] == "4"
    null_csv = out / "null-columns.csv"
    cli("csv", original, null_csv, options={"channels": None, "count": 0})
    assert len(list(csv.reader(null_csv.open(encoding="utf-8", newline="")))) == 1
    for command in ["subset", "rewrite", "csv"]:
        dst = out / ("rejected-unknown-" + command)
        cli(command, original, dst, options={"channels": ["missing"], "count": 0}, code=1)
        assert not dst.exists()
    for kind in ["bounds", "vertices", "integer_bounds"]:
        step = {"id": "bad"}
        if kind == "bounds":
            step[kind] = [["missing", 0, 1]]
        elif kind == "vertices":
            step.update(x="missing", y="SSC-A", vertices=[[0,0],[1,0],[0,1]])
        else:
            step[kind] = [{"channel": "missing", "lower": "0", "upper": "1"}]
        dst = out / f"rejected-plan-{kind}.fcs"
        cli("subset", original, dst, options={"gates": [step], "population": "bad"}, code=1)
        assert not dst.exists()
    cases.append(dict(case="count0 validation, exact spelling and nullable defaults"))

    ambiguous = out / "ambiguous.fcs"
    source.write_source(ambiguous, ["A", "A"], [8,8], [4,4], "I", "L", 1, bytes([1,2]))
    assert cli("values", ambiguous, options={"channels": [1]}) == [["2"]]
    assert cli("gate", ambiguous, options={"gates": [{"id": "physical", "bounds": [[1,1.5,2.5]]}], "population": "physical"}) == [0]
    cli("values", ambiguous, options={"count": 0, "channels": ["A"]}, code=1)
    duplicate_csv = out / "ambiguous-name.csv"
    cli("csv", ambiguous, duplicate_csv, options={"channels": ["A"], "count": 0}, code=1)
    assert not duplicate_csv.exists()
    numeric_csv = out / "explicit-numeric.csv"
    cli("csv", ambiguous, numeric_csv, options={"channels": [1]})
    assert list(csv.reader(numeric_csv.open(encoding="utf-8", newline=""))) == [["A"], ["2"]]
    cases.append(dict(case="duplicate PnN remains usable with numeric references"))
    pinned = ["gating.mbt", "cmd/bridge/main.mbt", "tools/fcs.mjs", "pkg.generated.mbti", "names10_wbtest.mbt",
              "tools/check-channel-names.py", "tools/check-gate-plan.py", "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", commands=len(commands), cases=cases, inputLicense="original MIT synthetic data",
                  oracle="explicit source-column identity and hand-worked members; raw bit extraction; actual CSV",
                  sourceSha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in pinned})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "commands": len(commands), "semanticGroups": len(cases)}))


if __name__ == "__main__":
    main()
