"""Original MIT binary64 files and independent exact-rational compensation truth."""
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import struct

P = math.ldexp(1.0, 1023)
Q = math.ldexp(1.0, 1022)
TINY = math.ldexp(1.0, -1074)
MAX = float.fromhex('0x1.fffffffffffffp+1023')
MATRIX = [[1, -1, 0], [0, .5, 0], [0, 0, 1]]
INVERSE = [[1, 2, 0], [0, 2, 0], [0, 0, 1]]
ROWS = [[P, -P, 0], [-P, P, 1], [1, 2, 2], [P, P, 3], [0, 0, 4], [math.nan, 1, 5], [math.inf, -math.inf, 6]]
PLAN = [
    {'id': 'zero', 'parent': 'finite', 'bounds': [['B', -.5, .5]], 'compensated': True},
    {'id': 'rest', 'parent': 'finite', 'boolean': {'op': 'not', 'refs': ['zero']}},
    {'id': 'finite', 'bounds': [['B', -1, 7]], 'compensated': True},
    {'id': 'either', 'boolean': {'op': 'or', 'refs': ['zero', 'rest']}},
]
MEMBERS = {'zero': [0, 1, 4], 'rest': [2], 'finite': [0, 1, 2, 4], 'either': [0, 1, 2, 4]}


