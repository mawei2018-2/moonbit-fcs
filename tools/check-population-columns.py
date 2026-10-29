"""Original MIT independent raw FCS / complete CSV membership consumers."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BASE_ID = 18446744073709551616
XY = [[0,0],[2,4],[12,6],[4,8],[8,2],[9,9],[10,4],[1,5]]
MEMBERS = {'band':[0,1,3,4,5,7],'child':[1,3,5,7],'id_65':[1,2,3],'never':[]}
GATES = [
    {'id':'child','parent':'band','bounds':[['Y',1,2.5]],'scaled':True},
    {'id':'band','bounds':[['X',0,10]]},
    {'id':'id_65','integer_bounds':[{'channel':'ID','lower':'18446744073709551617','upper':'18446744073709551620'}]},
    {'id':'never','bounds':[['X',90,100]]},
]
COLUMNS = [{'population':'band','column':'in_band'},{'population':'child','column':'in_child'},
           {'population':'id_65','column':'id_65'},{'population':'never','column':'never'}]
OPTIONS = {'strict':True,'gates':GATES,'channels':['ID','Y','X'],'event_index_column':'source_event_index','population_columns':COLUMNS}
SOURCE_SHA256 = {
    'small':'d17ae2390ef4977d0107b22af26f21843db24db8da932761c71d46749811b113',
    'chain':'06466144e64954c33435062a50a6311899fbb901472597531fe7a36ec6ede2a0',
    'multi':'a16d878f986bde17de08d6ec5bf3c7dd86937306a76bd14671df7d47da4f5d79',
}
CSV_SHA256 = {
    'full':'b42f2c86989985da2055829245e913eb899a53ada5396c80c12b1abbd5c22e0c',
    'unannotated-full':'5f82dc7ce031454148a166dca5869d8f615918a240ff96d908954bb58693cfab',
    'filtered':'e1fcd8a44f3cb09f98cac5dfe2d2052d4ce4f0809ec1d8aa7858376d6ba39b81',
    'unannotated-filtered':'e8c4ced57617564df121d5ffa2c6595105ebcb8dfb1eee8a5bbe4bdb5e2cfb17',
    'zero':'91d910a3878c4f82717f880e062a0d8fdb9e8aa13065a07419d6e8025cbad70f',
    'special':'a6dcd5cb232bbf30027526dba3568f95daad3fc984a76264f2e57163c2391306',
    'duplicate-population':'de47fd23e5130a7435cd5dba3eb80e086abf47566856c064e3fa60a361428a2f',
    'unselected-name':'cec6c7a471e5d021951b72dcc462b8a14ac36023d5ac3efddd1fc71fc0809265',
    'duplicate-scientific':'cfb3a4f6be762c5cf41d955e82e3368b05c56a284c4d3e7933a489ee24ae0e25',
    'no-index':'95774ec5a5b0030e503212a59d14d3cb8d407dfbdbc6f9be0cd5a988252f5d5a',
    'multi':'9a6f37affcc1c81916b7dc6cfa31c01eb9e114ae330241c0d48950967c317cc5',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fcs(names,widths,rows,gains=None,spill=None,next_offset=0):
    if all(width%8==0 for width in widths):
        raw = b''.join(value.to_bytes(width//8,'little') for row in rows for value,width in zip(row,widths))
    else:
        bits,at = 0,0
        for row in rows:
            for value,width in zip(row,widths):
                assert 0 <= value < 1<<width
                bits |= value<<at
                at += width
        raw = bits.to_bytes((at+7)//8,'little')
    pairs = [('$MODE','L'),('$DATATYPE','I'),('$BYTEORD','1,2,3,4'),('$PAR',str(len(names))),('$TOT',str(len(rows))),
             ('$BEGINSTEXT','0'),('$ENDSTEXT','0'),('$BEGINANALYSIS','0'),('$ENDANALYSIS','0'),('$NEXTDATA',str(next_offset)),
             ('$BEGINDATA','000000000000'),('$ENDDATA','000000000000')]
    for i,(name,width) in enumerate(zip(names,widths),1):
        pairs += [(f'$P{i}N',name),(f'$P{i}B',str(width)),(f'$P{i}R',str(1<<width)),(f'$P{i}E','0,0'),
                  (f'$P{i}G',str((gains or [1]*len(names))[i-1]))]
    if spill:pairs.append(('$SPILLOVER',spill))
    def text():return ('|'+'|'.join(value for pair in pairs for value in pair)+'|').encode()
    start = 256+len(text());end = start+len(raw)-1
    pairs = [(k,f'{start:012d}' if k=='$BEGINDATA' else f'{end:012d}' if k=='$ENDDATA' else v) for k,v in pairs]
    header = b'FCS3.1    '+b''.join(f'{n:8d}'.encode() for n in [256,start-1,start,end,0,0])
    result = header.ljust(256,b' ')+text()+raw
    assert result[start:]==raw and len(result)==end+1
    return result


def csv_bytes(header,rows):
    text = io.StringIO(newline='')
    csv.writer(text,lineterminator='\r\n',quoting=csv.QUOTE_ALL).writerow(header)
    csv.writer(text,lineterminator='\r\n').writerows(rows)
    return text.getvalue().encode('utf-8')


def literal(header,rows,flags=None,sort=None,intersection=None):
    rows = [list(map(str,row)) for row in rows]
    value = {'header':header,'rows':rows,'events':len(rows)}
    if flags:value['counts']={name:sum(int(row[header.index(name)]) for row in rows) for name in flags}
    if sort:value['sort']=sort
    if intersection:value['intersection']=intersection
    return value


def fixtures(directory):
    directory = Path(directory);directory.mkdir(parents=True,exist_ok=False)
    rows = [[BASE_ID+i,x,y] for i,(x,y) in enumerate(XY)]
    small = fcs(['ID','X','Y'],[65,16,16],rows,[1,2,4],'2,X,Y,1,0.5,0,1')
    prefix = fcs(['ID','X','Y'],[65,16,16],[[17,7,0]],[1,2,4],'2,X,Y,1,0.5,0,1',2048)
    assert len(prefix)<2048
    sources = {'small':small,'chain':prefix.ljust(2048,b' ')+small,
               'multi':fcs(['X','Y'],[16,16],[[i%13,i%7] for i in range(60013)])}
    for name,data in sources.items():(directory/(name+'.fcs')).write_bytes(data)
    labels = [column['column'] for column in COLUMNS]
    def raw_row(i):return [i,str(BASE_ID+i),XY[i][1],XY[i][0]]
    def flags(i):return [int(i in MEMBERS[column['population']]) for column in COLUMNS]
    header = ['source_event_index','ID','Y','X',*labels]
    full = [raw_row(i)+flags(i) for i in range(8)]
    filtered = [[3,'1','2',1,1,1,0],[5,'0','4.5',1,1,0,0]]
    special = ['band','child,"yes"\nflag','id_65','never']
    specs = {
        'full':literal(header,full,labels,sort={'column':'X','source_indices':[2,6,5,4,3,1,7,0]},
                       intersection={'columns':['in_band','id_65'],'source_indices':[1,3]}),
        'unannotated-full':literal(header[:4],[raw_row(i) for i in range(8)]),
        'filtered':literal(['source_event_index','Y','X',*labels],filtered,labels,
                           sort={'column':'X','source_indices':[5,3]}),
        'unannotated-filtered':literal(['source_event_index','Y','X'],[row[:3] for row in filtered]),
        'zero':literal(header,[],labels),
        'special':literal(['source_event_index','ID','Y','X',*special],full,special),
        'duplicate-population':literal(['source_event_index','ID','Y','X','child_one','child_two'],
                                       [raw_row(i)+[int(i in MEMBERS['child'])]*2 for i in range(8)],['child_one','child_two']),
        'unselected-name':literal(['source_event_index','X','Y'],[[i,XY[i][0],int(i in MEMBERS['band'])] for i in range(8)],['Y']),
        'duplicate-scientific':literal(['source_event_index','X','X','in_band'],
                                      [[i,XY[i][0],XY[i][0],int(i in MEMBERS['band'])] for i in range(8)],['in_band']),
        'no-index':literal(header[1:],[row[1:] for row in full],labels),
    }
    big_header = ['source_event_index','Y','X','in_a','in_b','in_c']
    big_rows = []
    for i in range(60013):
        x,y=i%13,i%7;a=2<=x<9;b=a and 1<=y<4;c=5<=y<7
        big_rows.append([i,y,x,int(a),int(b),int(c)])
    specs['multi']={'header':big_header,'rule':'modular_original_events','events':60013,
                    'counts':{name:sum(row[index] for row in big_rows) for index,name in enumerate(big_header) if index>=3}}
    for name,expectation in specs.items():
        payload = csv_bytes(expectation['header'],big_rows if name=='multi' else expectation['rows'])
        (directory/(name+'.csv')).write_bytes(payload)
        expectation['bytesSHA256']=hashlib.sha256(payload).hexdigest()
        (directory/(name+'.expected.json')).write_text(json.dumps(expectation,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (directory/'options.json').write_text(json.dumps(OPTIONS,indent=2)+'\n',encoding='utf-8')
    manifest = {'source':'original MIT independent raw-bit FCS plus literal/modular complete CSV expectations',
                'sourceSHA256':{name:sha(directory/(name+'.fcs')) for name in sources},
                'completeCSV_SHA256':{name:sha(directory/(name+'.csv')) for name in specs},
                'independentSmallMembers':MEMBERS,'events':{'small':8,'chain-selected-dataset':8,'multi':60013}}
    (directory/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--frozen-inputs',type=Path)
    args = parser.parse_args();out=args.directory.resolve();out.mkdir(parents=True,exist_ok=False)
    original = args.frozen_inputs.resolve() if args.frozen_inputs else out/'inputs'
    if not args.frozen_inputs:fixtures(original)
    assert all(sha(original/(name+'.fcs'))==value for name,value in SOURCE_SHA256.items())
    assert all(sha(original/(name+'.csv'))==value for name,value in CSV_SHA256.items())
    env = os.environ.copy();temp=Path(env.get('FCS_PRIVATE_TEMP',out/'tmp')).resolve();temp.mkdir(parents=True,exist_ok=True)
    env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1',NODE_COMPILE_CACHE=str(out/'node-cache'))
    process_log = Path(env.get('FCS_PROCESS_LOG',out/'PROCESS-LAUNCHES.jsonl'))
    commands,cases=[],[];status='failed'

    def launch(argv,cwd=ROOT):
        executable=shutil.which(str(argv[0]),path=env.get('PATH')) or str(argv[0]);argv=[executable,*map(str,argv[1:])]
        cwd=Path(cwd).resolve()
        if env.get('FCS_ALLOWED_WORKSPACE'):
            allowed=Path(env['FCS_ALLOWED_WORKSPACE']).resolve();assert cwd.is_relative_to(allowed) and temp.is_relative_to(allowed)
        record={'recordedBeforeLaunchUTC':datetime.now(timezone.utc).isoformat(),'argv':argv,'cwd':str(cwd),
                'processEnv':{key:env[key] for key in ['TEMP','TMP','TMPDIR']}}
        with process_log.open('a',encoding='utf-8') as f:f.write(json.dumps(record)+'\n')
        run=subprocess.run(argv,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        commands.append(dict(record,exitCode=run.returncode,stdout=run.stdout,stderr=run.stderr))
        return run

    def case(name,options,expected='full',source='small',atomic=False,error=False):
        directory=out/name;directory.mkdir();cfg=directory/'selection.json';cfg.write_text(json.dumps(options,ensure_ascii=False),encoding='utf-8')
        target=directory/'received.csv';argv=['node',ROOT/'tools/fcs.mjs','csv',original/(source+'.fcs'),target]
        if atomic:argv.append('--atomic-output')
        argv+=['--options',cfg]
        result=launch(argv,cwd=directory)
        record={'case':name,'source':source,'sourceSHA256':sha(original/(source+'.fcs')),'expected':expected,
                'options':options,'exitCode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
        cases.append(record)
        if error:
            assert result.returncode==1 and not result.stdout and result.stderr,record
            assert not target.exists() and not list(directory.glob('.moonbit-fcs-csv-*'))
            record['precreateFailureVerified']=True
            return
        assert result.returncode==0 and not result.stderr,record
        assert target.read_bytes()==(original/(expected+'.csv')).read_bytes(),name
        oracle=json.loads((original/(expected+'.expected.json')).read_text())
        wanted={'written':str(target),'events':oracle['events'],'scaled':bool(options.get('scaled') or options.get('compensated')),
                'compensated':bool(options.get('compensated'))}
        if options.get('event_index_column') is not None:wanted['event_index_column']=options['event_index_column']
        if options.get('population') is not None:
            selected=MEMBERS[options['population']];start=options.get('start',0);count=options.get('count',len(selected)-start)
            wanted.update(population=options['population'],population_events=len(selected),source_event_indices=selected[start:start+count])
        if options.get('population_columns'):
            wanted['population_columns']=[{'population':item['population'],'column':item['column']} for item in options['population_columns']]
        if atomic:wanted.update(atomic_output=True,cleanupPending=False)
        assert result.stdout==json.dumps(wanted,separators=(',',':'),ensure_ascii=False)+'\n',(name,result.stdout,wanted)
        received=launch([sys.executable,'-X','utf8','-B',ROOT/'examples/population-columns/receive.py',target,'--expected',original/(expected+'.expected.json')],cwd=directory)
        assert received.returncode==0 and not received.stderr,commands[-1]
        record['receiver']=json.loads(received.stdout);record['rawCSV_SHA256']=sha(target)

    base={key:value for key,value in OPTIONS.items() if key not in ['gates','population_columns']}
    filtered=dict(OPTIONS,population='child',start=1,count=2,channels=['Y','X'],compensated=True,scaled=False)
    big_gates=[{'id':'b','parent':'a','bounds':[['Y',1,4]]},{'id':'a','bounds':[['X',2,9]]},
               {'id':'c','integer_bounds':[{'channel':'Y','lower':'5','upper':'7'}]}]
    big_columns=[{'population':name,'column':'in_'+name} for name in ['a','b','c']]
    try:
        case('old-default-full',base,'unannotated-full')
        case('old-default-filtered',{key:value for key,value in filtered.items() if key!='population_columns'},'unannotated-filtered')
        case('disabled-null',dict(base,population_columns=None),'unannotated-full')
        case('disabled-empty',dict(base,population_columns=[]),'unannotated-full')
        case('all-event-membership',OPTIONS)
        case('null-row-filter',dict(OPTIONS,population=None))
        case('filtered-compensated-window',filtered,'filtered')
        case('complete-published-table',filtered,'filtered',atomic=True)
        case('selected-dataset',dict(OPTIONS,dataset=1),source='chain')
        case('zero-window',dict(OPTIONS,start=8,count=0),'zero')
        case('empty-population',dict(OPTIONS,population='never'),'zero')
        special=[dict(column) for column in COLUMNS];special[0]['column']='band';special[1]['column']='child,"yes"\nflag'
        case('escaped-header-labels',dict(OPTIONS,population_columns=special),'special')
        case('same-population-two-aliases',dict(OPTIONS,population_columns=[{'population':'child','column':'child_one'},{'population':'child','column':'child_two'}]),'duplicate-population')
        case('unselected-source-name-alias',dict(OPTIONS,channels=['X'],population_columns=[{'population':'band','column':'Y'}]),'unselected-name')
        case('duplicate-scientific-labels',dict(OPTIONS,channels=[1,1],population_columns=[{'population':'band','column':'in_band'}]),'duplicate-scientific')
        case('no-source-index',{key:value for key,value in OPTIONS.items() if key!='event_index_column'},'no-index')
        case('full-multiple-chunks',{'strict':True,'gates':big_gates,'channels':['Y','X'],'event_index_column':'source_event_index','population_columns':big_columns},'multi',source='multi')
        errors=[
            ('not-an-array',dict(OPTIONS,population_columns={})),
            ('bad-item',dict(OPTIONS,population_columns=[None])),
            ('unknown-column-population',dict(OPTIONS,population_columns=[{'population':'missing','column':'flag'}],count=0)),
            ('duplicate-alias',dict(OPTIONS,population_columns=[{'population':'band','column':'flag'},{'population':'child','column':'flag'}])),
            ('scientific-alias-collision',dict(OPTIONS,population_columns=[{'population':'band','column':'X'}])),
            ('index-alias-collision',dict(OPTIONS,population_columns=[{'population':'band','column':'source_event_index'}])),
            ('missing-gates',{key:value for key,value in OPTIONS.items() if key!='gates'}),
            ('bad-gate-empty-window',dict(OPTIONS,gates=[{'id':'band','bounds':[['X',2,1]]}],count=0)),
            ('unknown-row-population',dict(OPTIONS,population='missing')),
            ('empty-label',dict(OPTIONS,population_columns=[{'population':'band','column':''}])),
            ('disabled-preserves-gates-contract',dict(OPTIONS,population_columns=[])),
        ]
        for name,options in errors:case(name,options,error=True)
        example=ROOT/'examples/population-columns';assert sha(example/'input.fcs')==SOURCE_SHA256['small']
        assert json.loads((example/'selection.json').read_text())==OPTIONS
        assert json.loads((example/'expected.json').read_text())==json.loads((original/'full.expected.json').read_text())
        target=out/'example.csv'
        produced=launch(['node',ROOT/'tools/fcs.mjs','csv',example/'input.fcs',target,'--options',example/'selection.json'])
        assert produced.returncode==0 and not produced.stderr and target.read_bytes()==(original/'full.csv').read_bytes()
        received=launch([sys.executable,'-X','utf8','-B',example/'receive.py',target,'--expected',example/'expected.json'])
        assert received.returncode==0 and not received.stderr
        cases.append({'case':'standalone-public-file-example','stdout':produced.stdout,'receiver':json.loads(received.stdout),'rawCSV_SHA256':sha(target)})
        assert all(sha(original/(name+'.fcs'))==value for name,value in SOURCE_SHA256.items())
        assert all(sha(original/(name+'.csv'))==value for name,value in CSV_SHA256.items())
        status='passed'
    finally:
        files=['tools/fcs.mjs','tools/check-population-columns.py','examples/population-columns/receive.py','tools/csv-output.mjs',
               'pkg.generated.mbti','cmd/bridge/main.mbt','_build/js/release/build/cmd/bridge/bridge.js']
        report={'status':status,'platform':sys.platform,'cases':cases,'commands':commands,'sourceSHA256':SOURCE_SHA256,'completeCSV_SHA256':CSV_SHA256,
                'implementationSHA256':{name:sha(ROOT/name) for name in files},'processLaunchLog':str(process_log),
                'oracle':'complete original bit-packed FCS, fixed independent member index sets/literal CSVs and60013-row modular original-value/membership checks',
                'adoptionBoundary':'self-authored separate actual public CLI/CSV-only receiver, not external adoption'}
        (out/'CHECKS.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':status,'cases':len(cases),'commands':len(commands),'successfulFiles':sum(not c.get('precreateFailureVerified',False) for c in cases),
                      'precreateErrors':sum(c.get('precreateFailureVerified',False) for c in cases),'originalInputsAndCompleteExpectationsUnchanged':True}))


if __name__ == '__main__':
    main()
