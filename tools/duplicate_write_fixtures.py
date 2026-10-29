"""Original MIT complete duplicate-PnN sources and independent write expectations.

Compatibility inputs intentionally have repeated PnN labels: current default
reader warns and numeric access is supported; strict reading must still fail.
No production parser, writer, reference generator or product output imported.
"""
import hashlib
import json
from pathlib import Path
import re
import struct

LIST=[[4,12],[6,20],[10,28]]
SCALED=[[2,3],[3,5],[5,7]]
C=[1,2,3,4,5,6]
U=[6,9,2,5,8]


def digest(data):return hashlib.sha256(data).hexdigest()


def source(mode,names):
    counts=LIST if mode=='L' else (C if mode=='C' else U)
    raw=(b''.join(value.to_bytes(2,'little') for row in counts for value in row) if mode=='L'
         else b''.join(value.to_bytes(2,'little') for value in counts))
    meta=[('$MODE',mode),('$DATATYPE','I'),('$BYTEORD','1,2,3,4'),('$PAR','2'),
          ('$TOT','3' if mode=='L' else '21' if mode=='C' else '15'),
          ('$BEGINSTEXT','0'),('$ENDSTEXT','0'),('$BEGINANALYSIS','0'),('$ENDANALYSIS','0'),
          ('$NEXTDATA','0'),('$BEGINDATA','000000000000'),('$ENDDATA','000000000000'),
          ('$ORIGINALITY','Original'),('VENDOR','preserved|metadata 日本語')]
    for index,name in enumerate(names,1):
        meta += [(f'$P{index}N',name),(f'$P{index}S','left' if index==1 else 'right'),
                 (f'$P{index}B','16'),(f'$P{index}R','65536' if mode=='L' else str(index+1)),
                 (f'$P{index}E','0,0'),(f'$P{index}G',str((2 if index==1 else 4) if mode=='L' else 1))]
    if mode!='L':meta.append(('$COMP','2,1,0.25,0.50,1'))
    def text():return ('|'+'|'.join(value.replace('|','||') for pair in meta for value in pair)+'|').encode('utf-8')
    start=256+len(text());end=start+len(raw)-1
    meta=[(key,f'{start:012d}' if key=='$BEGINDATA' else f'{end:012d}' if key=='$ENDDATA' else value) for key,value in meta]
    header=b'FCS3.1    '+b''.join(f'{n:8d}'.encode() for n in [256,start-1,start,end,0,0])
    result=header.ljust(256,b' ')+text()+raw
    assert result[start:]==raw and len(result)==end+1
    return result,dict(meta)