def sha(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()


def tagged(value):
    return value if math.isfinite(value) else 'NaN' if math.isnan(value) else 'Infinity' if value > 0 else '-Infinity'


def bits(value):
    # Nonfinite NaN payloads are unspecified; public reports classify them.
    return 'NaN' if math.isnan(value) else str(int.from_bytes(struct.pack('>d', value), 'big'))


def exact_dot(values, weights):
    active = [(value, weight) for value, weight in zip(values, weights) if weight != 0]
    if any(math.isnan(value) for value, _ in active):
        return math.nan
    signs = {1 if (value > 0) == (weight > 0) else -1 for value, weight in active if math.isinf(value)}
    if len(signs) == 2:
        return math.nan
    if signs:
        return math.inf if 1 in signs else -math.inf
    rational = sum((Fraction.from_float(float(value)) * Fraction.from_float(float(weight)) for value, weight in active), Fraction())
    try:
        return float(rational)
    except OverflowError:
        return math.inf if rational > 0 else -math.inf


def make_fcs(rows, matrix, gains=None):
    n = len(matrix)
    names = list('ABCD'[:n])
    gains = gains or [1] * n
    data = b''.join(struct.pack('<d', value) for row in rows for value in row)
    matrix_text = ','.join([str(n), *names, *[str(v) if isinstance(v, int) else repr(v) for row in matrix for v in row]])
    pairs = [('$MODE', 'L'), ('$DATATYPE', 'D'), ('$BYTEORD', '1,2,3,4'), ('$PAR', str(n)), ('$TOT', str(len(rows))),
             ('$BEGINSTEXT', '0'), ('$ENDSTEXT', '0'), ('$NEXTDATA', '0'),
             ('$BEGINDATA', '000000000000'), ('$ENDDATA', '000000000000'),
             ('$BEGINANALYSIS', '000000000000'), ('$ENDANALYSIS', '000000000000'),
             ('$ORIGINALITY', 'Original'), ('$SPILLOVER', matrix_text), ('VENDOR', 'original MIT compensation overflow fixture')]
    for i, (name, gain) in enumerate(zip(names, gains), 1):
        pairs += [(f'$P{i}N', name), (f'$P{i}S', 'source-' + name), (f'$P{i}B', '64'), (f'$P{i}R', '1024'),
                  (f'$P{i}E', '0,0'), (f'$P{i}G', str(gain))]

    def text(values):
        return ('|' + '|'.join(value.replace('|', '||') for pair in values for value in pair) + '|').encode('utf-8')

    analysis = text([('NOTE', 'original analysis is preserved in input')])
    start = 256 + len(text(pairs))
    offsets = {'$BEGINDATA': start, '$ENDDATA': start + len(data) - 1,
               '$BEGINANALYSIS': start + len(data), '$ENDANALYSIS': start + len(data) + len(analysis) - 1}
    pairs = [(key, f'{offsets[key]:012d}' if key in offsets else value) for key, value in pairs]
    encoded = text(pairs)
    assert start == 256 + len(encoded)
    header = b'FCS3.1    ' + b''.join(f'{value:8d}'.encode() for value in [256, start-1, start, start+len(data)-1,
                                                                        start+len(data), start+len(data)+len(analysis)-1])
    return header.ljust(256, b' ') + encoded + data + analysis, dict(pairs)


def public_expected(rows, inverse, gains):
    result = [[exact_dot([value / gain for value, gain in zip(row, gains)], [inverse[i][column] for i in range(len(inverse))])
               for column in range(len(inverse))] for row in rows]
    return {'inverse': [value for row in inverse for value in row], 'values': [[tagged(value) for value in row] for row in result],
            'bits': [[bits(value) for value in row] for row in result]}


def fixtures(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)

    def write(name, value):
        (directory / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', 'utf-8')

    definitions = [
        ('product', ROWS, MATRIX, INVERSE, [1, 1, 1]),
        ('partial-sum', [[Q, Q, -Q], [-Q, -Q, Q], [1, 2, 3], [P, P, 0], [-P, -P, 0], [math.nan, 0, 0], [P, -P, math.nan]],
         [[1, 0, -1], [0, 1, -1], [0, 0, .5]], [[1, 0, 2], [0, 1, 2], [0, 0, 2]], [1, 1, 1]),
        ('subnormal', [[P, -P, factor*TINY] for factor in [1, 3, 5, -1, -3, 0, 7]],
         [[1, 0, -4], [0, 1, -4], [0, 0, 2]], [[1, 0, 2], [0, 1, 2], [0, 0, .5]], [1, 1, 1]),
        ('normal-rounding', [[P, -P, 1, math.ldexp(1., -53)], [P, -P, 1, math.ldexp(3., -53)],
                             [P, -P, -1, -math.ldexp(1., -53)], [P, -P, -1, -math.ldexp(3., -53)],
                             [P, -P, MAX, math.ldexp(1., 969)], [P, -P, MAX, math.ldexp(1., 970)]],
         [[1, 0, 0, -2], [0, 1, 0, -2], [0, 0, 1, -1], [0, 0, 0, 1]],
         [[1, 0, 0, 2], [0, 1, 0, 2], [0, 0, 1, 1], [0, 0, 0, 1]], [1, 1, 1, 1]),
        ('scaled', [[P, -P, 0], [-P, P, 1], [2, 4, 2]], [[1, -1, 0], [0, .25, 0], [0, 0, 1]],
         [[1, 4, 0], [0, 4, 0], [0, 0, 1]], [2, 2, 1]),
        ('control', [[1, 2, 0], [2, 3, 1], [0, -1, 2], [4, 0, 3]], MATRIX, INVERSE, [1, 1, 1]),
    ]
    public = []
    positives = []
    primary_metadata = None
    for name, rows, matrix, inverse, gains in definitions:
        raw, metadata = make_fcs(rows, matrix, gains)
        (directory / (name + '.fcs')).write_bytes(raw)
        expected = public_expected(rows, inverse, gains)
        write(name + '-values-expected.json', expected['values'])
        public.append(dict(id=name, **expected))
        positives.append({'id': name, 'source': name + '.fcs', 'expected': name + '-values-expected.json'})
        if name == 'product':
            primary_metadata = metadata
    write('values.json', {'compensated': True})
    write('public-expected.json', public)
    populations = []
    for step in PLAN:
        members = MEMBERS[step['id']]
        parent = step.get('parent')
        denominator = len(MEMBERS[parent]) if parent else len(ROWS)
        row = {'id': step['id'], 'event_indices': members, 'count': len(members), 'parent_count': denominator,
               'total_count': len(ROWS), 'parent_fraction': float(Fraction(len(members), denominator)),
               'total_fraction': float(Fraction(len(members), len(ROWS)))}
        if parent:
            row['parent'] = parent
        populations.append(row)
    write('plan.json', {'gates': PLAN})
    write('populations-expected.json', populations)
    selected = MEMBERS['either']
    write('subset.json', {'gates': PLAN, 'population': 'either', 'channels': ['C', 'B'], 'drop_analysis': True, 'drop_spillover': True})
    metadata = {key: value for key, value in primary_metadata.items()
                if key not in ['$BEGINDATA', '$ENDDATA', '$BEGINANALYSIS', '$ENDANALYSIS', '$SPILLOVER']
                and not re.fullmatch(r'\$P[0-9]+[A-Z].*', key)}
    metadata.update({'$PAR': '2', '$TOT': str(len(selected)), '$ORIGINALITY': 'Non-Original'})
    for new, old in enumerate([3, 2], 1):
        for suffix in ['N', 'S', 'B', 'R', 'E', 'G']:
            metadata[f'$P{new}{suffix}'] = primary_metadata[f'$P{old}{suffix}']
    selected_values = [[ROWS[event][column] for column in [2, 1]] for event in selected]
    write('subset-expected.json', {'version': 'FCS3.1', 'metadataExceptLayout': metadata, 'analysis': {},
        'rawDataHex': b''.join(struct.pack('<d', value) for row in selected_values for value in row).hex(),
        'values': [[tagged(value) for value in row] for row in selected_values], 'bits': [[bits(value) for value in row] for row in selected_values]})
    csv_options = {'gates': PLAN, 'population': 'either', 'channels': ['C', 'B'], 'compensated': True,
                   'event_index_column': 'source_event', 'population_columns': [{'population': 'zero', 'column': 'in_zero'}]}
    write('csv.json', csv_options)
    csv_rows = [['source_event', 'C', 'B', 'in_zero'], ['0', '0', '0', '1'], ['1', '1', '0', '1'],
                ['2', '2', '6', '0'], ['4', '4', '0', '1']]
    write('csv-expected.json', csv_rows)
    write('csv-window.json', dict(csv_options, start=1, count=2))
    write('csv-window-expected.json', [csv_rows[0]] + csv_rows[2:4])
    write('stats.json', {'gates': PLAN, 'population': 'either', 'channels': ['B', 'C'], 'compensated': True, 'include_read_report': True})
    stats = lambda lo, hi, mean, variance: {'count': 4, 'nonfinite': 0, 'minimum': lo, 'maximum': hi, 'mean': mean, 'variance': variance}
    write('stats-expected.json', {'population': 'either', 'population_events': 4, 'source_event_indices': selected,
        'channel_names': ['B', 'C'], 'scaled': True, 'compensated': True, 'channel_indices': [1, 2],
        'statistics': [stats(0, 6, 1.5, 9), stats(0, 4, 1.75, float(Fraction(35, 12)))],
        'read_report': {'source_sha256': sha(directory/'product.fcs'), 'dataset': 0, 'version': 'FCS3.1', 'warnings': []}})
    write('CASES.json', {'positive': positives, 'publicCases': [case[0] for case in definitions],
                        'fullFileConsumers': ['subset.fcs', 'csv.csv', 'csv-window.csv', 'stats.json', 'populations.json']})
    write('MANIFEST.json', {file.name: {'bytes': file.stat().st_size, 'SHA256': sha(file)} for file in sorted(directory.iterdir())})
    return len(list(directory.iterdir())) - 1


if __name__ == '__main__':
    import sys
    print(json.dumps({'frozenFiles': fixtures(sys.argv[1])}))
