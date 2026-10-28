#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const help = `MoonBit FCS data preparation (Node >= 22)
  node tools/fcs.mjs inspect|validate|stats|metadata|values|gate input.fcs [--options options.json]
  node tools/fcs.mjs csv input.fcs output.csv [--options options.json]
  node tools/fcs.mjs subset|rewrite input.fcs output.fcs [--options options.json]
  node tools/fcs.mjs create|create-histogram output.fcs --options events.json
  node tools/fcs.mjs histogram|histogram-axis|histogram-bin|compensation input.fcs [--options options.json]
  node tools/fcs.mjs populations input.fcs --options gate-plan.json
  node tools/fcs.mjs population-stats input.fcs --options population.json
  node tools/fcs.mjs compare first.fcs second.fcs [more.fcs ...]
Options: dataset (0-based), strict, allow_exclusive_end, latin1, allow_text_padding, allow_offset_padding, scaled;
allow_text_padding accepts only trailing ASCII spaces after the final TEXT delimiter and warns;
it cannot combine with strict. allow_offset_padding accepts outer ASCII spaces only in the seven
segment-offset TEXT values, warns per corrected field, and cannot combine with strict.
FCS 3.1 forbids this numeric padding. Inspect warnings before rewriting. values: start/count/channels,
exact_integers:true returns decimal strings for I/A without Double rounding;
subset: events or bounds:[[channel,lower,upper]] or vertices:[[x,y],...] with x/y channel;
channels, metadata:[[key,value]], drop_spillover, drop_analysis. Output must not exist.
Gate plans: gates:[{id,parent?,bounds|vertices|integer_bounds,...}];
gate/subset with population:"id" selects that group's original event indices. See GATE-PLANS.md.
compare exits 2 on inconsistent storage mode/channel metadata/type/timestep/spillover; error exits 1.
CSV receipts describe the selected view: compensation implies scaling.
CSV also accepts gates/population directly; start/count slice population members.
Gate view flags stay in each step; top-level view flags select CSV output values.
CSV event_index_column:"source_event_index" optionally prepends a zero-based source Dataset index.
population-stats requires gates/population and reports all original channels by default, plus source indices;
top-level scaled/compensated choose statistics views, independently of per-step gate views.
Its optional channels list selects/reorders report columns after full-channel compensation;
array requests include original channel_indices. Omitted/null retains the all-channel format.
population-stats start/count slice population member positions like CSV; an explicit window
adds events (window length), while population_events remains the full group length.
  include_read_report:true optionally adds the original source SHA-256, selected dataset,
  source version and actual read warnings before the private canonical statistics copy.
