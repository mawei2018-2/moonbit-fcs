"""Independent requested-statistics dependency consumers, original MIT.

No new numerical algorithm: closed-form triangular expectations and raw I16
bytes are independent of the implementation. RepOD compatibility controls retain
its existing CC BY4.0 attribution. All local subprocesses are recorded first.
"""
import argparse
import csv
from fractions import Fraction
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
ROWS=[[8,24,5],[20,100,7],[12,20,9],[4,8,11],[40,400,13]]
MEMBERS=[0,2,3]
SELECTED=[2,3]
NAMES=['Driver','Target','Unavailable']
PLAN={'gates':[{'id':'p','bounds':[['Driver',0,13]]}], 'population':'p','start':1,'count':2}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make(*,bad=True,dependent=False):
    raw=struct.pack('<15H',*[value for row in ROWS for value in row])
    pairs=[('$MODE','L'),('$DATATYPE','I'),('$BYTEORD','1,2,3,4'),('$PAR','3'),('$TOT','5'),
           ('$BEGINSTEXT','0'),('$ENDSTEXT','0'),('$BEGINANALYSIS','0'),('$ENDANALYSIS','0'),
           ('$NEXTDATA','0'),('$BEGINDATA','000000000000'),('$ENDDATA','000000000000')]
    for i,name in enumerate(NAMES,1):
        pairs += [(f'$P{i}N',name),(f'$P{i}B','16'),(f'$P{i}R','65536'),(f'$P{i}E','0,0'),
                  (f'$P{i}G',str([2,4,0 if bad else 1][i-1]))]
    matrix='3,Driver,Target,Unavailable,1,0.5,0,0,1,0,0,0.25,1' if dependent else '2,Driver,Target,1,0.5,0,1'
    pairs.append(('$SPILLOVER',matrix))
    def text():return ('|'+'|'.join(value for pair in pairs for value in pair)+'|').encode()
    start=256+len(text());end=start+len(raw)-1
    pairs=[(k,f'{start:012d}' if k=='$BEGINDATA' else f'{end:012d}' if k=='$ENDDATA' else v) for k,v in pairs]
    header=b'FCS3.1    '+b''.join(f'{n:8d}'.encode() for n in [256,start-1,start,end,0,0])
    data=header.ljust(256,b' ')+text()+raw
    fields=data[256:start][1:-1].split(b'|')
    meta=dict(zip(fields[::2],fields[1::2]))
    assert int(meta[b'$BEGINDATA'])==start and int(meta[b'$ENDDATA'])==len(data)-1
    assert list(struct.iter_unpack('<3H',data[start:]))==[tuple(row) for row in ROWS]
    return data


def truth(indices,columns,view,bad):
    rows=[]
    for index in indices:
        d,t,u=map(Fraction,ROWS[index])
        if view!='raw':
            d/=2;t/=4
            if view=='compensated':t-=d/2
            if not bad:u/=1
        rows.append([d,t,u])
    result=[]
    for column in columns:
        values=[row[column] for row in rows]
        stat={'count':len(values),'nonfinite':0}
        if values:
            mean=sum(values)/len(values)
            stat.update(minimum=float(min(values)),maximum=float(max(values)),mean=float(mean))
            if len(values)>1:stat['variance']=float(sum((x-mean)**2 for x in values)/(len(values)-1))
        result.append(stat)
    return result


