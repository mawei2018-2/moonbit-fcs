"""Independent source-offset, struct and Fraction consumers (original MIT).

The existing RepOD file and derived normalized copy remain CC BY 4.0.
No downloads or third-party Python packages are used.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from fractions import Fraction

OFFSET_KEYS = ['$BEGINSTEXT', '$ENDSTEXT', '$BEGINDATA', '$ENDDATA',
               '$BEGINANALYSIS', '$ENDANALYSIS', '$NEXTDATA']
ROWS = [[2,12,10],[4,8,20],[6,20,30],[8,16,40],[10,28,50],[12,24,60]]
GATES = [{'id':'base','bounds':[['X',0,20]]},
         {'id':'selected','parent':'base','bounds':[['Y',19,29]]},
         {'id':'empty','parent':'selected','bounds':[['X',-2,-1]]},
         {'id':'single','parent':'selected','bounds':[['X',10,11]]}]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(path, offset=0):
    data = Path(path).read_bytes()
    version = data[offset:offset+6].decode('ascii')
    ts,te,ds,de = [int(data[offset+i:offset+i+8]) for i in range(10,42,8)]
    text = data[offset+ts:offset+te+1]
    sep = text[:1]
    fields, part = [], b''
    for run in re.split(b'(' + re.escape(sep) + b'+)', text[1:]):
        if run.startswith(sep):
            part += sep*(len(run)//2)
            if len(run)%2:
                fields.append(part.decode('utf-8'))
                part = b''
        else:
            part += run
    assert not part and len(fields)%2 == 0
    meta = dict(zip(fields[::2],fields[1::2]))
    assert len(meta)*2 == len(fields)
    assert int(meta['$BEGINDATA']) == ds and int(meta['$ENDDATA']) == de
    raw = data[offset+ds:offset+de+1]
    n, total = int(meta['$PAR']), int(meta['$TOT'])
    names = [meta[f'$P{i}N'] for i in range(1,n+1)]
    kind = meta['$DATATYPE']
    code, width = {'I':('H','16'),'F':('f','32'),'D':('d','64')}[kind]
    assert all(meta[f'$P{i}B'] == width for i in range(1,n+1))
    endian = '<' if meta['$BYTEORD'] == '1,2,3,4' else '>'
    assert len(raw) == total*n*struct.calcsize(code)
    rows = list(struct.iter_unpack(endian + code*n, raw))
    offsets = {k:{'raw':meta[k], 'value':int(meta[k]),
                  'corrected':meta[k] != meta[k].strip(' ')} for k in OFFSET_KEYS}
    expected = ['accepted explicitly requested ASCII space padding in '+k
                for k in OFFSET_KEYS if offsets[k]['corrected']]
    return dict(data=data, meta=meta, raw=raw, names=names, rows=rows, version=version,
                offsets=offsets, expected_warnings=expected, text=text, delimiter=sep,
                text_start=offset+ts, next_offset=int(meta['$NEXTDATA']))


def normalize_offsets(source, target):
    original = decode(source)
    data = bytearray(original['data'])
    for key, entry in original['offsets'].items():
        if not entry['corrected']:
            continue
        old = entry['raw'].encode('ascii')
        needle = original['delimiter']+key.encode()+original['delimiter']+old+original['delimiter']
        assert original['text'].count(needle) == 1
        start = original['text_start'] + original['text'].index(needle) + 2 + len(key)
        replacement = str(entry['value']).encode('ascii').rjust(len(old),b'0')
        assert len(replacement) == len(old)
        data[start:start+len(old)] = replacement
    Path(target).write_bytes(data)
    normalized = decode(target)
    assert normalized['raw'] == original['raw']
    assert normalized['expected_warnings'] == [] and len(data) == len(original['data'])


def synthetic(*, padded=False, version='FCS3.0', next_offset=0, nonfinite=False):
    names = ['X','Z'] if nonfinite else ['X','Y','Z']
    rows = [[1,math.nan],[2,math.inf],[3,-math.inf],[4,7]] if nonfinite else ROWS
    kind, code, bits = ('D','d','64') if nonfinite else ('I','H','16')
    raw = struct.pack('<'+code*(len(rows)*len(names)),*[v for row in rows for v in row])
    pairs = [('$MODE','L'),('$DATATYPE',kind),('$BYTEORD','1,2,3,4'),
             ('$PAR',str(len(names))),('$TOT',str(len(rows))),
             ('$BEGINSTEXT','0'),('$ENDSTEXT','0'),('$BEGINANALYSIS','0'),('$ENDANALYSIS','0'),
             ('$NEXTDATA',f'{next_offset:012d}'),('$BEGINDATA','0'*12),('$ENDDATA','0'*12)]
    for i,name in enumerate(names,1):
        pairs += [(f'$P{i}N',name),(f'$P{i}B',bits),(f'$P{i}R','65536'),(f'$P{i}E','0,0')]
    if not nonfinite:
        pairs += [('$P1G','2'),('$P2G','4'),('$SPILLOVER','2,X,Y,1,0.5,0,1')]
    def text():
        return ('|'+'|'.join(v for pair in pairs for v in pair)+'|').encode('ascii')
    start = 256+len(text())
    end = start+len(raw)-1
    def number(n):
        return f' {n:010d} ' if padded else f'{n:012d}'
    pairs = [(k,number(start) if k=='$BEGINDATA' else number(end) if k=='$ENDDATA' else v) for k,v in pairs]
    header = version.encode()+b'    '+b''.join(f'{n:8d}'.encode() for n in [256,start-1,start,end,0,0])
    return header.ljust(256,b' ')+text()+raw


def fixtures(root,out):
    real = root/'examples/repod/titration_CD11c_concat.fcs'
    assert digest(real) == '91097cd6506972e13817bfda617ffa4fd27f81d93618554417ba39346882886c'
    normalized = out/'repod-normalized.fcs'
    normalize_offsets(real,normalized)
    plain, padded, nf, chain = [out/name for name in ['synthetic.fcs','synthetic-padded.fcs','nonfinite.fcs','two-datasets.fcs']]
    plain.write_bytes(synthetic())
    padded.write_bytes(synthetic(padded=True,version='FCS3.1'))
    nf.write_bytes(synthetic(version='FCS3.1',nonfinite=True))
    length = len(synthetic())
    chain.write_bytes(synthetic(next_offset=length)+synthetic(padded=True,version='FCS3.1'))
    source = decode(real)
    x,y = source['names'].index('FSC-A'),source['names'].index('SSC-A')
    real_members = [i for i,row in enumerate(source['rows']) if 600000 <= row[x] <= 900000 and 1400000 <= row[y] <= 1800000]
    assert len(real_members) == 662 and real_members[1:3] == [23,28]
    plan = json.loads((root/'examples/repod-gate-plan.json').read_text())
    real_options = dict(plan,population='inner',channels=['Time','FSC-A'],start=1,count=2)
    common = dict(gates=GATES,population='selected',channels=['Y','X','Y'],start=1,count=2)
    cases = [('real',real,0,real_options,real_members),
             ('normalized',normalized,0,real_options,real_members),
             ('no-channels',real,0,dict(real_options,channels=[]),real_members),
             ('raw',plain,0,common,[2,4,5]),
             ('scaled',plain,0,dict(common,scaled=True),[2,4,5]),
             ('compensated',plain,0,dict(common,scaled=False,compensated=True),[2,4,5]),
             ('empty',padded,0,dict(gates=GATES,population='empty',allow_offset_padding=True),[]),
             ('single',padded,0,dict(gates=GATES,population='single',allow_offset_padding=True),[4]),
             ('all',plain,0,dict(gates=GATES,population='selected'),[2,4,5]),
             ('null-channels',plain,0,dict(gates=GATES,population='selected',channels=None),[2,4,5]),
             ('nonfinite',nf,0,dict(gates=[{'id':'all','bounds':[['X',0,10]]}],population='all'),[0,1,2,3]),
             ('dataset0',chain,0,dict(common,dataset=0,allow_offset_padding=True),[2,4,5]),
             ('dataset1',chain,length,dict(common,dataset=1,allow_offset_padding=True),[2,4,5])]
    return [dict(id=name,path=path,offset=offset,options=options,members=members) for name,path,offset,options,members in cases]


def selection(case):
    options = case['options'];start = options.get('start',0)
    return case['members'][start:start+options.get('count',len(case['members'])-start)]


def expected_statistics(case):
    source = decode(case['path'],case['offset']);options = case['options']
    indices = [source['names'].index(c) if isinstance(c,str) else c for c in options['channels']] if options.get('channels') is not None else list(range(len(source['names'])))
    rows = [list(source['rows'][i]) for i in selection(case)]
    if options.get('scaled') or options.get('compensated'):
        for row in rows:
            row[0] = Fraction(row[0],2);row[1] = Fraction(row[1],4)
            if options.get('compensated'):
                row[1] -= row[0]/2
    stats=[]
    for index in indices:
        values = [row[index] for row in rows]
        finite = [Fraction(value) for value in values if math.isfinite(value)]
        s={'count':len(finite),'nonfinite':len(values)-len(finite)}
        if finite:
            mean=sum(finite)/len(finite)
            s.update(minimum=float(min(finite)),maximum=float(max(finite)),mean=float(mean))
            if len(finite)>1:s['variance']=float(sum((v-mean)**2 for v in finite)/(len(finite)-1))
        stats.append(s)
    return source,indices,stats


def verify_statistics(result,case):
    source,indices,stats = expected_statistics(case);options=case['options']
    assert result['population']==options['population'] and result['population_events']==len(case['members'])
    assert result['source_event_indices']==selection(case)
    assert result['channel_names']==[source['names'][i] for i in indices]
    assert result['scaled']==bool(options.get('scaled') or options.get('compensated')) and result['compensated']==bool(options.get('compensated'))
    assert ('channel_indices' in result)==(options.get('channels') is not None)
    if options.get('channels') is not None:assert result['channel_indices']==indices
    assert ('events' in result)==('start' in options or 'count' in options)
    if 'events' in result:assert result['events']==len(selection(case))
    assert len(result['statistics'])==len(stats)
    for actual,wanted in zip(result['statistics'],stats):
        assert set(actual)==set(wanted),(actual,wanted)
        for key,value in wanted.items():
            assert math.isclose(actual[key],value,rel_tol=2e-12,abs_tol=1e-12),(actual,wanted)
    return source,indices,stats


API_DRIVER = """
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const [root,request]=process.argv.slice(1);
const task=JSON.parse(fs.readFileSync(request,'utf8'));
const api=await import(pathToFileURL(path.join(root,'_build/js/release/build/cmd/bridge/bridge.js')).href);
const data=fs.readFileSync(task.input);
const d=api.load(data,JSON.stringify(task.options));
const source=JSON.parse(api.query(d,JSON.stringify({command:'inspect'})));
const members=JSON.parse(api.query(d,JSON.stringify({command:'gate',gates:task.options.gates,population:task.options.population})));
const parseKeys=['dataset','strict','allow_exclusive_end','latin1','allow_text_padding','allow_offset_padding'];
const options=Object.fromEntries(parseKeys.filter(k=>Object.hasOwn(task.options,k)).map(k=>[k,task.options[k]]));
const copy=api.load(api.transform(data,JSON.stringify({...options,command:'subset',events:task.selected,drop_analysis:true})),'{}');
const copyReport=JSON.parse(api.query(copy,JSON.stringify({command:'inspect'})));
const statistics=JSON.parse(api.query(copy,JSON.stringify({command:'stats',scaled:!!task.options.scaled,compensated:!!task.options.compensated})));
console.log(JSON.stringify({source,members,statistics,copy_version:copyReport.version,copy_warnings:copyReport.warnings}));
"""

# Frozen before adding the receipt at base 628e549; these pin the existing stdout bytes.
DEFAULT_STDOUT_SHA256 = {'real': '401a57a04e637b0306cc382531439f7f00f7dad4eecdda05aefaa17f88f727cb', 'normalized': '401a57a04e637b0306cc382531439f7f00f7dad4eecdda05aefaa17f88f727cb', 'no-channels': '140b26674c8787e70dc2d7fa8620d8010f7bb3cd2bb280629368e043ca777bf2', 'raw': '6f480036e3f5442af014334956efddffb3c5779b5cfc78995a761913da2f4c6a', 'scaled': '79807405a3bcb9f150e3f99b274e5cf0a753f06f2646ba7e07980f73414ae88e', 'compensated': '9b24829c2d3339f6408509f0c50aee73520cb521eae48412400ac205ca32546c', 'empty': '8a750e9ad0c4030ed4a6382aad414fabd376ac85bd3cc5f5b609598904544e95', 'single': '2906aed31b6d8c5bca9caf7b0f0e3187b181f7d55b6a20ee29beb68d8cdf7358', 'all': '8e095fc657ab54fea7bdab1f4d87f8fb4b347af21bd3de7e7c6a2ecba5ba1103', 'null-channels': '8e095fc657ab54fea7bdab1f4d87f8fb4b347af21bd3de7e7c6a2ecba5ba1103', 'nonfinite': 'd2486740e66f7827be71e8f4182eb1a2c69ba6c52da0583a21faab7dd7eb2975', 'dataset0': '6f480036e3f5442af014334956efddffb3c5779b5cfc78995a761913da2f4c6a', 'dataset1': '6f480036e3f5442af014334956efddffb3c5779b5cfc78995a761913da2f4c6a'}


def main():
    import argparse
    import os
    import shutil
    import subprocess
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    out=args.directory.resolve();out.mkdir(parents=True,exist_ok=False)
    cases=fixtures(root,out)
    before={str(case['path']):digest(case['path']) for case in cases}
    env=os.environ.copy();env['NODE_COMPILE_CACHE']=str(out/'node-cache');env['PYTHONDONTWRITEBYTECODE']='1'
    commands,checks=[],[]
    status='failed'
    def run_cli(path,options,error=False):
        option_file=out/f'options-{len(commands):03d}.json'
        option_file.write_text(json.dumps(options)+'\n',encoding='utf-8')
        argv=['node','tools/fcs.mjs','population-stats',str(path),'--options',str(option_file)]
        run=subprocess.run(argv,cwd=root,env=env,capture_output=True,text=True,encoding='utf-8')
        commands.append(dict(argv=argv,exitCode=run.returncode,stdout=run.stdout,stderr=run.stderr,expectedError=error))
        if error:
            assert run.returncode==1 and run.stderr and not run.stdout,commands[-1]
            return None
        assert run.returncode==0 and not run.stderr,commands[-1]
        return run.stdout
    def run_api(case,options=None,error=False):
        request=out/f'api-{len(commands):03d}.json'
        request.write_text(json.dumps(dict(input=str(case['path']),options=case['options'] if options is None else options,selected=selection(case))),encoding='utf-8')
        argv=['node','--input-type=module','-e',API_DRIVER,str(root),str(request)]
        run=subprocess.run(argv,cwd=root,env=env,capture_output=True,text=True,encoding='utf-8')
        commands.append(dict(argv=['node','public MoonBit API driver',str(request)],exitCode=run.returncode,stdout=run.stdout,stderr=run.stderr,expectedError=error))
        if error:
            assert run.returncode!=0 and run.stderr and not run.stdout,commands[-1]
            return None
        assert run.returncode==0 and not run.stderr,commands[-1]
        return json.loads(run.stdout)
    def verify_receipt(result,case,api):
        source,indices,truth=verify_statistics(result,case)
        report=result['read_report']
        assert set(report)=={'source_sha256','dataset','version','warnings'}
        assert report['source_sha256']==digest(case['path'])
        assert report['dataset']==case['options'].get('dataset',0) and report['version']==source['version']
        assert set(report['warnings'])==set(source['expected_warnings']) and len(report['warnings'])==len(source['expected_warnings'])
        assert report['warnings']==api['source']['warnings'] and report['version']==api['source']['version']
        assert api['members']==case['members'] and api['copy_warnings']==[]
        assert result['statistics']==[api['statistics'][i] for i in indices]
        return source
    try:
        indexed={case['id']:case for case in cases}
        for case in cases:
            plain=run_cli(case['path'],case['options'])
            assert hashlib.sha256(plain.encode()).hexdigest()==DEFAULT_STDOUT_SHA256[case['id']]
            default=json.loads(plain);verify_statistics(default,case);assert 'read_report' not in default
            disabled=run_cli(case['path'],dict(case['options'],include_read_report=False))
            assert disabled==plain
            enabled=json.loads(run_cli(case['path'],dict(case['options'],include_read_report=True)))
            legacy=dict(enabled);del legacy['read_report'];assert legacy==default
            api=run_api(case);source=verify_receipt(enabled,case,api)
            checks.append(dict(case=case['id'],source_sha256=digest(case['path']),dataset=enabled['read_report']['dataset'],version=source['version'],warnings=enabled['read_report']['warnings'],rawOffsets=source['offsets'],members=len(case['members']),selected=selection(case),defaultBytesPreserved=True,apiMatched=True,privateCopyWarnings=api['copy_warnings']))
        assert DEFAULT_STDOUT_SHA256['real']==DEFAULT_STDOUT_SHA256['normalized']
        real=indexed['real'];normal=indexed['normalized'];raw=indexed['raw']
        for bad in [None,0,'true',[],{}]:
            run_cli(real['path'],dict(real['options'],include_read_report=bad),error=True)
        # The original source still needs explicit compatibility, with no partial JSON on error.
        no_compat={k:v for k,v in real['options'].items() if k!='allow_offset_padding'}
        for options in [no_compat,dict(no_compat,strict=True),dict(real['options'],strict=True)]:
            run_cli(real['path'],dict(options,include_read_report=True),error=True)
            run_api(real,options,error=True)
        # Strict readability is independently obtained by changing only numeric offset spelling.
        strict={k:v for k,v in normal['options'].items() if k!='allow_offset_padding'}
        strict['strict']=True
        strict_case=dict(normal,options=strict)
        strict_default=run_cli(normal['path'],strict)
        assert hashlib.sha256(strict_default.encode()).hexdigest()==DEFAULT_STDOUT_SHA256['normalized']
        strict_result=json.loads(run_cli(normal['path'],dict(strict,include_read_report=True)))
        verify_receipt(strict_result,strict_case,run_api(strict_case));assert strict_result['read_report']['warnings']==[]
        for options in [dict(raw['options'],population='missing'),dict(raw['options'],channels=['missing']),
                        dict(raw['options'],population='empty',channels=['missing'],start=0,count=0),
                        dict(raw['options'],start=-1),dict(raw['options'],count=99),dict(raw['options'],start=0.5),
                        dict(raw['options'],count=None),dict(raw['options'],metadata=[['note','unsupported']]),
                        {k:v for k,v in raw['options'].items() if k!='population'}]:
            run_cli(raw['path'],dict(options,include_read_report=True),error=True)
        run_cli(out/'does-not-exist.fcs',dict(raw['options'],include_read_report=True),error=True)
        # Retain the original list-only statistics rule for both histogram modes.
        import importlib.util
        spec=importlib.util.spec_from_file_location('histogram_vectors',root/'tools/check-histogram-comp.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for mode in ['C','U']:
            path=out/(mode+'-histogram.fcs');path.write_bytes(module.make(mode))
            run_cli(path,dict(raw['options'],include_read_report=True),error=True)
        # The real licensed consumer uses a single statistics call, with no inspect side channel.
        example=out/'example'
        argv=['node','examples/repod-population-read-report.mjs',str(example)]
        run=subprocess.run(argv,cwd=root,env=env,capture_output=True,text=True,encoding='utf-8')
        commands.append(dict(argv=argv,exitCode=run.returncode,stdout=run.stdout,stderr=run.stderr))
        assert run.returncode==0 and not run.stderr,commands[-1]
        result=json.loads((example/'statistics.json').read_text(encoding='utf-8'))
        verify_receipt(result,real,run_api(real))
        assert not list(example.glob('*.fcs'))
        for name in ['ATTRIBUTION.md','CC-BY-4.0.txt','SOURCE.json']:
            assert (example/name).read_bytes()==(root/'examples/repod'/name).read_bytes()
            shutil.copyfile(root/'examples/repod'/name,out/name)
        (out/'CHANGES.md').write_text('Bronisz, Agnieszka (2026), Flow Cytometry data, RepOD V2, DOI10.18150/JOLWGT, file96804, CC BY4.0. Derived normalized FCS changes only ASCII spelling of padded zero offsets, preserving byte width and DATA. Statistics/provenance JSON is a format-exchange example, with no biological or clinical interpretation. Original source remains unchanged.\n',encoding='utf-8')
        assert all(digest(Path(path))==value for path,value in before.items())
        status='passed'
    finally:
        files=['tools/fcs.mjs','tools/check-population-read-report.py','examples/repod-population-read-report.mjs','cmd/bridge/main.mbt','events.mbt','write.mbt','offset_padding.mbt','pkg.generated.mbti','_build/js/release/build/cmd/bridge/bridge.js']
        report=dict(status=status,independentOracle='Raw TEXT offsets and struct values; exact Fraction sample statistics; pre-change stdout bytes; real public MoonBit API',checks=checks,commands=commands,
                    sourceSHA256={f:digest(root/f) for f in files},defaultStdoutHashes=DEFAULT_STDOUT_SHA256,
                    originalDataUnchanged=all(digest(Path(path))==value for path,value in before.items()))
        (out/'CHECKS.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=status,defaultCases=len(cases),commands=len(commands),errorCommands=sum(c.get('expectedError',False) for c in commands),originalDataUnchanged=True)))


if __name__=='__main__':
    main()
