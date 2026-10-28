import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {load,query,transform} from '../_build/js/release/build/cmd/bridge/bridge.js';
const bytes=transform(new Uint8Array(),JSON.stringify({command:'create',names:['A','B'],values:[1,10,2,20,3,30]}));
const original=createHash('sha256').update(bytes).digest('hex');
let rejected=0;
for(const value of [0.5,-0.5,2147483648,'1',true]){
 for(const key of ['dataset','start','count','x','y']){
  assert.throws(()=>load(bytes,JSON.stringify({[key]:value})),/exact 32-bit integers/);rejected++;
 }
 for(const key of ['events','channels']){
  // Numeric-looking strings are exact PnN names only for channel references.
  // Keep the original '1' counterexample: A/B has no such channel name.
  const reason=key==='channels' && value==='1' ? /unknown channel name: 1/ : /exact 32-bit integers/;
  assert.throws(()=>transform(bytes,JSON.stringify({command:'subset',[key]:[value]})),reason);rejected++;
 }
}
for(const selection of [{events:[0],bounds:[[0,0,2]]},{events:[0],vertices:[[0,0],[1,1],[2,0]],x:0,y:1},{bounds:[[0,0,2]],vertices:[[0,0],[1,1],[2,0]],x:0,y:1}]){
 assert.throws(()=>transform(bytes,JSON.stringify({command:'subset',...selection})),/choose exactly one event selector/);rejected++;
}
const selected=transform(bytes,JSON.stringify({command:'subset',events:[2,0],channels:[1,0]}));
assert.deepEqual(JSON.parse(query(load(selected,'{}'),'{"command":"values"}')),[[30,3],[10,1]]);
const named=transform(bytes,JSON.stringify({command:'subset',events:[2,0],channels:['B','A']}));
assert.deepEqual(JSON.parse(query(load(named,'{}'),'{"command":"values"}')),[[30,3],[10,1]]);
assert.equal(createHash('sha256').update(bytes).digest('hex'),original);
assert.deepEqual(JSON.parse(query(load(bytes,'{}'),'{"command":"values","start":1,"count":1}')),[[2,20]]);
console.log(JSON.stringify({rejectedRequests:rejected,exactSelectionPreserved:true,namedSelectionPreserved:true,inputUnchanged:true}));
