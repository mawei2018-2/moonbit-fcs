import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root = fileURLToPath(new URL('../',import.meta.url));
const temp = fs.mkdtempSync(path.join(os.tmpdir(),'moonbit-fcs-cli-'));
const run = (args,status=0) => {
  const r = spawnSync(process.execPath,['tools/fcs.mjs',...args],{cwd:root,encoding:'utf8'});
  assert.equal(r.status,status,r.stderr);return r.stdout;
};
const opt = (name,value) => {const p=path.join(temp,name+'.json');fs.writeFileSync(p,JSON.stringify(value));return p;};
try {
 const a=path.join(temp,'a.fcs'),b=path.join(temp,'b.fcs'),csv=path.join(temp,'a.csv');
 run(['create',a,'--options','examples/events.json']);
 const report=JSON.parse(run(['inspect',a]));assert.equal(report.events,4);
 run(['subset',a,b,'--options','examples/gate.json']);
 const values=JSON.parse(run(['values',b,'--options',opt('values',{count:2})]));
 assert.deepEqual(values,[[20,4],[30,8]]);
 run(['csv',a,csv,'--options',opt('csv',{scaled:true})]);
 const lines=fs.readFileSync(csv,'utf8').trim().split('\r\n');assert.equal(lines.length,5);assert.equal(lines[2],'20,4,0.1');
 run(['rewrite',a,a],1);assert.equal(JSON.parse(run(['inspect',a])).events,4);
 run(['compare',a,a]);run(['compare',a,b],2);
 run(['values',a,'--options',opt('bad',{start:-1})],1);
 run(['subset',a,path.join(temp,'bad.fcs'),'--options',opt('bad-gate',{bounds:[[0,30,10]]})],1);
 assert.equal(fs.existsSync(path.join(temp,'bad.fcs')),false);
 const broken=path.join(temp,'broken.fcs');fs.writeFileSync(broken,fs.readFileSync(a).subarray(0,60));
 run(['validate',broken],1);
 // Extend the declared TEXT range into a synthetic gap of 12 spaces. Move
 // DATA offsets consistently, without changing the event bytes or keywords.
 const src=fs.readFileSync(a),textStart=Number(src.subarray(10,18).toString()),textEnd=Number(src.subarray(18,26).toString());
 const dataStart=Number(src.subarray(26,34).toString()),dataEnd=Number(src.subarray(34,42).toString());
 const pad=Buffer.alloc(12,32),padded=Buffer.concat([src.subarray(0,textEnd+1),pad,src.subarray(textEnd+1)]);
 const writeOffset=(at,width,n)=>padded.write(String(n).padStart(width,'0'),at,width,'ascii');
 writeOffset(18,8,textEnd+12);writeOffset(26,8,dataStart+12);writeOffset(34,8,dataEnd+12);
 const sep=String.fromCharCode(src[textStart]);
 for(const [key,value] of [['$BEGINDATA',dataStart+12],['$ENDDATA',dataEnd+12]]){
   const at=padded.indexOf(Buffer.from(key+sep),textStart)+key.length+1;
   assert(at>textStart);writeOffset(at,10,value);
 }
 const legacy=path.join(temp,'padded.fcs');fs.writeFileSync(legacy,padded);
 run(['validate',legacy],1);
 const compatibility=opt('padding',{allow_text_padding:true});
 const paddedInfo=JSON.parse(run(['inspect',legacy,'--options',compatibility]));
 assert.equal(paddedInfo.events,4);assert.deepEqual(paddedInfo.warnings,['ignored 12 trailing ASCII spaces in primary TEXT; declared extent retained']);
 run(['validate',legacy,'--options',opt('strict-padding',{strict:true,allow_text_padding:true})],1);
 const normalized=path.join(temp,'normalized.fcs');run(['rewrite',legacy,normalized,'--options',compatibility]);
 assert.deepEqual(JSON.parse(run(['values',normalized])),JSON.parse(run(['values',a])));
 assert.deepEqual(JSON.parse(run(['validate',normalized,'--options',opt('strict',{strict:true})])).warnings,[]);
 assert.deepEqual(fs.readFileSync(legacy),padded);
 console.log(JSON.stringify({passed:11,temp}));
} finally {
 // A fresh private test directory, resolved by mkdtemp, is the only cleanup target.
 fs.rmSync(temp,{recursive:true,force:true});
}
