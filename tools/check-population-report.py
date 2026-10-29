"""Original MIT cohort report checks with full raw inputs and CSV-only receivers."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

from population_report_fixtures import fixtures, GATES, MEMBERS
from population_report_cases import negative_cases

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--frozen-inputs',type=Path)
    parser.add_argument('--frozen-negative-inputs',type=Path)
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    inputs=args.frozen_inputs.resolve() if args.frozen_inputs else out/'inputs'
    negatives=args.frozen_negative_inputs.resolve() if args.frozen_negative_inputs else out/'negative-inputs'
    if not args.frozen_inputs:fixtures(inputs)
    if not args.frozen_negative_inputs:negative_cases(negatives,inputs,GATES)
    for directory in [inputs,negatives]:
        for name,expected in json.loads((directory/'MANIFEST.json').read_text(encoding='utf-8')).items():
            assert sha(directory/name)==expected['SHA256'] and (directory/name).stat().st_size==expected['bytes']
    outputs=out/'outputs';outputs.mkdir()
    private_tmp=Path(os.environ.get('FCS_PRIVATE_TEMP',out/'tmp')).resolve();private_tmp.mkdir(exist_ok=True)
    child_env=os.environ.copy()
    child_env.update({key:str(private_tmp) for key in ['TEMP','TMP','TMPDIR']})
    child_env['PYTHONDONTWRITEBYTECODE']='1'
    logs={out/'PROCESS-LAUNCHES.jsonl'}
    if os.environ.get('FCS_PROCESS_LOG'):logs.add(Path(os.environ['FCS_PROCESS_LOG']))
    cases=[];commands=[];actual=[]
    check={'status':'in_progress','cases':cases,'commands':commands,'rawOutputs':actual,
           'inputs':str(inputs),'negativeInputs':str(negatives),'inputManifests':[str(inputs/'MANIFEST.json'),str(negatives/'MANIFEST.json')],
           'implementation':{str(path.relative_to(ROOT)):sha(path) for path in [ROOT/'tools/fcs.mjs',ROOT/'tools/population-report.mjs',
                            ROOT/'tools/population_report_fixtures.py',ROOT/'tools/population_report_cases.py',Path(__file__),
                            ROOT/'examples/population-report/receive.py',ROOT/'_build/js/release/build/cmd/bridge/bridge.js']}}
    def save():(out/'CHECKS.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def run(label,argv,cwd=out):
        record={'recordedBeforeLaunchUTC':datetime.now(timezone.utc).isoformat(),'label':label,'argv':list(map(str,argv)),
                'cwd':str(cwd),'processEnv':{key:child_env[key] for key in ['TEMP','TMP','TMPDIR']}}
        for log in logs:
            with log.open('a',encoding='utf-8') as stream:stream.write(json.dumps(record,ensure_ascii=False)+'\n')
        result=subprocess.run(record['argv'],cwd=cwd,env=child_env,capture_output=True,text=True,encoding='utf-8')
        record.update({'exitCode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
                       'stdioDomain':'Captured UTF-8 text; raw CSV bytes are read from files separately'})
        commands.append(record);save()
        return result
    try:
        for label,manifest,options,expected in [
            ('main','samples.json','gates.json','main'),('reverse','reverse.json','gates.json','reverse'),
            ('absolute','absolute.json','gates.json','absolute'),('override','override.json','override-gates.json','override'),
            ('warnings','warnings.json','warning-gates.json','warnings')]:
            destination=outputs/(label+'.csv')
            r=run(label,['node',ROOT/'tools/fcs.mjs','population-report',inputs/manifest,destination,'--options',inputs/options])
            assert r.returncode==0 and not r.stderr,(label,r.stdout,r.stderr)
            receipt=json.loads(r.stdout);exp=json.loads((inputs/(expected+'-expected.json')).read_text(encoding='utf-8'))
            assert receipt=={'written':str(destination),'samples':exp['sampleCount'],'rows':len(exp['rows'])}
            receiver=run(label+'-CSV-receiver',[sys.executable,'-X','utf8','-B',ROOT/'examples/population-report/receive.py',
                                                destination,'--expected',inputs/(expected+'-expected.json')])
            assert receiver.returncode==0 and not receiver.stderr,(label,receiver.stdout,receiver.stderr)
            actual.append({'path':str(destination),'bytes':destination.stat().st_size,'SHA256':sha(destination),'receiver':json.loads(receiver.stdout)})
            cases.append({'label':label,'status':'passed','exitCode':r.returncode,'receiverExitCode':receiver.returncode,'rows':len(exp['rows'])});save()
        for case in json.loads((negatives/'CASES.json').read_text(encoding='utf-8')):
            destination=outputs/(case['label']+'.csv')
            r=run(case['label'],['node',ROOT/'tools/fcs.mjs','population-report',case['manifest'],destination,'--options',case['options']])
            assert r.returncode==case['expectedExit'] and not r.stdout and case['expectedErrorContains'] in r.stderr,case
            assert not destination.exists(),case
            cases.append({**case,'status':'passed','actualExitCode':r.returncode,'outputAbsent':True});save()
        destination=outputs/'existing.csv';sentinel=b'EXISTING COHORT\r\n\x00\xff';destination.write_bytes(sentinel)
        r=run('preserve-existing',['node',ROOT/'tools/fcs.mjs','population-report',inputs/'samples.json',destination,'--options',inputs/'gates.json'])
        assert r.returncode==1 and not r.stdout and 'EEXIST' in r.stderr and destination.read_bytes()==sentinel
        cases.append({'label':'preserve-existing','status':'passed','actualExitCode':r.returncode,'SHA256':sha(destination)})
        destination=outputs/'standalone-example.csv';example=ROOT/'examples/population-report'
        r=run('standalone-example',['node',ROOT/'tools/fcs.mjs','population-report',example/'samples.json',destination,'--options',example/'gates.json'])
        assert r.returncode==0 and not r.stderr
        receiver=run('standalone-example-CSV-receiver',[sys.executable,'-X','utf8','-B',example/'receive.py',destination,'--expected',example/'expected.json'])
        assert receiver.returncode==0 and not receiver.stderr,(receiver.stdout,receiver.stderr)
        result=json.loads(receiver.stdout)
        assert json.loads(r.stdout)=={'written':str(destination),'samples':3,'rows':18}
        actual.append({'path':str(destination),'bytes':destination.stat().st_size,'SHA256':sha(destination),'receiver':result})
        cases.append({'label':'standalone-example','status':'passed','exitCode':r.returncode,'receiverExitCode':receiver.returncode,'rows':18})
        r=run('legacy-populations',['node',ROOT/'tools/fcs.mjs','populations',inputs/'panel A.fcs','--options',inputs/'gates.json'])
        assert r.returncode==0 and not r.stderr
        expected=[]
        for i,gate in enumerate(GATES):
            indices=MEMBERS['A'][i];count=len(indices);parent=gate.get('parent');denominator=(5 if parent=='band' else 0) if parent else 9
            row={'id':gate['id'],'event_indices':indices,'count':count,'parent_count':denominator,'total_count':9,'total_fraction':count/9}
            if parent:row['parent']=parent
            if denominator:row['parent_fraction']=count/denominator
            expected.append(row)
        assert json.loads(r.stdout)==expected
        cases.append({'label':'legacy-populations','status':'passed','exitCode':r.returncode})
        for directory in [inputs,negatives]:
            for name,expected in json.loads((directory/'MANIFEST.json').read_text(encoding='utf-8')).items():assert sha(directory/name)==expected['SHA256']
        check.update({'status':'passed','caseCount':len(cases),'commandCount':len(commands),'successfulCSVs':len(actual),
                      'expectedErrorCount':sum(command['exitCode']==1 for command in commands),'receiverCount':6,'originalInputsUnchanged':True})
    except BaseException:
        check.update({'status':'failed','failure':traceback.format_exc()});raise
    finally:save()
    print(json.dumps({'status':check['status'],'cases':len(cases),'commands':len(commands),'CSVFiles':len(actual),
                      'CSVOnlyReceivers':6,'expectedErrors':check['expectedErrorCount'],'report':str(out/'CHECKS.json')}))


if __name__=='__main__':main()
