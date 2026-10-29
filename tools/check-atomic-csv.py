"""Original MIT independent raw-input, publication and separate-file consumers.

All expected scientific bytes/rows are constructed without the FCS library.
The external Node driver injects IO faults without production test switches.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
HEADER = '"source_event_index","X"\r\n'
SMALL = HEADER + '1,8\r\n2,5\r\n'
WIDE = '"source_event_index","ID"\r\n0,18446744073709551617\r\n1,18446744073709551619\r\n'
SCIENCE = '"source_event_index","B","A"\r\n1,2,6\r\n2,1,2\r\n'
SMALL_OPTIONS = {'strict':True,'channels':['X'],'start':1,'count':2,'event_index_column':'source_event_index'}
SCIENCE_OPTIONS = {'strict':True,'gates':[{'id':'p','bounds':[['A',0,13]]}],'population':'p','channels':['B','A'],
                   'start':1,'count':2,'compensated':True,'scaled':False,'event_index_column':'source_event_index'}
SOURCE_SHA256 = {
    'small':'2374627e1120721567d67caaecd775d5555705c512ae5eb0803c1ceab8d03713',
    'multi':'b0f194f9178901b5f925a1371c2e323747d9c2ea8234a8b7710b0598cb1047da',
    'wide':'e5585ff19115a2ca07b6feda40c7a1583a7abd0c890303b751ce87015b1158ed',
    'science':'5f97b7c070b20d05cd324d3fca35e77ab336f1eacbd0420843742f3cf9dc5423',
}
EXPECTED_SHA256 = {
    'small':'a5e8bf73f1cd1d8b5e07e6052fea857b49b45a380ccd24769a43094ffbeee29f',
    'zero':'7d9d97f7e9ad820cb50206c5800385b8e58430e206b84d9441b8ca5e7abe6f1e',
    'wide':'83e555d287723a2932cead12e3e6e46941fc746fb9f5c99efc7ef3f710636c1a',
    'science':'13127554a307ce53414e61f38900d7399f4c37298f910a1803384595b0854b7d',
    'multi':'4006f5a257935c1537ad9dd734dbf355ec09a9063df7f71528b8953397c8baef',
    'prefix':'7d9d97f7e9ad820cb50206c5800385b8e58430e206b84d9441b8ca5e7abe6f1e',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fcs(names, widths, rows, gains=None, spill=None):
    if all(width % 8 == 0 for width in widths):
        raw = b''.join(value.to_bytes(width//8,'little') for row in rows for value,width in zip(row,widths))
    else:
        bits = 0
        at = 0
        for row in rows:
            assert len(row) == len(widths)
            for value,width in zip(row,widths):
                assert 0 <= value < (1 << width)
                bits |= value << at
                at += width
        raw = bits.to_bytes((at+7)//8, 'little')
    pairs = [('$MODE','L'),('$DATATYPE','I'),('$BYTEORD','1,2,3,4'),('$PAR',str(len(names))),('$TOT',str(len(rows))),
             ('$BEGINSTEXT','0'),('$ENDSTEXT','0'),('$BEGINANALYSIS','0'),('$ENDANALYSIS','0'),('$NEXTDATA','0'),
             ('$BEGINDATA','000000000000'),('$ENDDATA','000000000000')]
    for index,(name,width) in enumerate(zip(names,widths),1):
        pairs += [(f'$P{index}N',name),(f'$P{index}B',str(width)),(f'$P{index}R',str(1<<width)),
                  (f'$P{index}E','0,0'),(f'$P{index}G',str((gains or [1]*len(names))[index-1]))]
    if spill:
        pairs.append(('$SPILLOVER',spill))
    def text():
        return ('|'+'|'.join(value for pair in pairs for value in pair)+'|').encode()
    start = 256 + len(text())
    end = start + len(raw) - 1
    pairs = [(k,f'{start:012d}' if k=='$BEGINDATA' else f'{end:012d}' if k=='$ENDDATA' else v) for k,v in pairs]
    header = b'FCS3.1    '+b''.join(f'{value:8d}'.encode() for value in [256,start-1,start,end,0,0])
    result = header.ljust(256,b' ')+text()+raw
    assert len(result)==end+1 and result[start:]==raw
    return result


def fixtures(directory):
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=False)
    sources = {
        'small':fcs(['X'],[16],[[2],[8],[5],[0]]),
        'multi':fcs(['X'],[16],[[i%65536] for i in range(100001)]),
        'wide':fcs(['ID'],[65],[[18446744073709551617],[18446744073709551619],[0]]),
        'science':fcs(['A','B'],[16,16],[[8,24],[12,20],[4,8],[20,100]],[2,4],'2,A,B,1,0.5,0,1'),
    }
    for name,data in sources.items():
        (directory/(name+'.fcs')).write_bytes(data)
    expected = {
        'small':SMALL, 'zero':HEADER, 'wide':WIDE, 'science':SCIENCE,
        'multi':HEADER+''.join(f'{i},{i%65536}\r\n' for i in range(100001)),
        'prefix':HEADER,
    }
    for name,text in expected.items():
        (directory/(name+'.csv')).write_bytes(text.encode('utf-8'))
    expectations = {
        'absent':{'state':'absent'},
        'small':{'header':['source_event_index','X'],'rows':[['1','8'],['2','5']]},
        'zero':{'header':['source_event_index','X'],'rows':[]},
        'prefix':{'header':['source_event_index','X'],'rows':[]},
        'wide':{'header':['source_event_index','ID'],'rows':[['0','18446744073709551617'],['1','18446744073709551619']]},
        'science':{'header':['source_event_index','B','A'],'rows':[['1','2','6'],['2','1','2']]},
        'multi':{'header':['source_event_index','X'],'rule':'source_index_i_value_i_mod_65536'},
    }
    for name,value in expectations.items():
        if name!='absent':value['bytesSHA256']=sha(directory/(name+'.csv'))
        (directory/(name+'.expected.json')).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    (directory/'small.options.json').write_text(json.dumps(SMALL_OPTIONS,indent=2)+'\n',encoding='utf-8')
    (directory/'science.options.json').write_text(json.dumps(SCIENCE_OPTIONS,indent=2)+'\n',encoding='utf-8')
    manifest = {'source':'original independent MIT raw-bit/ASCII FCS constructor and hand-written CSV expectations',
                'sourceSHA256':{name:sha(directory/(name+'.fcs')) for name in sources},
                'expectedCSV_SHA256':{name:sha(directory/(name+'.csv')) for name in expected},
                'rawSmallDataHex':'0200080005000000','smallSourceIndices':[1,2],
                'multiRule':'100001 rows; source_index=i and X=i%65536; complete expected CSV frozen'}
    (directory/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--frozen-inputs',type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    out.mkdir(parents=True,exist_ok=False)
    original = args.frozen_inputs.resolve() if args.frozen_inputs else out/'inputs'
    if not args.frozen_inputs:fixtures(original)
    for name,digest in SOURCE_SHA256.items():assert sha(original/(name+'.fcs'))==digest,name
    for name,digest in EXPECTED_SHA256.items():assert sha(original/(name+'.csv'))==digest,name
    env = os.environ.copy()
    temp = Path(env.get('FCS_PRIVATE_TEMP',out/'tmp')).resolve()
    temp.mkdir(parents=True,exist_ok=True)
    env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1',NODE_COMPILE_CACHE=str(out/'node-cache'))
    process_log = Path(env.get('FCS_PROCESS_LOG',out/'PROCESS-LAUNCHES.jsonl'))
    commands,cases = [],[]
    status = 'failed'

    def launch(argv,cwd=ROOT):
        program = shutil.which(str(argv[0]),path=env.get('PATH')) or str(argv[0])
        argv = [program,*map(str,argv[1:])]
        cwd = Path(cwd).resolve()
        if 'FCS_ALLOWED_WORKSPACE' in env:
            allowed = Path(env['FCS_ALLOWED_WORKSPACE']).resolve()
            assert cwd.is_relative_to(allowed) and temp.is_relative_to(allowed)
        record = {'recordedBeforeLaunchUTC':datetime.now(timezone.utc).isoformat(),'argv':argv,'cwd':str(cwd),
                  'processEnv':{key:env[key] for key in ['TEMP','TMP','TMPDIR']}}
        with process_log.open('a',encoding='utf-8') as f:f.write(json.dumps(record)+'\n')
        r = subprocess.run(argv,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        commands.append(dict(record,exitCode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        return r

    def case(name,source='small',expected='small',options=None,atomic=True,error=None,**flags):
        directory = out/name
        directory.mkdir()
        final = directory/('--atomic-output' if flags.pop('literal_output',False) else 'received.csv')
        input_path = original/(source+'.fcs')
        input_arg = str(input_path)
        if flags.pop('literal_input',False):
            input_path = directory/'--atomic-output'
            shutil.copyfile(original/(source+'.fcs'),input_path)
            input_arg = '--atomic-output'
        output_arg = '--atomic-output' if final.name=='--atomic-output' else str(final)
        opts = dict(SMALL_OPTIONS if source=='small' else SCIENCE_OPTIONS if source=='science' else
                    {'strict':True,'channels':['ID' if source=='wide' else 'X'],'event_index_column':'source_event_index'},
                    **(options or {}))
        if source=='wide':opts['count']=2
        option_file = directory/'options.json'
        option_file.write_text(json.dumps(opts,indent=2)+'\n',encoding='utf-8')
        sentinel = 'USER_TARGET_SENTINEL\n'
        sentinel_file = directory/'sentinel.expected.json'
        sentinel_file.write_text(json.dumps({'state':'bytes','bytesSHA256':hashlib.sha256(sentinel.encode()).hexdigest()})+'\n',encoding='utf-8')
        if flags.get('existing'):final.write_bytes(sentinel.encode())
        cli_args = ['csv',input_arg,output_arg]
        if atomic:cli_args.append('--atomic-output')
        cli_args += ['--options',str(option_file)]
        cfg = {'python':sys.executable,'receiver':str(ROOT/'examples/atomic-csv/receive.py'),'target':str(final),
               'cli':str(ROOT/'tools/fcs.mjs'),'args':cli_args,'processLog':str(process_log),
               'trace':str(directory/'driver-trace.json'),'atomic':atomic,
               'absentExpectation':str(original/'absent.expected.json'),
               'completeExpectation':str(original/(expected+'.expected.json')),
               'sentinelExpectation':str(sentinel_file),'sentinelBytes':sentinel,**flags}
        config = directory/'config.json'
        config.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
        before = sha(input_path)
        r = launch(['node',ROOT/'tools/atomic-csv-driver.mjs',config],cwd=directory)
        trace = json.loads((directory/'driver-trace.json').read_text())
        record = {'case':name,'source':source,'sourceSHA256':before,'atomic':atomic,'exitCode':r.returncode,
                  'stdout':r.stdout,'stderr':r.stderr,'trace':trace,'rawOutputSHA256':sha(final) if final.exists() else None}
        cases.append(record)
        assert not trace['forbidden'],trace
        assert sha(input_path)==before
        assert all(receiver['status']==0 for receiver in trace['receivers'])
        if atomic and trace['staging']:
            opened = [event for event in trace['events'] if event['operation']=='open']
            assert len(opened)==1 and opened[0]['path']==trace['staging']
            assert opened[0]['flags']=='wx' and opened[0]['mode']==0o600
        if error:
            assert r.returncode==1 and not r.stdout and r.stderr,(name,r.stdout,r.stderr)
            if error!='request':assert r.stderr.startswith(error),r.stderr
            if flags.get('existing') or flags.get('concurrent'):
                assert final.read_bytes()==sentinel.encode()
                final_expectation = sentinel_file
            else:
                assert not final.exists(),name
                final_expectation = original/'absent.expected.json'
        else:
            assert r.returncode==0 and not r.stderr,(name,r.stdout,r.stderr)
            assert final.read_bytes()==(original/(expected+'.csv')).read_bytes(),name
            value = json.loads(r.stdout)
            rows = 0 if expected=='zero' else 100001 if source=='multi' else 2
            wanted = {'written':output_arg,'events':rows,'scaled':bool(opts.get('scaled') or opts.get('compensated')),
                      'compensated':bool(opts.get('compensated')),'event_index_column':'source_event_index'}
            if source=='science':wanted.update(population='p',population_events=3,source_event_indices=[1,2])
            if atomic:wanted.update(atomic_output=True,cleanupPending=bool(flags.get('failPostCleanup')))
            if flags.get('failPostCleanup'):
                wanted.update(stagingPath=trace['staging'],warning='CSV published; staging cleanup is pending (EACCES).')
            assert value==wanted,(name,value,wanted)
            assert r.stdout==json.dumps(wanted,separators=(',',':'),ensure_ascii=False)+'\n'
            final_expectation = original/(expected+'.expected.json')
            if atomic:
                published = [event for event in trace['events'] if event['operation']=='published']
                assert len(published)==1 and published[0]['sameInode'] and int(published[0]['links'])>=2
                assert trace['published'] and any(x['label']=='after-publication' for x in trace['receivers'])
                assert [x['operation'] for x in trace['events']].index('closed') < [x['operation'] for x in trace['events']].index('published')
        receiver = launch([sys.executable,'-X','utf8','-B',ROOT/'examples/atomic-csv/receive.py',final,'--expected',final_expectation],cwd=directory)
        assert receiver.returncode==0 and not receiver.stderr,receiver.stderr
        record['finalIndependentReceiver'] = json.loads(receiver.stdout)
        staging = Path(trace['staging']) if trace['staging'] else None
        if flags.get('failPostCleanup') or flags.get('failPreCleanup'):
            assert staging and staging.parent.resolve()==directory and staging.name.startswith('.moonbit-fcs-csv-')
            record['pendingStagingSHA256'] = sha(staging)
            if flags.get('failPostCleanup'):assert os.path.samefile(staging,final)
            else:assert 'Owned staging cleanup is pending at '+str(staging)+' (EACCES).' in r.stderr
            staging.unlink()  # Verified exact test-owned entry only; keep final artifact.
            record['testOwnedPendingStagingRemovedAfterEvidence'] = True
        elif staging:
            assert not staging.exists()
        assert not list(directory.glob('.moonbit-fcs-csv-*'))
        return record

    try:
        case('default-small',atomic=False)
        case('default-science',source='science',expected='science',atomic=False)
        case('literal-output-name',atomic=False,literal_output=True)
        case('literal-input-name',atomic=False,literal_input=True)
        case('atomic-small')
        case('atomic-multiple-chunks',source='multi',expected='multi')
        case('atomic-zero',expected='zero',options={'count':0})
        case('atomic-wide',source='wide',expected='wide')
        case('atomic-science',source='science',expected='science')
        case('late-write-error',source='multi',expected='multi',failWriteAt=3,error='atomic CSV write failed (EIO);')
        case('close-error',failClose=True,error='atomic CSV close failed (EIO);')
        case('unsupported-link',failLink=True,error='atomic CSV publish failed (EOPNOTSUPP);')
        case('existing-target',existing=True,error='atomic CSV publish failed (EEXIST);')
        case('concurrent-target',concurrent=True,error='atomic CSV publish failed (EEXIST);')
        case('post-commit-cleanup-warning',failPostCleanup=True)
        case('pre-commit-cleanup-warning',failLink=True,failPreCleanup=True,error='atomic CSV publish failed (EOPNOTSUPP);')
        case('bad-channel-before-staging',options={'channels':['missing']},error='request')
        example = ROOT/'examples/atomic-csv'
        assert sha(example/'input.fcs')==SOURCE_SHA256['small']
        assert json.loads((example/'selection.json').read_text())==SMALL_OPTIONS
        assert json.loads((example/'expected.json').read_text())==json.loads((original/'small.expected.json').read_text())
        # Use the published public CLI directly too, without the IO driver.
        final = out/'example.csv'
        r = launch(['node',ROOT/'tools/fcs.mjs','csv',example/'input.fcs',final,'--atomic-output','--options',example/'selection.json'])
        assert r.returncode==0 and not r.stderr and final.read_bytes()==SMALL.encode()
        received = launch([sys.executable,'-X','utf8','-B',example/'receive.py',final,'--expected',example/'expected.json'])
        assert received.returncode==0 and not received.stderr
        cases.append({'case':'standalone-public-cli-example','stdout':r.stdout,'receiver':json.loads(received.stdout),'rawOutputSHA256':sha(final)})
        assert all(sha(original/(name+'.fcs'))==digest for name,digest in SOURCE_SHA256.items())
        assert all(sha(original/(name+'.csv'))==digest for name,digest in EXPECTED_SHA256.items())
        status = 'passed'
    finally:
        files = ['tools/fcs.mjs','tools/csv-output.mjs','tools/atomic-csv-driver.mjs','tools/check-atomic-csv.py',
                 'examples/atomic-csv/receive.py','pkg.generated.mbti','_build/js/release/build/cmd/bridge/bridge.js']
        report = {'status':status,'platform':sys.platform,'oracle':'frozen original raw I16/65-bit bytes, complete literal/modular CSV expectations and separate CSV-only receivers',
                  'sourceSHA256':SOURCE_SHA256,'expectedCSV_SHA256':EXPECTED_SHA256,'cases':cases,'commands':commands,
                  'implementationSHA256':{name:sha(ROOT/name) for name in files},'processLaunchLog':str(process_log),
                  'adoptionBoundary':'self-authored actual file consumers; not external institution adoption'}
        (out/'CHECKS.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':status,'platform':sys.platform,'cases':len(cases),'commands':len(commands),
                      'separateCheckpointReceiverCommands':sum(len(c.get('trace',{}).get('receivers',[])) for c in cases),
                      'originalSourcesUnchanged':True}))


if __name__ == '__main__':
    main()
