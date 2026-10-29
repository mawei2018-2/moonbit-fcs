"""Original MIT quantile fixtures: struct FCS bytes and independent rational truth."""
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

PROBABILITIES = [1, 0.5, 0, 0.25, 0.75, 0.5]
ROWS = [[i, value, driver, 3, i * 4] for i, (value, driver) in enumerate([
    (40, 8), (10, 4), (30, 12), (20, 16), (1000, 20),
    (math.nan, 24), (math.inf, 28), (-math.inf, 32),
])]
NAMES = ['X', 'Target', 'Driver', 'Unavailable', 'Time']
MEMBERS = [1, 2, 3, 4, 5, 6]
PLAN = {'gates': [{'id': 'p', 'bounds': [[0, 1, 7]]}], 'population': 'p'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode_fcs(rows, names=NAMES, *, bad_gain=False, duplicate=False, mode='L'):
    """An independent small FCS3.1 encoder; never imports the product writer."""
    order = '<'
    if mode == 'L':
        data = b''.join(struct.pack(order + 'd', value) for row in rows for value in row)
        total, datatype, bits = len(rows), 'D', 64
    else:
        frequencies = [1, 2, 3, 4] if mode == 'C' else [1, 2, 1, 2]
        data = struct.pack('<4H', *frequencies)
        total, datatype, bits = (10 if mode == 'C' else 3), 'I', 16
    channels = list(names)
    if duplicate:
        channels[3] = 'Target'
    pairs = [('$BEGINANALYSIS', '0'), ('$ENDANALYSIS', '0'),
             ('$BEGINDATA', '0'), ('$ENDDATA', '0'), ('$BEGINSTEXT', '0'),
             ('$ENDSTEXT', '0'), ('$NEXTDATA', '0'), ('$BYTEORD', '1,2,3,4'),
             ('$DATATYPE', datatype), ('$MODE', mode), ('$PAR', str(len(channels))),
             ('$TOT', str(total))]
    for i, name in enumerate(channels, 1):
        gain = 2 if i == 2 and len(channels) == 5 else 4 if i == 3 else 1
        if bad_gain and i == 4:
            gain = 0
        pairs += [(f'$P{i}N', name), (f'$P{i}B', str(bits)),
                  (f'$P{i}R', '2' if mode != 'L' else '1.7976931348623157e308'),
                  (f'$P{i}E', '0,0'), (f'$P{i}G', str(gain))]
    if len(channels) == 5:
        pairs += [('$SPILLOVER', '2,Target,Driver,1,0,0.5,1'), ('$TIMESTEP', '0.25')]
    if duplicate:
        # Duplicate labels are a separate compatibility example, without an
        # intrinsically ambiguous named compensation matrix.
        pairs = [pair for pair in pairs if pair[0] != '$SPILLOVER']
    analysis = b'|note|original MIT quantile fixture analysis|'
    positions = {'$BEGINDATA': '0', '$ENDDATA': '0', '$BEGINANALYSIS': '0', '$ENDANALYSIS': '0'}
    for _ in range(30):
        text = ('|' + '|'.join(part for key, value in pairs
                              for part in (key, positions.get(key, value))) + '|').encode('ascii')
        begin = 58 + len(text)
        end = begin + len(data) - 1
        abegin = begin + len(data)
        revised = {'$BEGINDATA': str(begin),
                   '$ENDDATA': str(end),
                   '$BEGINANALYSIS': str(abegin), '$ENDANALYSIS': str(abegin + len(analysis) - 1)}
        if positions == revised:
            break
        positions = revised
    else:
        raise AssertionError('fixture offset convergence')
    header = b'FCS3.1    ' + b''.join(f'{value:8d}'.encode('ascii') for value in [
        58, 57 + len(text), int(positions['$BEGINDATA']), int(positions['$ENDDATA']),
        int(positions['$BEGINANALYSIS']), int(positions['$ENDANALYSIS']),
    ])
    assert len(header) == 58
    return header + text + data + analysis


def quantile_truth(values, probabilities=PROBABILITIES):
    finite = sorted(Fraction(value) for value in values if math.isfinite(value))
    answer = []
    for p in probabilities:
        if not finite:
            answer.append(None)
            continue
        rank = (len(finite) - 1) * Fraction(p)
        lower = rank.numerator // rank.denominator
        upper = min(lower + 1, len(finite) - 1)
        weight = rank - lower
        answer.append(float((1 - weight) * finite[lower] + weight * finite[upper]))
    return {'method': 'linear-type7', 'count': len(finite),
            'nonfinite': len(values) - len(finite),
            'probabilities': list(probabilities), 'values': answer}


def statistics_truth(values):
    finite = [Fraction(value) for value in values if math.isfinite(value)]
    report = {'count': len(finite), 'nonfinite': len(values) - len(finite)}
    if finite:
        mean = sum(finite) / len(finite)
        report.update(minimum=float(min(finite)), maximum=float(max(finite)), mean=float(mean))
        if len(finite) > 1:
            variance = sum((value - mean) ** 2 for value in finite) / (len(finite) - 1)
            try:
                converted = float(variance)
            except OverflowError:
                converted = math.inf
            if math.isfinite(converted):
                report['variance'] = converted
    return report


def view_value(rows, event, column, view):
    value = rows[event][column]
    if view == 'raw' or len(rows[event]) != 5:
        return value
    if column == 1:
        value /= 2
        if view == 'compensated':
            value -= rows[event][2] / 8
    elif column == 2:
        value /= 4
    elif column == 4:
        value *= 0.25
    return value


def expected_report(rows, names, members, options, *, quantiles=True, source=None, warnings=None):
    selected = members[options.get('start', 0):]
    if 'count' in options:
        selected = selected[:options['count']]
    requested = options.get('channels')
    columns = list(range(len(names))) if requested is None else [names.index(c) if isinstance(c, str) else c for c in requested]
    view = 'compensated' if options.get('compensated') else 'scaled' if options.get('scaled') else 'raw'
    values = [[view_value(rows, event, column, view) for event in selected] for column in columns]
    report = {'population': 'p', 'population_events': len(members),
              'source_event_indices': selected, 'channel_names': [names[column] for column in columns],
              'scaled': view != 'raw', 'compensated': view == 'compensated',
              'statistics': [statistics_truth(column) for column in values]}
    if quantiles:
        report['quantiles'] = [quantile_truth(column, options['probabilities']) for column in values]
    if requested is not None:
        report['channel_indices'] = columns
    if 'start' in options or 'count' in options:
        report['events'] = len(selected)
    if options.get('include_read_report'):
        report['read_report'] = {'source_sha256': sha(source), 'dataset': 0,
                                 'version': 'FCS3.1', 'warnings': warnings or []}
    return report


def fixtures(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    original = {'base.fcs': encode_fcs(ROWS), 'bad-gain.fcs': encode_fcs(ROWS, bad_gain=True),
                'duplicate.fcs': encode_fcs(ROWS, duplicate=True)}
    variants = {
        'empty': [], 'singleton': [[0, 3.5]],
        'nonfinite': [[0, math.nan], [1, math.inf], [2, -math.inf]],
        'extremes': [[0, -sys.float_info.max], [1, sys.float_info.max]],
        'subnormal': [[0, float.fromhex('0x0.0000000000001p-1022')],
                      [1, float.fromhex('0x0.0000000000001p-1022')]],
        'odd': [[0, 9], [1, 1], [2, 5]],
    }
    for name, rows in variants.items():
        original[name + '.fcs'] = encode_fcs(rows, ['X', 'Target'])
    original['correlated.fcs'] = encode_fcs([], ['X', 'Target'], mode='C')
    original['uncorrelated.fcs'] = encode_fcs([], ['X', 'Target'], mode='U')
    for name, data in original.items():
        (directory / name).write_bytes(data)
    cases = []

    def add(name, source, options, rows=ROWS, names=NAMES, members=MEMBERS):
        options = dict(options)
        options['probabilities'] = options.get('probabilities', PROBABILITIES)
        (directory / (name + '.json')).write_text(json.dumps(options, indent=2) + '\n', 'utf-8')
        truth = expected_report(rows, names, members, options, source=directory / source)
        (directory / (name + '-expected.json')).write_text(json.dumps(truth, indent=2, allow_nan=False) + '\n', 'utf-8')
        cases.append({'id': name, 'source': source, 'options': name + '.json', 'expected': name + '-expected.json'})

    for view in ['raw', 'scaled', 'compensated']:
        add(view, 'base.fcs', dict(PLAN, channels=['Target', 'Driver', 'Target'],
                                  **({view: True} if view != 'raw' else {})))
    add('window', 'base.fcs', dict(PLAN, channels=['Target'], start=1, count=4, compensated=True))
    add('empty-window', 'base.fcs', dict(PLAN, channels=['Target'], start=6, count=0))
    add('single-window', 'base.fcs', dict(PLAN, channels=['Target'], start=1, count=1, scaled=True))
    add('time', 'base.fcs', dict(PLAN, channels=['Time'], scaled=True))
    add('read-report', 'base.fcs', dict(PLAN, channels=[1], include_read_report=True))
    add('no-report-channels', 'base.fcs', dict(PLAN, channels=[]))
    add('unrelated-calibration', 'bad-gain.fcs', dict(PLAN, channels=[1], compensated=True))
    add('all-channels', 'base.fcs', dict(PLAN))
    for name, rows in variants.items():
        plan = {'gates': [{'id': 'p', 'bounds': [[0, -1, len(rows) + 1]]}], 'population': 'p', 'channels': ['Target']}
        add(name, name + '.fcs', plan, rows, ['X', 'Target'], list(range(len(rows))))
    controls = []
    for label, extra in [('default', {}), ('null', {'probabilities': None})]:
        options = dict(PLAN, channels=['Target', 'Driver'], start=1, count=4, **extra)
        (directory / (label + '.json')).write_text(json.dumps(options, indent=2) + '\n', 'utf-8')
        controls.append({'id': label, 'source': 'base.fcs', 'options': label + '.json'})
    errors = []
    bad_probabilities = [[], 0.5, [-0.01], [1.01], ['0.5'], [None], [True], [0.5, 'bad']]
    for i, probabilities in enumerate(bad_probabilities):
        name = 'invalid-probabilities-' + str(i)
        options = dict(PLAN, channels=[] if i == 0 else [1], probabilities=probabilities)
        (directory / (name + '.json')).write_text(json.dumps(options) + '\n', 'utf-8')
        errors.append({'id': name, 'source': 'base.fcs', 'options': name + '.json', 'error': 'probabilities'})
    for name, source, extra, error in [
        ('bad-channel', 'base.fcs', {'channels': ['missing']}, 'channel'),
        ('ambiguous-channel', 'duplicate.fcs', {'channels': ['Target']}, 'ambiguous'),
        ('requested-bad-calibration', 'bad-gain.fcs', {'channels': [3], 'scaled': True}, 'gain'),
        ('correlated-mode', 'correlated.fcs', {'channels': [1]}, 'list DATA'),
        ('uncorrelated-mode', 'uncorrelated.fcs', {'channels': [1]}, 'list DATA'),
    ]:
        (directory / (name + '.json')).write_text(json.dumps(dict(PLAN, probabilities=PROBABILITIES, **extra)) + '\n', 'utf-8')
        errors.append({'id': name, 'source': source, 'options': name + '.json', 'error': error})
    api_expected = {view: quantile_truth([view_value(ROWS, e, 1, view) for e in MEMBERS])
                    for view in ['raw', 'scaled', 'compensated']}
    (directory / 'public-consumer-expected.json').write_text(json.dumps(api_expected, indent=2) + '\n', 'utf-8')
    (directory / 'CASES.json').write_text(json.dumps({'positive': cases, 'controls': controls, 'negative': errors}, indent=2) + '\n', 'utf-8')
    manifest = {file.name: {'bytes': file.stat().st_size, 'SHA256': sha(file)}
                for file in sorted(directory.iterdir())}
    (directory / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', 'utf-8')
    return manifest


if __name__ == '__main__':
    print(json.dumps({'files': len(fixtures(Path(sys.argv[1]))), 'directory': sys.argv[1]}))
