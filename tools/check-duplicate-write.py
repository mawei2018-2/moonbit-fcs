"""Original MIT duplicate-PnN write regression and independent FCS file receivers."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

from duplicate_write_fixtures import fixtures

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path);parser.add_argument('--frozen-inputs',type=Path)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    inputs=args.frozen_inputs.resolve() if args.frozen_inputs else out/'inputs'
    if not args.frozen_inputs:fixtures(inputs)
    manifest=json.loads((inputs/'MANIFEST.json').read_text(encoding='utf-8'))
    for name,entry in manifest.items():assert sha(inputs/name)==entry['SHA256'] and (inputs/name).stat().st_size==entry['bytes']
    outputs=out/'outputs';outputs.mkdir()
    temp=Path(os.environ.get('FCS_PRIVATE_TEMP',out/'tmp')).resolve();temp.mkdir(exist_ok=True)
    env=os.environ.copy();env.update({key:str(temp) for key in ['TEMP','TMP','TMPDIR']});env['PYTHONDONTWRITEBYTECODE']='1'
    logs={out/'PROCESS-LAUNCHES.jsonl'}
    if os.environ.get('FCS_PROCESS_LOG'):logs.add(Path(os.environ['FCS_PROCESS_LOG']))
    cases=[];commands=[];actual=[]
    report={'status':'in_progress','cases':cases,'commands':commands,'rawOutputs':actual,'inputs':str(inputs),'inputManifest':str(inputs/'MANIFEST.json'),
            'implementation':{str(path.relative_to(ROOT)):sha(path) for path in [ROOT/'construction.mbt',ROOT/'write.mbt',ROOT/'duplicate_write_wbtest.mbt',ROOT/'pkg.generated.mbti',ROOT/'tools/fcs.mjs',Path(__file__),ROOT/'tools/duplicate_write_fixtures.py',ROOT/'examples/duplicate-write/receive.py',ROOT/'_build/js/release/build/cmd/bridge/bridge.js']}}
    def save():(out/'CHECKS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def run(label,args):
        entry={'recordedBeforeLaunchUTC':datetime.now(timezone.utc).isoformat(),'label':label,'argv':list(map(str,args)),'cwd':str(out),
               'processEnv':{key:env[key] for key in ['TEMP','TMP','TMPDIR']}}
        for log in logs:
            with log.open('a',encoding='utf-8') as stream:stream.write(json.dumps(entry,ensure_ascii=False)+'\n')
        result=subprocess.run(entry['argv'],cwd=out,env=env,capture_output=True,text=True,encoding='utf-8')
        entry.update({'exitCode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'stdioDomain':'Captured UTF-8 text; raw FCS bytes read separately'})
        commands.append(entry);save();return result
    def positive(label,source,options,expected):
        output=outputs/(label+'.fcs')
        producer=run(label,['node',ROOT/'tools/fcs.mjs','rewrite',source,output,'--options',options])
        assert producer.returncode==0 and not producer.stderr,(label,producer.stdout,producer.stderr)
        assert json.loads(producer.stdout)=={'written':str(output),'bytes':output.stat().st_size}
        receiver=run(label+'-file-receiver',[sys.executable,'-X','utf8','-B',ROOT/'examples/duplicate-write/receive.py',output,'--expected',expected])
        assert receiver.returncode==0 and not receiver.stderr,(label,receiver.stdout,receiver.stderr)
        result=json.loads(receiver.stdout)
        actual.append({'path':str(output),'bytes':output.stat().st_size,'SHA256':sha(output),'receiver':result})
        cases.append({'label':label,'status':'passed','producerExitCode':producer.returncode,'receiverExitCode':receiver.returncode});save()
    try:
        definitions=json.loads((inputs/'CASES.json').read_text(encoding='utf-8'))
        for case in definitions['positive']:positive(case['label'],inputs/case['source'],inputs/case['options'],inputs/case['expected'])
        for case in definitions['negative']:
            output=outputs/(case['label']+'.fcs')
            paths=([inputs/case['source']] if case['source'] else [])+[output]
            result=run(case['label'],['node',ROOT/'tools/fcs.mjs',case['command'],*paths,'--options',inputs/case['options']])
            assert result.returncode==1 and not result.stdout and case['expectedErrorContains'] in result.stderr,case
            assert not output.exists(),case
            cases.append({**case,'status':'passed','actualExitCode':result.returncode,'outputAbsent':True});save()
        example=ROOT/'examples/duplicate-write'
        positive('standalone-example',example/'input.fcs',example/'rewrite.json',example/'expected.json')
        for name,entry in manifest.items():assert sha(inputs/name)==entry['SHA256']
        report.update({'status':'passed','caseCount':len(cases),'commandCount':len(commands),'successfulFCSFiles':len(actual),
                       'independentFileReceivers':len(actual),'expectedErrorCount':sum(command['exitCode']==1 for command in commands),'originalInputsUnchanged':True})
    except BaseException:
        report.update({'status':'failed','failure':traceback.format_exc()});raise
    finally:save()
    print(json.dumps({'status':report['status'],'cases':len(cases),'commands':len(commands),'FCSFiles':len(actual),
                      'independentReceivers':len(actual),'expectedErrors':report['expectedErrorCount'],'report':str(out/'CHECKS.json')}))


if __name__=='__main__':main()
