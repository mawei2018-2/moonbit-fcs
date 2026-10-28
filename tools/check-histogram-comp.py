"""Original MIT FCS 3.0 I16 vectors, independent of the MoonBit writer.

This reader intentionally covers only these fixed synthetic I16 vectors.
Expected projections are frozen bin sequences, not computed by the library.
"""
import hashlib
import struct
from pathlib import Path

NAMES = ['FL1-A', 'FL2-A', 'FL3-A']
SHAPE = [2, 3, 2]
COMP = '3,0,-1,-2,-3,0,-4,-5,-6,0'
MAPPED_COMP = {'2,0,1': '3,0,-5,-6,-2,0,-1,-4,-3,0',
               '2,0': '2,0,-5,-2,0', '1': '1,0'}
LEXICAL_COMP = '3,+0.000,-0.1000000000000000000001,2.50e-040,+3.000E+04,-0.0,4.1250000000000000000000001,-5e-300,+6.25e+20,0e0'
MAPPED_LEXICAL_COMP = {
    '2,0,1': '3,0e0,-5e-300,+6.25e+20,2.50e-040,+0.000,-0.1000000000000000000001,4.1250000000000000000000001,+3.000E+04,-0.0',
    '2,0': '2,0e0,-5e-300,2.50e-040,+0.000', '1': '1,-0.0',
}
VALUES = {
    'C': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'U': [10, 11, 3, 7, 11, 5, 16],
    'L': [1, 2, 3, 4, 5, 6],
}
TOTAL = {'C': 78, 'U': 21, 'L': 2}
PROJECTIONS = {
    'C': [([2, 0, 1], [1, 7, 2, 8, 3, 9, 4, 10, 5, 11, 6, 12]),
          ([2, 0], [9, 27, 12, 30]), ([1], [18, 26, 34])],
    'U': [([2, 0, 1], [5, 16, 10, 11, 3, 7, 11]),
          ([2, 0], [5, 16, 10, 11]), ([1], [3, 7, 11])],
    'L': [([2, 0, 1], [3, 1, 2, 6, 4, 5])],
}

def make(mode, *, with_comp=True, comp=COMP):
    raw = struct.pack('<' + 'H' * len(VALUES[mode]), *VALUES[mode])
    pairs = [('$MODE', mode), ('$DATATYPE', 'I'), ('$BYTEORD', '1,2,3,4'),
             ('$PAR', '3'), ('$TOT', str(TOTAL[mode])), ('$NEXTDATA', '0'),
             ('$BEGINSTEXT', '0'), ('$ENDSTEXT', '0'),
             ('$BEGINANALYSIS', '0'), ('$ENDANALYSIS', '0'),
             ('$BEGINDATA', '0000000000'), ('$ENDDATA', '0000000000'),
             ('SOURCE', 'Original MIT legacy COMP projection vector')]
    for i, name in enumerate(NAMES, 1):
        pairs += [(f'$P{i}N', name), (f'$P{i}S', 'detector-' + name),
                  (f'$P{i}B', '16'), (f'$P{i}R', str(65536 if mode == 'L' else SHAPE[i-1])),
                  (f'$P{i}E', '0,0')]
    if with_comp:
        pairs.append(('$COMP', comp))
    def text():
        return ('|' + '|'.join(v for pair in pairs for v in pair) + '|').encode('ascii')
    begin = 256 + len(text())
    end = begin + len(raw) - 1
    pairs = [(k, f'{begin:010d}' if k == '$BEGINDATA' else
              f'{end:010d}' if k == '$ENDDATA' else v) for k, v in pairs]
    header = b'FCS3.0    ' + b''.join(f'{v:8d}'.encode('ascii') for v in [256, begin-1, begin, end, 0, 0])
    return header.ljust(256, b' ') + text() + raw

