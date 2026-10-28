#!/usr/bin/env node
// Run the actual release engine. The separate Python reader validates its bytes.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

const root = new URL('../', import.meta.url);
const engine = new URL('_build/js/release/build/cmd/bridge/bridge.js', root);
const api = await import(engine.href);
const manifest = JSON.parse(fs.readFileSync(new URL('examples/standard-encodings/INPUTS.json', root)));
const output = path.resolve(process.argv[2] ?? 'work/standard-encodings');
fs.mkdirSync(output, { recursive: false });
const sha = b => createHash('sha256').update(b).digest('hex');
const query = (data, options) => JSON.parse(api.query(api.load(data, '{}'), JSON.stringify(options)));
const receipt = { status: 'passed', engineSha256: sha(fs.readFileSync(engine)), cases: [] };
for (const c of manifest.cases) {
  const source = Buffer.from(c.sourceBase64, 'base64');
  assert.equal(sha(source), c.sourceSha256);
  assert.deepEqual(query(source, {command:'values', count:c.values.length, exact_integers:true}), c.values, c.name);
  const selected = Buffer.from(api.transform(source, JSON.stringify({command:'subset', events:c.events, channels:c.channels})));
  const expected = c.events.map(e => c.channels.map(ch => c.values[e][ch]));
  assert.deepEqual(query(selected, {command:'values', count:expected.length, exact_integers:true}), expected, `${c.name} subset`);
  const rewritten = Buffer.from(api.transform(source, '{"command":"rewrite"}'));
  assert.deepEqual(query(rewritten, {command:'values', count:c.values.length, exact_integers:true}), c.values, `${c.name} rewrite`);
  const empty = Buffer.from(api.transform(source, JSON.stringify({command:'subset', events:[], channels:c.channels})));
  assert.deepEqual(query(empty, {command:'values', count:0, exact_integers:true}), []);
  const products = {source, selected, rewritten, empty};
  const gateChannel = c.widths.findIndex((_,ch) => c.values.every(row => BigInt(row[ch]) >= 0n && BigInt(row[ch]) < 9007199254740991n));
  let gate = null;
  if (gateChannel >= 0) {
    const lower = Number(c.values[0][gateChannel]), upper = lower+1;
    const events = c.values.flatMap((row,e) => BigInt(row[gateChannel]) >= BigInt(lower) && BigInt(row[gateChannel]) < BigInt(upper) ? [e] : []);
    const bounds = [[gateChannel,lower,upper]];
    assert.deepEqual(query(source,{command:'gate',bounds}),events);
    products.gated = Buffer.from(api.transform(source,JSON.stringify({command:'subset',bounds,channels:c.channels})));
    gate = {bounds,events,channels:c.channels};
  }
  const files = {};
  for (const [key, bytes] of Object.entries(products)) {
    const file = `${c.name}-${key}.fcs`;
    fs.writeFileSync(path.join(output, file), bytes, {flag:'wx'});
    files[key] = {file, sha256:sha(bytes), bytes:bytes.length};
  }
  receipt.cases.push({name:c.name, gate, files});
}
fs.writeFileSync(path.join(output, 'ENGINE.json'), JSON.stringify(receipt, null, 2)+'\n', {flag:'wx'});
console.log(JSON.stringify({status:receipt.status, cases:receipt.cases.length, products:receipt.cases.reduce((n,c)=>n+Object.keys(c.files).length,0), output}));
