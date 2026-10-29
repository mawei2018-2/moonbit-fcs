"""Original MIT complete mixed Dataset chains and independent expectations.

No producer/parser/writer import. Layout and every metadata/ANALYSIS/DATA value
are declared before execution. A forged bundle keeps hashes consistent while
altering a DATA byte, so receiving cannot rely on manifest self-consistency.
"""
import hashlib
import json
from pathlib import Path
import struct

WORDS=[0x8000000000000000,0x3ff8000000000000,0x7ff8000000000123,
       0xfff0000000000000,0x4004000000000000,0x7ff0000000000000]
WARNINGS=['accepted explicitly requested ASCII space padding in $BEGINDATA',
          'accepted explicitly requested ASCII space padding in $ENDDATA']
LAYOUT=['$BEGINDATA','$ENDDATA','$BEGINANALYSIS','$ENDANALYSIS']


def sha(data):return hashlib.sha256(data).hexdigest()


def spec(index):
    if index==0:
        return {'version':'FCS2.0','mode':'L','kind':'I','names':['A','B'],'widths':[16,16],
                'ranges':['65536','65536'],'events':'2','order':'little','data':struct.pack('<4H',1,2,3,4),
                'analysis':{'NOTE':'first|analysis'},'consumed':{'columnSums':[4,6]}}
    if index==1:
        return {'version':'FCS3.1','mode':'L','kind':'D','names':['D1','D2'],'widths':[64,64],
                'ranges':['1024','1024'],'events':'3','order':'big','data':b''.join(word.to_bytes(8,'big') for word in WORDS),
                'analysis':{'NOTE':'second|analysis 日本語'},
                'consumed':{'finiteCount':3,'finiteSum':'4','negativeZeroCount':1,'nanCount':1,'positiveInfinityCount':1,'negativeInfinityCount':1}}
    if index==2:
        return {'version':'FCS3.0','mode':'C','kind':'I','names':['H1','H2'],'widths':[16,16],
                'ranges':['2','2'],'events':'17','order':'little','data':struct.pack('<4H',2,3,5,7),
                'analysis':{},'consumed':{'frequencies':[2,3,5,7],'marginals':[[7,10],[5,12]],'total':17}}
    return {'version':'FCS3.1','mode':'L','kind':'I','names':['Z1','Z2'],'widths':[16,16],
            'ranges':['65536','65536'],'events':'0','order':'little','data':b'',
            'analysis':{},'consumed':{'columnSums':[0,0]}}


def make(source,index,next_offset=0,padded=False,canonical=False,alter=False):
    raw=source['data']
    if alter:raw=raw[2:4]+raw[:2]+raw[4:]  # Swap two frequencies; keep total17 valid.
    pairs=[('$MODE',source['mode']),('$DATATYPE',source['kind']),('$BYTEORD','1,2,3,4' if source['order']=='little' else '4,3,2,1'),
           ('$PAR',str(len(source['names']))),('$TOT',source['events']),('$BEGINSTEXT','0'),('$ENDSTEXT','0'),
           ('$NEXTDATA',str(next_offset)),('$BEGINDATA',' 000000000000 ' if padded else '000000000000'),
           ('$ENDDATA',' 000000000000 ' if padded else '000000000000'),
           ('$BEGINANALYSIS','000000000000'),('$ENDANALYSIS','000000000000'),
           ('$ORIGINALITY','Non-Original' if canonical else 'Original'),('VENDOR',f'original-{index}|retained')]
    for number,(name,width,range_value) in enumerate(zip(source['names'],source['widths'],source['ranges']),1):
        pairs += [(f'$P{number}N',name),(f'$P{number}S',name+'-stain'),(f'$P{number}B',str(width)),
                  (f'$P{number}R',range_value),(f'$P{number}E','0,0'),(f'$P{number}G','1')]
    if source['mode']=='C':pairs.append(('$COMP','2,1,0.25,0.5,1'))
    def encode(rows):return ('|'+'|'.join(value.replace('|','||') for pair in rows for value in pair)+'|').encode('utf-8')
    analysis=encode(list(source['analysis'].items())) if source['analysis'] else b''
    ds=256+len(encode(pairs));de=ds+len(raw)-1;ast=de+1 if analysis else 0;ae=ast+len(analysis)-1 if analysis else 0
    offsets={'$BEGINDATA':ds,'$ENDDATA':de,'$BEGINANALYSIS':ast,'$ENDANALYSIS':ae}
    pairs=[(key,(' ' if padded and key in ['$BEGINDATA','$ENDDATA'] else '')+f'{offsets[key]:012d}'+(' ' if padded and key in ['$BEGINDATA','$ENDDATA'] else '') if key in offsets else value) for key,value in pairs]
    text=encode(pairs);assert len(text)+256==ds
    version='FCS3.1' if canonical else source['version']
    header=version.encode()+b'    '+b''.join(f'{number:8d}'.encode() for number in [256,ds-1,ds,de,ast,ae])
    data=header.ljust(256,b' ')+text+raw+analysis
    assert data[ds:de+1]==raw and len(data)==(ae+1 if analysis else de+1)
    return data,dict(pairs)


