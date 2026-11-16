#!/usr/bin/env node
/** Conservative source annotation. No course imports/configs are executed. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {addEditIds,reviewedFiles,ATTRIBUTE,parseSource} from '../common/edit_ids.mjs';
import {isMain} from '../common/_cli.mjs';

const ownRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const excluded = new Set(['node_modules', '.git', '.codex', '.shuku', '_scratchpad', 'shared', 'assets', 'vendor', 'dist', 'build', 'outputs', 'work', 'reference']);
// Reviewed local implementations + export entry points. Hashes normalize only
// UTF-8 BOM/CRLF. If any implementation/export changes, custom components stop
// being eligible until reviewed again. Native tags remain eligible.
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const readJSON = file => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));

function walk(node, visit) {
  if (!node || typeof node !== 'object') return;
  if (node.type) visit(node);
  for (const [key, value] of Object.entries(node)) {
    if (['loc', 'start', 'end', 'extra', 'tokens', 'comments'].includes(key)) continue;
    if (Array.isArray(value)) for (const child of value) walk(child, visit);
    else if (value && typeof value === 'object') walk(value, visit);
  }
}
function openings(ast) {
  const nodes = [];
  walk(ast, node => { if (node.type === 'JSXOpeningElement') nodes.push(node); });
  return nodes;
}
function existingAttribute(node) {
  return node.attributes.some(a => a.type === 'JSXAttribute' && a.name.type === 'JSXIdentifier' && a.name.name === ATTRIBUTE);
}
function literal(value) {
  if (value?.type === 'JSXExpressionContainer') value = value.expression;
  return value?.type === 'StringLiteral' ? value.value : undefined;
}
function within(base, file) {
  const relative = path.relative(base, file);
  return relative === '' || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative));
}
function closest(start, basename) {
  let dir = path.dirname(start);
  for (;;) {
    const candidate = path.join(dir, basename);
    if (fs.existsSync(candidate) && fs.lstatSync(candidate).isFile()) return candidate;
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}
const styleCache = new Map();
function reviewedStyleFor(file) {
  try {
    const outlinePath = closest(file, 'outlines.json');
    const catalogPath = closest(file, 'course-styles.json');
    if (!outlinePath || !catalogPath) return false;
    const outline = readJSON(outlinePath), catalog = readJSON(catalogPath);
    const id = outline.style_id || catalog.default_style;
    const entry = catalog.styles?.find(style => style.id === id);
    if (!entry || typeof entry.path !== 'string') return false;
    const repository = fs.realpathSync(path.dirname(catalogPath));
    const styleRoot = fs.realpathSync(path.resolve(repository, entry.path));
    if (!within(repository, styleRoot)) return false;
    if (!styleCache.has(styleRoot)) {
      let trusted = true;
      for (const [relative, expected] of Object.entries(reviewedFiles)) {
        const absolute = path.join(styleRoot, relative);
        if (fs.lstatSync(absolute).isSymbolicLink() || !within(styleRoot, fs.realpathSync(absolute))) { trusted = false; break; }
        const text = fs.readFileSync(absolute, 'utf8').replace(/^\uFEFF/, '').replaceAll('\r\n', '\n');
        if (hash(text) !== expected && !(relative === 'react/index.ts' && hash(text) === '1f0dab3af4f827ab568df38957fe79589c1a3e73867049b334fb3434d8e4404d')) { trusted = false; break; }
      }
      styleCache.set(styleRoot, trusted);
    }
    return styleCache.get(styleRoot) && readJSON(path.join(styleRoot, 'style.json')).id === id;
  } catch { return false; }
}
function collect(input, output, skipped) {
  const stat = fs.lstatSync(input);
  if (stat.isSymbolicLink()) { skipped.push({file: input, reason: 'symlink'}); return; }
  if (stat.isDirectory()) {
    if (excluded.has(path.basename(input).toLowerCase())) { skipped.push({file: input, reason: 'excluded-directory'}); return; }
    for (const entry of fs.readdirSync(input).sort()) collect(path.join(input, entry), output, skipped);
  } else if (stat.isFile() && /\.(?:tsx|jsx|ts|js)$/.test(input)) output.push(input);
}
function writeWithBackup(record, result, backupRoot, base) {
  const current = fs.lstatSync(record.file);
  if (!current.isFile() || current.isSymbolicLink() || current.nlink !== 1 || current.dev !== record.stat.dev || current.ino !== record.stat.ino || !fs.readFileSync(record.file).equals(record.raw)) throw Error('Source changed or is linked; refusing overwrite');
  fs.accessSync(record.file, fs.constants.W_OK);
  const relative = path.relative(base, record.file);
  if (!within(base, record.file)) throw Error('Backup path leaves target');
  const backup = path.join(backupRoot, relative);
  fs.mkdirSync(path.dirname(backup), {recursive: true});
  fs.writeFileSync(backup, record.raw, {flag: 'wx', mode: 0o600});
  const temporary = path.join(path.dirname(record.file), '.' + path.basename(record.file) + '.edit-id-' + crypto.randomUUID() + '.tmp');
  let fd;
  try {
    fd = fs.openSync(temporary, 'wx', record.stat.mode & 0o777);
    fs.writeFileSync(fd, Buffer.from(result.source, 'utf8')); fs.fsyncSync(fd); fs.closeSync(fd); fd = undefined;
    if (!fs.readFileSync(record.file).equals(record.raw)) throw Error('Source changed during preparation; refusing overwrite');
    fs.renameSync(temporary, record.file);
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
}

export function main(args = process.argv.slice(2)) {
if (args.includes('--help') || !args.length) {
  console.log('Usage: node scripts/module/add_edit_ids.mjs <file-or-directory> [--apply | --check] [--backup-dir <directory>]\nDefault: read-only dry run. --check fails on missing eligible IDs, invalid/duplicate IDs or unsafe native nodes. --apply adds IDs with backups; Shared stays read-only.');
  return 0;
}
const backupIndex = args.indexOf('--backup-dir');
const backupArgument = backupIndex < 0 ? null : args[backupIndex + 1];
if (backupIndex >= 0 && (!backupArgument || backupArgument.startsWith('--'))) { console.error('--backup-dir needs a directory'); return 2; }
const positional = args.filter((_, i) => i !== backupIndex && (backupIndex < 0 || i !== backupIndex + 1));
const unknown = positional.filter(a => a.startsWith('--') && !['--apply','--check'].includes(a));
const targets = positional.filter(a => !a.startsWith('--'));
if (unknown.length || targets.length !== 1) { console.error('Provide one target; use --apply or --check, optionally --backup-dir.'); return 2; }
const input = path.resolve(targets[0]), apply = args.includes('--apply');
const check = args.includes('--check');
if (check && apply) { console.error('--check and --apply are mutually exclusive'); return 2; }
if (!fs.existsSync(input) || fs.lstatSync(input).isSymbolicLink()) { console.error('Target must exist and must not be a symlink.'); return 2; }
const base = fs.lstatSync(input).isDirectory() ? input : path.dirname(input);
const report = {mode: apply ? 'apply' : check ? 'check' : 'dry-run', target: input, attribute: ATTRIBUTE, filesScanned: 0, filesWouldChange: 0, filesWritten: 0, idsPlanned: 0, idsWritten: 0, existingIdsKept: 0, blocked: [], idIssues: [], skipped: {}, excluded: [], samples: [], backup: null};
const candidates = [], records = [], reserved = new Set();
collect(input, candidates, report.excluded);
// First pass reserves existing literal IDs across the complete selected set.
for (const file of candidates) {
  try {
    if (file.split(path.sep).some(part => part.toLowerCase() === 'shared')) { report.excluded.push({file, reason: 'shared-source'}); continue; }
    const stat = fs.lstatSync(file);
    if (stat.nlink !== 1 || stat.size > 2 * 1024 * 1024) throw Error('Linked or larger than 2 MiB; skipped');
    const raw = fs.readFileSync(file), source = raw.toString('utf8');
    if (!Buffer.from(source, 'utf8').equals(raw)) throw Error('Not lossless UTF-8; skipped');
    const ast = parseSource(source);
    for (const node of openings(ast)) {
      const identities = node.attributes.filter(a => a.type === 'JSXAttribute' && a.name.name === ATTRIBUTE);
      if (identities.length > 1) report.idIssues.push({file, line: node.loc.start.line, reason: 'Duplicate ID attributes on one JSX node'});
      for (const [index, a] of node.attributes.entries()) if (a.type === 'JSXAttribute' && a.name.name === ATTRIBUTE) {
        const value = literal(a.value);
        if (typeof value !== 'string' || !value.trim() || reserved.has(value)) report.idIssues.push({file, line: node.loc.start.line, reason: 'ID must be a non-empty unique literal'});
        if (node.attributes.slice(index + 1).some(attribute => attribute.type === 'JSXSpreadAttribute')) report.idIssues.push({file, line: node.loc.start.line, reason: 'A later spread can override the ID; put the explicit literal after spreads'});
        if (value !== undefined) reserved.add(value);
      }
    }
    records.push({file, raw, stat}); report.filesScanned++;
  } catch (error) { report.blocked.push({file, reason: error.message}); }
}
const backupRoot = path.join(backupArgument ? path.resolve(backupArgument) : path.join(ownRoot, '_scratchpad', 'edit-id-backups'), new Date().toISOString().replaceAll(':', '-') + '-' + crypto.randomUUID());
if (report.idIssues.length || report.blocked.length) { console.log(JSON.stringify(report, null, 2)); return 1; }
for (const record of records) {
  try {
    const source = record.raw.toString('utf8');
    const result = addEditIds(source, {trustedStyle:reviewedStyleFor(record.file),reserved});
    report.existingIdsKept += result.kept;
    for (const [reason, count] of Object.entries(result.skipped)) report.skipped[reason] = (report.skipped[reason] || 0) + count;
    if (!result.edits.length) continue;
    report.filesWouldChange++; report.idsPlanned += result.edits.length;
    if (apply) { writeWithBackup(record, result, backupRoot, base); report.backup = backupRoot; report.filesWritten++; report.idsWritten += result.edits.length; }
    if (report.samples.length < 6) report.samples.push({file: record.file, added: result.edits.length, examples: result.edits.slice(0, 3).map(({tag, line, id}) => ({tag, line, id}))});
  } catch (error) { report.blocked.push({file: record.file, reason: error.message}); }
}
if (report.backup) {
  try { fs.writeFileSync(path.join(backupRoot, 'manifest.json'), JSON.stringify({target: input, attribute: ATTRIBUTE, files: records.filter(r => fs.existsSync(path.join(backupRoot, path.relative(base, r.file)))).map(r => ({path: path.relative(base, r.file), originalSha256: hash(r.raw)}))}, null, 2), {flag: 'wx'}); }
  catch (error) { report.blocked.push({file: backupRoot, reason: 'Backup manifest: ' + error.message}); }
}
console.log(JSON.stringify(report, null, 2));
if (report.blocked.length || report.idIssues.length || check && (report.idsPlanned || Object.entries(report.skipped).some(([kind,count]) => count && ['spread-props','jsx-pragma','dynamic-or-custom-as'].includes(kind)))) return 1;
return 0;
}
if (isMain(import.meta.url)) process.exitCode = main();
