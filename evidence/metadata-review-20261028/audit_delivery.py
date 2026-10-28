"""Bounded metadata/reordered-FCS audit; original MIT synthetic inputs.

Requires the existing development references FlowIO1.4.0 and NumPy2.5.3.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.project.resolve()
    out = args.directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    import flowio
    import numpy as np
    assert flowio.__version__ == "1.4.0" and np.__version__ == "2.5.3"
    spec = importlib.util.spec_from_file_location("source06", root / "tools/check-repair06.py")
    source = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    commands = []

    def cli(command, *paths, options):
        cfg = out / f"options-{len(commands)}.json"
        cfg.write_text(json.dumps(options), encoding="utf-8")
        argv = ["node", "tools/fcs.mjs", command, *map(str, paths), "--options", str(cfg)]
        result = subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, code=result.returncode, stdout=result.stdout, stderr=result.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8")
        assert result.returncode == 0 and not result.stderr, (argv, result.stdout, result.stderr)
        return json.loads(result.stdout)

    original = [[1.25, 10.5], [2.5, 20.75], [3.75, 30.125]]
    src = out / "source.fcs"
    source.write_source(src, ["A", "B"], [64, 64], [262144, 262144], "D", "L", 3,
                        struct.pack(">6d", *(v for row in original for v in row)), "big",
                        {"NOTE": "original", "SOURCE_SAMPLE": "batch14", "VENDOR_CUSTOM": "retain-me"})
    source_hash = sha(src)
    updates = [["note", "reviewed"], ["SOURCE_FILE_SHA256", source_hash],
               ["SOURCE_EVENTS", "2,0"], ["SOURCE_COLUMNS", "B,A"]]
    dst = out / "selected-with-provenance.fcs"
    cli("subset", src, dst, options={"events": [2, 0], "channels": ["B", "A"], "metadata": updates})
    metadata_pairs = cli("metadata", dst, options={"strict": True})
    metadata = dict(metadata_pairs)
    assert sum(key == "NOTE" for key, value in metadata_pairs) == 1
    expected_metadata = {"NOTE": "reviewed", "SOURCE_SAMPLE": "batch14", "VENDOR_CUSTOM": "retain-me",
                         "SOURCE_FILE_SHA256": source_hash, "SOURCE_EVENTS": "2,0", "SOURCE_COLUMNS": "B,A"}
    assert all(metadata[key] == value for key, value in expected_metadata.items())
    expected = [[original[e][c] for c in [1, 0]] for e in [2, 0]]
    expected_raw = struct.pack(">4d", *(v for row in expected for v in row))
    encoded = dst.read_bytes()
    begin, end = int(encoded[26:34]), int(encoded[34:42])
    assert encoded[begin:end + 1] == expected_raw
    assert metadata["$TOT"] == "2" and metadata["$PAR"] == "2"
    assert [metadata["$P1N"], metadata["$P2N"]] == ["B", "A"]
    result = flowio.FlowData(dst)
    assert result.event_count == 2 and result.pnn_labels == ["B", "A"]
    assert np.array_equal(result.as_array(preprocess=False), np.asarray(expected))
    assert all(result.text[key.lower()] == value for key, value in expected_metadata.items())
    assert sha(src) == source_hash
    pinned = ["write.mbt", "construction.mbt", "text.mbt", "cmd/bridge/main.mbt", "tools/fcs.mjs",
              "tools/check-repair06.py", "tools/check-repair05.py", "pkg.generated.mbti",
              "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", outcome="bounded_review_no_new_defect", commands=len(commands),
                  sourceEventIndices=[2, 0], sourceChannelIndices=[1, 0], sourceChannelNames=["B", "A"],
                  valuesVerified=4, rawBytesVerified=32, expectedValues=expected,
                  metadataVerified=expected_metadata, inputUnchanged=True, inputSha256=source_hash,
                  outputSha256=sha(dst), externalReader="FlowIO1.4.0 preprocess=False / NumPy2.5.3",
                  inputLicense="original MIT synthetic inputs",
                  oracle="Python struct byte projection and explicit source mapping; actual external file consumer",
                  limits=["one combined metadata/reorder path only", "caller-provided provenance is not authenticated identity"],
                  sourceSha256={name: sha(root / name) for name in pinned})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "outcome": report["outcome"], "commands": len(commands),
                      "valuesVerified": 4, "rawBytesVerified": 32, "expectedValues": expected}))


if __name__ == "__main__":
    main()
