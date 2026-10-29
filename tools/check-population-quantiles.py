"""Original byte/rational quantile checks and independent final-file consumers."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from population_quantile_fixtures import fixtures, sha

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--frozen-inputs', type=Path)
    parser.add_argument('--positive-from', type=int, default=0,
                        help='Resume only remaining positive cases; marks the report as a subset. CI uses the complete default.')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = args.frozen_inputs.resolve() if args.frozen_inputs else out / 'inputs'
    if not args.frozen_inputs:
        fixtures(inputs)
    manifest = json.loads((inputs / 'MANIFEST.json').read_text('utf-8'))
    for name, item in manifest.items():
        assert sha(inputs / name) == item['SHA256'] and (inputs / name).stat().st_size == item['bytes']
    definitions = json.loads((inputs / 'CASES.json').read_text('utf-8'))
    assert 0 <= args.positive_from <= len(definitions['positive'])
    outputs = out / 'outputs'
    outputs.mkdir()
    env = os.environ.copy()
    temp = Path(env.get('FCS_PRIVATE_TEMP', out / 'tmp')).resolve()
    temp.mkdir(exist_ok=True)
    env.update({key: str(temp) for key in ['TEMP', 'TMP', 'TMPDIR']})
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    logs = {out / 'PROCESS-LAUNCHES.jsonl'}
    if env.get('FCS_PROCESS_LOG'):
        logs.add(Path(env['FCS_PROCESS_LOG']))
    commands, cases = [], []
    report = {'status': 'in_progress', 'cases': cases, 'commands': commands,
              'oracle': 'Original struct FCS, independent rational type-7 truth, whole-JSON receiver; exact identity/counts/probabilities/zero/subnormal and <=4 ULP other Double results',
              'inputs': str(inputs), 'inputManifest': manifest,
              'skippedPositiveIDs': [case['id'] for case in definitions['positive'][:args.positive_from]]}

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
                             stdioDomain='captured UTF-8 text; delivered data files have separate raw identities'))
        save()
        return result

    def receive(label, actual, expected):
        r = run(label, [sys.executable, '-X', 'utf8', '-B', ROOT / 'examples/population-quantiles/receive.py', actual, '--expected', expected])
        assert r.returncode == 0 and not r.stderr, (label, r.stdout, r.stderr)

    def cli(label, source, options):
        return run(label, ['node', ROOT / 'tools/fcs.mjs', 'population-stats', source, '--options', options])

    try:
        save()
        for case in definitions['positive'][args.positive_from:]:
            r = cli(case['id'], inputs / case['source'], inputs / case['options'])
            assert r.returncode == 0 and not r.stderr, (case, r.stdout, r.stderr)
            actual = outputs / (case['id'] + '.json')
            actual.write_text(r.stdout, 'utf-8', newline='\n')
            receive(case['id'] + '-receiver', actual, inputs / case['expected'])
            cases.append({'id': case['id'], 'status': 'passed', 'wholeReportCompared': True, 'path': str(actual), 'SHA256': sha(actual)})
        baseline = (ROOT / 'examples/population-quantiles/default-report.json').read_text('utf-8')
        for case in definitions['controls']:
            r = cli(case['id'] + '-byte-control', inputs / case['source'], inputs / case['options'])
            assert r.returncode == 0 and not r.stderr and r.stdout == baseline
            cases.append({'id': case['id'] + '-byte-control', 'status': 'passed', 'stdoutSHA256': hashlib.sha256(r.stdout.encode()).hexdigest()})
        for case in definitions['negative']:
            r = cli(case['id'], inputs / case['source'], inputs / case['options'])
            assert r.returncode == 1 and not r.stdout and case['error'] in r.stderr, (case, r.stdout, r.stderr)
            cases.append({'id': case['id'], 'status': 'passed', 'expectedExitCode': 1})
        moon = shutil.which('moon', path=env.get('PATH'))
        assert moon
        for target in ['js', 'wasm-gc']:
            r = run('public-consumer-' + target, [moon, 'run', '.', '--target', target, '--deny-warn', '--frozen'], ROOT / 'examples/quantile-consumer')
            assert r.returncode == 0, (target, r.stdout, r.stderr)
            actual = outputs / ('public-consumer-' + target + '.json')
            actual.write_text(r.stdout, 'utf-8', newline='\n')
            receive('public-' + target + '-receiver', actual, inputs / 'public-consumer-expected.json')
            cases.append({'id': 'public-consumer-' + target, 'status': 'passed', 'wholeReportCompared': True, 'path': str(actual), 'SHA256': sha(actual)})
        driver = r'''import fs from 'node:fs';import {pathToFileURL} from 'node:url';
const api=await import(pathToFileURL(process.argv[1]).href);const d=api.load(fs.readFileSync(process.argv[2]),'{}');
const bad=[{probabilities:[]},{probabilities:[2]},{probabilities:[0.5],scaled:'bad'}];let errors=0;
for(const options of bad){try{api.query(d,JSON.stringify({command:'selected-quantiles',channels:[],...options}));throw Error('accepted invalid request');}catch(e){if(e.message==='accepted invalid request')throw e;errors++;}}
try{api.query(d,'{"command":"selected-quantiles","channels":[],"probabilities":[1e400]}');throw Error('accepted infinite probability');}catch(e){if(e.message==='accepted infinite probability')throw e;errors++;}
const empty=JSON.parse(api.query(d,'{"command":"selected-quantiles","channels":[],"probabilities":[0.5]}'));
if(empty.length!==0)throw Error('empty report columns changed');console.log(JSON.stringify({errors,empty}));'''
        r = run('direct-bridge-request-boundaries', ['node', '--input-type=module', '-e', driver,
                                                   ROOT / '_build/js/release/build/cmd/bridge/bridge.js', inputs / 'base.fcs'])
        assert r.returncode == 0 and json.loads(r.stdout) == {'errors': 4, 'empty': []}, (r.stdout, r.stderr)
        cases.append({'id': 'direct-bridge-request-boundaries', 'status': 'passed', 'expectedErrors': 4})
        example = ROOT / 'examples/population-quantiles'
        for original, frozen in [('input.fcs', 'base.fcs'), ('options.json', 'compensated.json'), ('expected.json', 'compensated-expected.json')]:
            assert (example / original).read_bytes() == (inputs / frozen).read_bytes()
        r = cli('documented-example', example / 'input.fcs', example / 'options.json')
        assert r.returncode == 0 and not r.stderr
        actual = outputs / 'documented-example.json'
        actual.write_text(r.stdout, 'utf-8', newline='\n')
        receive('documented-example-receiver', actual, example / 'expected.json')
        cases.append({'id': 'documented-example', 'status': 'passed', 'wholeReportCompared': True})
        forged = json.loads(actual.read_text('utf-8'))
        forged['quantiles'][0]['values'][1] = 999
        altered = outputs / 'forged-median.json'
        altered.write_text(json.dumps(forged) + '\n', 'utf-8')
        r = run('receiver-rejects-wrong-median', [sys.executable, '-X', 'utf8', '-B', example / 'receive.py', altered, '--expected', example / 'expected.json'])
        assert r.returncode == 1 and not r.stdout and 'AssertionError' in r.stderr
        cases.append({'id': 'receiver-rejects-wrong-median', 'status': 'passed'})
        erased = json.loads((inputs / 'subnormal-expected.json').read_text('utf-8'))
        erased['quantiles'][0]['values'][0] = 0
        erased_path = outputs / 'forged-subnormal.json'
        erased_path.write_text(json.dumps(erased) + '\n', 'utf-8')
        r = run('receiver-rejects-erased-subnormal', [sys.executable, '-X', 'utf8', '-B', example / 'receive.py', erased_path,
                                                   '--expected', inputs / 'subnormal-expected.json'])
        assert r.returncode == 1 and not r.stdout and 'AssertionError' in r.stderr
        cases.append({'id': 'receiver-rejects-erased-subnormal', 'status': 'passed'})
        assert all(sha(inputs / name) == item['SHA256'] for name, item in manifest.items())
        report.update(status='passed_subset' if args.positive_from else 'passed', sourceInputsUnchanged=True)
    except BaseException:
        report.update(status='failed', failure=traceback.format_exc())
        raise
    finally:
        files = ['quantiles.mbt', 'types.mbt', 'derived_extensions.mbt', 'events.mbt', 'compensation.mbt', 'pkg.generated.mbti',
                 'cmd/bridge/main.mbt', 'tools/fcs.mjs', 'tools/population_quantile_fixtures.py', 'tools/check-population-quantiles.py',
                 'examples/population-quantiles/receive.py', '_build/js/release/build/cmd/bridge/bridge.js']
        report['implementationSHA256'] = {name: sha(ROOT / name) for name in files}
        report['deliveredFiles'] = [{'path': str(file), 'bytes': file.stat().st_size, 'SHA256': sha(file)} for file in sorted(outputs.iterdir()) if file.is_file()]
        save()
    print(json.dumps({'status': report['status'], 'cases': len(cases), 'commands': len(commands),
                      'positiveReports': len(definitions['positive']) - args.positive_from, 'expectedErrors': len(definitions['negative']) + 6,
                      'sourceInputsUnchanged': True, 'report': str(out / 'CHECKS.json')}))


if __name__ == '__main__':
    main()
