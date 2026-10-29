import { createHash } from 'node:crypto';

const readKeys = ['strict','allow_exclusive_end','latin1','allow_text_padding','allow_offset_padding'];
const sha = bytes => createHash('sha256').update(bytes).digest('hex');

// Compose existing native read/rewrite operations. The caller creates no output
// directory until this whole plan, including every rewrite, has succeeded.
export function prepareDatasetExtraction(source, options, api) {
  for (const key of Object.keys(options)) {
    if (!readKeys.includes(key)) throw Error(`unsupported extract-datasets option: ${key}`);
    if (typeof options[key] !== 'boolean') throw Error(`${key} must be boolean`);
  }
  const files = [], datasets = [];
  let dataset = 0, sourceOffset = 0;
  while (true) {
    const parsed = api.load(source,JSON.stringify({...options,dataset}));
    const info = JSON.parse(api.query(parsed,JSON.stringify({command:'inspect'})));
    const bytes = Buffer.from(api.transform(source,JSON.stringify({...options,dataset,command:'rewrite'})));
    const file = `dataset-${String(dataset).padStart(6,'0')}.fcs`;
    files.push({file,bytes});
    datasets.push({dataset,source_offset:sourceOffset,source_version:info.version,source_mode:info.mode,
      source_events:info.events,source_warnings:info.warnings,file,bytes:bytes.length,sha256:sha(bytes)});
    if (info.next_offset === 0) break;
    sourceOffset += info.next_offset;
    dataset++;
  }
  return {source_sha256:sha(source),datasets,files};
}
