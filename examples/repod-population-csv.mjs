#!/usr/bin/env node
// MIT runner; RepOD source/derived CSV remains CC BY4.0.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
if (process.argv.length !== 3 && !(process.argv.length === 5 && process.argv[3] === '--event-index-column')) throw Error('usage: node examples/repod-population-csv.mjs NEW_DIRECTORY [--event-index-column NAME]');
const eventIndexColumn = process.argv.length === 5 ? process.argv[4] : undefined;
const output = path.resolve(process.argv[2]);
const source = path.join(root, 'examples/repod/titration_CD11c_concat.fcs');
const sourceHash = hash(source);
if (sourceHash !== '91097cd6506972e13817bfda617ffa4fd27f81d93618554417ba39346882886c') throw Error('licensed source identity mismatch');
fs.mkdirSync(output);
const commands = [];
function cli(command, ...args) {
  const argv = [path.join(root, 'tools/fcs.mjs'), command, ...args];
  const r = spawnSync(process.execPath, argv, {cwd:root, encoding:'utf8', windowsHide:true, maxBuffer:8*1024*1024});
  commands.push({argv, exit:r.status, stdout:r.stdout, stderr:r.stderr, error:r.error?.message});
  fs.writeFileSync(path.join(output, 'COMMANDS.json'), JSON.stringify(commands, null, 2) + '\n');
  if (r.status !== 0 || r.stderr) throw Error(`${command}: ${r.stderr ?? r.error}`);
  return JSON.parse(r.stdout);
}
for (const name of ['ATTRIBUTION.md','CC-BY-4.0.txt','SOURCE.json']) fs.copyFileSync(path.join(root, 'examples/repod', name), path.join(output, name));
const planPath = path.join(root, 'examples/repod-gate-plan.json');
const optionsPath = path.join(output, 'csv-options.json');
const options = {...JSON.parse(fs.readFileSync(planPath, 'utf8')), population:'inner', channels:['Time','FSC-A']};
if (eventIndexColumn !== undefined) options.event_index_column = eventIndexColumn;
fs.writeFileSync(optionsPath, JSON.stringify(options, null, 2) + '\n');
const info = cli('inspect', source, '--options', optionsPath);
const csv = path.join(output, 'inner.csv');
const receipt = cli('csv', source, csv, '--options', optionsPath);
if (receipt.population !== 'inner' || receipt.events !== 662 || receipt.population_events !== 662 || receipt.source_event_indices.length !== 662) throw Error('unexpected direct population CSV receipt');
if (hash(source) !== sourceHash) throw Error('source changed');
if (fs.readdirSync(output).some(name => name.endsWith('.fcs'))) throw Error('direct CSV example must not create an intermediate FCS');
fs.writeFileSync(path.join(output, 'receipt.json'), JSON.stringify(receipt, null, 2) + '\n');
fs.writeFileSync(path.join(output, 'CHANGES.md'),
  'Bronisz, Agnieszka (2026), Flow Cytometry data, RepOD V2, DOI10.18150/JOLWGT; file96804; CC BY4.0.\n' +
  'Changes: existing numeric inner gate plan, CSV Time/FSC-A columns; source Dataset event indices are in receipt.json.\n' +
  'Original unscaled/uncompensated values retained. No intermediate FCS, source rewrite or ANALYSIS removal.\n' +
  (eventIndexColumn === undefined ? '' : `Additional first CSV column ${JSON.stringify(eventIndexColumn)} is the zero-based source Dataset event index.\n`) +
  'Source offset spaces accepted explicitly and warnings retained in RESULT.json. Source untouched.\n' +
  'Numerical format-exchange example only; no biological classification or clinical inference.\n');
const report = {status:'passed', sourceSha256:sourceHash, planSha256:hash(planPath), optionsSha256:hash(optionsPath),
  csvSha256:hash(csv), sourceEvents:info.events, sourceWarnings:info.warnings,
  population:receipt.population, events:receipt.events, sourceEventIndices:receipt.source_event_indices,
  outputChannels:options.channels, scaled:receipt.scaled, compensated:receipt.compensated,
  ...(eventIndexColumn === undefined ? {} : {eventIndexColumn}),
  intermediateFcsCreated:false, commands:commands.length, inputLicense:'CC BY4.0 RepOD file96804',
  externalReadback:'not performed by this Node runner; independent CSV/source-byte evidence is separate'};
fs.writeFileSync(path.join(output, 'RESULT.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({status:'passed', events:receipt.events, commands:commands.length, intermediateFcsCreated:false}));
