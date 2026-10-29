"""Independent final-file Boolean gate receiver; Python stdlib, no producer imports."""
import argparse
import csv
import json
from pathlib import Path


def pairs(raw):
    if not raw:
        return {}
    delimiter = raw[0]
    fields, value, at = [], bytearray(), 1
    while at < len(raw):
        if raw[at] != delimiter:
            value.append(raw[at])
            at += 1
        elif at + 1 < len(raw) and raw[at + 1] == delimiter:
            value.append(delimiter)
            at += 2
        else:
            fields.append(value.decode('utf-8'))
            value = bytearray()
            at += 1
    assert not value and len(fields) % 2 == 0
    result = dict(zip(fields[::2], fields[1::2]))
    assert len(result) * 2 == len(fields)
    return result


def fcs(path):
    raw = path.read_bytes()
    assert raw[:10] == b'FCS3.1    ' and len(raw) >= 58
    offsets = [int(raw[at:at + 8]) for at in range(10, 58, 8)]
    ts, te, hs, he, ha, hb = offsets
    assert 58 <= ts <= te < len(raw)
    metadata = pairs(raw[ts:te + 1])
    begin, end = int(metadata['$BEGINDATA']), int(metadata['$ENDDATA'])
    assert (hs, he) == (begin, end)
    assert metadata['$MODE'] == 'L' and metadata['$DATATYPE'] == 'I'
    assert metadata['$BYTEORD'] == '1,2,3,4'
    columns, events = int(metadata['$PAR']), int(metadata['$TOT'])
    widths = [int(metadata[f'$P{i}B']) for i in range(1, columns + 1)]
    size = (events * sum(widths) + 7) // 8
    assert end == begin + size - 1 and begin > te and begin + size <= len(raw)
    data = raw[begin:begin + size]
    # Deliberately decode individual byte bits rather than importing the
    # constructor's Python integer packer or any product code.
    values, cursor = [], 0
    for _ in range(events):
        row = []
        for width in widths:
            number = 0
            for bit in range(width):
                location = cursor + bit
                number += ((data[location // 8] >> (location % 8)) & 1) * (2 ** bit)
            row.append(str(number))
            cursor += width
        values.append(row)
    assert all(((data[bit // 8] >> (bit % 8)) & 1) == 0 for bit in range(cursor, size * 8))
    abegin, aend = int(metadata['$BEGINANALYSIS']), int(metadata['$ENDANALYSIS'])
    assert (ha, hb) == (abegin, aend)
    if abegin == aend == 0:
        analysis = {}
        assert len(raw) == begin + size
    else:
        assert abegin >= begin + size and aend >= abegin and aend + 1 == len(raw)
        analysis = pairs(raw[abegin:aend + 1])
    layout = {'$BEGINDATA', '$ENDDATA', '$BEGINANALYSIS', '$ENDANALYSIS'}
    return {'version': 'FCS3.1', 'metadataExceptLayout': {key: value for key, value in metadata.items() if key not in layout},
            'analysis': analysis, 'rawDataHex': data.hex(), 'integerValues': values}


def compare(actual, expected, location='$'):
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), location + ' object keys'
        for key in expected:
            compare(actual[key], expected[key], location + '.' + key)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), location + ' array length'
        for i, (value, truth) in enumerate(zip(actual, expected)):
            compare(value, truth, location + '[' + str(i) + ']')
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert isinstance(actual, (int, float)) and not isinstance(actual, bool) and actual == expected, (location, actual, expected)
    else:
        assert type(actual) is type(expected) and actual == expected, (location, actual, expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--kind', choices=['json', 'fcs', 'csv'], required=True)
    parser.add_argument('--expected', type=Path, required=True)
    args = parser.parse_args()
    expected = json.loads(args.expected.read_text('utf-8'))
    if args.kind == 'fcs':
        actual = fcs(args.file)
    elif args.kind == 'csv':
        with args.file.open('r', encoding='utf-8', newline='') as stream:
            actual = list(csv.reader(stream))
    else:
        actual = json.loads(args.file.read_text('utf-8'))
    compare(actual, expected)
    print(json.dumps({'status': 'passed', 'kind': args.kind, 'wholeFileCompared': True, 'producerImports': False}))


if __name__ == '__main__':
    main()
