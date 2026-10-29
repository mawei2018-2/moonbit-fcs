"""Original MIT complete Dataset extraction and independent directory receiving."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

from extract_dataset_fixtures import fixtures

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path);parser.add_argument('--frozen-inputs',type=Path)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    inputs=args.frozen_inputs.resolve() if args.frozen_inputs else out/'inputs'
    if not args.frozen_inputs:fixtures(inputs)
    manifest=json.loads((inputs/'MANIFEST.json').read_text(encoding='utf-8'))
    for name,item in manifest.items():assert sha(inputs/name)==item['SHA256'] and (inputs/name).stat().st_size==item['bytes']
    outputs=out/'outputs';outputs.mkdir()
    temp=Path(os.environ.get('FCS_PRIVATE_TEMP',out/'tmp')).resolve();temp.mkdir(exist_ok=True)
    env=os.environ.copy();env.update({key:str(temp) for key in ['TEMP','TMP','TMPDIR']});env['PYTHONDONTWRITEBYTECODE']='1'
    logs={out/'PROCESS-LAUNCHES.jsonl'}
    if os.environ.get('FCS_PROCESS_LOG'):logs.add(Path(os.environ['FCS_PROCESS_LOG']))
    cases=[];commands=[];raw=[]
    report={'status':'in_progress','cases':cases,'commands':commands,'bundles':raw,'inputs':str(inputs),'inputManifest':str(inputs/'MANIFEST.json'),
            'implementation':{str(path.relative_to(ROOT)):sha(path) for path in [ROOT/'tools/fcs.mjs',ROOT/'tools/extract-datasets.mjs',Path(__file__),
               ROOT/'tools/extract_dataset_fixtures.py',ROOT/'examples/extract-datasets/receive.py',ROOT/'_build/js/release/build/cmd/bridge/bridge.js']}}
    def save():(out/'CHECKS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def run(label,argv):
        record={'recordedBeforeLaunchUTC':datetime.now(timezone.utc).isoformat(),'label':label,'argv':list(map(str,argv)),'cwd':str(out),
                'processEnv':{key:env[key] for key in ['TEMP','TMP','TMPDIR']}}
        for log in logs:
            with log.open('a',encoding='utf-8') as stream:stream.write(json.dumps(record,ensure_ascii=False)+'\n')
        result=subprocess.run(record['argv'],cwd=out,env=env,capture_output=True,text=True,encoding='utf-8')
        record.update({'exitCode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'stdioDomain':'Captured UTF-8 text; complete raw FCS/manifest files recorded separately'})
        commands.append(record);save();return result
    def positive(label,source,options,expected):
        directory=outputs/label
        argv=['node',ROOT/'tools/fcs.mjs','extract-datasets',source,directory]
        if options is not None:argv+=['--options',options]
        producer=run(label,argv)
        assert producer.returncode==0 and not producer.stderr,(label,producer.stdout,producer.stderr)
        count=len(json.loads(expected.read_text(encoding='utf-8'))['datasets'])
        assert json.loads(producer.stdout)=={'written':str(directory),'datasets':count,'manifest':str(directory/'manifest.json')}
        receiver=run(label+'-bundle-receiver',[sys.executable,'-X','utf8','-B',ROOT/'examples/extract-datasets/receive.py',directory,
                                             '--expected',expected,'--source-file',source])
        assert receiver.returncode==0 and not receiver.stderr,(label,receiver.stdout,receiver.stderr)
        files=[{'path':str(path),'bytes':path.stat().st_size,'SHA256':sha(path),'kind':'manifest JSON' if path.name=='manifest.json' else 'raw standalone FCS'} for path in sorted(directory.iterdir())]
        raw.append({'label':label,'directory':str(directory),'files':files,'receiver':json.loads(receiver.stdout)})
        cases.append({'label':label,'status':'passed','producerExitCode':0,'receiverExitCode':0,'datasets':count});save()
    try:
        definitions=json.loads((inputs/'CASES.json').read_text(encoding='utf-8'))
        for case in definitions['positive']:positive(case['label'],inputs/case['source'],inputs/case['options'],inputs/case['expected'])
        sentinel=(inputs/'existing-sentinel.bin').read_bytes()
        for case in definitions['negative']:
            destination=outputs/case['label']
            if case.get('existing')=='directory':destination.mkdir();(destination/'sentinel.bin').write_bytes(sentinel)
            elif case.get('existing')=='file':destination.write_bytes(sentinel)
            result=run(case['label'],['node',ROOT/'tools/fcs.mjs','extract-datasets',inputs/case['source'],destination,'--options',inputs/case['options']])
            assert result.returncode==1 and not result.stdout and case['error'] in result.stderr,(case,result.stdout,result.stderr)
            if case.get('existing')=='directory':assert {path.name for path in destination.iterdir()}=={'sentinel.bin'} and (destination/'sentinel.bin').read_bytes()==sentinel
            elif case.get('existing')=='file':assert destination.is_file() and destination.read_bytes()==sentinel
            else:assert not destination.exists()
            cases.append({**case,'status':'passed','actualExitCode':1,'existingPreservedOrTargetAbsent':True});save()
        forged=inputs/'forged-bundle';forged_manifest=json.loads((forged/'manifest.json').read_text(encoding='utf-8'))
        for item in forged_manifest['datasets']:assert sha(forged/item['file'])==item['sha256'] and (forged/item['file']).stat().st_size==item['bytes']
        result=run('forged-hash-receiver',[sys.executable,'-X','utf8','-B',ROOT/'examples/extract-datasets/receive.py',forged,
                                          '--expected',inputs/'main-expected.json','--source-file',definitions['forgedReceiver']['source_file']])
        assert result.returncode==1 and not result.stdout and definitions['forgedReceiver']['expectedError'] in result.stderr,result.stderr
        cases.append({'label':'forged-hash-receiver','status':'passed','actualExitCode':1,'allManifestFileHashesSelfConsistent':True,'independentWrongDATARejected':True})
        example=ROOT/'examples/extract-datasets'
        positive('standalone-example',example/'input.fcs',None,example/'expected.json')
        for name,item in manifest.items():assert sha(inputs/name)==item['SHA256']
        report.update({'status':'passed','caseCount':len(cases),'commandCount':len(commands),'successfulBundles':len(raw),
                       'successfulFCSFiles':sum(item['receiver']['datasets'] for item in raw),'manifestFiles':len(raw),
                       'decodedCells':sum(item['receiver']['decodedCells'] for item in raw),'independentBundleReceivers':len(raw),
                       'expectedErrorCount':sum(command['exitCode']==1 for command in commands),'frozenInputsUnchanged':True})
    except BaseException:
        report.update({'status':'failed','failure':traceback.format_exc()});raise
    finally:save()
    print(json.dumps({'status':report['status'],'cases':len(cases),'commands':len(commands),'bundles':len(raw),
                      'FCSFiles':report['successfulFCSFiles'],'manifestFiles':len(raw),'decodedCells':report['decodedCells'],
                      'expectedErrors':report['expectedErrorCount'],'report':str(out/'CHECKS.json')}))


if __name__=='__main__':main()
