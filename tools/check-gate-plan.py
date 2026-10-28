"""Original MIT gate-plan oracle: hand-worked memberships and raw integer bits.

No graph resolver, product predicate implementation, downloads or third-party deps.
"""
import argparse
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fcs_source06", ROOT / "tools/check-repair06.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
BASE = 1 << 64
ROWS = [[10, 1, 0, BASE], [20, 2, 5, BASE + 1], [30, 3, 9, BASE + 2],
        [40, 4, 9, BASE + 3], [50, 5, 2, BASE + 4], [20, 4, 8, BASE + 5]]
EXPECTED = [("id_window", "shape", [2, 5], 3), ("high", "window", [2, 3, 5], 4),
            ("window", None, [1, 2, 3, 5], 6), ("shape", "window", [1, 2, 5], 4),
            ("low", "window", [1], 4)]


def packed(rows, widths, order):
    bits = "".join(f"{value:0{width}b}"[::-1] if order == "little" else f"{value:0{width}b}"
                   for row in rows for value, width in zip(row, widths))
    bits = bits.ljust((len(bits) + 7) // 8 * 8, "0")
    return bytes(int(bits[i:i + 8][::-1] if order == "little" else bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def check_populations(actual, expected, total):
    assert len(actual) == len(expected)
    for p, (name, parent, members, denominator) in zip(actual, expected):
        assert p["id"] == name and p.get("parent") == parent
        if parent is None:
            assert "parent" not in p
        assert p["event_indices"] == members
        assert (p["count"], p["parent_count"], p["total_count"]) == (len(members), denominator, total)
        for key, n in [("parent_fraction", denominator), ("total_fraction", total)]:
            if n:
                assert p[key] == float(Fraction(len(members), n))
            else:
                assert key not in p, ("zero-denominator fraction must be absent", p)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    out = p.parse_args().directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands, cases = [], []

    def cli(command, *paths, options=None, code=0):
        argv = ["node", "tools/fcs.mjs", command, *map(str, paths)]
        if options is not None:
            file = out / f"options-{len(commands)}.json"
            file.write_text(json.dumps(options), encoding="utf-8")
            argv += ["--options", str(file)]
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, code=r.returncode, stdout=r.stdout, stderr=r.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
        assert r.returncode == code, (command, r.stdout, r.stderr)
        if code:
            assert r.stderr and not r.stdout
            return None
        assert not r.stderr
        return json.loads(r.stdout)

    plan = json.loads((ROOT / "examples/gate-plan.json").read_text(encoding="utf-8"))
    integer_source = None
    floating_source = None
    for kind, order in [("I", "little"), ("I", "big"), ("A", "little"), ("F", "big"), ("D", "little")]:
        src = out / f"source-{kind}-{order}.fcs"
        if kind == "I":
            widths, ranges = [8, 8, 8, 65], [256, 256, 256, 1 << 65]
            raw = packed(ROWS, widths, order)
        elif kind == "A":
            widths, ranges = ["*"] * 4, [256, 256, 256, 1 << 65]
            raw = " ".join(str(v) for row in ROWS for v in row).encode()
        else:
            widths, ranges = [32 if kind == "F" else 64] * 4, [256] * 4
            raw = struct.pack((">" if order == "big" else "<") + ("f" if kind == "F" else "d") * 24,
                              *[v for row in ROWS for v in row])
        source.write_source(src, ["X", "Y", "M", "ID"], widths, ranges, kind, "L", 6, raw, order)
        current = copy.deepcopy(plan)
        expected = EXPECTED
        if kind in ["F", "D"]:
            # Exact IDs are intentionally unavailable for floating DATA.
            current["gates"] = current["gates"][1:]
            expected = EXPECTED[1:]
            floating_source = src
        else:
            integer_source = src if kind == "I" and order == "big" else integer_source
        check_populations(cli("populations", src, options=current), expected, 6)
        population = "id_window" if kind in ["I", "A"] else "shape"
        members = [2, 5] if population == "id_window" else [1, 2, 5]
        selection = dict(current, population=population, channels=[3, 0, 2])
        assert cli("gate", src, options=selection) == members
        dst = out / f"selected-{kind}-{order}.fcs"
        cli("subset", src, dst, options=selection)
        meta, payload, _ = source.oracle.decode(dst)
        assert meta["$TOT"] == str(len(members))
        assert [meta[f"$P{i}N"] for i in [1, 2, 3]] == ["ID", "X", "M"]
        if kind == "I":
            assert source.oracle.integers(meta, payload) == [[ROWS[e][c] for c in [3, 0, 2]] for e in members]
        elif kind == "A":
            assert list(map(int, payload.split())) == [ROWS[e][c] for e in members for c in [3, 0, 2]]
        else:
            fields = struct.unpack((">" if order == "big" else "<") + ("f" if kind == "F" else "d") * (len(members) * 3), payload)
            expected_float = [struct.unpack((">" if order == "big" else "<") + ("f" if kind == "F" else "d"),
                                           struct.pack((">" if order == "big" else "<") + ("f" if kind == "F" else "d"), ROWS[e][c]))[0]
                              for e in members for c in [3, 0, 2]]
            assert list(fields) == expected_float
        assert cli("inspect", dst, options={"strict": True})["warnings"] == []
        cases.append(dict(case="forward parents and branches", datatype=kind, order=order, selected=members))

    empty = out / "empty.fcs"
    source.write_source(empty, ["X", "Y", "M", "ID"], [8, 8, 8, 65], [256, 256, 256, 1 << 65], "I", "L", 0, b"")
    check_populations(cli("populations", empty, options=plan), [(n, p, [], 0) for n, p, _, _ in EXPECTED], 0)
    assert cli("populations", integer_source, options={"gates": []}) == []
    zero_parent = {"gates": [{"id": "none", "bounds": [[0, 99, 100]]},
                              {"id": "child", "parent": "none", "bounds": [[0, 0, 100]]}]}
    check_populations(cli("populations", integer_source, options=zero_parent), [("none", None, [], 6), ("child", "none", [], 0)], 6)
    cases.append(dict(case="empty data/plan/parent have defined denominators"))

    timed = out / "timed.fcs"
    source.write_source(timed, ["TIME", "A", "B"], [64] * 3, [100] * 3, "D", "L", 3,
                        struct.pack("<9d", 1, 10, 15, 2, 20, 35, 3, 30, 65),
                        extra={"$TIMESTEP": "0.5", "$SPILLOVER": "2,A,B,1,1,0,1"})
    views = {"gates": [{"id": "time", "scaled": True, "bounds": [[0, .5, 1.5]]},
                        {"id": "corrected", "parent": "time", "compensated": True, "bounds": [[2, 10, 20]]},
                        {"id": "raw", "parent": "time", "bounds": [[2, 10, 20]]}]}
    check_populations(cli("populations", timed, options=views), [("time", None, [0, 1], 3), ("corrected", "time", [1], 2), ("raw", "time", [0], 2)], 3)
    timed_out = out / "timed-selected.fcs"
    cli("subset", timed, timed_out, options=dict(views, population="corrected"))
    assert source.oracle.decode(timed_out)[1] == struct.pack("<3d", 2, 20, 35)
    cases.append(dict(case="per-step time scaling and compensation preserve raw subset bytes"))

    nf = out / "nonfinite.fcs"
    source.write_source(nf, ["A", "B", "C"], [64] * 3, [100] * 3, "D", "L", 3,
                        struct.pack("<9d", 2, float("nan"), 5, 3, float("inf"), 7, 4, -float("inf"), 9),
                        extra={"$SPILLOVER": "3,A,B,C,1,0,0,0,1,0,0,0,1"})
    nf_plan = {"gates": [{"id": "a", "compensated": True, "bounds": [[0, 1, 4]]},
                          {"id": "ac", "parent": "a", "compensated": True, "x": 0, "y": 2,
                           "vertices": [[1, 4], [5, 4], [5, 10], [1, 10]]}]}
    check_populations(cli("populations", nf, options=nf_plan), [("a", None, [0, 1], 3), ("ac", "a", [0, 1], 2)], 3)
    cases.append(dict(case="repair08 independent channels work inside a plan"))

    # A population selector must retain write's ANALYSIS invalidation gate.
    original_meta, original_raw, _ = source.oracle.decode(integer_source)
    offsets = {"$BEGINDATA", "$ENDDATA", "$BEGINANALYSIS", "$ENDANALYSIS"}
    pairs = [(k, "0000000000" if k in offsets else v) for k, v in original_meta.items()]
    analysis = source.oracle.text_bytes([("NOTE", "selection invalidates this analysis")])
    data_start = 256 + len(source.oracle.text_bytes(pairs))
    data_end = data_start + len(original_raw) - 1
    analysis_start, analysis_end = data_end + 1, data_end + len(analysis)
    values = {"$BEGINDATA": data_start, "$ENDDATA": data_end,
              "$BEGINANALYSIS": analysis_start, "$ENDANALYSIS": analysis_end}
    pairs = [(k, f"{values[k]:010d}" if k in values else v) for k, v in pairs]
    text = source.oracle.text_bytes(pairs)
    assert 256 + len(text) == data_start
    header = b"FCS3.1    " + b"".join(f"{n:8d}".encode() for n in [256, data_start - 1, data_start, data_end, analysis_start, analysis_end])
    with_analysis = out / "with-analysis.fcs"
    with_analysis.write_bytes(header.ljust(256, b" ") + text + original_raw + analysis)
    refused = out / "analysis-must-not-be-silently-dropped.fcs"
    selection = dict(plan, population="id_window", channels=[3, 0, 2])
    cli("subset", with_analysis, refused, options=selection, code=1)
    assert not refused.exists()
    dropped = out / "analysis-explicitly-dropped.fcs"
    cli("subset", with_analysis, dropped, options=dict(selection, drop_analysis=True))
    meta, payload, _ = source.oracle.decode(dropped)
    assert int(meta["$BEGINANALYSIS"]) == int(meta["$ENDANALYSIS"]) == 0
    assert len(dropped.read_bytes()) == int(meta["$ENDDATA"]) + 1
    assert source.oracle.integers(meta, payload) == [[BASE + 2, 30, 9], [BASE + 5, 20, 8]]
    cases.append(dict(case="ANALYSIS requires explicit removal on population subset"))

    basic = {"id": "window", "bounds": [[0, 15, 45]]}
    bad = [
        ("duplicate", {"gates": [basic, basic]}),
        ("empty-id", {"gates": [dict(basic, id="")]}),
        ("unknown-parent", {"gates": [dict(basic, parent="missing")]}),
        ("cycle", {"gates": [dict(basic, id="a", parent="b"), dict(basic, id="b", parent="a")]}),
        ("self-cycle", {"gates": [dict(basic, parent="window")]}),
        ("unknown-population", dict(plan, population="missing")),
        ("no-population", dict(plan, population=None)),
        ("no-gates", {"population": "window"}),
        ("events-conflict", dict(plan, events=[0])),
        ("bounds-conflict", dict(plan, bounds=[[0, 0, 100]])),
        ("multiple-predicates", {"gates": [dict(basic, integer_bounds=[{"channel": 0, "lower": "0", "upper": "100"}])]}),
        ("unknown-option", {"gates": [dict(basic, parents="missing")]}),
        ("fractional-channel", {"gates": [dict(basic, bounds=[[.5, 0, 100]])]}),
        ("fractional-x", {"gates": [{"id": "window", "x": .5, "y": 1, "vertices": [[0, 0], [100, 0], [0, 100]]}]}),
        ("fractional-exact", {"gates": [{"id": "window", "integer_bounds": [{"channel": .5, "lower": "0", "upper": "100"}]}]}),
        ("top-scaled", dict(plan, scaled=True)),
        ("top-compensated", dict(plan, compensated=False)),
        ("exact-scaled", {"gates": [{"id": "window", "scaled": True, "integer_bounds": [{"channel": 0, "lower": "0", "upper": "100"}]}]}),
        ("exact-compensated", {"gates": [{"id": "window", "compensated": True, "integer_bounds": [{"channel": 0, "lower": "0", "upper": "100"}]}]}),
        ("empty-exact", {"gates": [{"id": "window", "integer_bounds": []}]}),
        ("empty-bounds", {"gates": [dict(basic, bounds=[])]}),
        ("backwards-bounds", {"gates": [dict(basic, bounds=[[0, 20, 10]])]}),
        ("short-bounds", {"gates": [dict(basic, bounds=[[0, 20]])]}),
        ("nonpolygon-xy", {"gates": [dict(basic, x=0, y=1)]}),
        ("empty-parent-invalid-child", {"gates": [zero_parent["gates"][0], {"id": "window", "parent": "none", "bounds": [[99, 0, 1]]}]}),
        ("nonboolean-view", {"gates": [dict(basic, scaled="yes")]}),
    ]
    for label, options in bad:
        options = copy.deepcopy(options)
        options.setdefault("population", "window")
        destination = out / f"rejected-{label}.fcs"
        cli("subset", integer_source, destination, options=options, code=1)
        assert not destination.exists(), label
        cases.append(dict(case="rejected before output", vector=label))
    for mode, values, total in [("C", [1, 2, 3, 4], 10), ("U", [1, 2, 1, 2], 3)]:
        src = out / f"hist-{mode}.fcs"
        source.write_source(src, ["A", "B"], [8, 8], [2, 2], "I", mode, total, bytes(values))
        cli("populations", src, options={"gates": []}, code=1)
        dst = out / f"rejected-hist-{mode}.fcs"
        cli("subset", src, dst, options={"gates": [basic], "population": "window"}, code=1)
        assert not dst.exists()
        cases.append(dict(case="histogram is not an event plan", mode=mode))
    dst = out / "rejected-floating-exact.fcs"
    cli("subset", floating_source, dst, options=dict(plan, population="id_window"), code=1)
    assert not dst.exists()
    cases.append(dict(case="exact plan requires I/A DATA"))
    pinned = ["gating.mbt", "gating_wbtest.mbt", "cmd/bridge/main.mbt", "tools/fcs.mjs", "pkg.generated.mbti",
              "compensation.mbt", "events.mbt", "write.mbt", "tools/check-gate-plan.py", "examples/gate-plan.json",
              "examples/gate-plan-events.json", "examples/run-gate-plan.mjs", "examples/gate-plan-consumer/main.mbt",
              "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", cases=cases, commands=len(commands), inputLicense="original MIT synthetic data",
                  oracle="explicit hand-worked membership sets; Fraction denominators; struct and raw bit extraction",
                  sourceSha256={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in pinned})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "commands": len(commands), "cases": len(cases)}))


if __name__ == "__main__":
    main()
