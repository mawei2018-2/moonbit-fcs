"""Read release outputs independently with Python big integers and ASCII fields.

This is an original standards-vector oracle, not an external parser comparison.
It deliberately reads the complete DATA as one integer, unlike the per-field
MoonBit reader. Manual 12-bit hex cases also constrain the fixture builder.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(contents):
    assert contents[:6] == b'FCS3.1'
    numbers = [int(contents[i:i+8]) for i in range(10, 58, 8)]
    start, end = numbers[:2]
    text = contents[start:end+1]
    delimiter = text[:1]
    # These original fixtures have no embedded delimiter. The release writer
    # may choose a different delimiter, which is taken from the actual TEXT.
    fields = text[1:-1].split(delimiter)
    assert len(fields) % 2 == 0
    meta = {fields[i].decode(): fields[i+1].decode() for i in range(0, len(fields), 2)}
    begin, last = int(meta['$BEGINDATA']), int(meta['$ENDDATA'])
    count, channels = int(meta['$TOT']), int(meta['$PAR'])
    widths = [meta[f'$P{i}B'] for i in range(1, channels+1)]
    data = contents[begin:last+1] if count else b''
    if count:
        assert numbers[2:4] == [begin, last] and last == len(contents)-1
    kind = meta['$DATATYPE']
    values, spellings = [], []
    if kind == 'I':
        widths = list(map(int, widths))
        order = 'little' if meta['$BYTEORD'] == '1,2,3,4' else 'big'
        stream = int.from_bytes(data, order)
        offset = 0
        masks = [(1 << (int(meta[f'$P{i}R'])-1).bit_length())-1 for i in range(1, channels+1)]
        for _ in range(count):
            row = []
            for width, mask in zip(widths, masks):
                shift = offset if order == 'little' else len(data)*8-offset-width
                row.append(str(((stream >> shift) & ((1 << width)-1)) & mask))
                offset += width
            values.append(row)
        assert len(data) == (count*sum(widths)+7)//8
    else:
        assert kind == 'A'
        if '*' in widths:
            tokens = [x for x in re.split(rb'[ \t,\r\n]+', data) if x]
            assert len(tokens) == count*channels
        else:
            widths = list(map(int, widths))
            assert len(data) == count*sum(widths)
            tokens, offset = [], 0
            for _ in range(count):
                for width in widths:
                    tokens.append(data[offset:offset+width]); offset += width
        values = [[str(int(v)) for v in tokens[i:i+channels]] for i in range(0, len(tokens), channels)]
        spellings = [tokens[i:i+channels] for i in range(0, len(tokens), channels)]
    return meta, data, values, spellings


def pack(widths, rows, order):
    # Expected selected DATA is a concatenated bit string; Python's reader
    # above instead shifts a complete integer. Preserve stored unused bits.
    chunks = []
    for row in rows:
        for width, value in zip(widths, row):
            bits = f'{int(value):0{width}b}'
            chunks.append(bits[::-1] if order == 'little' else bits)
    stream = ''.join(chunks)
    stream = stream.ljust((len(stream)+7)//8*8, '0')
    return bytes(int(stream[i:i+8][::-1] if order == 'little' else stream[i:i+8], 2)
                 for i in range(0, len(stream), 8))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    manifest = json.loads((ROOT/'examples/standard-encodings/INPUTS.json').read_text())
    receipt = json.loads((args.directory/'ENGINE.json').read_text())
    assert len(receipt['cases']) == len(manifest['cases'])
    cases = []
    for c, item in zip(manifest['cases'], receipt['cases'], strict=True):
        assert c['name'] == item['name']
        parsed = {}
        for key, file in item['files'].items():
            contents = (args.directory/file['file']).read_bytes()
            assert hashlib.sha256(contents).hexdigest() == file['sha256']
            parsed[key] = read(contents)
        original, source_data, values, spellings = parsed['source']
        assert values == c['values'] and source_data.hex() == c['dataHex'], c['name']
        products = [('rewritten', list(range(len(values))), list(range(len(c['widths'])))),
                    ('selected', c['events'], c['channels']), ('empty', [], c['channels'])]
        if item['gate']:
            channel, lower, upper = item['gate']['bounds'][0]
            events = [e for e,row in enumerate(values) if lower <= int(row[channel]) < upper]
            assert item['gate']['events'] == events
            products.append(('gated', events, item['gate']['channels']))
        for key, events, channels in products:
            meta, data, actual, _ = parsed[key]
            assert actual == [[values[e][ch] for ch in channels] for e in events], (c['name'], key)
            assert meta['$ORIGINALITY'] == 'Non-Original'
            assert meta['NOTE'] == original['NOTE'] and int(meta['$NEXTDATA']) == 0
            assert int(meta['$TOT']) == len(events) and int(meta['$PAR']) == len(channels)
            for i, channel in enumerate(channels, 1):
                for suffix in ['N', 'B', 'R']:
                    assert meta[f'$P{i}{suffix}'] == original[f'$P{channel+1}{suffix}']
            if key == 'rewritten':
                assert data == source_data, (c['name'], 'full DATA must be unchanged')
            elif c['datatype'] == 'I':
                expected = pack([c['widths'][ch] for ch in channels],
                                [[c['storedValues'][e][ch] for ch in channels] for e in events], c['order'])
                assert data == expected, (c['name'], key, data.hex(), expected.hex())
            elif '*' in [c['widths'][ch] for ch in channels]:
                expected = b' '.join(spellings[e][ch].strip() for e in events for ch in channels)
                assert data == expected
            else:
                expected = b''.join(spellings[e][ch].strip().rjust(int(c['widths'][ch]), b' ')
                                    for e in events for ch in channels)
                assert data == expected, (c['name'], key, data, expected)
        cases.append({'name':c['name'], 'products':len(item['files']), 'numeric_gate':item['gate'] is not None,
                      'checks':['exact-values','raw-subset-bits-or-spelling','full-rewrite','empty-selection','metadata-remap']})
    report = {'status':'passed', 'oracle':'independent Python complete-integer/ASCII reader and bit-string writer',
              'external_parser_claim':False, 'engineSha256':receipt['engineSha256'], 'cases':cases,
              'products':sum(c['products'] for c in cases)}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'status':'passed','cases':len(cases),'products':report['products']}))


if __name__ == '__main__':
    main()
