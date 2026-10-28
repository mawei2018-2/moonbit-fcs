"""Compile a cold separate MoonBit consumer of the original licensed FCS file."""
from pathlib import Path
import argparse, base64, hashlib, json, shutil, subprocess

p=argparse.ArgumentParser();p.add_argument('directory',type=Path)
p.add_argument('--target',choices=('js','wasm-gc'),default='js')
p.add_argument('--expected',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1];output=a.directory.resolve()
assert not output.exists() and not output.is_relative_to(root)
fixture=root/'examples/repod/titration_CD11c_concat.fcs'
source=json.loads((fixture.parent/'SOURCE.json').read_text('utf-8'))
raw=fixture.read_bytes();assert hashlib.sha256(raw).hexdigest()==source['sha256']
output.mkdir(parents=True);workspace=output/'workspace';workspace.mkdir()
vendor=workspace/'vendor/fcs';vendor.mkdir(parents=True)
if (root/'.git').exists():
 names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).decode().split('\0')
 names=sorted({name for name in names if name});origin='git checkout including non-ignored new files'
else:
 excluded={'.git','.mooncakes','_build','node_modules','__pycache__'}
 names=sorted(file.relative_to(root).as_posix() for file in root.rglob('*') if file.is_file() and not excluded.intersection(file.relative_to(root).parts))
 origin='exported source without git metadata'
for name in names:
 original=(root/name).resolve();assert original.is_file() and original.is_relative_to(root)
 copied=vendor/name;copied.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,copied)
app=workspace/'app';shutil.copytree(root/'examples/repod-consumer',app,ignore=shutil.ignore_patterns('.git','.mooncakes','_build','node_modules','__pycache__'))
(workspace/'moon.work').write_text('members = ["./vendor/fcs", "./app"]\n','utf-8',newline='\n')
encoded=base64.b64encode(raw).decode('ascii');chunks=[json.dumps(encoded[i:i+4096]) for i in range(0,len(encoded),4096)]
(app/'fixture.mbt').write_text('///|\nfn fixture() -> String {\n  [\n    '+',\n    '.join(chunks)+'\n  ].join("")\n}\n','utf-8',newline='\n')
moon=shutil.which('moon');assert moon
run=subprocess.run([moon,'run','.','--target',a.target,'--deny-warn'],cwd=app,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240)
(output/'stdout.log').write_text(run.stdout,'utf-8',newline='\n');(output/'stderr.log').write_text(run.stderr,'utf-8',newline='\n')
assert run.returncode==0,'Inspect retained consumer logs'
record=json.loads(run.stdout);expected=json.loads(a.expected.read_text('utf-8'))
assert record==expected,'Whole public-consumer report differs from Node file consumer'
assert len(record['indices'])==2117 and len(record['selectedValues'])==2117
(output/'selected.fcs').write_bytes(base64.b64decode(record['encodedOutput'],validate=True))
runtime=['moon.mod','parse.mbt','offset_padding.mbt','types.mbt','events.mbt','write.mbt','text.mbt','derived_extensions.mbt','moon.pkg','pkg.generated.mbti',
 'examples/repod-consumer/main.mbt','examples/repod-consumer/moon.mod','examples/repod-consumer/moon.pkg','tools/run-repod-consumer.py']
receipt=dict(target=a.target,separateModule=True,sourceOrigin=origin,exitCode=0,wholeReportMatches=True,
 inputSha256=source['sha256'],sourceEvents=record['sourceEvents'],sourceChannels=record['sourceChannels'],selectedEvents=2117,valuesCompared=6351,
 outputSha256=hashlib.sha256(base64.b64decode(record['encodedOutput'])).hexdigest(),
 sourceSha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in runtime},
 limits=['project-authored separate module, not external adoption','raw values only; numeric exchange selection, not biological interpretation'])
(output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n','utf-8',newline='\n')
print(json.dumps(dict(directory=str(output),target=a.target,separateModule=True,wholeReportMatches=True)))