def read(path):
    data = Path(path).read_bytes()
    assert data[:6] in (b'FCS3.0', b'FCS3.1')
    ts, te, ds, de, astart, aend = [int(data[i:i+8]) for i in range(10, 58, 8)]
    assert ts >= 58 and ts <= te < ds <= de == len(data)-1 and astart == aend == 0
    text = data[ts:te+1]
    assert text[:1] == text[-1:] and text[:1] != b''
    fields = text[1:-1].split(text[:1])
    assert len(fields) % 2 == 0
    meta = {fields[i].decode('ascii'): fields[i+1].decode('ascii') for i in range(0, len(fields), 2)}
    assert len(meta)*2 == len(fields)
    assert int(meta['$BEGINDATA']) == ds and int(meta['$ENDDATA']) == de
    n = int(meta['$PAR'])
    assert meta['$DATATYPE'] == 'I' and meta['$BYTEORD'] == '1,2,3,4'
    assert all(meta[f'$P{i}B'] == '16' for i in range(1, n+1))
    raw = data[ds:de+1]
    values = list(struct.unpack('<' + 'H'*(len(raw)//2), raw))
    ranges = [int(meta[f'$P{i}R']) for i in range(1, n+1)]
    mode = meta['$MODE']
    if mode == 'C':
        from math import prod
        assert len(values) == prod(ranges) and sum(values) == int(meta['$TOT'])
    elif mode == 'U':
        assert len(values) == sum(ranges)
        at = 0
        for size in ranges:
            assert sum(values[at:at+size]) == int(meta['$TOT'])
            at += size
    else:
        assert mode == 'L' and len(values) == n*int(meta['$TOT'])
    return meta, values, raw

def verify_projection(path, mode, axes, expected, *, comp):
    meta, values, raw = read(path)
    assert meta['$MODE'] == mode and int(meta['$TOT']) == TOTAL[mode]
    assert int(meta['$PAR']) == len(axes)
    assert [meta[f'$P{i}N'] for i in range(1, len(axes)+1)] == [NAMES[c] for c in axes]
    assert [meta[f'$P{i}S'] for i in range(1, len(axes)+1)] == ['detector-' + NAMES[c] for c in axes]
    assert [int(meta[f'$P{i}R']) for i in range(1, len(axes)+1)] == [65536 if mode == 'L' else SHAPE[c] for c in axes]
    assert meta.get('$COMP') == comp
    if comp is not None:
        from decimal import Decimal
        fields = meta['$COMP'].split(',')
        dimension = int(fields[0])
        assert dimension == len(axes) and len(fields) == 1 + dimension*dimension
        assert all(Decimal(token).is_finite() for token in fields[1:])
    assert values == expected and raw == struct.pack('<'+'H'*len(expected), *expected)
    return {'mode': mode, 'axes': axes, 'names': [NAMES[c] for c in axes],
            'shape': [int(meta[f'$P{i}R']) for i in range(1, len(axes)+1)],
            'frequencies': values, 'COMP': meta.get('$COMP'), 'rawDataSha256': hashlib.sha256(raw).hexdigest()}


def main():
    import argparse
    import json
    import subprocess
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    commands, cases, inputs = [], [], {}
    status = 'failed'

    def cli(command, source, dest=None, options=None, error=None):
        opts = out / f'options-{len(commands):02d}.json'
        opts.write_text(json.dumps({'strict': True, **(options or {})}) + '\n', encoding='utf-8')
        cmd = ['node', 'tools/fcs.mjs', command, str(source)]
        if dest is not None:
            cmd.append(str(dest))
        cmd += ['--options', str(opts)]
        result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding='utf-8')
        commands.append({'command': cmd, 'exitCode': result.returncode,
                         'stdout': result.stdout, 'stderr': result.stderr})
        if error is not None:
            assert result.returncode != 0 and error in result.stderr, commands[-1]
            assert dest is not None and not dest.exists(), str(dest)
        else:
            assert result.returncode == 0, commands[-1]
        return result

    try:
        for mode in ['C', 'U', 'L']:
            source = out / f'{mode}-legacy.fcs'
            source.write_bytes(make(mode))
            inputs[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
            meta, values, raw = read(source)
            assert meta['$COMP'] == COMP and values == VALUES[mode]
            inspected = cli('inspect', source)
            assert json.loads(inspected.stdout)['warnings'] == []
            if mode != 'L':
                histogram = json.loads(cli('histogram', source).stdout)
                assert histogram['shape'] == SHAPE
                assert histogram['frequencies'] == list(map(str, VALUES[mode]))
            # Omitted and explicit identity axes remain legal and preserve COMP and every DATA byte.
            for label, options in [('implicit', {}), ('identity', {'channels': [0, 1, 2]})]:
                dest = out / f'{mode}-{label}.fcs'
                cli('rewrite', source, dest, options)
                case = verify_projection(dest, mode, [0, 1, 2], VALUES[mode], comp=COMP)
                assert read(dest)[2] == raw
                cases.append(dict(case, operation=label, expected='retain opaque COMP and raw DATA'))
            plain = out / f'{mode}-no-comp.fcs'
            plain.write_bytes(make(mode, with_comp=False))
            inputs[plain.name] = hashlib.sha256(plain.read_bytes()).hexdigest()
            mapped_outputs = []
            for number, (axes, expected) in enumerate(PROJECTIONS[mode]):
                default = out / f'{mode}-default-{number}.fcs'
                if mode == 'L':
                    cli('subset', source, default, {'channels': axes},
                        error='legacy COMP requires explicit removal before channel changes')
                    cases.append({'mode': mode, 'axes': axes, 'operation': 'existing list-mode rejection',
                                  'destinationCreated': False})
                else:
                    cli('subset', source, default, {'channels': axes})
                    mapped = MAPPED_COMP[','.join(map(str, axes))]
                    case = verify_projection(default, mode, axes, expected, comp=mapped)
                    cases.append(dict(case, operation='default exact positional COMP projection',
                                      correctedPreviousRejectionExpectation=True))
                    mapped_outputs.append(default)
                removed = out / f'{mode}-drop-{number}.fcs'
                cli('subset', source, removed, {'channels': axes, 'drop_spillover': True})
                case = verify_projection(removed, mode, axes, expected, comp=None)
                assert all(key not in read(removed)[0] for key in ['$COMP', '$SPILL', '$SPILLOVER'])
                cases.append(dict(case, operation='explicit removal'))
                control = out / f'{mode}-control-{number}.fcs'
                cli('subset', plain, control, {'channels': axes})
                case = verify_projection(control, mode, axes, expected, comp=None)
                assert read(control)[2] == read(removed)[2]
                cases.append(dict(case, operation='COMP-free legal projection'))
            if mode != 'L':
                # Consume a produced two-axis file again: the matrix is indexed by its new axes.
                dest = out / f'{mode}-chained.fcs'
                cli('subset', mapped_outputs[1], dest, {'channels': [1, 0]})
                expected = [9, 12, 27, 30] if mode == 'C' else [10, 11, 5, 16]
                case = verify_projection(dest, mode, [0, 2], expected, comp='2,0,-2,-5,0')
                cases.append(dict(case, operation='chained two-axis matrix reorder'))
                # Decimal spelling, signs, negative zero and exponents must survive without Double rounding.
                lexical = out / f'{mode}-lexical.fcs'
                lexical.write_bytes(make(mode, comp=LEXICAL_COMP))
                inputs[lexical.name] = hashlib.sha256(lexical.read_bytes()).hexdigest()
                assert json.loads(cli('inspect', lexical).stdout)['warnings'] == []
                for label, options in [('implicit', {}), ('identity', {'channels': [0, 1, 2]})]:
                    dest = out / f'{mode}-lexical-{label}.fcs'
                    cli('rewrite', lexical, dest, options)
                    case = verify_projection(dest, mode, [0, 1, 2], VALUES[mode], comp=LEXICAL_COMP)
                    cases.append(dict(case, operation='lexical COMP unchanged ' + label))
                for number, (axes, expected) in enumerate(PROJECTIONS[mode]):
                    dest = out / f'{mode}-lexical-mapped-{number}.fcs'
                    cli('subset', lexical, dest, {'channels': axes})
                    mapped = MAPPED_LEXICAL_COMP[','.join(map(str, axes))]
                    case = verify_projection(dest, mode, axes, expected, comp=mapped)
                    cases.append(dict(case, operation='exact lexical COMP projection'))
                dest = out / f'{mode}-lexical-drop.fcs'
                cli('subset', lexical, dest, {'channels': [2, 0], 'drop_spillover': True})
                case = verify_projection(dest, mode, [2, 0], PROJECTIONS[mode][1][1], comp=None)
                cases.append(dict(case, operation='explicit lexical COMP removal'))
                # Unmappable metadata is not a new read/identity restriction; only mapping cannot be inferred.
                unrecognized = ['2,0,-1,-2,-3,0,-4,-5,-6,0',
                                '3,0,-1,-2,-3,0,-4,-5,-6,0,9',
                                'three,0,-1,-2,-3,0,-4,-5,-6,0', 'vendor-specific']
                for number, value in enumerate(unrecognized):
                    unknown = out / f'{mode}-unknown-{number}.fcs'
                    unknown.write_bytes(make(mode, comp=value))
                    inputs[unknown.name] = hashlib.sha256(unknown.read_bytes()).hexdigest()
                    assert json.loads(cli('inspect', unknown).stdout)['warnings'] == []
                    dest = out / f'{mode}-unknown-identity-{number}.fcs'
                    cli('rewrite', unknown, dest)
                    meta, values, raw = read(dest)
                    assert meta['$COMP'] == value and values == VALUES[mode] and raw == read(unknown)[2]
                    cases.append({'mode': mode, 'operation': 'unrecognized COMP identity preserved',
                                  'COMP': value, 'rawDataSha256': hashlib.sha256(raw).hexdigest()})
                    dest = out / f'{mode}-unknown-mapping-{number}.fcs'
                    cli('subset', unknown, dest, {'channels': [2, 0]}, error='unrecognized legacy COMP matrix shape')
                    cases.append({'mode': mode, 'operation': 'unrecognized COMP mapping fails explicitly',
                                  'COMP': value, 'destinationCreated': False})
                    dest = out / f'{mode}-unknown-drop-{number}.fcs'
                    cli('subset', unknown, dest, {'channels': [2, 0], 'drop_spillover': True})
                    case = verify_projection(dest, mode, [2, 0], PROJECTIONS[mode][1][1], comp=None)
                    cases.append(dict(case, operation='explicit unrecognized COMP removal'))
                # Explicit removal never bypasses selector or structural-keyword validation.
                for number, axes in enumerate([[3], [-1], [1, 1]]):
                    dest = out / f'{mode}-bad-axis-{number}.fcs'
                    cli('subset', source, dest, {'channels': axes, 'drop_spillover': True}, error='channel')
                    cases.append({'mode': mode, 'axes': axes, 'operation': 'invalid axis rejected',
                                  'destinationCreated': False})
                dest = out / f'{mode}-reinsert.fcs'
                cli('subset', source, dest, {'channels': [2, 0], 'drop_spillover': True,
                                            'metadata': [['$COMP', COMP]]},
                    error='structural keyword cannot be edited')
                cases.append({'mode': mode, 'operation': 'COMP reinsertion rejected', 'destinationCreated': False})
        assert all(hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
                   for name, digest in inputs.items())
        status = 'passed'
    finally:
        files = ['construction.mbt', 'write.mbt', 'histogram.mbt', 'compensation.mbt',
                 'cmd/bridge/main.mbt', 'tools/check-histogram-comp.py',
                 '_build/js/release/build/cmd/bridge/bridge.js']
        report = {'status': status, 'oracle': 'Frozen complete bin sequences; independent Python struct I16 and HEADER/TEXT reader',
                  'sourceLicense': 'Original MIT synthetic FCS3.0 vectors',
                  'specification': 'https://bioc.r-universe.dev/flowCore/doc/fcs3.html',
                  'legacyMatrix': COMP, 'mappedMatrices': MAPPED_COMP,
                  'lexicalMatrix': LEXICAL_COMP, 'mappedLexicalMatrices': MAPPED_LEXICAL_COMP,
                  'previousCaseCorrection': 'Retain all original 35 cases; change six legal C/U default-rejection expectations to exact successful matrix/DATA assertions',
                  'inputSHA256': inputs,
                  'sourceSHA256': {f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in files},
                  'cases': cases, 'commands': commands}
        (out / 'CHECKS.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': status, 'cases': len(cases), 'publicCLICalls': len(commands),
                      'allSourceBytesUnchanged': True}))


if __name__ == '__main__':
    main()
