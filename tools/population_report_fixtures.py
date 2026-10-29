"""Original MIT complete sources and mathematical CSV expectations.

No product import, FCS writer or FCS reader dependency. Frozen before product
edits or execution. Counts are from explicit original source-index sets, also
checked against an independent raw byte decoder and rational predicates.
"""
import csv
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path

BASE = 18446744073709551616
CHILD = 'child,"Y"\n生細胞'
A = [(0,0),(2,4),(12,6),(4,8),(8,2),(9,9),(10,4),(1,5),(6,12)]
B = [(3,5),(7,9),(15,0),(0,0),(6,2)]
GATES = [
    {'id':CHILD,'parent':'band','bounds':[['Y',1,2.5]],'scaled':True},
    {'id':'band','bounds':[['X',2,10]]},
    {'id':'ID-window','integer_bounds':[{'channel':'ID','lower':str(BASE+1),'upper':str(BASE+4)}]},
    {'id':'vacant','bounds':[['X',90,100]]},
    {'id':'empty-child','parent':'vacant','bounds':[['Y',0,100]]},
    {'id':'compensated','bounds':[['Y',1,4]],'compensated':True},
]
MEMBERS = {
    'A':[[1,3,5],[1,3,4,5,8],[1,2,3],[],[],[3,7,8]],
    'B':[[0,1],[0,1,4],[0,1],[],[],[]],
    'empty':[[],[],[],[],[],[]],
}
HEADER = ['sample','source_file','source_sha256','dataset','source_version','read_warnings',
          'population','parent','count','parent_count','total_count','parent_fraction','total_fraction']
WARNINGS = ['accepted explicitly requested ASCII space padding in $BEGINDATA',
            'accepted explicitly requested ASCII space padding in $ENDDATA']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fcs(names, widths, rows, order='little', next_offset=0, padded=False):
    assert all(width%8==0 for width in widths)
    raw = b''.join(value.to_bytes(width//8,order) for row in rows for value,width in zip(row,widths))
    pairs = [('$MODE','L'),('$DATATYPE','I'),('$BYTEORD','1,2,3,4' if order=='little' else '4,3,2,1'),
             ('$PAR',str(len(names))),('$TOT',str(len(rows))),('$BEGINSTEXT','0'),('$ENDSTEXT','0'),
             ('$BEGINANALYSIS','0'),('$ENDANALYSIS','0'),('$NEXTDATA',str(next_offset)),
             ('$BEGINDATA',' 000000000000 ' if padded else '000000000000'),
             ('$ENDDATA',' 000000000000 ' if padded else '000000000000')]
    for i,(name,width) in enumerate(zip(names,widths),1):
        gain = {'ID':1,'X':2,'Y':4}[name]
        pairs += [(f'$P{i}N',name),(f'$P{i}B',str(width)),(f'$P{i}R',str(1<<width)),
                  (f'$P{i}E','0,0'),(f'$P{i}G',str(gain))]
    pairs.append(('$SPILLOVER','2,X,Y,1,0.5,0,1'))
    def text():
        return ('|'+'|'.join(value.replace('|','||') for pair in pairs for value in pair)+'|').encode()
    start = 256+len(text())
    end = start+len(raw)-1
    def number(n):return (' ' if padded else '')+f'{n:012d}'+(' ' if padded else '')
    pairs = [(k,number(start) if k=='$BEGINDATA' else number(end) if k=='$ENDDATA' else v) for k,v in pairs]
    header = b'FCS3.1    '+b''.join(f'{n:8d}'.encode() for n in [256,start-1,start,end,0,0])
    result = header.ljust(256,b' ')+text()+raw
    assert result[start:]==raw and len(result)==end+1
    return result


def independent_decode(data, offset=0):
    h = data[offset:offset+58]
    ts,te,ds,de = [int(h[i:i+8]) for i in [10,18,26,34]]
    values = data[offset+ts:offset+te+1].decode().split('|')[1:-1]
    meta = dict(zip(values[::2],values[1::2]))
    count = int(meta['$TOT']);par = int(meta['$PAR'])
    widths = [int(meta[f'$P{i}B'])//8 for i in range(1,par+1)]
    names = [meta[f'$P{i}N'] for i in range(1,par+1)]
    order = 'little' if meta['$BYTEORD']=='1,2,3,4' else 'big'
    payload = data[offset+ds:offset+de+1];assert len(payload)==count*sum(widths)
    rows=[];at=0
    for _ in range(count):
        row={}
        for name,width in zip(names,widths):
            row[name]=int.from_bytes(payload[at:at+width],order);at+=width
        rows.append(row)
    return rows


def expected_members(rows):
    band = [i for i,r in enumerate(rows) if 2<=r['X']<10]
    vacant = [i for i,r in enumerate(rows) if 90<=r['X']<100]
    return [[i for i in band if 1<=Fraction(rows[i]['Y'],4)<Fraction(5,2)],band,
            [i for i,r in enumerate(rows) if BASE+1<=r['ID']<BASE+4],vacant,
            [i for i in vacant if 0<=rows[i]['Y']<100],
            [i for i,r in enumerate(rows) if 1<=Fraction(r['Y']-r['X'],4)<4]]


def ratio(n,d):
    if not d:return ''
    value=n/d
    return str(int(value)) if value.is_integer() else str(value)


def summary(sample, file, data, group, dataset=0, warnings=None):
    members=MEMBERS[group];total={'A':9,'B':5,'empty':0}[group]
    rows=[]
    for index,gate in enumerate(GATES):
        count=len(members[index]);parent=gate.get('parent','')
        parent_count=len(members[1 if parent=='band' else 3]) if parent else total
        rows.append([sample,file,sha(data),str(dataset),'FCS3.1',json.dumps(warnings or [],separators=(',',':'),ensure_ascii=False),
                     gate['id'],parent,str(count),str(parent_count),str(total),ratio(count,parent_count),ratio(count,total)])
    return rows


def csv_bytes(rows):
    text=io.StringIO(newline='')
    csv.writer(text,lineterminator='\r\n',quoting=csv.QUOTE_ALL).writerow(HEADER)
    for row in rows:
        # CSV text fields are quoted; numeric fields are unquoted, null is empty.
        text.write(','.join('"'+value.replace('"','""')+'"' if i in [0,1,2,4,5,6,7] else value for i,value in enumerate(row))+'\r\n')
    return text.getvalue().encode('utf-8')


def fixtures(directory):
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=False)
    rows_a=[[BASE+i,x,y] for i,(x,y) in enumerate(A)]
    rows_b=[[y,BASE+i+2,x] for i,(x,y) in enumerate(B)]
    a=fcs(['ID','X','Y'],[72,16,16],rows_a)
    b=fcs(['Y','ID','X'],[16,72,16],rows_b,'big')
    empty=fcs(['ID','X','Y'],[72,16,16],[])
    padded=fcs(['ID','X','Y'],[72,16,16],rows_a,padded=True)
    prefix=fcs(['ID','X','Y'],[72,16,16],rows_a,next_offset=4096)
    linked=prefix.ljust(4096,b' ')+b
    sources={'panel A.fcs':a,'panel B.fcs':b,'linked.fcs':linked,'empty.fcs':empty,'padded.fcs':padded,'broken.fcs':b'not FCS\x00\xff'}
    for name,data in sources.items():(directory/name).write_bytes(data)
    for data,group,offset in [(a,'A',0),(b,'B',0),(linked,'B',4096),(empty,'empty',0),(padded,'A',0)]:
        assert expected_members(independent_decode(data,offset))==MEMBERS[group]
    samples=[{'sample':'donor α,"A"\nline','file':'panel A.fcs'},
             {'sample':'donor β','file':'linked.fcs','dataset':1},{'sample':'empty','file':'empty.fcs'}]
    main={'samples':samples}
    options={'strict':True,'gates':GATES}
    warning_options={'strict':False,'allow_offset_padding':True,'gates':GATES}
    manifests={'samples.json':main,'reverse.json':{'samples':samples[::-1]},
               'absolute.json':{'samples':[{'sample':'absolute β','file':str(directory/'panel B.fcs')}]},
               'override.json':{'samples':[{'sample':'zero override','file':'panel A.fcs','dataset':0},
                                            {'sample':'inherited one','file':'linked.fcs'}]},
               'warnings.json':{'samples':[{'sample':'actual correction','file':'padded.fcs'},
                                           {'sample':'no correction','file':'panel A.fcs','allow_offset_padding':False,'strict':True}]}}
    for name,value in manifests.items():(directory/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name,value in [('gates.json',options),('warning-gates.json',warning_options),('override-gates.json',{**options,'dataset':1})]:
        (directory/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    first=summary(samples[0]['sample'],'panel A.fcs',a,'A')
    second=summary('donor β','linked.fcs',linked,'B',1)
    third=summary('empty','empty.fcs',empty,'empty')
    expectations={'main':first+second+third,'reverse':third+second+first,
                  'absolute':summary('absolute β',str(directory/'panel B.fcs'),b,'B'),
                  'override':summary('zero override','panel A.fcs',a,'A')+summary('inherited one','linked.fcs',linked,'B',1),
                  'warnings':summary('actual correction','padded.fcs',padded,'A',warnings=WARNINGS)+summary('no correction','panel A.fcs',a,'A')}
    for name,rows in expectations.items():
        data=csv_bytes(rows)
        (directory/f'{name}-expected.csv').write_bytes(data)
        expected={'header':HEADER,'rows':rows,'bytesSHA256':sha(data),'sampleCount':len(rows)//len(GATES),
                  'pivotCounts':{r[0]:{x[6]:int(x[8]) for x in rows if x[0]==r[0]} for r in rows},
                  'rankByBand':[r[0] for r in sorted((row for row in rows if row[6]=='band'),key=lambda row:-Fraction(row[12] or 0))]}
        (directory/f'{name}-expected.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest={path.name:{'SHA256':sha(path.read_bytes()),'bytes':path.stat().st_size} for path in sorted(directory.iterdir())}
    (directory/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest
