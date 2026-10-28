#!/usr/bin/env node
// MIT runner; original/derived RepOD data remains CC BY4.0.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
if (process.argv.length !== 3) throw Error('usage: node examples/repod-gate-plan.mjs NEW_DIRECTORY');
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
const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const info = cli('inspect', source, '--options', planPath);
const populations = cli('populations', source, '--options', planPath);
fs.writeFileSync(path.join(output, 'populations.json'), JSON.stringify(populations, null, 2) + '\n');
if (JSON.stringify(populations.map(p => p.count)) !== JSON.stringify([2117,1794,662])) throw Error('unexpected numeric-example membership counts');
const selection = path.join(output, 'selection.json');
fs.writeFileSync(selection, JSON.stringify({...plan, population:'inner', channels:['SSC-A','FSC-A','Time'],
  drop_spillover:true, drop_analysis:true, metadata:[['SOURCE_DOI','10.18150/JOLWGT'],['SOURCE_FILE_ID','96804']]}, null, 2) + '\n');
const selected = path.join(output, 'selected.fcs');
cli('subset', source, selected, '--options', selection);
const selectedInfo = cli('inspect', selected);
if (selectedInfo.events !== 662 || selectedInfo.warnings.length) throw Error('unexpected output structure');
const csvOptions = path.join(output, 'csv-options.json');
fs.writeFileSync(csvOptions, JSON.stringify({channels:['Time','FSC-A']}));
cli('csv', selected, path.join(output, 'selected.csv'), '--options', csvOptions);
if (hash(source) !== sourceHash) throw Error('source changed');
fs.writeFileSync(path.join(output, 'CHANGES.md'),
  'Bronisz, Agnieszka (2026), Flow Cytometry data, RepOD V2, DOI10.18150/JOLWGT; file96804; CC BY4.0.\n' +
  'Changes: numeric parent/child gates in repod-gate-plan.json; source event indices are in populations.json.\n' +
  'Output FCS columns SSC-A/FSC-A/Time; CSV columns Time/FSC-A. Original unscaled DATA values retained.\n' +
  'Offsets normalized; ANALYSIS and spillover explicitly removed; source provenance added. Original source untouched.\n' +
  'Numerical format-exchange example only; no biological classification or clinical inference.\n');
const report = {status:'passed', output, sourceSha256:sourceHash, selectedSha256:hash(selected), planSha256:hash(planPath),
  sourceEvents:info.events, sourceWarnings:info.warnings, counts:populations.map(({id,count,parent_count,parent_fraction}) => ({id,count,parent_count,parent_fraction})),
  outputChannels:selectedInfo.channels.map(c => c.name), csvChannels:['Time','FSC-A'], commands:commands.length,
  inputLicense:'CC BY4.0 RepOD file96804', externalReadback:'not performed by this Node runner; use tools/verify-named-repod.py'};
fs.writeFileSync(path.join(output, 'RESULT.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
