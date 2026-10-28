"""Independent FCS 3.1 byte vectors and NumPy compensation oracle.

Original MIT vectors: wide list integers, all DATA encodings, C/U histogram
layout, frequency projection, and SPILLOVER direction/metadata synchronization.
"""
import argparse,hashlib,json,math,re,struct,subprocess
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def packed(values,widths,order):
    bits=sum(widths)
    if order=='little':
        total=offset=0
        for value,width in zip(values,widths,strict=True): total|=int(value)<<offset;offset+=width
        return total.to_bytes((bits+7)//8,'little')
    stream=''.join(f'{int(value):0{width}b}' for value,width in zip(values,widths,strict=True))
    return int(stream.ljust((bits+7)//8*8,'0') or '0',2).to_bytes((bits+7)//8,'big')

def make(kind,widths,ranges,values,*,mode='L',order='little',spill=None):
    fields=[]
    if mode=='L': field_widths=widths*(len(values)//len(widths))
    elif mode=='C': field_widths=[0 if kind=='A' and 0 in widths else max(widths)]*math.prod(map(int,ranges))
    else: field_widths=[width for width,n in zip(widths,ranges,strict=True) for _ in range(int(n))]
    if kind=='I': raw=packed(values,field_widths,order)
    elif kind in 'FD': raw=b''.join(struct.pack(('<' if order=='little' else '>')+('f' if kind=='F' else 'd'),float(v)) for v in values)
    elif 0 in field_widths: raw=b', \t'.join(str(v).encode() for v in values)
    else: raw=b''.join(str(v).encode().rjust(width,b' ') for v,width in zip(values,field_widths,strict=True))
    total=len(values)//len(widths) if mode=='L' else sum(map(int,values[:int(ranges[0])] if mode=='U' else values))
    pairs=[('$MODE',mode),('$DATATYPE',kind),('$BYTEORD','1,2,3,4' if order=='little' else '4,3,2,1'),('$PAR',str(len(widths))),('$TOT',str(total)),
           ('$BEGINSTEXT','0'),('$ENDSTEXT','0'),('$BEGINANALYSIS','0'),('$ENDANALYSIS','0'),('$NEXTDATA','0'),
           ('$BEGINDATA','0000000000'),('$ENDDATA','0000000000'),('SOURCE','Original independent deep development vectors')]
    for c,(width,ran) in enumerate(zip(widths,ranges,strict=True),1):
        pairs += [(f'$P{c}N',chr(64+c)),(f'$P{c}B','*' if width==0 else str(width)),(f'$P{c}R',str(ran)),(f'$P{c}E','0,0')]
    if spill is not None:
        pairs.append(('$SPILLOVER',str(len(spill))+','+','.join(chr(65+c) for c in range(len(spill)))+','+','.join(str(v) for row in spill for v in row)))
    def text():return ('|'+'|'.join(v for pair in pairs for v in pair)+'|').encode()
    begin=256+len(text());end=begin+len(raw)-1
    pairs=[(k,f'{begin:010d}' if k=='$BEGINDATA' else f'{end:010d}' if k=='$ENDDATA' else v) for k,v in pairs]
    header=b'FCS3.1    '+b''.join(f'{v:08d}'.encode() for v in [256,begin-1,begin,end,0,0])
    return header.ljust(256,b' ')+text()+raw

def read(path):
    data=path.read_bytes();start,end=int(data[10:18]),int(data[18:26]);text=data[start:end+1]
    fields=text[1:-1].split(text[:1]);meta={fields[i].decode():fields[i+1].decode() for i in range(0,len(fields),2)}
    first,last=int(meta['$BEGINDATA']),int(meta['$ENDDATA']);raw=data[first:last+1]
    assert int(data[26:34])==first and int(data[34:42])==last and last==len(data)-1
    n=int(meta['$PAR']);kind=meta['$DATATYPE'];mode=meta['$MODE']
    widths=[0 if meta[f'$P{i}B']=='*' else int(meta[f'$P{i}B']) for i in range(1,n+1)]
    ranges=[int(meta[f'$P{i}R']) for i in range(1,n+1)]
    if mode=='L': all_widths=widths*int(meta['$TOT'])
    elif mode=='C': all_widths=[0 if kind=='A' and 0 in widths else max(widths)]*math.prod(ranges)
    else:all_widths=[width for width,count in zip(widths,ranges,strict=True) for _ in range(count)]
    values=[]
    if kind=='I':
        little=meta['$BYTEORD']=='1,2,3,4';stream=int.from_bytes(raw,'little' if little else 'big');at=0
        for i,width in enumerate(all_widths):
            shift=at if little else len(raw)*8-at-width
            value=(stream>>shift)&((1<<width)-1)
            if mode=='L':value&=(1<<(ranges[i%n]-1).bit_length())-1
            values.append(value);at+=width
        assert len(raw)==(sum(all_widths)+7)//8
    elif kind in 'FD':
        size=4 if kind=='F' else 8
        values=list(struct.unpack(('<' if meta['$BYTEORD']=='1,2,3,4' else '>')+str(len(raw)//size)+('f' if kind=='F' else 'd'),raw))
    else:
        if 0 in all_widths:values=[int(x) for x in re.split(rb'[\s,]+',raw) if x]
        else:
            at=0
            for width in all_widths: values.append(int(raw[at:at+width]));at+=width
            assert at==len(raw)
    assert len(values)==len(all_widths)
    return meta,values,raw

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    a.directory.mkdir(parents=True,exist_ok=False)
    tasks=[];checks=[];files=[];cases=[]
    def task(options,input=None,output=None,check=lambda _:None):
        tasks.append(dict(options=options,input=str(input) if input else None,**({'output':str(output)} if output else {})));checks.append(check)
    def source(name,data):
        file=a.directory/(name+'.fcs');file.write_bytes(data);files.append(file);return file
    for order in ['little','big']:
        widths=[65,97,257,1024];rows=[[2**64+1,2**96+7,2**256+3,2**1023+9],[2**64+2,2**96+8,2**256+4,2**1023+10],[0,0,0,0]]
        src=source('wide-'+order,make('I',widths,[2**w for w in widths],[v for row in rows for v in row],order=order))
        task(dict(command='values',count=3),src,check=lambda r,rows=rows: np.testing.assert_array_equal(r,[[str(v) for v in row] for row in rows]))
        bounds=[dict(channel=3,lower=str(rows[1][3]),upper=str(rows[1][3]+1))]
        task(dict(command='gate',integer_bounds=bounds),src,check=lambda r:np.testing.assert_array_equal(r,[1]))
        selected=a.directory/('wide-selected-'+order+'.fcs')
        task(dict(command='subset',integer_bounds=bounds,channels=[3,0]),src,selected)
        files.append(selected)
        cases.append(dict(case='arbitrary widths and exact gate',order=order,input=src.name,output=selected.name,expected=[rows[1][3],rows[1][0]]))
        ascii_file=a.directory/('wide-ascii-'+order+'.fcs')
        task(dict(command='rewrite',encoding=dict(datatype='A',widths=[0]*4,big_endian=order=='big')),src,ascii_file);files.append(ascii_file)
        task(dict(command='gate',integer_bounds=bounds),ascii_file,check=lambda r:np.testing.assert_array_equal(r,[1]))
        binary=a.directory/('wide-converted-'+order+'.fcs')
        task(dict(command='rewrite',encoding=dict(datatype='I',widths=widths,big_endian=order=='big')),ascii_file,binary);files.append(binary)
        cases.append(dict(case='ASCII to arbitrary binary',input=src.name,output=binary.name,expected=[v for row in rows for v in row]))
    src=source('wide-mask',make('I',[97],[32],[(1<<96)|17]))
    task(dict(command='values',count=1),src,check=lambda r:np.testing.assert_array_equal(r,[['17']]))
    for mode in ['C','U']:
        values=[1,2,3,4,5,6] if mode=='C' else [3,7,1,5,4]
        for kind,widths in [('I',[16,32]),('A',[4,5]),('A',[0,0]),('F',[32,32]),('D',[64,64])]:
            name=f'hist-{mode}-{kind}-'+str(widths[0]);src=source(name,make(kind,widths,[2,3],values,mode=mode,order='big'))
            task(dict(command='histogram'),src,check=lambda r,values=values:np.testing.assert_allclose([float(v) for v in r['frequencies']],values))
            out=a.directory/(name+'-reorder.fcs');task(dict(command='subset',channels=[1,0]),src,out);files.append(out)
            expected=[1,3,5,2,4,6] if mode=='C' else [1,5,4,3,7]
            cases.append(dict(case='histogram reorder '+mode,input=src.name,output=out.name,expected=expected))
            out=a.directory/(name+'-marginal.fcs');task(dict(command='subset',channels=[0]),src,out);files.append(out)
            cases.append(dict(case='histogram marginal '+mode,input=src.name,output=out.name,expected=[9,12] if mode=='C' else [3,7]))
    for mode in ['C','U']:
        values=[2**64+1]*4
        src=source('wide-hist-'+mode,make('I',[65,65],[2,2],values,mode=mode))
        out=a.directory/('wide-hist-'+mode+'-subset.fcs');task(dict(command='subset',channels=[1]),src,out);files.append(out)
        cases.append(dict(case='wide histogram frequency and TOT '+mode,input=src.name,output=out.name,expected=[2*(2**64+1)]*2 if mode=='C' else [2**64+1]*2))
    for kind,widths,values in [('I',[65,97],[str(2**64+1),str(2**96+3)]),('A',[0,40],[str(2**64+1),str(2**96+3)]),('F',[32,32],[1.25,-2]),('D',[64,64],[1.25,-2])]:
        out=a.directory/('create-'+kind+'.fcs');options=dict(command='create',names=['A','B'],encoding=dict(datatype=kind,widths=widths))
        options['integer_values' if kind in 'IA' else 'values']=values
        task(options,output=out);files.append(out);cases.append(dict(case='create '+kind,output=out.name,expected=list(map(int,values)) if kind in 'IA' else values))
    out=a.directory/'create-hist-auto-total.fcs'
    task(dict(command='create-histogram',names=['A','B'],shape=[2,2],frequencies=[str(2**64+1)]*4,mode='C',encoding=dict(datatype='I',widths=[65,65])),output=out)
    files.append(out);cases.append(dict(case='histogram constructor exact total',output=out.name,expected=[2**64+1]*4))
    matrix=np.array([[1,.1,.03],[.02,1,.05],[.1,.03,1.]])
    true=np.array([[10.,20.,30.],[-5.,10.,2.]])
    measured=true@matrix
    src=source('compensation',make('D',[64]*3,[262144]*3,measured.ravel(),spill=matrix.tolist()))
    task(dict(command='values',count=2,compensated=True),src,check=lambda r:np.testing.assert_allclose(r,np.linalg.solve(matrix.T,measured.T).T,rtol=1e-12,atol=1e-12))
    task(dict(command='stats',compensated=True),src,check=lambda r:np.testing.assert_allclose([v['mean'] for v in r],true.mean(axis=0)))
    task(dict(command='gate',compensated=True,bounds=[[0,9,11]]),src,check=lambda r:np.testing.assert_array_equal(r,[0]))
    task(dict(command='gate',compensated=True,x=0,y=1,vertices=[[9,19],[11,19],[11,21],[9,21]]),src,check=lambda r:np.testing.assert_array_equal(r,[0]))
    sub=a.directory/'compensation-subset.fcs';task(dict(command='subset',channels=[2,0]),src,sub);files.append(sub)
    taskfile=a.directory/'TASKS.json';resultfile=a.directory/'RESULTS.json';taskfile.write_text(json.dumps(tasks),encoding='utf-8')
    subprocess.run(['node','tools/deep-batch.mjs',str(taskfile),str(resultfile)],cwd=ROOT,check=True)
    results=json.loads(resultfile.read_text('utf-8'))
    assert len(results)==len(tasks)==len(checks)
    for i,(result,check) in enumerate(zip(results,checks,strict=True)):
        assert result['ok'],(i,tasks[i],result)
        check(result.get('result'))
    for c in cases:
        meta,actual,raw=read(a.directory/c['output'])
        if meta['$DATATYPE'] in 'IA':assert actual==c['expected'],(c,actual)
        else:np.testing.assert_allclose(actual,c['expected'],rtol=1e-6)
        if c['case']=='histogram constructor exact total': assert int(meta['$TOT'])==4*(2**64+1)
    meta,_,_=read(sub);parts=meta['$SPILLOVER'].split(',');assert parts[1:3]==['C','A']
    np.testing.assert_allclose(list(map(float,parts[3:])),matrix[np.ix_([2,0],[2,0])].ravel())
    # Exercise public CLI commands too, using the same independent reader.
    result=subprocess.run(['node','tools/fcs.mjs','histogram',str(out)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=True)
    assert json.loads(result.stdout)['frequencies']==[str(2**64+1)]*4
    cli_options=a.directory/'CLI-HISTOGRAM.json'
    cli_options.write_text(json.dumps(dict(names=['A','B'],shape=[2,2],frequencies=['1','2','2','1'],mode='U',encoding=dict(datatype='A',widths=[0,0]))),encoding='utf-8')
    cli_output=a.directory/'CLI-HISTOGRAM.fcs'
    subprocess.run(['node','tools/fcs.mjs','create-histogram',str(cli_output),'--options',str(cli_options)],cwd=ROOT,capture_output=True,text=True,check=True)
    assert read(cli_output)[1]==[1,2,2,1]
    unchanged=cli_output.read_bytes()
    again=subprocess.run(['node','tools/fcs.mjs','create-histogram',str(cli_output),'--options',str(cli_options)],cwd=ROOT,capture_output=True,text=True)
    assert again.returncode!=0 and cli_output.read_bytes()==unchanged
    files.append(cli_output)
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['parse.mbt','encoding.mbt','histogram.mbt','compensation.mbt','construction.mbt','geometry.mbt','write.mbt','events.mbt','cmd/bridge/main.mbt','tools/check-deep-features.py','_build/js/release/build/cmd/bridge/bridge.js']}
    report=dict(status='passed',oracle='independent Python integer/struct/ASCII reader and NumPy.linalg.solve',numpy=np.__version__,tasks=len(tasks),sourceSha256=hashes,
                cases=cases,files=[dict(file=file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest()) for file in files],sourceLicense='original MIT synthetic vectors')
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='passed',tasks=len(tasks),independentFiles=len(files),cases=len(cases))))

if __name__=='__main__':main()
