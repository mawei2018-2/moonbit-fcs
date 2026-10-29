"""Original Boolean DAG truth, public API and independent final-file receivers."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from boolean_gate_fixtures import fixtures, sha

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--frozen-inputs', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = args.frozen_inputs.resolve() if args.frozen_inputs else out / 'inputs'
    if not args.frozen_inputs:
        fixtures(inputs)
    manifest = json.loads((inputs / 'MANIFEST.json').read_text('utf-8'))
    for name, item in manifest.items():
        assert (inputs / name).stat().st_size == item['bytes'] and sha(inputs / name) == item['SHA256']
    definitions = json.loads((inputs / 'CASES.json').read_text('utf-8'))
    outputs = out / 'outputs'
    outputs.mkdir()
    temporary = Path(os.environ.get('FCS_PRIVATE_TEMP', out / 'tmp')).resolve()
    temporary.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({key: str(temporary) for key in ['TEMP', 'TMP', 'TMPDIR']})
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    logs = {out / 'PROCESS-LAUNCHES.jsonl'}
    if env.get('FCS_PROCESS_LOG'):
        logs.add(Path(env['FCS_PROCESS_LOG']))
    commands, cases = [], []
    report = {'status': 'in_progress', 'cases': cases, 'commands': commands,
              'oracle': 'Original complete bit-packed FCS; explicit independent full memberships and rational fractions; stdlib-only JSON/CSV/FCS receiver',
              'inputs': str(inputs), 'inputManifest': manifest}

    def save():
        (out / 'CHECKS.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')

    def run(label, argv, cwd=ROOT):
        record = {'recordedBeforeLaunchUTC': datetime.now(timezone.utc).isoformat(), 'label': label,
                  'argv': list(map(str, argv)), 'cwd': str(cwd),
                  'processEnv': {key: env[key] for key in ['TEMP', 'TMP', 'TMPDIR']}}
        for log in logs:
            with log.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(record) + '\n')
        result = subprocess.run(record['argv'], cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8')
        commands.append(dict(record, exitCode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                             stdioDomain='captured UTF-8 text, LF-normalized; FCS/CSV have separate raw byte identities'))
        save()
        return result

    def cli(label, command, source, options, destination=None):
        argv = ['node', ROOT / 'tools/fcs.mjs', command, source]
        if destination is not None:
            argv.append(destination)
        return run(label, argv + ['--options', options])

    def receive(label, actual, expected, kind='json', rejected=False):
        r = run(label, [sys.executable, '-X', 'utf8', '-B', ROOT / 'examples/boolean-gates/receive.py',
                        actual, '--kind', kind, '--expected', expected])
        if rejected:
            assert r.returncode == 1 and not r.stdout and 'AssertionError' in r.stderr, (label, r.stdout, r.stderr)
        else:
            assert r.returncode == 0 and not r.stderr, (label, r.stdout, r.stderr)

    def deliver_json(label, result, expected):
        assert result.returncode == 0 and not result.stderr, (label, result.stdout, result.stderr)
        actual = outputs / (label + '.json')
        actual.write_text(result.stdout, 'utf-8', newline='\n')
        receive(label + '-receiver', actual, expected)
        cases.append({'id': label, 'status': 'passed', 'wholeReportCompared': True, 'path': str(actual), 'SHA256': sha(actual)})
        return actual

    try:
        save()
        example = ROOT / 'examples/boolean-gates'
        for installed, frozen in [('input.fcs', 'source.fcs'), ('options.json', 'main.json'), ('expected.json', 'main-expected.json'),
                                  ('subset.json', 'subset.json'), ('subset-expected.json', 'subset-expected.json'),
                                  ('csv.json', 'csv.json'), ('csv-expected.json', 'csv-expected.json')]:
            assert (example / installed).read_bytes() == (inputs / frozen).read_bytes()
        for case in definitions['positive']:
            # The main case runs the documented, byte-identical installed example.
            source = example / 'input.fcs' if case['id'] == 'main' else inputs / case['source']
            options = example / 'options.json' if case['id'] == 'main' else inputs / case['options']
            deliver_json(case['id'], cli(case['id'], 'populations', source, options), inputs / case['expected'])
        r = cli('geometric-byte-control', 'populations', inputs / 'source.fcs', inputs / 'geometric.json')
        baseline = (example / 'geometric-report.json').read_text('utf-8')
        assert r.returncode == 0 and not r.stderr and r.stdout == baseline
        deliver_json('geometric-byte-control', r, inputs / 'geometric-expected.json')
        gate_expected = outputs / 'gate-expected.json'
        gate_expected.write_text('[3,4]\n', 'utf-8')
        deliver_json('selected-gate', cli('selected-gate', 'gate', inputs / 'source.fcs', inputs / 'subset.json'), gate_expected)
        for kind in ['fcs', 'csv']:
            for case in definitions[kind]:
                actual = outputs / (case['id'] + '.' + kind)
                command = 'subset' if kind == 'fcs' else 'csv'
                r = cli(case['id'], command, inputs / 'source.fcs', inputs / case['options'], actual)
                assert r.returncode == 0 and not r.stderr, (case, r.stdout, r.stderr)
                (outputs / (case['id'] + '-receipt.json')).write_text(r.stdout, 'utf-8', newline='\n')
                receive(case['id'] + '-receiver', actual, inputs / case['expected'], kind)
                cases.append({'id': case['id'], 'status': 'passed', 'wholeFileCompared': True,
                              'path': str(actual), 'bytes': actual.stat().st_size, 'SHA256': sha(actual)})
        deliver_json('stats', cli('stats', 'population-stats', inputs / 'source.fcs', inputs / 'stats.json'), inputs / 'stats-expected.json')
        for case in definitions['negative']:
            r = cli(case['id'], 'populations', inputs / 'source.fcs', inputs / case['options'])
            assert r.returncode == 1 and not r.stdout and case['error'] in r.stderr, (case, r.stdout, r.stderr)
            cases.append({'id': case['id'], 'status': 'passed', 'expectedExitCode': 1})
        # A selected valid branch cannot hide an unused invalid reference/cycle.
        for name in ['unknown-reference', 'mixed-parent-cycle', 'invalid-geometry-under-boolean-empty']:
            options = json.loads((inputs / (name + '.json')).read_text('utf-8'))
            options.update(population='A')
            fragment = next(case['error'] for case in definitions['negative'] if case['id'] == name)
            option_file = outputs / (name + '-selection.json')
            option_file.write_text(json.dumps(options) + '\n', 'utf-8')
            r = cli(name + '-selected', 'gate', inputs / 'source.fcs', option_file)
            assert r.returncode == 1 and not r.stdout and fragment in r.stderr
            cases.append({'id': name + '-selected', 'status': 'passed', 'expectedExitCode': 1})
            for command, suffix in [('subset', 'fcs'), ('csv', 'csv')]:
                target = outputs / (name + '-absent.' + suffix)
                r = cli(name + '-' + command + '-absent', command, inputs / 'source.fcs', option_file, target)
                assert r.returncode == 1 and not r.stdout and fragment in r.stderr and not target.exists()
                cases.append({'id': name + '-' + command + '-absent', 'status': 'passed', 'createdOutput': False})
        # Existing destinations are guarded with a valid Boolean selection too.
        for command, option, suffix in [('subset', 'subset.json', 'fcs'), ('csv', 'csv.json', 'csv')]:
            target = outputs / ('existing.' + suffix)
            target.write_bytes(b'original destination must remain\r\n')
            before = sha(target)
            r = cli('existing-' + command, command, inputs / 'source.fcs', inputs / option, target)
            assert r.returncode == 1 and not r.stdout and r.stderr and sha(target) == before
            cases.append({'id': 'existing-' + command, 'status': 'passed', 'existingBytesPreserved': True})
        moon = shutil.which('moon', path=env.get('PATH'))
        assert moon
        for target in ['js', 'wasm-gc']:
            r = run('public-consumer-' + target, [moon, 'run', '.', '--target', target, '--deny-warn', '--frozen'], ROOT / 'examples/boolean-consumer')
            assert r.returncode == 0, (target, r.stdout, r.stderr)
            # Moon may emit build progress on stderr; the report remains stdout.
            actual = outputs / ('public-consumer-' + target + '.json')
            actual.write_text(r.stdout, 'utf-8', newline='\n')
            receive('public-' + target + '-receiver', actual, inputs / 'api-expected.json')
            cases.append({'id': 'public-consumer-' + target, 'status': 'passed', 'wholeReportCompared': True,
                          'path': str(actual), 'SHA256': sha(actual)})
        raw = bytearray((outputs / 'subset.fcs').read_bytes())
        raw[int(raw[26:34])] ^= 1
        altered_fcs = outputs / 'forged-data.fcs'
        altered_fcs.write_bytes(raw)
        receive('receiver-rejects-changed-data', altered_fcs, inputs / 'subset-expected.json', 'fcs', rejected=True)
        with (outputs / 'csv.csv').open(encoding='utf-8', newline='') as stream:
            rows = list(csv.reader(stream))
        rows[1][-1] = '1'
        altered_csv = outputs / 'forged-membership.csv'
        with altered_csv.open('w', encoding='utf-8', newline='') as stream:
            csv.writer(stream).writerows(rows)
        receive('receiver-rejects-changed-membership', altered_csv, inputs / 'csv-expected.json', 'csv', rejected=True)
        populations = json.loads((outputs / 'main.json').read_text('utf-8'))
        populations[2]['event_indices'] = [2, 4]
        altered_json = outputs / 'forged-populations.json'
        altered_json.write_text(json.dumps(populations) + '\n', 'utf-8')
        receive('receiver-rejects-count-preserving-wrong-indices', altered_json, inputs / 'main-expected.json', rejected=True)
        cases.append({'id': 'receiver-rejects-three-structurally-valid-forgeries', 'status': 'passed', 'expectedReceiverErrors': 3})
        assert all(sha(inputs / name) == item['SHA256'] for name, item in manifest.items())
        report.update(status='passed', sourceInputsUnchanged=True)
    except BaseException:
        report.update(status='failed', failure=traceback.format_exc())
        raise
    finally:
        files = ['gating.mbt', 'pkg.generated.mbti', 'cmd/bridge/main.mbt', 'tools/fcs.mjs',
                 'tools/boolean_gate_fixtures.py', 'tools/check-boolean-gates.py', 'examples/boolean-gates/receive.py',
                 'examples/boolean-consumer/main.mbt', 'examples/boolean-consumer/fixture.mbt',
                 '_build/js/release/build/cmd/bridge/bridge.js']
        report['implementationSHA256'] = {name: sha(ROOT / name) for name in files if (ROOT / name).is_file()}
        bridge = ROOT / '_build/js/release/build/cmd/bridge/bridge.js'
        if bridge.is_file():
            compiled = out / 'compiled'
            compiled.mkdir()
            shutil.copyfile(bridge, compiled / 'bridge.js')
            report['compiledBridge'] = {'path': str(compiled / 'bridge.js'), 'bytes': bridge.stat().st_size, 'SHA256': sha(bridge)}
        report['deliveredFiles'] = [{'path': str(file), 'bytes': file.stat().st_size, 'SHA256': sha(file)}
                                    for file in sorted(outputs.iterdir()) if file.is_file()]
        save()
    print(json.dumps({'status': report['status'], 'cases': len(cases), 'commands': len(commands),
                      'wholePopulationReports': len(definitions['positive']), 'expectedPlanErrors': len(definitions['negative']),
                      'FCSFiles': len(definitions['fcs']), 'CSVFiles': len(definitions['csv']),
                      'sourceInputsUnchanged': True, 'report': str(out / 'CHECKS.json')}))


if __name__ == '__main__':
    main()
