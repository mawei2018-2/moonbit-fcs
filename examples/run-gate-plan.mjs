#!/usr/bin/env node
// Original MIT data-preparation example. Thresholds have no biological meaning.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const commands = [];
if (process.argv.length !== 3) throw Error('usage: node examples/run-gate-plan.mjs NEW_DIRECTORY');
const output = path.resolve(process.argv[2]);
fs.mkdirSync(output);
function cli(command, ...args) {
  const argv = [path.join(root, 'tools/fcs.mjs'), command, ...args];
  const run = spawnSync(process.execPath, argv, {cwd:root, encoding:'utf8', windowsHide:true, maxBuffer:8*1024*1024});
  commands.push({argv, exit:run.status, stdout:run.stdout, stderr:run.stderr, error:run.error?.message});
  fs.writeFileSync(path.join(output, 'commands.json'), JSON.stringify(commands, null, 2) + '\n');
  if (run.status !== 0 || run.stderr) throw Error(`example command failed: ${command}: ${run.stderr ?? run.error}`);
  return JSON.parse(run.stdout);
}
const source = path.join(output, 'events.fcs');
const selected = path.join(output, 'selected.fcs');
const planPath = path.join(root, 'examples/gate-plan.json');
const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
cli('create', source, '--options', path.join(root, 'examples/gate-plan-events.json'));
const populations = cli('populations', source, '--options', planPath);
fs.writeFileSync(path.join(output, 'populations.json'), JSON.stringify(populations, null, 2) + '\n');
const expected = [[2,5], [2,3,5], [1,2,3,5], [1,2,5], [1]];
if (JSON.stringify(populations.map(p => p.event_indices)) !== JSON.stringify(expected)) throw Error('unexpected source-event membership');
const selection = path.join(output, 'selection.json');
fs.writeFileSync(selection, JSON.stringify({...plan, population:'id_window', channels:[3,0,2]}, null, 2) + '\n');
cli('subset', source, selected, '--options', selection);
const values = cli('values', selected);
const expectedValues = [['18446744073709551618','30','9'], ['18446744073709551621','20','8']];
if (JSON.stringify(values) !== JSON.stringify(expectedValues)) throw Error('unexpected selected exact values');
cli('csv', selected, path.join(output, 'selected.csv'));
const info = cli('inspect', selected);
if (info.events !== 2 || info.warnings.length) throw Error('unexpected selected file structure');
const report = {status:'passed', output, inputLicense:'original MIT synthetic events',
  sourceSha256:hash(source), selectedSha256:hash(selected), planSha256:hash(planPath),
  population:'id_window', originalEventIndices:populations[0].event_indices,
  populations:populations.map(({id,count,parent_count,parent_fraction}) => ({id,count,parent_count,parent_fraction})),
  selectedValues:values, commands:commands.length};
fs.writeFileSync(path.join(output, 'RESULT.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