def verify_statistics(actual,expected):
    assert len(actual)==len(expected)
    for statistic,wanted in zip(actual,expected):
        assert set(statistic)==set(wanted)
        for key,value in wanted.items():
            if key in ['count','nonfinite']:assert statistic[key]==value
            else:assert math.isclose(statistic[key],value,rel_tol=2e-12,abs_tol=1e-12),(statistic,wanted)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args();out=args.directory.resolve();out.mkdir(parents=True,exist_ok=False)
    temporary=Path(os.environ.get('FCS_PRIVATE_TEMP',out/'tmp')).resolve();temporary.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(TEMP=str(temporary),TMP=str(temporary),TMPDIR=str(temporary),PYTHONDONTWRITEBYTECODE='1',NODE_COMPILE_CACHE=str(out/'node-cache'))
    process_log=Path(os.environ.get('FCS_PROCESS_LOG',out/'PROCESS-LAUNCHES.jsonl'))
    commands,cases=[],[];status='failed'
    def launch(argv,cwd=ROOT,error=False):
        executable=shutil.which(str(argv[0]),path=env.get('PATH')) or str(argv[0])
        argv=[executable,*map(str,argv[1:])];cwd=Path(cwd).resolve()
        if 'FCS_ALLOWED_WORKSPACE' in env:
            allowed=Path(env['FCS_ALLOWED_WORKSPACE']).resolve()
            assert cwd.is_relative_to(allowed) and temporary.is_relative_to(allowed)
        record={'recordedBeforeLaunchUTC':datetime.now(timezone.utc).isoformat(),'argv':argv,'cwd':str(cwd),
                'processEnv':{key:env[key] for key in ['TEMP','TMP','TMPDIR','PYTHONDONTWRITEBYTECODE','NODE_COMPILE_CACHE']}}
        with process_log.open('a',encoding='utf-8') as f:f.write(json.dumps(record)+'\n')
        run=subprocess.run(argv,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        commands.append(dict(record,exitCode=run.returncode,stdout=run.stdout,stderr=run.stderr,expectedError=error))
        if error:assert run.returncode!=0 and run.stderr and not run.stdout,commands[-1]
        else:assert run.returncode==0,commands[-1]
        return run
    def cli(command,path,options,dest=None,error=False):
        cfg=out/f'options-{len(commands):03d}.json';cfg.write_text(json.dumps(options),encoding='utf-8')
        argv=['node','tools/fcs.mjs',command,str(path)]
        if dest is not None:argv.append(str(dest))
        argv+=['--options',str(cfg)]
        result=launch(argv,error=error)
        if not error:assert not result.stderr,commands[-1]
        return result
    def check(path,columns,view,*,bad=True,indices=SELECTED,members=MEMBERS,options=None):
        options=dict(PLAN,channels=columns,**(options or {}))
        if view=='scaled':options['scaled']=True
        if view=='compensated':options.update(scaled=False,compensated=True)
        r=cli('population-stats',path,options);result=json.loads(r.stdout)
        selected_columns=[NAMES.index(c) if isinstance(c,str) else c for c in columns]
        expected=truth(indices,selected_columns,view,bad)
        assert result['source_event_indices']==indices and result['population_events']==len(members)
        assert result['channel_indices']==selected_columns and result['channel_names']==[NAMES[i] for i in selected_columns]
        assert result['scaled']==(view!='raw') and result['compensated']==(view=='compensated')
        assert result['events']==len(indices)
        verify_statistics(result['statistics'],expected)
        if options.get('include_read_report'):
            assert result['read_report']['source_sha256']==sha(path)
            assert 'non-positive $P3G: scaled access is unavailable' in result['read_report']['warnings']
        cases.append({'case':'requested value path','source':path.name,'columns':selected_columns,'view':view,'members':indices,'statistics':result['statistics']})
        return result
    paths={}
    for label,options in [('unrelated',{}),('dependent',{'dependent':True}),('healthy',{'bad':False})]:
        paths[label]=out/(label+'.fcs');paths[label].write_bytes(make(**options))
    assert sha(paths['unrelated'])=='f80683ff5f93984f2dd7b15c1d23efbef2e4b657da3f646d3a4d07c71008af3c'
    original={str(path):sha(path) for path in paths.values()}
    try:
        for view in ['raw','scaled','compensated']:
            check(paths['unrelated'],['Target'],view,options={'include_read_report':True})
            check(paths['unrelated'],[1,'Driver',1],view)
            check(paths['unrelated'],[],view)
        check(paths['unrelated'],['Target']*25,'compensated')
        check(paths['unrelated'],['Target'],'compensated',indices=[],options={'start':3,'count':0})
        check(paths['unrelated'],['Target'],'compensated',indices=[2],options={'start':1,'count':1})
        # Complete original matrix remains present. Driver does not depend on the bad channel,
        # but the dependent Target expression contains -Unavailable/4 and must still fail.
        check(paths['dependent'],['Driver'],'compensated')
        check(paths['dependent'],['Target'],'scaled')
        for options in [dict(PLAN,channels=['Target'],compensated=True),dict(PLAN,channels=['Driver','Target'],compensated=True),
                        dict(PLAN,channels=['Unavailable'],scaled=True),dict(PLAN,channels=['Unavailable'],compensated=True)]:
            cli('population-stats',paths['dependent'],options,error=True)
        for channels in [None,'omit']:
            options=dict(PLAN,scaled=True)
            if channels is None:options['channels']=None
            cli('population-stats',paths['unrelated'],options,error=True)
            healthy=json.loads(cli('population-stats',paths['healthy'],options).stdout)
            assert healthy['statistics']==truth(SELECTED,[0,1,2],'scaled',False)
            assert 'channel_indices' not in healthy and 'read_report' not in healthy
            cases.append({'case':'healthy default all-channel compatibility','channels':channels})
        # Default generic stats is intentionally unchanged, even if a channels option is supplied.
        cli('stats',paths['unrelated'],{'channels':['Target'],'scaled':True},error=True)
        generic=json.loads(cli('stats',paths['healthy'],{'channels':['Target'],'scaled':True}).stdout)
        verify_statistics(generic,truth(range(len(ROWS)),[0,1,2],'scaled',False))
        cases.append({'case':'generic stats retains all outputs'})
        for columns in [['Unavailable'],[1.5],['missing']]:
            cli('population-stats',paths['unrelated'],dict(PLAN,channels=columns,scaled=True),error=True)
        cli('population-stats',paths['unrelated'],dict(PLAN,channels=['Target'],strict=True,scaled=True),error=True)
        gate_options=dict(PLAN,channels=['Driver'],compensated=True,gates=[{'id':'p','bounds':[['Target',0,100]],'compensated':True}])
        cli('population-stats',paths['dependent'],gate_options,error=True)
        csv_path=out/'compensated-target.csv'
        csv_result=cli('csv',paths['unrelated'],dict(PLAN,channels=['Target'],compensated=True),csv_path)
        assert list(csv.reader(io.StringIO(csv_path.read_text())))==[['Target'],['2'],['1']]
        assert json.loads(csv_result.stdout)['source_event_indices']==SELECTED
        # Actual original project consumers pin default bytes; only replay the affected path,
        # not the unchanged old complete suite or its previously successful error checks.
        spec=importlib.util.spec_from_file_location('read_report_oracle',ROOT/'tools/check-population-read-report.py')
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        compatibility=out/'compatibility';compatibility.mkdir()
        for case in old.fixtures(ROOT,compatibility):
            r=cli('population-stats',case['path'],case['options'])
            assert hashlib.sha256(r.stdout.encode()).hexdigest()==old.DEFAULT_STDOUT_SHA256[case['id']]
            old.verify_statistics(json.loads(r.stdout),case)
            cases.append({'case':'existing default-byte control','id':case['id'],'stdoutSHA256':hashlib.sha256(r.stdout.encode()).hexdigest()})
        for name in ['ATTRIBUTION.md','CC-BY-4.0.txt','SOURCE.json']:shutil.copyfile(ROOT/'examples/repod'/name,compatibility/name)
        (compatibility/'CHANGES.md').write_text('Bronisz, Agnieszka (2026), Flow Cytometry data, RepOD V2, DOI10.18150/JOLWGT, file96804; CC BY4.0. Existing independently normalized offset control and statistics JSON only; original DATA and source remain unchanged. No clinical interpretation.\n',encoding='utf-8')
        # Consume the new bridge selection query directly on the full retained Dataset.
        driver=r"""import fs from 'node:fs';import path from 'node:path';import {pathToFileURL} from 'node:url';
const [root,source]=process.argv.slice(1);const api=await import(pathToFileURL(path.join(root,'_build/js/release/build/cmd/bridge/bridge.js')).href);
const data=fs.readFileSync(source);const copy=api.transform(data,JSON.stringify({command:'subset',events:[2,3]}));const d=api.load(copy,'{}');
const result=JSON.parse(api.query(d,JSON.stringify({command:'selected-stats',channels:['Target',0,'Target'],compensated:true})));
for(const field of ['scaled','compensated']){let failed=false;try{api.query(d,JSON.stringify({command:'selected-stats',channels:[],[field]:'invalid'}));}catch{failed=true;}if(!failed)throw new Error('empty requested channels hid an invalid '+field);}
console.log(JSON.stringify(result));"""
        r=launch(['node','--input-type=module','-e',driver,str(ROOT),str(paths['unrelated'])])
        assert json.loads(r.stdout)==truth(SELECTED,[1,0,1],'compensated',True)
        # Actual public MoonBit per-channel API on the identical original raw-byte file.
        consumer=out/'public-consumer';consumer.mkdir()
        (consumer/'moon.mod').write_text('name = "mawei2018-2/fcs-stat-dependency-consumer"\nversion = "0.1.0"\nlicense = "MIT"\nimport { "mawei2018-2/fcs@0.5.0", }\n',encoding='utf-8')
        (consumer/'moon.pkg').write_text('import { "mawei2018-2/fcs", }\npkgtype(kind: "executable")\n',encoding='utf-8')
        (consumer/'moon.work').write_text('members = ['+json.dumps(ROOT.as_posix())+', ".",]\n',encoding='utf-8')
        literal='b"'+''.join('\\x'+f'{byte:02x}' for byte in paths['unrelated'].read_bytes())+'"'
        main='''///|
fn main {
 let source = try! @fcs.parse(FIXTURE)
 let d = try! @fcs.parse(try! source.write(event_indices=[2, 3]))
 let result : Json = {
   "scaled": (try! d.statistics(1, scaled=true)).to_json(),
   "compensated": (try! d.statistics(1, compensated=true)).to_json(),
 }
 println(result.stringify())
}
'''.replace('FIXTURE',literal)
        (consumer/'main.mbt').write_text(main,encoding='utf-8')
        moon=shutil.which('moon',path=env.get('PATH'));assert moon
        for target in ['js','wasm-gc']:
            r=launch([moon,'run','.','--target',target,'--deny-warn'],cwd=consumer)
            value=json.loads(r.stdout.strip().splitlines()[-1])
            assert value['scaled']==truth(SELECTED,[1],'scaled',True)[0] and value['compensated']==truth(SELECTED,[1],'compensated',True)[0]
            cases.append({'case':'public MoonBit statistics channel consumer','target':target,'result':value})
        example=ROOT/'examples/stat-channel-dependencies'
        assert (example/'input.fcs').read_bytes()==paths['unrelated'].read_bytes()
        result=json.loads(cli('population-stats',example/'input.fcs',json.loads((example/'population.json').read_text())).stdout)
        assert result['statistics']==truth(SELECTED,[1],'compensated',True)
        assert all(sha(Path(path))==value for path,value in original.items())
        status='passed'
    finally:
        files=['tools/fcs.mjs','cmd/bridge/main.mbt','events.mbt','compensation.mbt','tools/check-population-stat-dependencies.py','pkg.generated.mbti','_build/js/release/build/cmd/bridge/bridge.js']
        report={'status':status,'oracle':'Original raw I16/struct bytes and closed-form Fraction values; same-window CSV; actual per-channel API; frozen default stdout consumers',
                'cases':cases,'commands':commands,'sourceSHA256':{f:sha(ROOT/f) for f in files},'sourceFilesUnchanged':all(sha(Path(path))==value for path,value in original.items()),'processLaunchLog':str(process_log)}
        (out/'CHECKS.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':status,'cases':len(cases),'commands':len(commands),'defaultByteControls':13,'sourceFilesUnchanged':True}))


if __name__=='__main__':main()
