from pathlib import Path
import argparse,json,hashlib
import flowio,numpy as np
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('directory',type=Path);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
assert flowio.__version__=='1.4.0'
original=flowio.FlowData(a.source);written=flowio.FlowData(a.directory/'selected.fcs')
raw=original.as_array(preprocess=False);indices=np.flatnonzero((raw[:,0]>=1000)&(raw[:,0]<2000));expected=raw[indices,:][:,[0,1,2]]
np.testing.assert_array_equal(indices,np.array(json.loads((a.directory/'indices.json').read_text(encoding='utf-8'))))
np.testing.assert_array_equal(written.as_array(preprocess=False),expected)
for channel in range(1,4):
 for suffix in ['n','s','e','g','r','b']:
  key=f'p{channel}{suffix}';assert original.text.get(key)==written.text.get(key),(key,original.text.get(key),written.text.get(key))
assert not any(k in written.text for k in ['spillover','spill','comp'])
manifest=json.loads((a.directory/'manifest.json').read_text(encoding='utf-8'));assert manifest['complete']
for key,file in [('sourceSha256',a.source),('outputSha256',a.directory/'selected.fcs')]:assert hashlib.sha256(file.read_bytes()).hexdigest()==manifest[key]
result=dict(flowio=flowio.__version__,sourceEvents=original.event_count,selectedEvents=len(indices),valuesCompared=int(expected.size),channelMetadataEqual=True,selection='original numeric interval only; not biological gating',sourceSha256=manifest['sourceSha256'],outputSha256=manifest['outputSha256'])
a.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
