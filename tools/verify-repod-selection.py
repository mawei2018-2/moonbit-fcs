"""Independent FlowIO/NumPy exchange and exact raw-DATA preservation checks."""
from pathlib import Path
import argparse, base64, csv, hashlib, json
import flowio, numpy as np

p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1];source_file=root/'examples/repod/titration_CD11c_concat.fcs'
assert flowio.__version__=='1.4.0' and np.__version__=='2.5.3'
source=flowio.FlowData(source_file);selected=flowio.FlowData(a.directory/'selected.fcs');normalized=flowio.FlowData(a.directory/'normalized.fcs')
values=source.as_array(preprocess=False)
with (a.directory/'source.csv').open(encoding='utf-8',newline='') as stream:
 reader=csv.reader(stream);names=next(reader);exported=np.array([[float(cell) for cell in row] for row in reader])
assert names==[source.text[f'p{i}n'] for i in range(1,27)]
np.testing.assert_array_equal(exported,values)
indices=np.flatnonzero((values[:,0]>=500000)&(values[:,0]<1000000));channels=[2,0,1]
expected=values[indices,:][:,channels]
np.testing.assert_array_equal(selected.as_array(preprocess=False),expected)
np.testing.assert_array_equal(normalized.as_array(preprocess=False),values)
record=json.loads((a.directory/'consumer-record.json').read_text('utf-8'))
np.testing.assert_array_equal(np.array(record['indices']),indices)
np.testing.assert_array_equal(np.array(record['selectedValues']),expected)
assert base64.b64decode(record['encodedOutput'],validate=True)==(a.directory/'selected.fcs').read_bytes()
for out,input_channel in enumerate(channels,1):
 for suffix in ['n','s','b','r','g']:
  assert selected.text.get(f'p{out}{suffix}')==source.text.get(f'p{input_channel+1}{suffix}'),(out,suffix)
 assert [float(n) for n in selected.text[f'p{out}e'].split(',')]==[float(n) for n in source.text[f'p{input_channel+1}e'].split(',')]
assert not any(key in selected.text for key in ['spillover','spill','comp'])
assert selected.text['originality']=='Non-Original'
assert normalized.text['originality']=='Non-Original'
for key in ['beginstext','endstext','beginanalysis','endanalysis']:
 assert source.text[key].strip()=='0' and normalized.text[key].strip()==normalized.text[key]
def data_bytes(path):
 raw=path.read_bytes();return raw[int(raw[26:34]):int(raw[34:42])+1]
raw=data_bytes(source_file);assert len(raw)==14320*26*4
assert data_bytes(a.directory/'normalized.fcs')==raw
expected_bytes=b''.join(raw[int(row)*104+col*4:int(row)*104+col*4+4] for row in indices for col in channels)
assert data_bytes(a.directory/'selected.fcs')==expected_bytes
manifest=json.loads((a.directory/'manifest.json').read_text('utf-8'))
for key,file in [('sourceSha256',source_file),('selectedSha256',a.directory/'selected.fcs'),('normalizedSha256',a.directory/'normalized.fcs')]:
 assert hashlib.sha256(file.read_bytes()).hexdigest()==manifest[key]
for name in ['SOURCE.json','ATTRIBUTION.md','CC-BY-4.0.txt']:
 assert (a.directory/name).read_bytes()==(root/'examples/repod'/name).read_bytes()
assert manifest['complete'] and manifest['defaultRejected'] and manifest['strictOptionRejected'] and manifest['outputWarnings']==[]
result=dict(flowio=flowio.__version__,numpy=np.__version__,sourceEvents=14320,sourceChannels=26,
 sourceValuesCompared=int(values.size),selectedEvents=len(indices),selectedValuesCompared=int(expected.size),
 allSourceValuesEqual=True,selectedValuesEqual=True,normalizationValuesEqual=True,normalizationDataBytesIdentical=True,
 selectedDataBytesExactProjection=True,selectedChannelMetadataPreserved=True,originalFileUnchanged=True,
 sourceSha256=manifest['sourceSha256'],selectedSha256=manifest['selectedSha256'],normalizedSha256=manifest['normalizedSha256'],
 attributionRetained=True,fileLevelLicense='CC BY 4.0; RepOD file 96804, dataset V2.0 only',
 limits=['FlowIO accepts padded offsets independently; original file is nonconforming to FCS 3.1 section 3.2.17',
 'raw intensities and numeric selection only; no biological interpretation','historical G11 file license still unconfirmed'])
a.report.write_text(json.dumps(result,indent=2)+'\n','utf-8',newline='\n');print(json.dumps(result))
