// Original MIT external IO checkpoint driver. Production receives no test flags.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const real = Object.fromEntries(['openSync','writeFileSync','closeSync','linkSync','unlinkSync','renameSync','copyFileSync','statSync']
  .map(key => [key, fs[key].bind(fs)]));
const state = {platform:process.platform, node:process.version, events:[], receivers:[], staging:null, published:false, writes:0, closeFaultUsed:false, cleanupFaultUsed:false, forbidden:[]};
const target = path.resolve(config.target);
let outputFD = null;

function checkpoint(expectation, label) {
  const argv = [config.python, '-X', 'utf8', '-B', config.receiver, target, '--expected', expectation];
  const record = {recordedBeforeLaunchUTC:new Date().toISOString(), argv, cwd:process.cwd(),
    processEnv:Object.fromEntries(['TEMP','TMP','TMPDIR'].map(key => [key, process.env[key]]))};
  fs.appendFileSync(config.processLog, JSON.stringify(record)+'\n');
  const result = spawnSync(argv[0], argv.slice(1), {cwd:process.cwd(), env:process.env, encoding:'utf8', windowsHide:true});
  state.receivers.push({...record, label, status:result.status, stdout:result.stdout, stderr:result.stderr});
  if (result.status !== 0) throw Error('independent receiver failed at '+label+': '+result.stderr);
}
function ioError(code) { return Object.assign(new Error('external deterministic IO failure'), {code}); }
function currentExpectation() { return config.existing ? config.sentinelExpectation : config.absentExpectation; }

fs.openSync = function(file, flags, ...rest) {
  const resolved = path.resolve(String(file));
  const stage = path.dirname(resolved) === path.dirname(target) && path.basename(resolved).startsWith('.moonbit-fcs-csv-');
  const isOutput = flags === 'wx' && (stage || resolved === target);
  const fd = real.openSync(file, flags, ...rest);
  if (isOutput) {
    outputFD = fd;
    if (stage) state.staging = resolved;
    state.events.push({operation:'open', path:resolved, flags, mode:rest[0] ?? null});
  }
  return fd;
};
fs.writeFileSync = function(file, ...rest) {
  if (file !== outputFD) return real.writeFileSync(file, ...rest);
  state.writes++;
  state.events.push({operation:'before-write', number:state.writes});
  if (config.atomic) checkpoint(currentExpectation(), 'before-write-'+state.writes);
  if (config.failWriteAt === state.writes) throw ioError('EIO');
  const result = real.writeFileSync(file, ...rest);
  state.events.push({operation:'after-write', number:state.writes});
  if (config.atomic) checkpoint(currentExpectation(), 'after-write-'+state.writes);
  else if (config.baselinePrefix && state.writes === 1) checkpoint(config.prefixExpectation, 'default-final-name-after-header');
  return result;
};
fs.closeSync = function(fd) {
  if (fd !== outputFD) return real.closeSync(fd);
  if (config.failClose && !state.closeFaultUsed) {
    state.closeFaultUsed = true;
    state.events.push({operation:'injected-close-error', code:'EIO'});
    throw ioError('EIO');
  }
  const result = real.closeSync(fd);
  outputFD = null;
  state.events.push({operation:'closed'});
  if (config.atomic && !state.published) checkpoint(currentExpectation(), 'after-close-before-publish');
  return result;
};
fs.linkSync = function(from, to) {
  if (!config.atomic) return real.linkSync(from, to);
  state.events.push({operation:'before-link', from:String(from), to:String(to)});
  checkpoint(currentExpectation(), 'before-link');
  if (config.concurrent) {
    const sentinelFD = real.openSync(target, 'wx');
    try { real.writeFileSync(sentinelFD, config.sentinelBytes); } finally { real.closeSync(sentinelFD); }
    state.events.push({operation:'concurrent-target-created'});
    checkpoint(config.sentinelExpectation, 'concurrent-sentinel');
  }
  if (config.failLink) throw ioError('EOPNOTSUPP');
  const result = real.linkSync(from, to);
  state.published = true;
  const a = real.statSync(from, {bigint:true}), b = real.statSync(to, {bigint:true});
  state.events.push({operation:'published', sameInode:a.ino === b.ino && a.dev === b.dev,
    stagingInode:String(a.ino), targetInode:String(b.ino), device:String(a.dev), links:String(b.nlink)});
  try { state.filesystemType = String(fs.statfsSync(path.dirname(target), {bigint:true}).type); }
  catch { state.filesystemType = 'not exposed by this host'; }
  checkpoint(config.completeExpectation, 'after-publication');
  return result;
};
fs.unlinkSync = function(file) {
  if (path.resolve(String(file)) === target) {
    state.forbidden.push('unlink-caller-target');
    throw Error('production attempted to unlink caller target');
  }
  if (state.staging && path.resolve(String(file)) === state.staging) {
    state.events.push({operation:'cleanup-attempt', published:state.published});
    if ((config.failPostCleanup && state.published || config.failPreCleanup && !state.published) && !state.cleanupFaultUsed) {
      state.cleanupFaultUsed = true;
      throw ioError('EACCES');
    }
    const result = real.unlinkSync(file);
    state.events.push({operation:'staging-removed'});
    return result;
  }
  return real.unlinkSync(file);
};
for (const name of ['renameSync','copyFileSync']) fs[name] = function(...args) {
  state.forbidden.push(name);
  throw Error('atomic CSV used forbidden '+name);
};
process.on('exit', code => real.writeFileSync(config.trace, JSON.stringify({...state, exitCode:code}, null, 2)+'\n'));
process.argv = [process.execPath, config.cli, ...config.args];
await import(pathToFileURL(config.cli).href);
