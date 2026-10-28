"""FlowIO 1.4.0 cross-check; pass --reference-dir for pinned upstream public files.
No patient metadata or public instrument files are copied into this repository.
"""
import argparse, csv, hashlib, json, subprocess, tempfile
from pathlib import Path
import flowio
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PIN = '83d28a22d42235c10d17afb017250ee208afed95'

def main():
    p=argparse.ArgumentParser();p.add_argument('--reference-dir',type=Path);p.add_argument('--report',type=Path);a=p.parse_args()
    assert flowio.__version__=='1.4.0', flowio.__version__
    results=[]
    with tempfile.TemporaryDirectory(prefix='moonbit-fcs-reference-') as td:
        tmp=Path(td);count=0
        def cli(command,*files,options=None,ok=True):
            nonlocal count
            args=['node','tools/fcs.mjs',command,*map(str,files)]
            if options is not None:
                count+=1;cfg=tmp/f'options{count}.json';cfg.write_text(json.dumps(options),encoding='utf8');args+=['--options',str(cfg)]
            r=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf8')
            if ok: assert r.returncode==0, r.stderr
            else: assert r.returncode!=0,'unexpectedly accepted invalid file'
            return json.loads(r.stdout) if ok else r.stderr.strip()
        arr=np.array([[i,i*.125,-i*.25,i+1] for i in range(250)],dtype=np.float32)
        source=tmp/'flowio.fcs'
        with source.open('wb') as f: flowio.create_fcs(f,arr.reshape(-1).tolist(),['A','B','C','Time'],metadata_dict={'timestep':'0.1','spillover':'2,A,B,1,0.05,0.1,1'})
        assert cli('inspect',source)['events']==250
        actual=np.asarray(cli('values',source,options={'count':250}))
        np.testing.assert_array_equal(actual,arr)
        filtered=tmp/'filtered.fcs'
        cli('subset',source,filtered,options={'bounds':[[0,50,100]],'channels':[1,0,3]})
        reread=flowio.FlowData(filtered)
        np.testing.assert_array_equal(reread.as_array(preprocess=False),arr[50:100][:,[1,0,3]])
        matrix=reread.text['spillover'].split(',')
        assert matrix[:3]==['2','B','A']
        np.testing.assert_allclose(list(map(float,matrix[3:])),[1,.1,.05,1])
        single=tmp/'single.fcs';cli('subset',source,single,options={'channels':[0]})
        assert 'spillover' not in flowio.FlowData(single).text
        dropped=tmp/'drop.fcs';cli('subset',source,dropped,options={'channels':[0],'drop_spillover':True})
        assert 'spillover' not in flowio.FlowData(dropped).text
        results.append({'case':'FlowIO -> MoonBit gate/channel reorder -> FlowIO','events':250,'selected':50,'status':'pass'})
        for double in [False,True]:
            out=tmp/f'created-{double}.fcs'
            cli('create',out,options={'names':['X','Y'],'values':[1.25,-2,3.5,1e20],'double_precision':double,'big_endian':True})
            actual=flowio.FlowData(out).as_array(preprocess=False)
            expected=np.array([[1.25,-2],[3.5,1e20]],dtype=np.float64 if double else np.float32)
            np.testing.assert_array_equal(actual,expected)
            results.append({'case':'MoonBit -> FlowIO','type':'D' if double else 'F','endian':'big','status':'pass'})
        if a.reference_dir:
            sha=subprocess.check_output(['git','-C',str(a.reference_dir),'rev-parse','HEAD'],text=True).strip();assert sha==PIN,sha
            folder=a.reference_dir/'data'/'fcs_files'
            for name in ['100715.fcs','3FITC_4PE_004.fcs','variable_int_example.fcs']:
                file=folder/name;d=flowio.FlowData(file)
                destination=tmp/(name+'.csv')
                cli('csv',file,destination,options={'latin1':True})
                # Read the complete exported event matrix, not just a preview.
                with destination.open(encoding='utf8',newline='') as f:
                    rows=csv.reader(f);next(rows);raw=np.array([[float(x) for x in row] for row in rows])
                np.testing.assert_array_equal(raw,d.as_array(preprocess=False))
                small=tmp/(name+'.subset.fcs');cli('subset',file,small,options={'events':[0,d.event_count-1],'latin1':True,'drop_analysis':True})
                np.testing.assert_array_equal(flowio.FlowData(small).as_array(preprocess=False),raw[[0,-1]])
                results.append({'file':name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'events':d.event_count,'channels':d.channel_count,'all_values_equal':True,'rewrite_equal':True})
            for name in ['data_start_offset_discrepancy_example.fcs','data_stop_offset_discrepancy_example.fcs']:
                message=cli('validate',folder/name,options={'latin1':True},ok=False)
                assert 'discrepancy' in message;results.append({'file':name,'rejected':'HEADER/TEXT DATA discrepancy'})
            # Pinned vendor example: primary TEXT includes 5714 padding spaces.
            # Default remains rejecting; opt-in reads all events without changing DATA.
            name='G11.fcs';file=folder/name;original=file.read_bytes()
            message=cli('validate',file,ok=False)
            assert 'terminating delimiter' in message
            info=cli('inspect',file,options={'allow_text_padding':True})
            assert info['warnings']==['ignored 5714 trailing ASCII spaces in primary TEXT; declared extent retained']
            d=flowio.FlowData(file);csvfile=tmp/'G11.csv'
            cli('csv',file,csvfile,options={'allow_text_padding':True})
            with csvfile.open(encoding='utf8',newline='') as f:
                values=csv.reader(f);next(values);raw=np.array([[float(x) for x in row] for row in values])
            np.testing.assert_array_equal(raw,d.as_array(preprocess=False))
            clean=tmp/'G11-normalized.fcs'
            cli('rewrite',file,clean,options={'allow_text_padding':True})
            assert cli('validate',clean,options={'strict':True})['warnings']==[]
            np.testing.assert_array_equal(flowio.FlowData(clean).as_array(preprocess=False),raw)
            rewritten=clean.read_bytes()
            def event_bytes(b):return b[int(b[26:34]):int(b[34:42])+1]
            assert event_bytes(original)==event_bytes(rewritten)
            small=tmp/'G11-selected.fcs'
            cli('subset',file,small,options={'events':[0,d.event_count-1],'allow_text_padding':True})
            np.testing.assert_array_equal(flowio.FlowData(small).as_array(preprocess=False),raw[[0,-1]])
            assert file.read_bytes()==original
            results.append({'file':name,'sha256':hashlib.sha256(original).hexdigest(),'events':d.event_count,'channels':d.channel_count,'defaultRejected':True,'explicitOption':'allow_text_padding','ignoredTrailingSpaces':5714,'all_values_equal':True,'rewrite_equal':True,'raw_DATA_bytes_identical':True,'rewrite_strict_validation':True,'selected_events_equal':True,'source_unchanged':True})
            for name in ['data1.fcs','B01 KC-A-W---91-US.fcs']:
                message=cli('validate',folder/name,options={'latin1':True},ok=False)
                results.append({'file':name,'known_unsupported_vendor_metadata':message})
    sources={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['parse.mbt','text.mbt','write.mbt','cmd/bridge/main.mbt','tools/fcs.mjs','tools/reference_check.py','_build/js/release/build/cmd/bridge/bridge.js']}
    report={'flowio':flowio.__version__,'numpy':np.__version__,'reference_commit':PIN if a.reference_dir else None,'results':results,'sourceSha256':sources}
    if a.report: a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