def expected(meta,mode,columns,kind='I',width=16,big=False):
    result={key:value for key,value in meta.items() if not re.match(r'^\$P\d+',key)}
    for output,original in enumerate(columns,1):
        for suffix in ['N','S','R','E','G']:
            result[f'$P{output}{suffix}']=meta[f'$P{original+1}{suffix}']
        result[f'$P{output}B']=str(width)
        if kind in ['F','D']:result[f'$P{output}G']='1';result[f'$P{output}E']='0,0'
    result.update({'$ORIGINALITY':'Non-Original','$PAR':str(len(columns)),'$DATATYPE':kind,
                   '$BYTEORD':'4,3,2,1' if big else '1,2,3,4'})
    for key in ['$BEGINDATA','$ENDDATA']:result.pop(key)
    if mode=='L':values=[[row[index] for index in columns] for row in (SCALED if kind in ['F','D'] else LIST)]
    elif mode=='C':
        values=C if columns==[0,1] else [1,3,5,2,4,6] if columns==[1,0] else [3,7,11]
    else:values=U if columns==[0,1] else [2,5,8,6,9]
    if mode!='L':result['$COMP']='2,1,0.25,0.50,1' if columns==[0,1] else '2,1,0.50,0.25,1' if columns==[1,0] else '1,1'
    flat=[value for row in values for value in row] if mode=='L' else values
    raw=None
    if kind=='I':raw=b''.join(value.to_bytes(width//8,'big' if big else 'little') for value in flat)
    elif kind in ['F','D']:raw=struct.pack(('>' if big else '<')+('f' if kind=='F' else 'd')*len(flat),*flat)
    return {'mode':mode,'metadataExceptDataOffsets':result,'values':values,'rawDataHex':None if raw is None else raw.hex(),
            'expectedDataBytes':len(flat)*width if kind=='A' else len(flat)*(width//8),
            'sourceNamesAreCompatibilityInput':len({meta['$P1N'],meta['$P2N']})<2,'standardStrictInputClaimed':False}


def fixtures(directory):
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=False)
    sources={};metadata={}
    for name,mode,names in [('list','L',['DUP','DUP']),('C','C',['DUP','DUP']),('U','U',['DUP','DUP']),('unique','L',['DUP','OTHER'])]:
        sources[name],metadata[name]=source(mode,names);(directory/(name+'.fcs')).write_bytes(sources[name])
    positives=[]
    definitions=[('list-copy','list',{},[0,1],'I',16,False),
                 ('list-I','list',{'encoding':{'datatype':'I','widths':[16,16]}},[0,1],'I',16,False),
                 ('list-A','list',{'channels':[1,0],'encoding':{'datatype':'A','widths':[8,8]}},[1,0],'A',8,False),
                 ('list-F','list',{'channels':[1,0],'encoding':{'datatype':'F','widths':[32,32],'big_endian':True}},[1,0],'F',32,True),
                 ('list-D','list',{'channels':[1,0],'encoding':{'datatype':'D','widths':[64,64],'big_endian':True}},[1,0],'D',64,True),
                 ('C-copy','C',{},[0,1],'I',16,False),('C-swap','C',{'channels':[1,0]},[1,0],'I',16,False),
                 ('C-one','C',{'channels':[1]},[1],'I',16,False),
                 ('U-copy','U',{},[0,1],'I',16,False),('U-swap','U',{'channels':[1,0]},[1,0],'I',16,False),
                 ('unique-control','unique',{'encoding':{'datatype':'D','widths':[64,64]}},[0,1],'D',64,False)]
    for label,src,options,columns,kind,width,big in definitions:
        exp=expected(metadata[src],'L' if src in ['list','unique'] else src,columns,kind,width,big)
        (directory/(label+'-options.json')).write_text(json.dumps(options,indent=2)+'\n',encoding='utf-8')
        (directory/(label+'-expected.json')).write_text(json.dumps(exp,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        positives.append({'label':label,'source':src+'.fcs','options':label+'-options.json','expected':label+'-expected.json'})
    negatives=[]
    errors=[('strict-list','rewrite','list.fcs',{'strict':True},'duplicate channel name DUP'),
            ('strict-C','rewrite','C.fcs',{'strict':True},'duplicate channel name DUP'),
            ('strict-U','rewrite','U.fcs',{'strict':True},'duplicate channel name DUP'),
            ('ambiguous-name','rewrite','list.fcs',{'channels':['DUP']},'ambiguous channel name: DUP'),
            ('duplicate-position','rewrite','list.fcs',{'channels':[0,0]},'duplicate output channel'),
            ('invalid-width-shape','rewrite','list.fcs',{'encoding':{'datatype':'I','widths':[16]}},'encoding width count'),
            ('create-default','create',None,{'names':['DUP','DUP'],'values':[1,2]},'unique nonempty channel'),
            ('create-encoding','create',None,{'names':['DUP','DUP'],'integer_values':['1','2'],'encoding':{'datatype':'I','widths':[16,16]}},'unique nonempty channel'),
            ('create-histogram','create-histogram',None,{'names':['DUP','DUP'],'shape':[2,3],'frequencies':list(map(str,C)),'mode':'C','encoding':{'datatype':'I','widths':[16,16]}},'unique nonempty channel')]
    for label,command,src,options,message in errors:
        (directory/(label+'-options.json')).write_text(json.dumps(options,indent=2)+'\n',encoding='utf-8')
        negatives.append({'label':label,'command':command,'source':src,'options':label+'-options.json','expectedErrorContains':message,'expectedExit':1})
    (directory/'CASES.json').write_text(json.dumps({'positive':positives,'negative':negatives},indent=2)+'\n',encoding='utf-8')
    manifest={path.name:{'SHA256':digest(path.read_bytes()),'bytes':path.stat().st_size} for path in sorted(directory.iterdir())}
    (directory/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest
