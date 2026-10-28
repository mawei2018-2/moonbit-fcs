"""Explicit event-list boundary/order regression, with optional real consumer.

Code/synthetic inputs MIT; optional RepOD-derived output remains CC BY4.0.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source06", ROOT / "tools/check-repair06.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    p.add_argument("--repod-only", action="store_true", help="only the frozen-population FlowIO consumer; needs dev dependencies")
    args = p.parse_args()
    out = args.directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands, cases = [], []

    def cli(command, *paths, options, code=0):
        cfg = out / f"options-{len(commands)}.json"
        cfg.write_text(json.dumps(options), encoding="utf-8")
        argv = ["node", "tools/fcs.mjs", command, *map(str, paths), "--options", str(cfg)]
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, code=r.returncode, stdout=r.stdout, stderr=r.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
        assert r.returncode == code, (argv, r.stdout, r.stderr)
        if code:
            assert r.stderr and not r.stdout
            return None
        assert not r.stderr
        return json.loads(r.stdout)

    def verify_output(path, expected, name):
        meta, raw, _ = source.oracle.decode(path)
        assert meta["$TOT"] == str(len(expected)) and meta["$P1N"] == name
        assert raw == b"".join(struct.pack("<d", value) for value in expected)

    if args.repod_only:
        import flowio
        import numpy as np
        assert flowio.__version__ == "1.4.0"
        src = ROOT / "examples/repod/titration_CD11c_concat.fcs"
        source_hash = "91097cd6506972e13817bfda617ffa4fd27f81d93618554417ba39346882886c"
        assert digest(src) == source_hash
        meta = flowio.FlowData(src, only_text=True).text
        assert meta["datatype"] == "F" and meta["byteord"] == "1,2,3,4"
        channels, total = int(meta["par"]), int(meta["tot"])
        labels = [meta[f"p{c}n"] for c in range(1, channels + 1)]
        columns = [labels.index(name) for name in ["Time", "FSC-A", "SSC-A"]]
        # From round10's frozen inner population, reordered with a duplicate.
        indices = [14232, 10, 7454, 14232]
        options = {"allow_offset_padding": True, "events": indices}
        assert cli("gate", src, options=options) == indices
        dst = out / "frozen-population-events.fcs"
        cli("subset", src, dst, options=dict(options, channels=["Time", "FSC-A", "SSC-A"],
            drop_analysis=True, drop_spillover=True,
            metadata=[["SOURCE_DOI", "10.18150/JOLWGT"], ["SOURCE_FILE_ID", "96804"], ["SOURCE_POPULATION", "inner"]]))
        original = src.read_bytes()
        begin = int(meta["begindata"])
        expected_raw = b"".join(original[begin + (e * channels + c) * 4:begin + (e * channels + c + 1) * 4]
                                for e in indices for c in columns)
        expected = np.asarray(list(struct.iter_unpack("<fff", expected_raw)))
        # Verify the retained IDs still meet the frozen numeric example bounds.
        assert np.all((expected[:,1] >= 600000) & (expected[:,1] <= 900000) &
                      (expected[:,2] >= 1400000) & (expected[:,2] <= 1800000))
        result = flowio.FlowData(dst)
        assert result.event_count == 4 and result.pnn_labels == ["Time", "FSC-A", "SSC-A"]
        assert np.array_equal(result.as_array(preprocess=False), expected, equal_nan=True)
        encoded = dst.read_bytes()
        actual_raw = encoded[int(result.text["begindata"]):int(result.text["enddata"]) + 1]
        assert actual_raw == expected_raw
        for invalid in [[-1], [total], [indices[0], total]]:
            cli("gate", src, options={"allow_offset_padding": True, "events": invalid}, code=1)
        for name in ["ATTRIBUTION.md", "CC-BY-4.0.txt", "SOURCE.json"]:
            shutil.copyfile(ROOT / "examples/repod" / name, out / name)
        (out / "CHANGES.md").write_text(
            "Bronisz, Agnieszka (2026), Flow Cytometry data, RepOD V2, DOI10.18150/JOLWGT; file96804; CC BY4.0.\n"
            "Changes: frozen inner-population source IDs [14232,10,7454,14232], preserving order and repetition; columns Time/FSC-A/SSC-A.\n"
            "Offsets canonicalized; ANALYSIS/spillover explicitly removed, provenance added. Raw DATA values retained; source unchanged.\n"
            "Numerical format exchange only, no biological interpretation.\n", encoding="utf-8")
        assert digest(src) == source_hash
        cases.append(dict(case="frozen population IDs to FlowIO consumer", sourceIndices=indices,
                          valuesVerified=12, rawBytesVerified=48, sourceSha256=source_hash,
                          outputSha256=digest(dst), externalReader="FlowIO1.4.0 preprocess=False"))
        license_name = "CC BY4.0 RepOD file96804"
    else:
        fixtures = {}
        for n in [0, 1, 3]:
            src = out / f"n{n}.fcs"
            values = list(range(1, n + 1))
            source.write_source(src, ["A"], [64], [100], "D", "L", n, struct.pack("<" + "d" * n, *values))
            fixtures[n] = src
            legal = [[]] + ([[n - 1, 0, n - 1]] if n else [])
            for j, indices in enumerate(legal):
                assert cli("gate", src, options={"events": indices}) == indices
                dst = out / f"n{n}-valid-{j}.fcs"
                cli("subset", src, dst, options={"events": indices})
                verify_output(dst, [values[e] for e in indices], "A")
            for j, indices in enumerate([[-1], [n], [0, n]]):
                cli("gate", src, options={"events": indices}, code=1)
                dst = out / f"n{n}-invalid-{j}.fcs"
                cli("subset", src, dst, options={"events": indices}, code=1)
                assert not dst.exists()
            cases.append(dict(case="bounds and order", events=n, legal=legal))
        second = out / "second.fcs"
        source.write_source(second, ["B"], [64], [100], "D", "L", 1, struct.pack("<d", 9))
        meta, raw, _ = source.oracle.decode(fixtures[3])
        offsets = {"$BEGINDATA", "$ENDDATA", "$NEXTDATA"}
        pairs = [(k, "0000000000" if k in offsets else v) for k, v in meta.items()]
        start = 256 + len(source.oracle.text_bytes(pairs))
        stop, next_dataset = start + len(raw) - 1, start + len(raw)
        replacements = {"$BEGINDATA": start, "$ENDDATA": stop, "$NEXTDATA": next_dataset}
        pairs = [(k, f"{replacements[k]:010d}" if k in offsets else v) for k, v in pairs]
        text = source.oracle.text_bytes(pairs)
        assert 256 + len(text) == start
        header = b"FCS3.1    " + b"".join(f"{n:8d}".encode() for n in [256, start - 1, start, stop, 0, 0])
        chain = out / "chained.fcs"
        chain.write_bytes(header.ljust(256, b" ") + text + raw + second.read_bytes())
        for dataset, indices, expected, name in [(0, [2,0,2], [3,1,3], "A"), (1, [0,0], [9,9], "B")]:
            options = {"dataset": dataset, "events": indices}
            assert cli("gate", chain, options=options) == indices
            dst = out / f"chain-valid-{dataset}.fcs"
            cli("subset", chain, dst, options=options)
            verify_output(dst, expected, name)
        for dataset, invalid in [(0, [3]), (1, [1])]:
            options = {"dataset": dataset, "events": invalid}
            cli("gate", chain, options=options, code=1)
            dst = out / f"chain-invalid-{dataset}.fcs"
            cli("subset", chain, dst, options=options, code=1)
            assert not dst.exists()
        null = out / "null-selection.fcs"
        cli("subset", fixtures[3], null, options={"events": None})
        verify_output(null, [1,2,3], "A")
        cases.append(dict(case="selected dataset owns the event boundary", datasetSizes=[3,1], nullSelectionPreserved=True))
        license_name = "original MIT synthetic inputs"
    pinned = ["cmd/bridge/main.mbt", "tools/fcs.mjs", "pkg.generated.mbti", "gating.mbt", "write.mbt",
              "tools/check-event-selection.py", "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", commands=len(commands), cases=cases, inputLicense=license_name,
                  oracle="explicit event sequences, struct DATA and independent metadata; optional FlowIO raw readback",
                  sourceSha256={name: digest(ROOT / name) for name in pinned})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "commands": len(commands), "cases": cases}))


if __name__ == "__main__":
    main()