def expected(source,index,offset,meta,warnings=None):
    values={key:value for key,value in meta.items() if key not in LAYOUT}
    values['$NEXTDATA']='0';values['$ORIGINALITY']='Non-Original'
    return {'dataset':index,'source_offset':offset,'source_version':source['version'],
            'source_mode':'ListMode' if source['mode']=='L' else 'Correlated',
            'source_events':int(source['events']) if source['mode']=='L' else source['events'],
            'source_warnings':warnings or [],'metadataExceptLayoutOffsets':values,'analysis':source['analysis'],
            'rawDataHex':source['data'].hex(),'consumed':source['consumed']}


def fixtures(directory):
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=False)
    specs=[spec(index) for index in range(3)];offsets=[0,2048,6144];nexts=[2048,4096,0]
    pieces=[make(value,index,nexts[index]) for index,value in enumerate(specs)]
    chain=pieces[0][0].ljust(2048,b'\x00')+pieces[1][0].ljust(4096,b'\x00')+pieces[2][0]
    assert len(pieces[0][0])<2048 and len(pieces[1][0])<4096
    padded_piece=make(specs[1],1,4096,padded=True)
    warning_chain=pieces[0][0].ljust(2048,b'\x00')+padded_piece[0].ljust(4096,b'\x00')+pieces[2][0]
    single,single_meta=make(specs[1],1)
    empty_spec=spec(3);empty,empty_meta=make(empty_spec,3)
    broken=pieces[0][0].ljust(2048,b'\x00')+b'BROKEN'+b' '*(58-6)
    sources={'chain.fcs':chain,'warning-chain.fcs':warning_chain,'single.fcs':single,'empty.fcs':empty,'broken-later.fcs':broken}
    for name,data in sources.items():(directory/name).write_bytes(data)
    main=[expected(value,index,offsets[index],pieces[index][1]) for index,value in enumerate(specs)]
    warns=[expected(value,index,offsets[index],padded_piece[1] if index==1 else pieces[index][1],WARNINGS if index==1 else []) for index,value in enumerate(specs)]
    single_expected=expected(specs[1],0,0,single_meta);single_expected['source_version']=specs[1]['version']
    empty_expected=expected(empty_spec,0,0,empty_meta)
    for name,data,rows in [('main',chain,main),('warnings',warning_chain,warns),('single',single,[single_expected]),('empty',empty,[empty_expected])]:
        (directory/(name+'-expected.json')).write_text(json.dumps({'source_sha256':sha(data),'datasets':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for index,row in enumerate(main):(directory/(f'dataset-{index}-expected.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    options={'strict.json':{'strict':True},'warnings.json':{'allow_offset_padding':True},
             'unsupported.json':{'dataset':0},'bad-boolean.json':{'strict':'true'},
             'strict-conflict.json':{'strict':True,'allow_offset_padding':True}}
    options.update({f'dataset-{index}.json':{'strict':True,'dataset':index} for index in range(3)})
    for name,value in options.items():(directory/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    (directory/'existing-sentinel.bin').write_bytes(b'EXISTING EXTRACTION\x00\xff')
    cases={'positive':[
        {'label':'main','source':'chain.fcs','options':'strict.json','expected':'main-expected.json'},
        {'label':'single','source':'single.fcs','options':'strict.json','expected':'single-expected.json'},
        {'label':'empty','source':'empty.fcs','options':'strict.json','expected':'empty-expected.json'},
        {'label':'warnings','source':'warning-chain.fcs','options':'warnings.json','expected':'warnings-expected.json'}],
        'negative':[
        {'label':'bad-later','source':'broken-later.fcs','options':'strict.json','error':'FCS version'},
        {'label':'unsupported-option','source':'chain.fcs','options':'unsupported.json','error':'unsupported extract-datasets option: dataset'},
        {'label':'bad-boolean','source':'chain.fcs','options':'bad-boolean.json','error':'strict must be boolean'},
        {'label':'strict-conflict','source':'warning-chain.fcs','options':'strict-conflict.json','error':'strict mode cannot enable offset padding compatibility'},
        {'label':'missing-input','source':'absent.fcs','options':'strict.json','error':'ENOENT'},
        {'label':'existing-directory','source':'chain.fcs','options':'strict.json','error':'EEXIST','existing':'directory'},
        {'label':'existing-file','source':'chain.fcs','options':'strict.json','error':'EEXIST','existing':'file'}],
        'forgedReceiver':{'source_file':'frozen-forged-source.fcs','expectedError':'DATA bytes differ'}}
    (directory/'CASES.json').write_text(json.dumps(cases,indent=2)+'\n',encoding='utf-8')
    forged=directory/'forged-bundle';forged.mkdir();records=[]
    for index,value in enumerate(specs):
        data,_=make(value,index,canonical=True,alter=index==2)
        name=f'dataset-{index:06d}.fcs';(forged/name).write_bytes(data)
        records.append({key:main[index][key] for key in ['dataset','source_offset','source_version','source_mode','source_events','source_warnings']})
        records[-1].update({'file':name,'bytes':len(data),'sha256':sha(data)})
    (forged/'manifest.json').write_text(json.dumps({'schema_version':1,'source_file':'frozen-forged-source.fcs','source_sha256':sha(chain),'datasets':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest={path.relative_to(directory).as_posix():{'SHA256':sha(path.read_bytes()),'bytes':path.stat().st_size} for path in sorted(directory.rglob('*')) if path.is_file()}
    (directory/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest
