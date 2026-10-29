"""Original MIT complete bad manifests/options, frozen before product edits."""
import copy
import hashlib
import json
from pathlib import Path


def negative_cases(directory, inputs, gates):
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=False)
    inputs=Path(inputs).resolve()
    a={'sample':'first','file':str(inputs/'panel A.fcs')}
    b={'sample':'later','file':str(inputs/'linked.fcs'),'dataset':1}
    options={'strict':True,'gates':gates}
    normal={'samples':[a,b]}
    cases=[
        ('manifest-array',[],options,'manifest must be an object'),
        ('empty-roster',{'samples':[]},options,'nonempty samples'),
        ('duplicate-sample',{'samples':[a,{**b,'sample':'first'}]},options,'unique'),
        ('unknown-manifest-key',{**normal,'typo':True},options,'unsupported manifest'),
        ('unknown-sample-key',{'samples':[{**a,'typo':True}]},options,'unsupported sample'),
        ('invalid-sample-id',{'samples':[{**a,'sample':7}]},options,'nonempty sample'),
        ('invalid-file',{'samples':[{**a,'file':False}]},options,'nonempty file'),
        ('fractional-dataset',{'samples':[a,{**b,'dataset':0.5}]},options,'dataset'),
        ('nonboolean-read-option',{'samples':[a,{**b,'strict':'true'}]},options,'strict must be boolean'),
        ('unsupported-options',normal,{**options,'population':'band'},'unsupported population-report'),
        ('empty-gates',normal,{**options,'gates':[]},'nonempty gates'),
        ('late-missing-file',{'samples':[a,{**b,'file':str(inputs/'absent.fcs')}]},options,'later'),
        ('late-broken-source',{'samples':[a,{**b,'file':str(inputs/'broken.fcs'),'dataset':0}]},options,'later'),
        ('late-missing-dataset',{'samples':[a,{**b,'dataset':2}]},options,'later'),
        ('invalid-gate-on-empty',{'samples':[{'sample':'empty','file':str(inputs/'empty.fcs')}]},
         {**options,'gates':[{'id':'cycle','parent':'cycle','bounds':[['X',0,1]]}]},'cycle'),
    ]
    records=[]
    for label,manifest,opts,message in cases:
        m=directory/(label+'-samples.json');o=directory/(label+'-options.json')
        for path,value in [(m,manifest),(o,opts)]:path.write_text(json.dumps(copy.deepcopy(value),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        records.append({'label':label,'manifest':str(m),'options':str(o),'expectedExit':1,'expectedErrorContains':message,'targetMustBeAbsent':True})
    (directory/'CASES.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    hashes={path.name:{'SHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size} for path in sorted(directory.iterdir())}
    (directory/'MANIFEST.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return records,hashes
