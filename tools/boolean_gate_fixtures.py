"""Original MIT bit-packed FCS and explicit Boolean membership expectations."""
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

ID_BASE = 1 << 64
ROWS = [[i, value, ID_BASE + i] for i, value in enumerate([2, 6, 4, 8, 10, 12, 14, 16])]
NAMES = ['X', 'B', 'ID']
WIDTHS = [8, 8, 65]
MAIN = [
    {'id': 'notA', 'parent': 'union', 'boolean': {'op': 'not', 'refs': ['A']}},
    {'id': 'after', 'parent': 'notA', 'vertices': [[5.5, 0], [7, 0], [7, 20], [5.5, 20]], 'x': 'X', 'y': 'B'},
    {'id': 'intersection', 'parent': 'base', 'boolean': {'op': 'and', 'refs': ['A', 'B']}},
    {'id': 'A', 'parent': 'base', 'bounds': [['B', 2, 6]], 'scaled': True},
    {'id': 'union', 'parent': 'base', 'boolean': {'op': 'or', 'refs': ['A', 'B']}},
    {'id': 'B', 'parent': 'base', 'integer_bounds': [{'channel': 'ID', 'lower': str(ID_BASE + 3), 'upper': str(ID_BASE + 7)}]},
    {'id': 'base', 'bounds': [['X', 1, 7]]},
    {'id': 'rootNotA', 'boolean': {'op': 'not', 'refs': ['A']}},
    {'id': 'notnotA', 'parent': 'base', 'boolean': {'op': 'not', 'refs': ['notA']}},
    {'id': 'repeated', 'parent': 'base', 'boolean': {'op': 'and', 'refs': ['A', 'A', 'B']}},
    {'id': 'parentRef', 'parent': 'base', 'boolean': {'op': 'and', 'refs': ['base', 'A']}},
]
MAIN_MEMBERS = {'base': [1, 2, 3, 4, 5, 6], 'A': [1, 2, 3, 4], 'B': [3, 4, 5, 6],
                'union': [1, 2, 3, 4, 5, 6], 'intersection': [3, 4], 'notA': [5, 6],
                'after': [6], 'rootNotA': [0, 5, 6, 7], 'notnotA': [1, 2, 3, 4],
                'repeated': [3, 4], 'parentRef': [1, 2, 3, 4]}
