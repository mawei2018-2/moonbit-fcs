// A reproducible raw-intensity exchange example, not biological gating.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {load,query,transform} from '../_build/js/release/build/cmd/bridge/bridge.js';

const root=path.dirname(fileURLToPath(import.meta.url));
const [directory]=process.argv.slice(2);
if(!directory)throw Error('Usage: node examples/repod-selection.mjs NEW_DIRECTORY');
const folder=path.join(root,'repod');
const source=JSON.parse(fs.readFileSync(path.join(folder,'SOURCE.json'),'utf8'));
const bytes=fs.readFileSync(path.join(folder,source.filename));
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
if(hash(bytes)!==source.sha256||bytes.length!==source.bytes)throw Error('Original licensed file changed');
let defaultRejected=false,strictRejected=false;
try{load(bytes,'{}');}catch{defaultRejected=true;}
try{load(bytes,'{"strict":true,"allow_offset_padding":true}');}catch{strictRejected=true;}
if(!defaultRejected||!strictRejected)throw Error('Padding must be explicitly enabled outside strict mode');
const data=load(bytes,'{"allow_offset_padding":true}');
const read=options=>JSON.parse(query(data,JSON.stringify(options)));
const info=read({command:'inspect'});
const indices=read({command:'gate',bounds:[[0,500000,1000000]],scaled:false});
const channels=[2,0,1];
const selected=transform(bytes,JSON.stringify({command:'subset',allow_offset_padding:true,events:indices,channels,drop_spillover:true,drop_analysis:true}));
const normalized=transform(bytes,'{"command":"rewrite","allow_offset_padding":true}');
const selectedData=load(selected,'{"strict":true}');
const outputInfo=JSON.parse(query(selectedData,'{"command":"inspect"}'));
if(info.events!==14320||info.channels.length!==26||indices.length!==2117||outputInfo.warnings.length)throw Error('Unexpected pinned file result');
const report={sourceEvents:info.events,sourceChannels:info.channels.length,sourceWarnings:info.warnings,
  originalOffsetMetadata:['$BEGINSTEXT','$ENDSTEXT','$BEGINANALYSIS','$ENDANALYSIS'].map(key=>[key,JSON.parse(query(data,'{"command":"metadata"}')).find(pair=>pair[0].toUpperCase()===key)[1]]),
  indices,outputChannels:outputInfo.channels,
  selectedValues:JSON.parse(query(selectedData,JSON.stringify({command:'values',count:indices.length,channels:[0,1,2],scaled:false}))),
  encodedOutput:Buffer.from(selected).toString('base64'),outputWarnings:outputInfo.warnings};
fs.mkdirSync(directory);
for(const [filename,contents]of [['selected.fcs',selected],['normalized.fcs',normalized],
  ['consumer-record.json',JSON.stringify(report)+'\n']])fs.writeFileSync(path.join(directory,filename),contents,{flag:'wx'});
const fd=fs.openSync(path.join(directory,'source.csv'),'wx');
try{
  fs.writeSync(fd,info.channels.map(channel=>'"'+channel.name.replaceAll('"','""')+'"').join(',')+'\r\n');
  for(let start=0;start<info.events;start+=1000){
    const rows=read({command:'values',start,count:Math.min(1000,info.events-start),scaled:false});
    fs.writeSync(fd,rows.map(row=>row.join(',')).join('\r\n')+'\r\n');
  }
}finally{fs.closeSync(fd);}
for(const filename of ['SOURCE.json','ATTRIBUTION.md','CC-BY-4.0.txt'])fs.copyFileSync(path.join(folder,filename),path.join(directory,filename),fs.constants.COPYFILE_EXCL);
const manifest={complete:true,sourceSha256:source.sha256,sourceEvents:info.events,sourceChannels:26,selectedEvents:indices.length,
  selectedSha256:hash(selected),normalizedSha256:hash(normalized),sourceWarnings:info.warnings,outputWarnings:outputInfo.warnings,
  defaultRejected,strictOptionRejected:strictRejected,selection:{bounds:[[0,500000,1000000]],channels,scaled:false},
  metadataPolicy:'preserve selected channel metadata; explicitly drop spillover and analysis; canonicalize structural offsets',
  derivedFileChanges:{'selected.fcs':'selected events and reordered channels; structural metadata updated','normalized.fcs':'canonical structural metadata; DATA bytes retained'},
  license:source.fileLevelLicense,attribution:'Bronisz, Agnieszka, 2026, Flow Cytometry data, RepOD V2, doi:10.18150/JOLWGT',
  limits:['numeric format-exchange example; no biological or clinical classification','project-authored consumer; no external adoption']};
fs.writeFileSync(path.join(directory,'manifest.json'),JSON.stringify(manifest,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({directory,sourceEvents:info.events,sourceChannels:26,selectedEvents:indices.length}));
