"""Independent new named-plan exchange check. FlowIO/NumPy are dev-only.

Original/derived RepOD data is CC BY4.0, code MIT. No download or old full suite.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import flowio
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    assert not args.report.exists()
    assert flowio.__version__ == "1.4.0"
    src = ROOT / "examples/repod/titration_CD11c_concat.fcs"
    assert digest(src) == "91097cd6506972e13817bfda617ffa4fd27f81d93618554417ba39346882886c"
    original = flowio.FlowData(src)
    a = original.as_array(preprocess=False)
    labels = original.pnn_labels
    x, y = a[:, labels.index("FSC-A")], a[:, labels.index("SSC-A")]
    window = (x >= 500000) & (x < 1000000)
    scatter = window & (y >= 1250000) & (y < 2000000)
    inner = scatter & (x >= 600000) & (x <= 900000) & (y >= 1400000) & (y <= 1800000)
    expected = [np.flatnonzero(mask).tolist() for mask in [window, scatter, inner]]
    out = args.directory.resolve()
    populations = json.loads((out / "populations.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in populations] == ["window", "scatter", "inner"]
    assert [p["event_indices"] for p in populations] == expected
    assert [p["parent_count"] for p in populations] == [len(a), len(expected[0]), len(expected[1])]
    for pop in populations:
        assert pop["count"] == len(pop["event_indices"])
        assert pop["parent_fraction"] == pop["count"] / pop["parent_count"]
        assert pop["total_fraction"] == pop["count"] / len(a)
    selected = out / "selected.fcs"
    result = flowio.FlowData(selected)
    assert result.pnn_labels == ["SSC-A", "FSC-A", "Time"]
    columns = [labels.index(name) for name in result.pnn_labels]
    values = a[inner][:, columns]
    assert np.array_equal(result.as_array(preprocess=False), values, equal_nan=True)
    source_bytes = src.read_bytes()
    begin = int(original.text["begindata"])
    expected_raw = b"".join(source_bytes[begin + (e * len(labels) + c) * 4:begin + (e * len(labels) + c + 1) * 4]
                            for e in expected[2] for c in columns)
    rewritten = selected.read_bytes()
    actual_raw = rewritten[int(result.text["begindata"]):int(result.text["enddata"]) + 1]
    assert actual_raw == expected_raw
    assert result.text["source_doi"] == "10.18150/JOLWGT" and result.text["source_file_id"] == "96804"
    assert int(result.text["beginanalysis"]) == int(result.text["endanalysis"]) == 0
    assert "spillover" not in result.text and "spill" not in result.text
    with (out / "selected.csv").open(encoding="utf-8", newline="") as f:
        csv_rows = list(csv.reader(f))
    assert csv_rows[0] == ["Time", "FSC-A"]
    assert np.array_equal(np.asarray(csv_rows[1:], dtype=np.float64), a[inner][:, [labels.index("Time"), labels.index("FSC-A")]], equal_nan=True)
    for name in ["ATTRIBUTION.md", "CC-BY-4.0.txt", "SOURCE.json"]:
        assert (out / name).read_bytes() == (ROOT / "examples/repod" / name).read_bytes()
    assert (out / "CHANGES.md").is_file()
    node = json.loads((out / "RESULT.json").read_text(encoding="utf-8"))
    assert node["sourceSha256"] == digest(src) and node["selectedSha256"] == digest(selected)
    assert node["sourceWarnings"] and node["sourceEvents"] == len(a)
    names = ["gating.mbt", "cmd/bridge/main.mbt", "tools/fcs.mjs", "pkg.generated.mbti", "examples/repod-gate-plan.json",
             "examples/repod-gate-plan.mjs", "tools/verify-named-repod.py", "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", inputLicense="CC BY4.0 file96804", externalReader="FlowIO1.4.0 preprocess=False",
                  counts=[len(ids) for ids in expected], selectedValuesVerified=int(values.size), rawDataBytesVerified=len(actual_raw),
                  csvValuesVerified=len(expected[2]) * 2, sourceSha256=digest(src), selectedSha256=digest(selected),
                  oracle="explicit NumPy numeric conditions; FlowIO raw values; direct source DATA byte projection",
                  sourceFilesSha256={name: digest(ROOT / name) for name in names})
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "sourceFilesSha256"}))


if __name__ == "__main__":
    main()