GEOMETRIC = [copy.deepcopy(MAIN[i]) for i in [3, 5, 6]]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pack_integer(rows, widths):
    payload, offset = 0, 0
    for row in rows:
        for value, width in zip(row, widths):
            assert 0 <= value < (1 << width)
            payload |= value << offset
            offset += width
    return payload.to_bytes((offset + 7) // 8, 'little')


def make_fcs(rows, *, floating=False):
    names, widths = (['F'], [64]) if floating else (NAMES, WIDTHS)
    data = b''.join(struct.pack('<d', row[0]) for row in rows) if floating else pack_integer(rows, widths)
    pairs = [('$MODE', 'L'), ('$DATATYPE', 'D' if floating else 'I'), ('$BYTEORD', '1,2,3,4'),
             ('$PAR', str(len(names))), ('$TOT', str(len(rows))), ('$BEGINSTEXT', '0'), ('$ENDSTEXT', '0'),
             ('$NEXTDATA', '0'), ('$BEGINDATA', '000000000000'), ('$ENDDATA', '000000000000'),
             ('$BEGINANALYSIS', '000000000000'), ('$ENDANALYSIS', '000000000000'),
             ('$ORIGINALITY', 'Original'), ('VENDOR', 'original MIT Boolean fixture')]
    for i, (name, width) in enumerate(zip(names, widths), 1):
        pairs += [(f'$P{i}N', name), (f'$P{i}S', 'source-' + name), (f'$P{i}B', str(width)),
                  (f'$P{i}R', '1024' if floating else str(1 << width)), (f'$P{i}E', '0,0'),
                  (f'$P{i}G', '2' if not floating and i == 2 else '1')]

    def text(values):
        return ('|' + '|'.join(value.replace('|', '||') for pair in values for value in pair) + '|').encode('utf-8')

    analysis = text([('NOTE', 'original analysis kept in source')])
    begin = 256 + len(text(pairs))
    end = begin + len(data) - 1
    abegin = begin + len(data)
    offsets = {'$BEGINDATA': begin, '$ENDDATA': end,
               '$BEGINANALYSIS': abegin, '$ENDANALYSIS': abegin + len(analysis) - 1}
    pairs = [(key, f'{offsets[key]:012d}' if key in offsets else value) for key, value in pairs]
    encoded = text(pairs)
    assert begin == 256 + len(encoded)
    header = b'FCS3.1    ' + b''.join(f'{value:8d}'.encode('ascii') for value in [
        256, begin - 1, begin, end, abegin, abegin + len(analysis) - 1])
    raw = header.ljust(256, b' ') + encoded + data + analysis
    return raw, dict(pairs)


def populations(plan, members, total):
    result = []
    for step in plan:
        events = members[step['id']]
        parent = step.get('parent')
        denominator = len(members[parent]) if parent is not None else total
        row = {'id': step['id'], 'event_indices': events, 'count': len(events),
               'parent_count': denominator, 'total_count': total}
        if parent is not None:
            row['parent'] = parent
        if denominator:
            row['parent_fraction'] = float(Fraction(len(events), denominator))
        if total:
            row['total_fraction'] = float(Fraction(len(events), total))
        result.append(row)
    return result


def fcs_expectation(source_meta, events, columns):
    metadata = {key: value for key, value in source_meta.items()
                if key not in ['$BEGINDATA', '$ENDDATA', '$BEGINANALYSIS', '$ENDANALYSIS']
                and not re.fullmatch(r'\$P[0-9]+[A-Z].*', key)}
    metadata.update({'$PAR': str(len(columns)), '$TOT': str(len(events)), '$ORIGINALITY': 'Non-Original'})
    for new, old in enumerate(columns, 1):
        for suffix in ['N', 'S', 'B', 'R', 'E', 'G']:
            metadata[f'$P{new}{suffix}'] = source_meta[f'$P{old + 1}{suffix}']
    selected = [[ROWS[event][column] for column in columns] for event in events]
    return {'version': 'FCS3.1', 'metadataExceptLayout': metadata, 'analysis': {},
            'rawDataHex': pack_integer(selected, [WIDTHS[column] for column in columns]).hex(),
            'integerValues': [[str(value) for value in row] for row in selected]}


def fixtures(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)

    def write(name, value):
        (directory / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', 'utf-8')

    source, metadata = make_fcs(ROWS)
    (directory / 'source.fcs').write_bytes(source)
    (directory / 'empty.fcs').write_bytes(make_fcs([])[0])
    (directory / 'nonfinite.fcs').write_bytes(make_fcs([[0.0], [math.nan], [2.0]], floating=True)[0])
    # These memberships are explicit independent truth, not the output of a
    # copied graph evaluator. Set checks document the intended algebra only.
    assert set(MAIN_MEMBERS['intersection']) == set(MAIN_MEMBERS['A']) & set(MAIN_MEMBERS['B'])
    assert set(MAIN_MEMBERS['union']) == set(MAIN_MEMBERS['A']) | set(MAIN_MEMBERS['B'])
    assert set(MAIN_MEMBERS['notA']) == set(MAIN_MEMBERS['union']) - set(MAIN_MEMBERS['A'])
    positive = []

    def add(name, filename, plan, members, total):
        write(name + '.json', {'gates': plan})
        write(name + '-expected.json', populations(plan, members, total))
        positive.append({'id': name, 'source': filename, 'options': name + '.json', 'expected': name + '-expected.json'})

    add('main', 'source.fcs', MAIN, MAIN_MEMBERS, 8)
    add('empty-source', 'empty.fcs', MAIN, {name: [] for name in MAIN_MEMBERS}, 0)
    empty_plan = [
        {'id': 'all', 'boolean': {'op': 'not', 'refs': ['empty']}},
        {'id': 'intersection', 'boolean': {'op': 'and', 'refs': ['empty', 'A']}},
        {'id': 'union', 'boolean': {'op': 'or', 'refs': ['empty', 'A']}},
        {'id': 'clipped', 'parent': 'empty', 'boolean': {'op': 'not', 'refs': ['A']}},
        {'id': 'child', 'parent': 'intersection', 'bounds': [['X', 0, 9]]},
        {'id': 'empty', 'bounds': [['X', 20, 30]]},
        {'id': 'A', 'bounds': [['B', 2, 6]], 'scaled': True},
    ]
    add('empty-parent', 'source.fcs', empty_plan,
        {'all': list(range(8)), 'intersection': [], 'union': [1, 2, 3, 4], 'clipped': [],
         'child': [], 'empty': [], 'A': [1, 2, 3, 4]}, 8)
    finite_plan = [
        {'id': 'notA', 'boolean': {'op': 'not', 'refs': ['A']}},
        {'id': 'qualified', 'parent': 'finite', 'boolean': {'op': 'not', 'refs': ['A']}},
        {'id': 'all', 'boolean': {'op': 'or', 'refs': ['A', 'notA']}},
        {'id': 'none', 'boolean': {'op': 'and', 'refs': ['A', 'notA']}},
        {'id': 'twice', 'boolean': {'op': 'not', 'refs': ['notA']}},
        {'id': 'A', 'bounds': [['F', 0, 1]]}, {'id': 'finite', 'bounds': [['F', -1, 3]]},
    ]
    add('nonfinite-complement', 'nonfinite.fcs', finite_plan,
        {'notA': [1, 2], 'qualified': [2], 'all': [0, 1, 2], 'none': [], 'twice': [0], 'A': [0], 'finite': [0, 2]}, 3)
    cross = [
        {'id': 'intersection', 'boolean': {'op': 'and', 'refs': ['A', 'B']}},
        {'id': 'leftUnion', 'parent': 'left', 'boolean': {'op': 'or', 'refs': ['A', 'B']}},
        {'id': 'rightNotA', 'parent': 'right', 'boolean': {'op': 'not', 'refs': ['A']}},
        {'id': 'A', 'parent': 'left', 'bounds': [['X', -1, 9]]},
        {'id': 'B', 'parent': 'right', 'bounds': [['X', -1, 9]]},
        {'id': 'left', 'bounds': [['X', 0, 4]]}, {'id': 'right', 'bounds': [['X', 4, 8]]},
    ]
    add('cross-parent', 'source.fcs', cross, {'intersection': [], 'leftUnion': [0, 1, 2, 3],
        'rightNotA': [4, 5, 6, 7], 'A': [0, 1, 2, 3], 'B': [4, 5, 6, 7],
        'left': [0, 1, 2, 3], 'right': [4, 5, 6, 7]}, 8)
    chain = [{'id': 'n' + str(i), 'boolean': {'op': 'not', 'refs': ['all' if i == 0 else 'n' + str(i - 1)]}}
             for i in range(16)]
    chain = list(reversed(chain)) + [{'id': 'all', 'bounds': [['X', -1, 9]]}]
    members = {'all': list(range(8)), **{'n' + str(i): [] if i % 2 == 0 else list(range(8)) for i in range(16)}}
    add('forward-chain', 'source.fcs', chain, members, 8)
    write('geometric.json', {'gates': GEOMETRIC})
    write('geometric-expected.json', populations(GEOMETRIC, MAIN_MEMBERS, 8))
    write('subset.json', {'gates': MAIN, 'population': 'intersection', 'channels': ['ID', 'B'], 'drop_analysis': True})
    write('subset-expected.json', fcs_expectation(metadata, [3, 4], [2, 1]))
    write('child-subset.json', {'gates': MAIN, 'population': 'after', 'channels': ['ID', 'X'], 'drop_analysis': True})
    write('child-subset-expected.json', fcs_expectation(metadata, [6], [2, 0]))
    write('empty-subset.json', {'gates': empty_plan, 'population': 'intersection', 'channels': ['ID', 'B'], 'drop_analysis': True})
    write('empty-subset-expected.json', fcs_expectation(metadata, [], [2, 1]))
    csv_options = {'gates': MAIN, 'population': 'union', 'channels': ['ID', 'B'], 'event_index_column': 'source_event',
                   'population_columns': [{'population': 'intersection', 'column': 'in_both'}, {'population': 'notA', 'column': 'outside_A'}]}
    csv_rows = [['source_event', 'ID', 'B', 'in_both', 'outside_A']] + [
        [str(e), str(ROWS[e][2]), str(ROWS[e][1]), str(int(e in [3, 4])), str(int(e in [5, 6]))] for e in range(1, 7)]
    write('csv.json', csv_options)
    write('csv-expected.json', csv_rows)
    write('csv-window.json', dict(csv_options, start=1, count=3))
    write('csv-window-expected.json', [csv_rows[0]] + csv_rows[2:5])
    write('stats.json', {'gates': MAIN, 'population': 'notA', 'channels': ['B', 'X', 'B'], 'scaled': True, 'include_read_report': True})
    statistic = lambda mean, minimum, maximum: {'count': 2, 'nonfinite': 0, 'minimum': minimum, 'maximum': maximum, 'mean': mean, 'variance': 0.5}
    write('stats-expected.json', {'population': 'notA', 'population_events': 2, 'source_event_indices': [5, 6],
        'channel_names': ['B', 'X', 'B'], 'scaled': True, 'compensated': False,
        'statistics': [statistic(6.5, 6, 7), statistic(5.5, 5, 6), statistic(6.5, 6, 7)], 'channel_indices': [1, 0, 1],
        'read_report': {'source_sha256': sha(directory / 'source.fcs'), 'dataset': 0, 'version': 'FCS3.1', 'warnings': []}})
    write('api-expected.json', {'populations': populations(MAIN, MAIN_MEMBERS, 8),
                               'selectedValues': [[str(ROWS[e][2]), str(ROWS[e][1])] for e in [3, 4]]})
    negative = []

    def bad(name, plan, fragment, **extra):
        write(name + '.json', dict(gates=plan, **extra))
        negative.append({'id': name, 'options': name + '.json', 'error': fragment})

    valid = {'id': 'A', 'bounds': [['X', -1, 9]]}
    for operation in ['and', 'or']:
        bad('empty-' + operation, [valid, {'id': 'bad', 'boolean': {'op': operation, 'refs': []}}], 'nonempty')
    for refs in [[], ['A', 'A']]:
        bad('not-arity-' + str(len(refs)), [valid, {'id': 'bad', 'boolean': {'op': 'not', 'refs': refs}}], 'exactly one')
    for name, boolean in [('unknown-operation', {'op': 'xor', 'refs': ['A']}),
                          ('wrong-reference-array', {'op': 'and', 'refs': 'A'}),
                          ('wrong-reference-type', {'op': 'and', 'refs': [1]}),
                          ('empty-reference-id', {'op': 'and', 'refs': ['']}),
                          ('unknown-nested-option', {'op': 'and', 'refs': ['A'], 'typo': True})]:
        bad(name, [valid, {'id': 'bad', 'boolean': boolean}], 'Boolean')
    bad('unknown-reference', [valid, {'id': 'bad', 'boolean': {'op': 'or', 'refs': ['A', 'missing']}}], 'unknown Boolean')
    bad('unknown-parent', [valid, {'id': 'bad', 'parent': 'missing', 'boolean': {'op': 'not', 'refs': ['A']}}], 'unknown parent')
    bad('duplicate-id', [valid, {'id': 'A', 'boolean': {'op': 'not', 'refs': ['A']}}], 'unique')
    bad('empty-id', [valid, {'id': '', 'boolean': {'op': 'not', 'refs': ['A']}}], 'unique')
    bad('self-cycle', [{'id': 'A', 'boolean': {'op': 'not', 'refs': ['A']}}], 'cycle')
    bad('reference-cycle', [{'id': 'A', 'boolean': {'op': 'or', 'refs': ['B']}}, {'id': 'B', 'boolean': {'op': 'and', 'refs': ['A']}}], 'cycle')
    bad('mixed-parent-cycle', [{'id': 'A', 'parent': 'B', 'bounds': [['X', -1, 9]]}, {'id': 'B', 'boolean': {'op': 'not', 'refs': ['A']}}], 'cycle')
    for flag in ['scaled', 'compensated']:
        bad('boolean-' + flag, [valid, {'id': 'bad', 'boolean': {'op': 'not', 'refs': ['A']}, flag: True}], 'Boolean')
    bad('mixed-predicate', [valid, {'id': 'bad', 'bounds': [['X', 0, 1]], 'boolean': {'op': 'not', 'refs': ['A']}}], 'exactly one predicate')
    bad('boolean-xy', [valid, {'id': 'bad', 'x': 0, 'boolean': {'op': 'not', 'refs': ['A']}}], 'x/y')
    for i, value in enumerate([None, True, []]):
        bad('wrong-boolean-object-' + str(i), [valid, {'id': 'bad', 'boolean': value}], 'boolean')
    bad('empty-parent-view', [empty_plan[5], valid, {'id': 'bad', 'parent': 'empty', 'boolean': {'op': 'not', 'refs': ['A']}, 'scaled': True}], 'Boolean')
    bad('invalid-geometry-under-boolean-empty', [valid, {'id': 'empty', 'boolean': {'op': 'not', 'refs': ['A']}},
        {'id': 'bad', 'parent': 'empty', 'bounds': [[99, 0, 1]]}], 'channel')
    write('CASES.json', {'positive': positive, 'negative': negative,
        'fcs': [{'id': name, 'options': name + '.json', 'expected': name + '-expected.json'} for name in ['subset', 'child-subset', 'empty-subset']],
        'csv': [{'id': name, 'options': name + '.json', 'expected': name + '-expected.json'} for name in ['csv', 'csv-window']]})
    manifest = {file.name: {'bytes': file.stat().st_size, 'SHA256': sha(file)} for file in sorted(directory.iterdir())}
    write('MANIFEST.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'files': len(fixtures(sys.argv[1])), 'directory': sys.argv[1]}))
