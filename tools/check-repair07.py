"""Original MIT conversion vectors; Python struct/Fraction and raw bit extraction.

No downloads or external packages. Run after the JS release bridge is built.
"""
import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fcs_oracle06", ROOT / "tools/check-repair06.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
decoder = source.oracle


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    args = p.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    out = args.directory.resolve()
    commands, cases = [], []

    def cli(command, *paths, options=None, code=0):
        argv = ["node", "tools/fcs.mjs", command, *map(str, paths)]
        if options is not None:
            config = out / f"options-{len(commands)}.json"
            config.write_text(json.dumps(options), encoding="utf-8")
            argv += ["--options", str(config)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        commands.append(dict(argv=argv, code=result.returncode, stdout=result.stdout, stderr=result.stderr))
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
        assert result.returncode == code, (command, result.stdout, result.stderr)
        if code:
            assert result.stderr and not result.stdout
            return None
        assert not result.stderr
        return json.loads(result.stdout)

    def decoded(path):
        meta, raw, _ = decoder.decode(path)
        if meta["$DATATYPE"] == "I":
            rows = decoder.integers(meta, raw)  # Storage bits, without applying PnR.
            for row in rows:
                for c, value in enumerate(row, 1):
                    mask = (1 << (int(meta[f"$P{c}R"]) - 1).bit_length()) - 1
                    assert value & mask == value, ("PnR would mask a real value", value, meta)
        else:
            widths = [int(meta[f"$P{c}B"]) for c in range(1, int(meta["$PAR"]) + 1)]
            fields, at = [], 0
            for _ in range(int(meta["$TOT"])):
                row = []
                for width in widths:
                    row.append(int(raw[at:at + width]))
                    at += width
                fields.append(row)
            assert at == len(raw)
            rows = fields
        return meta, rows

    # Independent physical truth: ADC raw/gain; TIME raw ticks with TIMESTEP.
    expected_adc = [int(Fraction(v) / Fraction(1, 2)) for v in [99, 90, 99]]
    expected_time = [198, 180, 198]
    expected_raw = [list(v) for v in zip(expected_time, expected_adc)]
    expected_scaled = [[int(Fraction(t, 2)), a] for t, a in expected_raw]
    for kind in ["F", "D"]:
        for order in ["little", "big"]:
            src = out / f"gain-{kind}-{order}.fcs"
            raw = struct.pack(("<" if order == "little" else ">") + ("f" if kind == "F" else "d") * 4,
                              90, 180, 99, 198)
            source.write_source(src, ["ADC", "TIME"], [32 if kind == "F" else 64] * 2,
                                [100, 100], kind, "L", 2, raw, order,
                                {"$P1G": "0.5", "$TIMESTEP": "0.5"})
            assert cli("values", src, options={"scaled": True}) == [[180, 90], [198, 99]]
            for target in ["I", "A"]:
                dst = out / f"gain-{kind}-{order}-{target}.fcs"
                cli("rewrite", src, dst, options={"events": [1, 0, 1], "channels": [1, 0],
                    "encoding": {"datatype": target, "widths": [9, 9] if target == "I" else [3, 3],
                                 "big_endian": order == "little"}})
                meta, rows = decoded(dst)
                assert rows == expected_raw
                assert meta["$P1N"] == "TIME" and meta["$P2N"] == "ADC"
                assert int(meta["$P1R"]) > max(expected_time) and int(meta["$P2R"]) > max(expected_adc)
                assert meta["$TIMESTEP"] == "0.5" and meta["$P2G"] == "1"
                assert cli("values", dst) == [[str(v) for v in row] for row in expected_raw]
                assert cli("values", dst, options={"scaled": True}) == expected_scaled
                assert cli("gate", dst, options={"integer_bounds": [{"channel": 1, "lower": "198", "upper": "199"}]}) == [0, 2]
                cases.append(dict(case="gain and above-PnR TIME survive selection and conversion", source=kind,
                                  order=order, target=target, raw=rows, scaled=expected_scaled))

    # Positive floating ranges accepted by the current public API must not make
    # a successful write produce integer/ASCII metadata that cannot be read.
    for kind in ["F", "D"]:
        src = out / f"fractional-range-{kind}.fcs"
        source.write_source(src, ["A", "B"], [32 if kind == "F" else 64] * 2,
                            ["2.5", "0.125"], kind, "L", 1,
                            struct.pack("<" + ("ff" if kind == "F" else "dd"), 2, 0))
        for target in ["I", "A"]:
            for empty in [False, True]:
                dst = out / f"fractional-{kind}-{target}-{empty}.fcs"
                cli("rewrite", src, dst, options={"events": [] if empty else [0],
                    "encoding": {"datatype": target, "widths": [8, 8] if target == "I" else [1, 1], "big_endian": True}})
                meta, rows = decoded(dst)
                assert rows == ([] if empty else [[2, 0]])
                assert int(meta["$P1R"]) >= 3 and int(meta["$P2R"]) >= 1
                assert cli("inspect", dst, options={"strict": True})["warnings"] == []
                assert cli("values", dst) == ([] if empty else [["2", "0"]])
                cases.append(dict(case="accepted fractional range to integral range, including empty selection",
                                  source=kind, target=target, empty=empty, raw=rows))

    # Exercise the exact power-of-two boundary and capacity clipping separately.
    for label, value, value_range, width in [("bit-boundary", 256, "100", 9), ("capacity", 255, "10000000000", 8)]:
        src, dst = out / f"{label}.fcs", out / f"{label}-I.fcs"
        source.write_source(src, ["A"], [64], [value_range], "D", "L", 1, struct.pack("<d", value))
        cli("rewrite", src, dst, options={"encoding": {"datatype": "I", "widths": [width]}})
        meta, rows = decoded(dst)
        assert rows == [[value]] and 0 < int(meta["$P1R"]) <= (1 << width)
        assert cli("values", dst) == [[str(value)]]
        cases.append(dict(case=label, raw=rows))

    # All errors must happen before the CLI creates the requested destination.
    gain_source = out / "gain-D-little.fcs"
    for target, width in [("I", 7), ("A", 2)]:
        dst = out / f"error-width-{target}.fcs"
        cli("rewrite", gain_source, dst, options={"encoding": {"datatype": target, "widths": [width, width]}}, code=1)
        assert not dst.exists()
        cases.append(dict(case="insufficient storage is still rejected before output", target=target))
    for label, value, target in [("fraction-I", 1.5, "I"), ("fraction-A", 1.5, "A"),
                                 ("negative-I", -1, "I"), ("infinity-I", float("inf"), "I"),
                                 ("nan-I", float("nan"), "I")]:
        src, dst = out / f"error-{label}-source.fcs", out / f"error-{label}-output.fcs"
        source.write_source(src, ["A"], [64], [100], "D", "L", 1, struct.pack("<d", value))
        cli("rewrite", src, dst, options={"encoding": {"datatype": target, "widths": [16]}}, code=1)
        assert not dst.exists()
        cases.append(dict(case="unrepresentable data rejected before output", vector=label))
    pinned = ["write.mbt", "conversion07_wbtest.mbt", "pkg.generated.mbti", "tools/fcs.mjs",
              "tools/check-repair05.py", "tools/check-repair06.py", "tools/check-repair07.py",
              "_build/js/release/build/cmd/bridge/bridge.js"]
    report = dict(status="passed", cases=cases, commands=len(commands), inputLicense="original MIT synthetic inputs",
                  oracle="struct source bytes; Fraction gain/time; independent raw bit extraction and PnR mask identity",
                  sourceSha256={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in pinned})
    (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "commands": len(commands), "semanticCases": len(cases)}))


if __name__ == "__main__":
    main()
