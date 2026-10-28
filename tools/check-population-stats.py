"""Population statistics integration: independent bits/struct/Fraction consumers.

Code and synthetic fixtures MIT. Existing RepOD file96804 is CC BY4.0; no download.
No MoonBit tools, FlowIO, NumPy, or package-manager cache is needed.
"""
import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("oracle05", ROOT / "tools/check-repair05.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def source(path, names, widths, rows, kind="I", extra=None, analysis=False, mode="L", ranges=None):
    flat = [v for row in rows for v in row]
    if kind == "I":
        stream = "".join(f"{value:0{width}b}"[::-1] for row in rows for width, value in zip(widths, row))
        stream = stream.ljust((len(stream) + 7) // 8 * 8, "0")
        raw = bytes(int(stream[i:i + 8][::-1], 2) for i in range(0, len(stream), 8))
    else:
        raw = struct.pack("<" + "d" * len(flat), *flat)
    pairs = [("$MODE", mode), ("$DATATYPE", kind), ("$BYTEORD", "1,2,3,4"),
             ("$PAR", str(len(names))), ("$TOT", str(len(rows) if mode == "L" else sum(flat))),
             ("$BEGINSTEXT", "0"), ("$ENDSTEXT", "0"), ("$NEXTDATA", "0000000000")]
    pairs += [(key, "0000000000") for key in ["$BEGINDATA", "$ENDDATA", "$BEGINANALYSIS", "$ENDANALYSIS"]]
    for i, (name, width) in enumerate(zip(names, widths), 1):
        pairs += [(f"$P{i}N", name), (f"$P{i}B", str(width)), (f"$P{i}R", str(ranges[i - 1] if ranges else 1 << width)), (f"$P{i}E", "0,0")]
    pairs += list((extra or {}).items())
    a = oracle.text_bytes([("note", "source analysis remains unchanged")]) if analysis else b""
    start = 256 + len(oracle.text_bytes(pairs))
    stop = start + len(raw) - 1
    ast, ae = (stop + 1, stop + len(a)) if a else (0, 0)
    offsets = {"$BEGINDATA": start, "$ENDDATA": stop, "$BEGINANALYSIS": ast, "$ENDANALYSIS": ae}
    pairs = [(k, f"{offsets[k]:010d}" if k in offsets else v) for k, v in pairs]
    text = oracle.text_bytes(pairs)
    assert len(text) + 256 == start
    header = b"FCS3.1    " + b"".join(f"{n:8d}".encode() for n in [256, start - 1, start, stop, ast, ae])
    path.write_bytes(header.ljust(256, b" ") + text + raw + a)


def expected(values):
    finite = [Fraction.from_float(float(v)) for v in values if math.isfinite(float(v))]
    result = {"count": len(finite), "nonfinite": len(values) - len(finite)}
    if finite:
        mean = sum(finite) / len(finite)
        result.update(minimum=float(min(finite)), maximum=float(max(finite)), mean=float(mean))
        if len(finite) > 1:
            v = sum((x - mean) ** 2 for x in finite) / (len(finite) - 1)
            try:
                value = float(v)
            except OverflowError:
                value = math.inf
            if math.isfinite(value):
                result["variance"] = value
    return result


def verify_stats(actual, rows):
    truth = [expected(list(column)) for column in zip(*rows)] if rows else None
    for c, stat in enumerate(actual):
        wanted = truth[c] if truth else {"count": 0, "nonfinite": 0}
        assert set(stat) == set(wanted), (c, stat, wanted)
        for key, value in wanted.items():
            if key in ["count", "nonfinite"]:
                assert stat[key] == value, (c, key, stat, wanted)
            else:
                assert math.isclose(stat[key], value, rel_tol=2e-12, abs_tol=1e-12), (c, key, stat, wanted)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands, cases = [], []
    env = os.environ.copy()
    env["NODE_COMPILE_CACHE"] = str(out / "node-cache")
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    def cli(command, path, options, code=0):
        option_file = out / f"options-{len(commands)}.json"
        option_file.write_text(json.dumps(options), encoding="utf-8")
        argv = ["node", "tools/fcs.mjs", command, str(path), "--options", str(option_file)]
        r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, expectedCode=code, code=r.returncode, stdout=r.stdout, stderr=r.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8")
        assert r.returncode == code, commands[-1]
        if code:
            assert r.stderr and not r.stdout
            return None
        assert not r.stderr
        return json.loads(r.stdout)

    high = 1 << 64
    rows = [[2, 12, high], [4, 8, high + 1], [6, 20, high + 2],
            [8, 16, high + 3], [10, 28, high + 4], [12, 24, high + 5]]
    base = out / "original-with-analysis.fcs"
    source(base, ["X", "Y", "ID"], [16, 16, 65], rows, analysis=True,
           extra={"$P1G": "2", "$P2G": "4", "$SPILLOVER": "2,X,Y,1,0.5,0,1"})
    base_hash = digest(base)
    plan = {"gates": [
        {"id": "selected", "parent": "ids", "bounds": [["Y", 19, 29]]},
        {"id": "ids", "integer_bounds": [{"channel": "ID", "lower": str(high + 1), "upper": str(high + 6)}]},
        {"id": "empty", "parent": "selected", "bounds": [["X", -1, 0]]},
        {"id": "single", "parent": "selected", "bounds": [["X", 10, 11]]},
    ], "population": "selected"}
    verify_stats(cli("stats", base, {}), rows)

    def check(path, options, indices, names, wanted_rows):
        result = cli("population-stats", path, options)
        assert result["population"] == options["population"]
        assert result["population_events"] == len(indices) and result["source_event_indices"] == indices
        assert result["channel_names"] == names and len(result["statistics"]) == len(names)
        assert result["scaled"] == bool(options.get("scaled") or options.get("compensated"))
        assert result["compensated"] == bool(options.get("compensated"))
        verify_stats(result["statistics"], wanted_rows)
        return result

    members = [2, 4, 5]
    for view in ["raw", "scaled", "compensated"]:
        options = dict(plan)
        if view == "scaled": options["scaled"] = True
        if view == "compensated": options.update(scaled=False, compensated=True)
        wanted = []
        for e in members:
            x, y, identifier = rows[e]
            wanted.append([x if view == "raw" else x / 2,
                           y if view == "raw" else y / 4 - (x / 4 if view == "compensated" else 0),
                           float(identifier)])
        check(base, options, members, ["X", "Y", "ID"], wanted)
        cases.append({"case": "exact-ID membership and full-matrix statistics", "view": view, "members": members})
    scaled_plan = json.loads(json.dumps(plan))
    scaled_plan["gates"][0].update(bounds=[["Y", 4.75, 7.25]], scaled=True)
    check(base, scaled_plan, members, ["X", "Y", "ID"], [rows[e] for e in members])
    check(base, dict(plan, population="empty", compensated=True), [], ["X", "Y", "ID"], [])
    check(base, dict(plan, population="single"), [4], ["X", "Y", "ID"], [rows[4]])
    assert digest(base) == base_hash
    assert b"source analysis remains unchanged" in base.read_bytes()

    nonfinite = out / "nonfinite.fcs"
    source(nonfinite, ["Mask", "Signal"], [64, 64], [[1, math.nan], [2, 3], [3, math.inf], [4, -math.inf], [5, 7]], kind="D")
    finite_plan = {"gates": [{"id": "p", "bounds": [["Mask", 1, 5]]}], "population": "p", "compensated": True}
    check(nonfinite, finite_plan, [0, 1, 2, 3], ["Mask", "Signal"], [[1, math.nan], [2, 3], [3, math.inf], [4, -math.inf]])
    extreme = out / "extreme.fcs"
    source(extreme, ["Mask", "Huge"], [64, 64], [[1, 1e154], [2, -1e154], [3, 0], [9, 0]], kind="D")
    check(extreme, {"gates": [{"id": "p", "bounds": [[0, 1, 4]]}], "population": "p"}, [0, 1, 2], ["Mask", "Huge"], [[1, 1e154], [2, -1e154], [3, 0]])

    first = out / "first.fcs"
    source(first, ["Other"], [64], [[99]], kind="D")
    data = first.read_bytes()
    marker = b"|$NEXTDATA|0000000000|"
    assert data.count(marker) == 1
    chain = out / "chain.fcs"
    chain.write_bytes(data.replace(marker, b"|$NEXTDATA|" + f"{len(data):010d}".encode() + b"|") + base.read_bytes())
    check(chain, dict(plan, dataset=1), members, ["X", "Y", "ID"], [rows[e] for e in members])
    cases += [{"case": "scaled gate/raw statistics separation"}, {"case": "empty and singleton populations"},
              {"case": "nonfinite counts and no-matrix scaled fallback"}, {"case": "finite extreme sample variance"},
              {"case": "nonzero dataset resets private standalone dataset index"}]

    requests = [dict(plan, population="missing"), {"gates": [], "population": "p"},
           dict(plan, start=0), dict(plan, channels=[0]), dict(plan, scaled="yes"), {"gates": []},
           {"gates": [{"id": "a", "parent": "a", "bounds": []}], "population": "a"}]
    for options in requests:
        if "channels" in options:
            # Preserve the round25 input: this formerly unsupported request is
            # the round26 additive feature, so verify its values and identity.
            result = cli("population-stats", base, options)
            assert result["source_event_indices"] == members
            assert result["channel_indices"] == [0] and result["channel_names"] == ["X"]
            verify_stats(result["statistics"], [[rows[e][0]] for e in members])
        elif "start" in options:
            # Keep the original round25 request; round29 now supports its full
            # member window with explicit actual/full-population counts.
            result = cli("population-stats", base, options)
            assert result["events"] == result["population_events"] == len(members)
            assert result["source_event_indices"] == members and result["channel_names"] == ["X", "Y", "ID"]
            verify_stats(result["statistics"], [rows[e] for e in members])
        else:
            cli("population-stats", base, options, code=1)
    hist = out / "histogram.fcs"
    source(hist, ["Bin"], [16], [[1], [2]], mode="C", ranges=[2])
    cli("population-stats", hist, {"gates": [], "population": "p"}, code=1)
    cases.append({"case": "retained channel/window requests now supported; bad plans/options/types and histogram rejected", "expectedFailures": sum(not any(key in row for key in ["channels", "start"]) for row in requests) + 1})

    repod = ROOT / "examples/repod/titration_CD11c_concat.fcs"
    repod_hash = digest(repod)
    assert repod_hash == "91097cd6506972e13817bfda617ffa4fd27f81d93618554417ba39346882886c"
    meta, raw, _ = oracle.decode(repod)
    names = [meta[f"$P{i}N"] for i in range(1, int(meta["$PAR"]) + 1)]
    assert meta["$DATATYPE"] == "F" and all(meta[f"$P{i}B"] == "32" for i in range(1, len(names) + 1))
    fmt = "<f" if meta["$BYTEORD"] == "1,2,3,4" else ">f"
    def value(e, c): return struct.unpack_from(fmt, raw, (e * len(names) + c) * 4)[0]
    xc, yc = names.index("FSC-A"), names.index("SSC-A")
    indices = [e for e in range(int(meta["$TOT"]))
               if 600000 <= value(e, xc) <= 900000 and 1400000 <= value(e, yc) <= 1800000]
    assert len(indices) == 662
    repod_plan = json.loads((ROOT / "examples/repod-gate-plan.json").read_text(encoding="utf-8"))
    report = check(repod, dict(repod_plan, population="inner"), indices, names,
                   [[value(e, c) for c in range(len(names))] for e in indices])
    assert digest(repod) == repod_hash
    for name in ["ATTRIBUTION.md", "CC-BY-4.0.txt", "SOURCE.json"]:
        shutil.copyfile(ROOT / "examples/repod" / name, out / name)
    (out / "REPOD-CHANGES.md").write_text("New population-stats JSON summary for the numeric inner gate; no FCS/CSV output or source changes. Membership independently derived from source F32 scatter coordinates. Original/derived data CC BY4.0, attribution retained; no biological or clinical inference.\n", encoding="utf-8")
    cases.append({"case": "licensed RepOD actual population statistics", "events": 662, "channels": len(names), "valuesUsed": len(indices) * len(names)})
    result = dict(status="passed", commands=len(commands), cases=cases,
                  expectedFailureCommands=sum(c["expectedCode"] == 1 for c in commands),
                  oracle="independent integer bitstream/struct inputs, exact Fraction sample statistics and actual pinned RepOD F32 cells",
                  repod=dict(events=662, channels=len(names), sourceValuesUsed=len(indices) * len(names), sourceSha256=repod_hash, sourceUnchanged=True),
                  analysisSourceUnchanged=digest(base) == base_hash,
                  sourceSha256={name: digest(ROOT / name) for name in ["tools/fcs.mjs", "tools/check-population-stats.py", "tools/check-repair05.py", "events.mbt", "write.mbt", "cmd/bridge/main.mbt", "pkg.generated.mbti", "_build/js/release/build/cmd/bridge/bridge.js"]})
    (out / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "commands": len(commands), "cases": len(cases), "repodEvents": 662, "repodValues": len(indices) * len(names)}))


if __name__ == "__main__":
    main()
