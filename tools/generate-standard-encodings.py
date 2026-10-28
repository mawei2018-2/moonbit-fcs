"""Original, redistributable vectors built with Python integers/ASCII, not Moon FCS.

The 12-bit hand vector is bcfade (LE) / abcdef (BE). Other integers use
one Python arbitrary integer for the complete DATA stream, independently of
the MoonBit per-field reader. Do not overwrite earlier fixture collections.
"""
from pathlib import Path
import base64, hashlib, json, sys

ROOT = Path(__file__).resolve().parents[1]

def fcs(kind, widths, rows, payload, order='little', ranges=None):
    if kind == 'A' and ranges is None:
        ranges = [max(10**20, max(row[c] for row in rows)+1) for c in range(len(widths))]
    pairs = [('$MODE', 'L'), ('$DATATYPE', kind), ('$BYTEORD', '1,2,3,4' if order == 'little' else '4,3,2,1'),
             ('$PAR', str(len(widths))), ('$TOT', str(len(rows))), ('$NEXTDATA', '0'),
             ('$BEGINSTEXT', '0'), ('$ENDSTEXT', '0'), ('$BEGINANALYSIS', '0'), ('$ENDANALYSIS', '0'),
             ('$BEGINDATA', '0000000000'), ('$ENDDATA', '0000000000'), ('NOTE', 'Original normative encoding example')]
    for i, width in enumerate(widths, 1):
        pairs += [(f'$P{i}N', f'C{i}'), (f'$P{i}B', str(width)),
                  (f'$P{i}R', str(ranges[i-1] if ranges else 2**width if kind == 'I' else 10**20)), (f'$P{i}E', '0,0')]
    encode = lambda: ('|' + '|'.join(value for pair in pairs for value in pair) + '|').encode('ascii')
    first = 256 + len(encode())
    pairs = [(key, f'{first:010d}' if key == '$BEGINDATA' else f'{first+len(payload)-1:010d}' if key == '$ENDDATA' else value) for key, value in pairs]
    text = encode()
    header = b'FCS3.1    ' + b''.join(f'{n:08d}'.encode() for n in [256, first-1, first, first+len(payload)-1, 0, 0])
    return header.ljust(256, b' ') + text + payload

def binary(widths, rows, order):
    bits = sum(widths) * len(rows)
    if order == 'little':
        value, offset = 0, 0
        for row in rows:
            for n, width in zip(row, widths):
                value |= n << offset
                offset += width
        return value.to_bytes((bits + 7)//8, 'little')
    stream = ''.join(f'{n:0{width}b}' for row in rows for n, width in zip(row, widths))
    return int(stream.ljust((bits + 7)//8*8, '0') or '0', 2).to_bytes((bits+7)//8, 'big')

def vectors():
    result = []
    def add(name, kind, widths, rows, raw, order='little', ranges=None, selection=None):
        contents = fcs(kind, widths, rows, raw, order, ranges)
        result.append({'name': name, 'datatype': kind, 'widths': widths, 'order': order,
          'ranges': [str(n) for n in ranges] if ranges else None,
          'values': [[str(n & ((1 << (ranges[c]-1).bit_length())-1) if kind == 'I' and ranges else n) for c,n in enumerate(row)] for row in rows],
          'storedValues': [[str(n) for n in row] for row in rows], 'dataHex': raw.hex(),
          'sourceBase64': base64.b64encode(contents).decode(), 'sourceSha256': hashlib.sha256(contents).hexdigest(),
          'events': selection[0] if selection else list(reversed(range(len(rows)))),
          'channels': selection[1] if selection else list(reversed(range(len(widths))))})
    for order, expected in [('little', 'bcfade'), ('big', 'abcdef')]:
        rows = [[0xabc, 0xdef]]
        raw = binary([12,12], rows, order)
        assert raw.hex() == expected
        add('packed12_'+order, 'I', [12,12], rows, raw, order)
    for order in ['little', 'big']:
        rows = [[5,683,17], [7,1023,31], [0,1,0]]
        add('cross_event_'+order, 'I', [3,10,5], rows, binary([3,10,5], rows, order), order, selection=([2,0],[2,0]))
        rows = [[1,127,511,2147483647,18446744073709551615], [0,1,256,123,9007199254740993]]
        widths = [1,7,9,31,64]
        add('mixed_wide_'+order, 'I', widths, rows, binary(widths, rows, order), order, selection=([1,0],[4,2,0]))
    rows = [[9007199254740993], [9007199254740992]]
    add('exact_range_above_double', 'I', [64], rows, binary([64], rows, 'little'), ranges=[9007199254740994])
    rows = [[0xc01,5],[0xfff,7]]
    add('packed_unused_bits', 'I', [12,3], rows, binary([12,3], rows, 'little'), ranges=[1024,4])
    add('ascii_fixed', 'A', [4,3], [[12,7],[3,456]], b'0012  70003456')
    add('ascii_variable', 'A', ['*','*'], [[1,3],[3,0],[17,2]], b'1,3,, \t,3\r\n0\t17\n 2', selection=([2,0],[1]))
    add('ascii_mixed_width', 'A', ['*',4], [[1,3],[0,17],[2,0]], b'1,0003 0,0017 2,0000', selection=([1,0],[1]))
    add('ascii_wide_integer', 'A', [22], [[184467440737095516160]], b' 184467440737095516160')
    return result

def main():
    rows = vectors()
    manifest = {'source': 'Original synthetic cases, MIT; ISAC FCS3.1 normative sections DATATYPE, PnB, PnR and DATA',
                'reference': 'https://www.citometriagic.it/wp-content/uploads/2025/02/FCS_3_1.pdf', 'cases': rows}
    encoded = json.dumps(manifest, indent=2) + '\n'
    blocks = ['// Original Python-generated standard encoding vectors. See tools/generate-standard-encodings.py.', '', '///|', 'fn standard_fixture(name : String) -> Bytes {', '  match name {']
    for row in rows:
        contents = base64.b64decode(row['sourceBase64'])
        escaped = ''.join(f'\\x{n:02x}' for n in contents)
        blocks += [f'    "{row["name"]}" =>', f'      b"{escaped}"']
    blocks += ['    _ => abort("unknown standard fixture")', '  }', '}', '']
    files = {ROOT / 'examples/standard-encodings/INPUTS.json': encoded,
             ROOT / 'standard_encoding_fixtures_wbtest.mbt': '\n'.join(blocks)}
    for file, text in files.items():
        if '--check' in sys.argv: assert file.read_text('utf-8') == text, str(file)
        else:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, 'utf-8', newline='\n')
    print(json.dumps({'vectors': len(rows), 'checked': '--check' in sys.argv}))

if __name__ == '__main__': main()