It uses an in-memory population FCS copy; see POPULATION-STATS.md for limits.
Build first: moon build --target js --release`;

function input(file) {
  const fd = fs.openSync(file, 'r');
  try {
    const s = fs.fstatSync(fd);
    if (!s.isFile() || s.size > 2147483647) throw Error('input must be a regular file within runtime byte address space');
    const data = Buffer.alloc(s.size);
    let at = 0;
    while (at < data.length) {
      const n = fs.readSync(fd, data, at, data.length - at, at);
      if (!n) throw Error('input changed or truncated while reading');
      at += n;
    }
    return data;
  } finally { fs.closeSync(fd); }
}
function writeNew(file, data) {
  const fd = fs.openSync(file, 'wx');
  try { fs.writeFileSync(fd, data); } finally { fs.closeSync(fd); }
}
function csvCell(value) {
  // Standard RFC-style quoting; these scientific labels are not a spreadsheet formula sanitizer.
  return '"' + String(value).replaceAll('"', '""') + '"';
}
async function main() {
  const args = process.argv.slice(2);
  if (!args.length || args[0] === '--help') { console.log(help); return; }
  let options = {};
  const p = args.indexOf('--options');
  if (p >= 0) {
    if (!args[p + 1]) throw Error('--options requires a JSON file');
    const opt = input(args[p + 1]);

    options = JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(opt));
    if (!options || Array.isArray(options) || typeof options !== 'object') throw Error('options must be object');
    args.splice(p, 2);
  }
  const [command, ...files] = args;
  const modulePath = new URL('../_build/js/release/build/cmd/bridge/bridge.js', import.meta.url);
  if (!fs.existsSync(modulePath)) throw Error('run moon build --target js --release first');
  const api = await import(modulePath.href);
  const read = file => api.load(input(file), JSON.stringify(options));
  const query = (d, command, extra = {}) => JSON.parse(api.query(d, JSON.stringify({...options, ...extra, command})));
  if (command === 'compare') {
    if (files.length < 2) throw Error('compare needs at least two files');
    const rows = files.map(file => ({ file, report: query(read(file), 'inspect') }));
    const key = r => JSON.stringify({mode:r.mode, channels:r.channels, datatype:r.datatype, timestep:r.timestep, spillover:r.spillover});
    const baseline = key(rows[0].report);
    const output = rows.map(r => ({file:r.file, events:r.report.events, mode:r.report.mode, compatible:key(r.report) === baseline, warnings:r.report.warnings}));
    console.log(JSON.stringify(output, null, 2));
    if (output.some(r => !r.compatible)) process.exitCode = 2;
    return;
  }
  if (['create','create-histogram'].includes(command)) {
    if (files.length !== 1) throw Error('create needs output path');
    writeNew(files[0], api.transform(new Uint8Array(), JSON.stringify({...options, command})));
    console.log(JSON.stringify({written:files[0]})); return;
  }
  if (['rewrite','subset'].includes(command)) {
    if (files.length !== 2) throw Error('transform needs input and output paths');
    const bytes = api.transform(input(files[0]), JSON.stringify({...options, command}));
    writeNew(files[1], bytes); console.log(JSON.stringify({written:files[1], bytes:bytes.length})); return;
  }
  if (command === 'population-stats') {
    if (files.length !== 1) throw Error('population-stats needs one input path');
    const parseKeys = ['dataset','strict','allow_exclusive_end','latin1','allow_text_padding','allow_offset_padding'];
    const allowed = new Set([...parseKeys,'gates','population','scaled','compensated','channels','start','count','include_read_report']);
    for (const key of Object.keys(options)) if (!allowed.has(key)) throw Error(`unsupported population-stats option: ${key}`);
    for (const key of ['scaled','compensated','include_read_report']) if (Object.hasOwn(options, key) && typeof options[key] !== 'boolean') throw Error(`${key} must be boolean`);
    if (!Object.hasOwn(options, 'gates') || typeof options.population !== 'string') throw Error('population-stats requires gates and population');
    const source = input(files[0]);
    const sourceHash = options.include_read_report ? createHash('sha256').update(source).digest('hex') : null;
    const d = api.load(source, JSON.stringify(options));
    const info = query(d, 'inspect');
    if (info.mode !== 'ListMode') throw Error('population statistics require list DATA; use histogram APIs');
    const reportChannels = options.channels == null ? null : query(d, 'channel-indices', {channels:options.channels});
    const gateOptions = {...options, command:'gate'};
    delete gateOptions.scaled;
    delete gateOptions.compensated;
    delete gateOptions.start;
    delete gateOptions.count;
    delete gateOptions.include_read_report;
    const members = JSON.parse(api.query(d, JSON.stringify(gateOptions)));
    const hasWindow = Object.hasOwn(options, 'start') || Object.hasOwn(options, 'count');
    const start = options.start ?? 0, count = options.count ?? members.length - start;
    if (!Number.isSafeInteger(start) || !Number.isSafeInteger(count) || start < 0 || count < 0 || start > members.length || count > members.length - start) throw Error('invalid population statistics range');
    const selected = hasWindow ? members.slice(start, start + count) : members;
    const parseOptions = Object.fromEntries(parseKeys.filter(key => Object.hasOwn(options, key)).map(key => [key, options[key]]));
    // Keep every channel so compensation uses the original full matrix. Only
    // this private in-memory copy drops ANALYSIS; source bytes remain untouched.
    const bytes = api.transform(source, JSON.stringify({...parseOptions, command:'subset', events:selected, drop_analysis:true}));
    const population = api.load(bytes, '{}');
    const statistics = JSON.parse(api.query(population, JSON.stringify({command:reportChannels === null ? 'stats' : 'selected-stats',
      ...(reportChannels === null ? {} : {channels:reportChannels}), scaled:!!options.scaled, compensated:!!options.compensated})));
    console.log(JSON.stringify({population:options.population, population_events:members.length,
      source_event_indices:selected, channel_names:(reportChannels ?? info.channels.map((_, i) => i)).map(i => info.channels[i].name),
      scaled:!!options.scaled || !!options.compensated, compensated:!!options.compensated,
      statistics,
      ...(reportChannels === null ? {} : {channel_indices:reportChannels}),
      ...(hasWindow ? {events:count} : {}),
      ...(options.include_read_report ? {read_report:{source_sha256:sourceHash, dataset:options.dataset ?? 0,
        version:info.version, warnings:info.warnings}} : {})}, null, 2));
    return;
  }
  if (command === 'csv') {
    if (files.length !== 2) throw Error('csv needs input and output paths');
    const d = read(files[0]);
    const info = query(d, 'inspect');
    if (info.mode !== 'ListMode') throw Error('CSV event export requires list DATA; use histogram APIs');
    const channels = query(d, 'channel-indices', {channels:options.channels ?? info.channels.map((_, i) => i)});
    if (!Array.isArray(channels) || !channels.length || channels.some(i => !Number.isSafeInteger(i) || i < 0 || i >= info.channels.length)) throw Error('invalid CSV channels');
    const eventIndexColumn = options.event_index_column ?? null;
    if (eventIndexColumn !== null && (typeof eventIndexColumn !== 'string' || !eventIndexColumn.length || channels.some(i => info.channels[i].name === eventIndexColumn))) throw Error('CSV event_index_column must be a nonempty name distinct from selected data columns');
    let selected = null;
    if (Object.hasOwn(options, 'gates') || Object.hasOwn(options, 'population')) {
      // Output view flags are independent of the per-step gate views.
      const gateOptions = {...options, command:'gate'};
      delete gateOptions.scaled;
      delete gateOptions.compensated;
      selected = JSON.parse(api.query(d, JSON.stringify(gateOptions)));
    }
    const available = selected ? selected.length : info.events;
    const start = options.start ?? 0, count = options.count ?? available - start;
    if (!Number.isSafeInteger(start) || !Number.isSafeInteger(count) || start < 0 || count < 0 || start > available || count > available - start) throw Error('invalid CSV range');
    // Resolve every requested scaling path before creating the destination.
    if (count) query(d, 'values', {start:selected ? selected[start] : start,count:1,channels});
    const fd = fs.openSync(files[1], 'wx');
    try {
      const header = channels.map(i => csvCell(info.channels[i].name));
      if (eventIndexColumn !== null) header.unshift(csvCell(eventIndexColumn));
      fs.writeFileSync(fd, header.join(',') + '\r\n');
      const chunk = Math.max(1, Math.floor(100000 / (channels.length + (eventIndexColumn === null ? 0 : 1))));
      for (let at = start; at < start + count;) {
        const sourceAt = selected ? selected[at] : at;
        let take = Math.min(chunk, start + count - at);
        if (selected) {
          take = 1;
          while (take < chunk && at + take < start + count && selected[at + take] === sourceAt + take) take++;
        }
        const rows = query(d, 'values', {start:sourceAt, count:take, channels});
        fs.writeFileSync(fd, rows.map((row, i) => (eventIndexColumn === null ? row : [sourceAt + i, ...row]).join(',')).join('\r\n') + '\r\n');
        at += take;
      }
    } finally { fs.closeSync(fd); }
    console.log(JSON.stringify({written:files[1], events:count, scaled:!!options.scaled || !!options.compensated, compensated:!!options.compensated,
      ...(eventIndexColumn === null ? {} : {event_index_column:eventIndexColumn}),
      ...(selected ? {population:options.population, population_events:selected.length, source_event_indices:selected.slice(start,start + count)} : {})})); return;
  }
  if (!['inspect','validate','stats','metadata','values','gate','populations','histogram','histogram-axis','histogram-bin','compensation'].includes(command) || files.length !== 1) throw Error('invalid command/arguments; use --help');
  console.log(JSON.stringify(query(read(files[0]), command), null, 2));
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(e => { console.error(String(e.message ?? e)); process.exitCode = 1; });
}
