import path from 'node:path';
import { createHash } from 'node:crypto';

const parseKeys = ['dataset','strict','allow_exclusive_end','latin1','allow_text_padding','allow_offset_padding'];
const header = ['sample','source_file','source_sha256','dataset','source_version','read_warnings',
  'population','parent','count','parent_count','total_count','parent_fraction','total_fraction'];
const textColumns = new Set([0,1,2,4,5,6,7]);
const quote = value => '"' + String(value).replaceAll('"','""') + '"';
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);

function rejectUnknown(object, allowed, kind) {
  for (const key of Object.keys(object)) if (!allowed.includes(key)) throw Error(`unsupported ${kind} key: ${key}`);
}

function readOptions(options) {
  const result = {};
  for (const key of parseKeys) if (Object.hasOwn(options,key)) {
    const value = options[key];
    if (key === 'dataset') {
      if (!Number.isSafeInteger(value) || value < 0 || value > 2147483647) throw Error('dataset must be a nonnegative exact 32-bit integer');
    } else if (typeof value !== 'boolean') throw Error(`${key} must be boolean`);
    result[key] = value;
  }
  return result;
}

// Host roster/report composition only. Every scientific result comes from the
// existing MoonBit populations query; member arrays are released per sample.
export function collectPopulationReport(manifestPath, options, api, input) {
  rejectUnknown(options, ['gates',...parseKeys], 'population-report option');
  if (!Array.isArray(options.gates) || !options.gates.length) throw Error('population-report requires a nonempty gates array');
  const defaults = readOptions(options);
  const manifest = JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(input(manifestPath)));
  if (!isObject(manifest)) throw Error('population-report manifest must be an object');
  rejectUnknown(manifest,['samples'],'manifest');
  if (!Array.isArray(manifest.samples) || !manifest.samples.length) throw Error('manifest requires a nonempty samples array');
  const names = new Set();
  const samples = manifest.samples.map(entry => {
    if (!isObject(entry)) throw Error('sample entry must be an object');
    rejectUnknown(entry,['sample','file',...parseKeys],'sample');
    if (typeof entry.sample !== 'string' || !entry.sample.length) throw Error('sample entry requires a nonempty sample string');
    if (names.has(entry.sample)) throw Error('sample IDs must be unique: '+entry.sample);
    names.add(entry.sample);
    if (typeof entry.file !== 'string' || !entry.file.length) throw Error('sample entry requires a nonempty file string');
    return {sample:entry.sample,file:entry.file,options:{...defaults,...readOptions(entry)}};
  });
  const directory = path.dirname(path.resolve(manifestPath));
  const lines = [header.map(quote).join(',')];
  let rows = 0;
  for (const sample of samples) {
    try {
      const source = input(path.resolve(directory,sample.file));
      const sourceHash = createHash('sha256').update(source).digest('hex');
      const dataset = api.load(source,JSON.stringify(sample.options));
      const info = JSON.parse(api.query(dataset,JSON.stringify({command:'inspect'})));
      const populations = JSON.parse(api.query(dataset,JSON.stringify({command:'populations',gates:options.gates})));
      for (const population of populations) {
        const values = [sample.sample,sample.file,sourceHash,sample.options.dataset ?? 0,info.version,JSON.stringify(info.warnings),
          population.id,population.parent ?? '',population.count,population.parent_count,population.total_count,
          population.parent_fraction ?? '',population.total_fraction ?? ''];
        lines.push(values.map((value,index) => textColumns.has(index) ? quote(value) : String(value)).join(','));
        rows++;
      }
    } catch (error) {
      throw Error(`sample ${JSON.stringify(sample.sample)}: ${error.message ?? error}`);
    }
  }
  // All sources and gate plans must succeed before the CLI creates output.
  return {csv:Buffer.from(lines.join('\r\n')+'\r\n','utf8'),samples:samples.length,rows};
}
