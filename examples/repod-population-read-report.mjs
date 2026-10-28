#!/usr/bin/env node
// MIT runner; source and derived RepOD statistics remain CC BY 4.0.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
if (process.argv.length !== 3) throw Error('usage: node examples/repod-population-read-report.mjs NEW_DIRECTORY');
const output = path.resolve(process.argv[2]);
const source = path.join(root, 'examples/repod/titration_CD11c_concat.fcs');
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const sourceHash = hash(source);
if (sourceHash !== '91097cd6506972e13817bfda617ffa4fd27f81d93618554417ba39346882886c') throw Error('licensed source identity mismatch');
fs.mkdirSync(output);
for (const name of ['ATTRIBUTION.md','CC-BY-4.0.txt','SOURCE.json']) fs.copyFileSync(path.join(root, 'examples/repod', name), path.join(output, name));
const options = {...JSON.parse(fs.readFileSync(path.join(root, 'examples/repod-gate-plan.json'), 'utf8')),
  population:'inner', channels:['Time','FSC-A'], start:1, count:2, include_read_report:true};
const optionFile = path.join(output, 'options.json');
fs.writeFileSync(optionFile, JSON.stringify(options, null, 2) + '\n', {flag:'wx'});
const argv = [path.join(root, 'tools/fcs.mjs'), 'population-stats', source, '--options', optionFile];
const run = spawnSync(process.execPath, argv, {cwd:root, encoding:'utf8', windowsHide:true, maxBuffer:8*1024*1024});
fs.writeFileSync(path.join(output, 'COMMAND.json'), JSON.stringify({argv, exitCode:run.status, stdout:run.stdout, stderr:run.stderr, error:run.error?.message}, null, 2) + '\n', {flag:'wx'});
if (run.status !== 0 || run.stderr) throw Error(run.stderr || run.error?.message || 'statistics command failed');
const result = JSON.parse(run.stdout);
if (result.read_report?.source_sha256 !== sourceHash || result.read_report.dataset !== 0 || result.read_report.version !== 'FCS3.1') throw Error('unexpected source read receipt');
if (hash(source) !== sourceHash) throw Error('original source changed');
fs.writeFileSync(path.join(output, 'statistics.json'), run.stdout, {flag:'wx'});
fs.writeFileSync(path.join(output, 'CHANGES.md'),
  'Bronisz, Agnieszka (2026), Flow Cytometry data, RepOD V2, DOI10.18150/JOLWGT, file96804; CC BY4.0.\n' +
  'Derived output: numeric inner-gate statistics for member window start1/count2, Time/FSC-A columns.\n' +
  'The optional read_report preserves actual original Dataset warnings and binds them to the original input SHA-256. No separate inspect call or intermediate FCS is written.\n' +
  'Original data, ANALYSIS and attribution are unchanged. Numerical exchange example only; no biological or clinical conclusion.\n', {flag:'wx'});
console.log(JSON.stringify({status:'passed', population_events:result.population_events, source_event_indices:result.source_event_indices,
  read_report:result.read_report, statisticsFile:path.join(output,'statistics.json')}));
