"""Complete exact-rational compensation regressions and independent file consumers."""
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from compensation_overflow_fixtures import fixtures, sha

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
    assert all((inputs/name).stat().st_size == item['bytes'] and sha(inputs/name) == item['SHA256'] for name,item in manifest.items())
    definitions = json.loads((inputs / 'CASES.json').read_text('utf-8'))
    outputs = out / 'outputs'; outputs.mkdir()
    temporary = Path(os.environ.get('FCS_PRIVATE_TEMP', out/'tmp')).resolve()
    temporary.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({key: str(temporary) for key in ['TEMP','TMP','TMPDIR']})
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    logs = {out/'PROCESS-LAUNCHES.jsonl'}
    if env.get('FCS_PROCESS_LOG'): logs.add(Path(env['FCS_PROCESS_LOG']))
    cases, commands = [], []
    report = {'status':'in_progress','cases':cases,'commands':commands,'inputs':str(inputs),'inputManifest':manifest,
              'oracle':'Original struct binary64 files, explicit binary triangular inverses and Python Fraction exact products/sum rounded once; complete stdlib-only file receivers'}

    def save():
        (out/'CHECKS.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')

    def run(label, argv, cwd=ROOT):
        record = {'recordedBeforeLaunchUTC':datetime.now(timezone.utc).isoformat(),'label':label,
                  'argv':list(map(str,argv)),'cwd':str(cwd),'processEnv':{key:env[key] for key in ['TEMP','TMP','TMPDIR']}}
        for log in logs:
            with log.open('a',encoding='utf-8') as stream: stream.write(json.dumps(record)+'\n')
        r = subprocess.run(record['argv'],cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8')
        commands.append(dict(record,exitCode=r.returncode,stdout=r.stdout,stderr=r.stderr,
                             stdioDomain='captured UTF-8/LF text; data files separately identified as raw bytes'))
        save()
        return r

    def cli(label, command, source, options, destination=None):
        argv = ['node',ROOT/'tools/fcs.mjs',command,source]
        if destination is not None: argv.append(destination)
        return run(label,argv+['--options',options])

    def receive(label, actual, expected, kind='json', rejected=False):
        r = run(label,[sys.executable,'-X','utf8','-B',ROOT/'examples/compensation-overflow/receive.py',actual,'--expected',expected,'--kind',kind])
        if rejected: assert r.returncode==1 and not r.stdout and 'AssertionError' in r.stderr,(label,r.stdout,r.stderr)
        else: assert r.returncode==0 and not r.stderr,(label,r.stdout,r.stderr)

    def deliver(label, r, expected):
        assert r.returncode==0 and not r.stderr,(label,r.stdout,r.stderr)
        path=outputs/(label+'.json'); path.write_text(r.stdout,'utf-8',newline='\n')
        receive(label+'-receiver',path,expected)
        cases.append({'id':label,'status':'passed','wholeReportCompared':True,'path':str(path),'SHA256':sha(path)})
        return path

    try:
        save()
        example=ROOT/'examples/compensation-overflow'
        for installed,frozen in [('input.fcs','product.fcs'),('values.json','values.json'),('expected-values.json','product-values-expected.json'),
                                 ('plan.json','plan.json'),('expected-populations.json','populations-expected.json'),
                                 ('subset.json','subset.json'),('expected-subset.json','subset-expected.json'),
                                 ('csv.json','csv.json'),('expected-csv.json','csv-expected.json'),('stats.json','stats.json'),('expected-stats.json','stats-expected.json')]:
            assert (example/installed).read_bytes()==(inputs/frozen).read_bytes()
        for case in definitions['positive']:
            source=example/'input.fcs' if case['id']=='product' else inputs/case['source']
            r=cli(case['id'],'values',source,inputs/'values.json')
            if case['id']=='control': assert r.stdout==(example/'ordinary-control.json').read_text('utf-8')
            deliver(case['id'],r,inputs/case['expected'])
        deliver('populations',cli('populations','populations',inputs/'product.fcs',inputs/'plan.json'),inputs/'populations-expected.json')
        gate_expected=outputs/'gate-expected.json'; gate_expected.write_text('[0,1,2,4]\n','utf-8')
        deliver('gate',cli('gate','gate',inputs/'product.fcs',inputs/'subset.json'),gate_expected)
        for name,command,kind in [('subset','subset','fcs'),('csv','csv','csv'),('csv-window','csv','csv')]:
            target=outputs/(name+'.'+kind)
            r=cli(name,command,inputs/'product.fcs',inputs/(name+'.json'),target)
            assert r.returncode==0 and not r.stderr,(name,r.stdout,r.stderr)
            (outputs/(name+'-receipt.json')).write_text(r.stdout,'utf-8',newline='\n')
            receive(name+'-receiver',target,inputs/(name+'-expected.json'),kind)
            cases.append({'id':name,'status':'passed','wholeFileCompared':True,'path':str(target),'bytes':target.stat().st_size,'SHA256':sha(target)})
        deliver('stats',cli('stats','population-stats',inputs/'product.fcs',inputs/'stats.json'),inputs/'stats-expected.json')
        moon=shutil.which('moon',path=env.get('PATH')); assert moon
        for target in ['js','wasm-gc']:
            r=run('public-consumer-'+target,[moon,'run','.','--target',target,'--deny-warn','--frozen'],ROOT/'examples/compensation-overflow-consumer')
            assert r.returncode==0,(target,r.stdout,r.stderr)
            # Compiler progress on stderr is not part of the report.
            path=outputs/('public-'+target+'.json'); path.write_text(r.stdout,'utf-8',newline='\n')
            receive('public-'+target+'-receiver',path,inputs/'public-expected.json')
            cases.append({'id':'public-'+target,'status':'passed','wholeReportAndBinary64BitsCompared':True,'path':str(path),'SHA256':sha(path)})
        bad_options=outputs/'invalid-channel.json'; bad_options.write_text('{"compensated":true,"channels":[99]}\n','utf-8')
        r=cli('invalid-channel','values',inputs/'product.fcs',bad_options)
        assert r.returncode==1 and not r.stdout and 'channel' in r.stderr
        cases.append({'id':'invalid-channel','status':'passed','expectedExitCode':1})
        source=(inputs/'product.fcs').read_bytes()
        assert source.count(b'3,A,B,C,1,-1,0,0,0.5,0,0,0,1')==1
        singular=outputs/'derived-singular.fcs'
        singular.write_bytes(source.replace(b'3,A,B,C,1,-1,0,0,0.5,0,0,0,1',b'3,A,B,C,1,-1,0,0,0.0,0,0,0,1'))
        r=cli('singular-matrix','values',singular,inputs/'values.json')
        assert r.returncode==1 and not r.stdout and 'singular spillover matrix' in r.stderr
        cases.append({'id':'singular-matrix','status':'passed','expectedExitCode':1,'derivedInput':'same-length coefficient substitution, valid offsets; existing error contract'})
        for command,suffix in [('subset','fcs'),('csv','csv')]:
            path=outputs/('existing.'+suffix); path.write_bytes(b'keep original destination\r\n'); before=sha(path)
            r=cli('existing-'+command,command,inputs/'product.fcs',inputs/(command+'.json'),path)
            assert r.returncode==1 and not r.stdout and r.stderr and sha(path)==before
            cases.append({'id':'existing-'+command,'status':'passed','existingBytesPreserved':True})
        raw=bytearray((outputs/'subset.fcs').read_bytes()); raw[int(raw[26:34])]^=1
        forged=outputs/'forged.fcs'; forged.write_bytes(raw)
        receive('reject-wrong-raw-data',forged,inputs/'subset-expected.json','fcs',True)
        cases.append({'id':'reject-wrong-raw-data','status':'passed','expectedReceiverExitCode':1})
        with (outputs/'csv.csv').open(encoding='utf-8',newline='') as stream: rows=list(csv.reader(stream))
        rows[1][2]='1'
        forged=outputs/'forged.csv'
        with forged.open('w',encoding='utf-8',newline='') as stream: csv.writer(stream).writerows(rows)
        receive('reject-wrong-compensated-cell',forged,inputs/'csv-expected.json','csv',True)
        cases.append({'id':'reject-wrong-compensated-cell','status':'passed','expectedReceiverExitCode':1})
        populations=json.loads((outputs/'populations.json').read_text('utf-8')); populations[0]['event_indices']=[0,2,4]
        forged=outputs/'forged-populations.json'; forged.write_text(json.dumps(populations)+'\n','utf-8')
        receive('reject-count-preserving-wrong-members',forged,inputs/'populations-expected.json',rejected=True)
        cases.append({'id':'reject-count-preserving-wrong-members','status':'passed','expectedReceiverExitCode':1})
        public=json.loads((outputs/'public-js.json').read_text('utf-8')); public[0]['bits'][0][1]='1'
        forged=outputs/'forged-bits.json'; forged.write_text(json.dumps(public)+'\n','utf-8')
        receive('reject-wrong-bit-despite-zero-value',forged,inputs/'public-expected.json',rejected=True)
        cases.append({'id':'reject-wrong-bit-despite-zero-value','status':'passed','expectedReceiverExitCode':1})
        assert all(sha(inputs/name)==item['SHA256'] for name,item in manifest.items())
        report.update(status='passed',sourceInputsUnchanged=True,ordinaryControlByteCompatible=True)
    except BaseException:
        report.update(status='failed',failure=traceback.format_exc())
        raise
    finally:
        names=['compensation.mbt','compensated_dot.mbt','geometry.mbt','pkg.generated.mbti','tools/fcs.mjs',
               'tools/compensation_overflow_fixtures.py','tools/check-compensation-overflow.py','examples/compensation-overflow/receive.py',
               'examples/compensation-overflow-consumer/main.mbt','examples/compensation-overflow-consumer/fixture.mbt']
        report['implementationSHA256']={name:sha(ROOT/name) for name in names}
        compiled=out/'compiled'; compiled.mkdir()
        artifacts=[('bridge.js',ROOT/'_build/js/release/build/cmd/bridge/bridge.js')]
        for target,extension in [('js','js'),('wasm-gc','wasm')]:
            path=ROOT/'examples/compensation-overflow-consumer/_build'/target/'debug/build/mawei2018-2/fcs-compensation-overflow-example'/('fcs-compensation-overflow-example.'+extension)
            if path.is_file(): artifacts.append(('public-'+target+'.'+extension,path))
        report['actualCompiledArtifacts']=[]
        for name,source in artifacts:
            if source.is_file():
                dest=compiled/name; shutil.copyfile(source,dest)
                report['actualCompiledArtifacts'].append({'actualUsedPath':str(source),'sealedCopy':str(dest),'bytes':source.stat().st_size,'SHA256':sha(source)})
        report['deliveredFiles']=[{'path':str(file),'bytes':file.stat().st_size,'SHA256':sha(file)} for file in sorted(outputs.iterdir()) if file.is_file()]
        save()
    print(json.dumps({'status':report['status'],'cases':len(cases),'commands':len(commands),'fullBinary64Cases':len(definitions['positive']),
                      'publicAPITargets':['js','wasm-gc'],'sourceInputsUnchanged':True,'report':str(out/'CHECKS.json')}))


if __name__=='__main__': main()
