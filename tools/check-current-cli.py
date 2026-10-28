"""Small current-CLI audit using a 3x3 projection of licensed RepOD file96804.

Original MIT validation code. Source data remains CC BY4.0, not MIT.
Needs FlowIO1.4.0; performs no complete source-event comparison.
"""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path

import flowio

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="new output directory")
    args = parser.parse_args()
    assert flowio.__version__ == "1.4.0", flowio.__version__
    args.directory.mkdir(parents=True, exist_ok=False)
    output = args.directory.resolve()
    source = ROOT / "examples/repod/titration_CD11c_concat.fcs"
    original = source.read_bytes()
    assert digest(original) == "91097cd6506972e13817bfda617ffa4fd27f81d93618554417ba39346882886c"
    metadata = flowio.FlowData(source, only_text=True).text
    assert metadata["datatype"] == "F"
    assert metadata["byteord"] == "1,2,3,4"
    n = int(metadata["par"])
    begin = int(metadata["begindata"])
    source_events, source_channels = [0, 7160, 14319], [2, 0, 1]
    # Independent direct byte projection, not MoonBit creation/readback.
    data = b"".join(
        original[begin + (event * n + channel) * 4:begin + (event * n + channel + 1) * 4]
        for event in source_events for channel in source_channels
    )
    values = [list(row) for row in struct.iter_unpack("<fff", data)]
    pairs = [
        ("$MODE", "L"), ("$DATATYPE", "F"), ("$BYTEORD", "1,2,3,4"),
        ("$PAR", "3"), ("$TOT", "3"), ("$BEGINSTEXT", "0"), ("$ENDSTEXT", "0"),
        ("$BEGINANALYSIS", "0"), ("$ENDANALYSIS", "0"), ("$NEXTDATA", "0"),
        ("$BEGINDATA", "0000000000"), ("$ENDDATA", "0000000000"),
        ("$ORIGINALITY", "Non-Original"), ("SOURCE_DOI", "10.18150/JOLWGT"),
        ("SOURCE_FILE_ID", "96804"),
    ]
    for position, channel in enumerate(source_channels, 1):
        pairs.extend((f"$P{position}{suffix}", metadata[f"p{channel + 1}{suffix.lower()}"])
                     for suffix in ["N", "R", "E"])
        pairs.append((f"$P{position}B", "32"))

    def text():
        return ("|" + "|".join(value.replace("|", "||") for pair in pairs for value in pair) + "|").encode()

    first = 256 + len(text())
    last = first + len(data) - 1
    pairs = [(key, f"{first:010d}" if key == "$BEGINDATA" else f"{last:010d}" if key == "$ENDDATA" else value)
             for key, value in pairs]
    header = b"FCS3.1    " + b"".join(f"{v:8d}".encode() for v in [256, first - 1, first, last, 0, 0])
    tiny = output / "repod-3x3.fcs"
    tiny.write_bytes(header.ljust(256, b" ") + text() + data)
    shutil.copyfile(ROOT / "examples/repod/CC-BY-4.0.txt", output / "CC-BY-4.0.txt")
    (output / "ATTRIBUTION.md").write_text(
        "Bronisz, Agnieszka (2026), Flow Cytometry data, RepOD V2, DOI10.18150/JOLWGT; file96804; CC BY4.0.\n"
        "https://repod.icm.edu.pl/file.xhtml?fileId=96804&version=2.0\n"
        "Changes: events [0,7160,14319], channels [2,0,1]; rebuilt minimal metadata, omitted spillover/ANALYSIS.\n"
        "Further outputs select/reorder this projection. Raw Float32 bytes retained. Numeric exchange only; no clinical inference.\n",
        encoding="utf-8",
    )
    assert flowio.FlowData(tiny).as_array(preprocess=False).tolist() == values
    commands = []

    def cli(command, *files, options=None, status=0):
        command_args = ["node", "tools/fcs.mjs", command, *map(str, files)]
        if options is not None:
            config = output / f"options-{len(commands)}.json"
            config.write_text(json.dumps(options), encoding="utf-8")
            command_args.extend(["--options", str(config)])
        run = subprocess.run(command_args, cwd=ROOT, text=True, capture_output=True, encoding="utf-8")
        commands.append(dict(command=command_args, exitCode=run.returncode, stdout=run.stdout, stderr=run.stderr))
        (output / "COMMANDS.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
        assert run.returncode == status, (run.stdout, run.stderr)
        return json.loads(run.stdout) if status == 0 else run.stderr

    assert cli("validate", tiny, options={"strict": True})["warnings"] == []
    assert cli("values", tiny, options={"count": 3}) == values
    selected = output / "selected-2x2.fcs"
    cli("subset", tiny, selected, options={"events": [2, 0], "channels": [2, 0]})
    expected = [[values[event][channel] for channel in [2, 0]] for event in [2, 0]]
    assert flowio.FlowData(selected).as_array(preprocess=False).tolist() == expected
    rewritten = selected.read_bytes()
    actual_data = rewritten[int(rewritten[26:34]):int(rewritten[34:42]) + 1]
    expected_data = b"".join(data[(event * 3 + channel) * 4:(event * 3 + channel + 1) * 4]
                             for event in [2, 0] for channel in [2, 0])
    assert actual_data == expected_data
    names = [metadata[f"p{i + 1}n"] for i in source_channels]
    assert flowio.FlowData(selected).pnn_labels == [names[2], names[0]]
    assert cli("validate", selected, options={"strict": True})["warnings"] == []
    boundary = output / "last-event.fcs"
    cli("subset", tiny, boundary, options={"events": [2], "channels": [2]})
    assert flowio.FlowData(boundary).as_array(preprocess=False).tolist() == [[values[2][2]]]
    invalid = output / "invalid.fcs"
    assert cli("subset", tiny, invalid, options={"events": [3]}, status=1)
    assert not invalid.exists()
    assert cli("values", tiny, options={"start": -1}, status=1)
    before = selected.read_bytes()
    assert cli("rewrite", tiny, selected, status=1)
    assert selected.read_bytes() == before
    broken = output / "truncated.fcs"
    broken.write_bytes(tiny.read_bytes()[:60])
    assert cli("validate", broken, status=1)
    assert source.read_bytes() == original
    bound_files = ["parse.mbt", "encoding.mbt", "compensation.mbt", "write.mbt", "events.mbt",
                   "cmd/bridge/main.mbt", "pkg.generated.mbti", "tools/fcs.mjs", "tools/check-current-cli.py",
                   "_build/js/release/build/cmd/bridge/bridge.js"]
    report = {
        "status": "passed", "flowio": flowio.__version__,
        "scope": "current CLI, independent raw-byte/struct projection and FlowIO; not full RepOD or universal compatibility",
        "sourceSha256": {name: digest((ROOT / name).read_bytes()) for name in bound_files},
        "inputSha256": digest(original), "sourceEvents": source_events, "sourceChannels": source_channels,
        "sourceValuesCompared": 9, "selectedValuesCompared": 4, "boundaryValuesCompared": 1,
        "sourceValues": values, "selectedValues": expected, "selectedDataBytesExactProjection": True,
        "sourceUnchanged": True, "normalCasesPassed": True, "lastEventBoundaryPassed": True,
        "errorCases": ["out-of-range event rejected without output", "negative start rejected",
                       "existing output preserved", "truncated header rejected"],
        "license": "RepOD file96804 and derived projections CC BY4.0; validation code original MIT",
        "commands": len(commands),
    }
    (output / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
