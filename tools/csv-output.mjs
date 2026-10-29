import fs from 'node:fs';
import path from 'node:path';
import {randomUUID} from 'node:crypto';

function ioCode(error) {
  return typeof error?.code === 'string' && /^[A-Z0-9_]{1,40}$/.test(error.code) ? error.code : 'UNKNOWN';
}

// CSV-only optional publication. The link is the commit point; a caller target
// is never removed, replaced, or used as the incremental write destination.
export function publishCsv(file, render) {
  const target = path.resolve(file);
  const staging = path.join(path.dirname(target), `.moonbit-fcs-csv-${randomUUID()}.tmp`);
  let fd;
  let owned = false;
  let phase = 'staging';
  let failure = null;
  let cleanupFailure = null;
  try {
    fd = fs.openSync(staging, 'wx', 0o600);
    owned = true;
    phase = 'write';
    render(fd);
    phase = 'close';
    fs.closeSync(fd);
    fd = undefined;
    phase = 'publish';
    fs.linkSync(staging, target);
  } catch (error) {
    failure = error;
  }
  if (fd !== undefined) {
    // The original operation already failed. A close may have closed the fd
    // before reporting an error; retry best-effort and retain the fatal error.
    try { fs.closeSync(fd); } catch {}
  }
  if (owned) {
    try { fs.unlinkSync(staging); } catch (error) { cleanupFailure = error; }
  }
  if (failure) {
    let message = `atomic CSV ${phase} failed (${ioCode(failure)}); no output was published by this invocation.`;
    if (cleanupFailure) message += ` Owned staging cleanup is pending at ${staging} (${ioCode(cleanupFailure)}).`;
    throw Error(message);
  }
  if (cleanupFailure) {
    return {atomic_output:true, cleanupPending:true, stagingPath:staging,
      warning:`CSV published; staging cleanup is pending (${ioCode(cleanupFailure)}).`};
  }
  return {atomic_output:true, cleanupPending:false};
}
