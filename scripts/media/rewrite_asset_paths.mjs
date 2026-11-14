/** Rewrite existing course asset references; never compress, rename or delete assets.
 * Reads: one configured course, an explicit change list or existing target files.
 * Writes: --apply changes source text only, with backups and a checked transaction.
 * JavaScript is parsed, never executed. Dynamic families must have complete coverage.
 */
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {emitResult, isMain, parseOptions, printHelp, reportError} from '../common/_cli.mjs';
import {getTargetRoot} from '../common/_target_root.mjs';
import coursePaths from '../common/_course_paths.cjs';

const SKILL = fileURLToPath(new URL('../..', import.meta.url));
const SKIP = new Set(['.git', 'node_modules', 'dist', 'vendor', '_scratchpad', 'shared']);
const SOURCE = /\.(?:[cm]?[jt]sx?|json|gltf|css|html?|md)$/i;
const CODE = /\.[cm]?[jt]sx?$/i;
const SLOT = /\u0000(\d+)\u0000/g;
const slash = value => value.replaceAll('\\', '/');
const inside = (base, file) => file === base || (!path.relative(base, file).startsWith('..' + path.sep) && path.relative(base, file) !== '..' && !path.isAbsolute(path.relative(base, file)));
const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function buildParser() {
  return {
    module: {type: 'string', description: 'required course UUID, directory or alias'},
    changes: {type: 'string', description: 'JSON path relative to targetRoot or absolute; conversion report, rows or old:new object'},
    'to-ext': {type: 'string', description: 'discover replacements from existing targets, e.g. webp; exclusive with --changes'},
    'from-ext': {type: 'string', default: 'png,jpg,jpeg', description: 'comma-separated source extensions for --to-ext'},
    apply: {type: 'boolean', default: false, description: 'write only when the complete plan has no unresolved references'},
    'dry-run': {type: 'boolean', default: false, description: 'explicit read-only preview (the default)'},
    report: {type: 'string', description: 'optional JSON result inside this course _scratchpad; written only with --apply'},
    help: {type: 'boolean', short: 'h', description: 'show help without loading TypeScript or project configuration'},
  };
}

function linked(file) {
  const info = fs.lstatSync(file);
  return info.isSymbolicLink() || Boolean(info.isDirectory() && fs.realpathSync(file).toLowerCase() !== path.resolve(file).toLowerCase());
}

function checked(base, file, mustExist = true) {
  file = path.resolve(file);
  if (!inside(base, file)) throw Error('Path leaves selected scope: ' + file);
  for (let current = file; inside(base, current); current = path.dirname(current)) {
    if (fs.existsSync(current) && (linked(current) || !inside(base, fs.realpathSync(current)))) throw Error('Linked path is not allowed: ' + current);
    if (current === base) break;
  }
  if (mustExist && !fs.statSync(file).isFile()) throw Error('Expected an existing file: ' + file);
  return file;
}

function walk(base, directories = true) {
  const files = [];
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, {withFileTypes: true})) {
      const file = path.join(directory, entry.name);
      if (linked(file)) continue;
      if (entry.isDirectory()) { if (!directories || !SKIP.has(entry.name)) visit(file); }
      else if (entry.isFile()) files.push(file);
    }
  }
  visit(base);
  return files.sort();
}

export function loadTypeScript(root = SKILL) {
  for (const directory of [root, path.join(SKILL, 'player-preview'), process.env.SHUKU_ROOT].filter(Boolean)) {
    try { return createRequire(path.join(directory, 'package.json'))('typescript'); } catch { /* Try the next documented dependency location. */ }
  }
  throw Error('TypeScript is required; install Player Preview dependencies with npm ci in creator-skill/player-preview.');
}

function readChanges(args, root, assets, inventory) {
  if (Boolean(args.changes) === Boolean(args['to-ext'])) throw Error('Provide exactly one of --changes or --to-ext');
  const changes = new Map();
  function assetPath(value, target) {
    if (typeof value !== 'string' || !value || /[?#\u0000]/.test(value)) throw Error('Change paths must be non-empty file paths without query or fragment');
    const file = checked(assets, path.isAbsolute(value) ? value : path.join(assets, value), target);
    return slash(path.relative(assets, file));
  }
  function add(source, target) {
    const old = assetPath(source, false), next = assetPath(target, true);
    if (old === next) return;
    if (changes.has(old) && changes.get(old) !== next) throw Error('Conflicting replacements for ' + old);
    changes.set(old, next);
  }
  if (args.changes) {
    const document = JSON.parse(fs.readFileSync(path.resolve(root, args.changes), 'utf8').replace(/^\uFEFF/, ''));
    const rows = Array.isArray(document) ? document : document.images ?? document.changes;
    if (rows !== undefined) {
      if (!Array.isArray(rows)) throw Error('Change list must be an array');
      for (const row of rows) {
        if (!row || typeof row !== 'object') throw Error('Invalid change row');
        if (row.status && row.status !== 'converted') continue;
        add(row.source ?? row.from, row.target ?? row.to);
      }
    } else if (document && typeof document === 'object') {
      for (const [old, next] of Object.entries(document)) add(old, next);
    } else throw Error('Expected a JSON object or array');
  } else {
    const normalize = ext => {
      ext = ext.replace(/^\./, '').toLowerCase();
      if (!/^[a-z0-9]+$/.test(ext)) throw Error('Invalid extension: ' + ext);
      return '.' + ext;
    };
    const next = normalize(args['to-ext']);
    const old = args['from-ext'].split(',').map(normalize).filter(ext => ext !== next);
    for (const file of inventory) if (path.extname(file).toLowerCase() === next) {
      for (const ext of old) add(file.slice(0, -next.length) + ext, file);
    }
  }
  // Chains cannot be resolved by a second pass without changing their meaning.
  for (const target of changes.values()) if (changes.has(target)) throw Error('Chained replacements are not supported: ' + target);
  return changes;
}

function patternRegex(pattern) {
  const tokens = pattern.split(/(\u0000\d+\u0000|\*\*\/|\*\*|\*)/);
  return new RegExp('^' + tokens.map(token => token === '**/' ? '(?:.*/)?' : /^\u0000\d+\u0000$/.test(token) || token === '**' ? '.*?' : token === '*' ? '[^/]*' : escape(token)).join('') + '$');
}

/** Plan text changes against a closed inventory; unmatched dynamic families block writes. */
export function planReferences({course, changes, ts}) {
  const assets = path.join(course, 'assets');
  const inventory = walk(assets).map(file => slash(path.relative(assets, file)));
  const known = [...new Set([...inventory, ...changes.keys()])];
  const files = walk(course).filter(file => SOURCE.test(file));
  const originals = new Map(files.map(file => [file, fs.readFileSync(file, 'utf8')]));
  const sourceFiles = new Map([...originals].filter(([file]) => CODE.test(file)).map(([file, text]) => [file, ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true)]));
  const canonical = file => process.platform === 'win32' ? slash(path.resolve(file)).toLowerCase() : path.resolve(file);
  const byName = new Map([...sourceFiles].map(([file, source]) => [canonical(file), source]));
  const host = {...ts.createCompilerHost({}), getSourceFile: file => byName.get(canonical(file)), fileExists: file => byName.has(canonical(file)), readFile: file => byName.get(canonical(file))?.text};
  const program = ts.createProgram([...sourceFiles.keys()], {allowJs: true, noResolve: true, noLib: true}, host);
  const checker = program.getTypeChecker();
  const edits = new Map(), unresolved = [], unverified = [], matches = [];
  const diagnostic = (file, start, kind, expression, detail) => {
    const text = originals.get(file);
    unresolved.push({file: slash(path.relative(course, file)), line: text.slice(0, start).split('\n').length, kind, expression, detail});
  };

  function replacement(pattern, file, start, disk = false) {
    const dynamic = /\u0000\d+\u0000|\*/.test(pattern);
    if (/^(?:[a-z][a-z\d+.-]*:|\/\/|#)/i.test(pattern) && !path.isAbsolute(pattern)) return null;
    const split = pattern.search(/[?#]/), suffix = split < 0 ? '' : pattern.slice(split);
    const clean = split < 0 ? pattern : pattern.slice(0, split);
    if (!clean || /\s/.test(clean) && !known.some(name => clean.endsWith(name))) return null;
    if (dynamic && !/\.[a-z\d]+$/i.test(clean) && !(/\.\u0000\d+\u0000$/.test(clean) && known.some(name => clean.startsWith(path.posix.dirname(name) + '/')))) return null;
    let relative = clean, prefix = '', mode = 'asset';
    if (disk || clean.startsWith('../') || path.isAbsolute(clean) && inside(assets, path.resolve(clean))) {
      const absolute = path.resolve(path.dirname(file), clean);
      if (!inside(assets, absolute)) return null;
      relative = slash(path.relative(assets, absolute)); mode = 'disk';
    } else {
      const marker = clean.lastIndexOf('/assets/');
      const idPrefix = '/' + path.basename(course) + '/';
      if (marker >= 0) { prefix = clean.slice(0, marker + 8); relative = clean.slice(marker + 8); }
      else if (clean.startsWith('assets/')) { prefix = 'assets/'; relative = clean.slice(7); }
      else if (clean.startsWith(idPrefix)) { prefix = idPrefix; relative = clean.slice(idPrefix.length); }
      else if (clean.startsWith('./')) { prefix = './'; relative = clean.slice(2); }
      else if (clean.startsWith('/')) return null;
    }
    // An unknown URL/directory base may be remote or select another asset root.
    if (/^\u0000\d+\u0000\//.test(relative)) {
      if (known.some(name => relative.includes(path.extname(name)))) diagnostic(file, start, 'unknown-base', pattern, 'Resolve the base directory before rewriting this expression');
      return null;
    }
    const regex = patternRegex(relative);
    let candidates = known.filter(name => regex.test(name));
    if (!candidates.length && mode !== 'disk') {
      const ending = new RegExp('(?:^|/)' + regex.source.slice(1));
      candidates = known.filter(name => ending.test(name)); mode = 'suffix';
    }
    const selected = candidates.filter(name => changes.has(name));
    if (!selected.length) return null;
    if (selected.length !== candidates.length) {
      diagnostic(file, start, dynamic ? 'partial-family' : 'ambiguous-path', pattern, {mapped: selected, unmapped: candidates.filter(name => !changes.has(name))});
      return null;
    }
    if (!dynamic && candidates.length > 1) {
      diagnostic(file, start, 'ambiguous-path', pattern, candidates); return null;
    }
    let next;
    if (dynamic) {
      const ext = path.posix.extname(relative);
      const extensions = [...new Set(selected.map(name => path.posix.extname(changes.get(name))))];
      if (!ext || /\u0000|\*/.test(ext) || extensions.length !== 1 || selected.some(name => name.slice(0, -path.posix.extname(name).length) !== changes.get(name).slice(0, -extensions[0].length))) {
        diagnostic(file, start, 'unsupported-dynamic-rename', pattern, 'Dynamic migration requires fixed extensions and unchanged asset stems/directories'); return null;
      }
      next = clean.slice(0, -ext.length) + extensions[0];
    } else {
      const old = selected[0], target = changes.get(old);
      if (mode === 'disk') {
        next = slash(path.relative(path.dirname(file), path.join(assets, target)));
        if (clean.startsWith('./') && !next.startsWith('.')) next = './' + next;
      } else if (mode === 'suffix') {
        const base = old.slice(0, old.length - relative.length);
        if (!target.startsWith(base)) { diagnostic(file, start, 'hidden-directory-change', pattern, target); return null; }
        next = prefix + target.slice(base.length);
      } else next = prefix + target;
    }
    if (next + suffix === pattern) return null;
    matches.push({file: slash(path.relative(course, file)), line: originals.get(file).slice(0, start).split('\n').length, before: pattern.replace(SLOT, '${…}'), after: (next + suffix).replace(SLOT, '${…}'), assets: selected});
    return next + suffix;
  }

  function add(file, start, end, value) {
    const list = edits.get(file) ?? [];
    if (list.some(edit => start < edit.end && end > edit.start)) throw Error('Overlapping source edits in ' + file);
    list.push({start, end, value}); edits.set(file, list);
  }

  for (const [file, source] of sourceFiles) {
    if (source.parseDiagnostics.length) throw Error('Cannot parse source: ' + file + ': ' + ts.flattenDiagnosticMessageText(source.parseDiagnostics[0].messageText, '\n'));
    function evaluate(node, seen = new Set()) {
      if (!node) return null;
      if (ts.isStringLiteralLike(node)) return [{text: node.text, string: true}];
      if (ts.isNumericLiteral(node)) return [{text: node.text}];
      if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isTypeAssertionExpression(node) || ts.isNonNullExpression(node) || ts.isSatisfiesExpression(node)) return evaluate(node.expression, seen);
      if (ts.isIdentifier(node)) {
        const declaration = checker.getSymbolAtLocation(node)?.valueDeclaration;
        if (declaration && ts.isVariableDeclaration(declaration) && ts.isIdentifier(declaration.name) && declaration.initializer && declaration.parent.flags & ts.NodeFlags.Const && !seen.has(declaration)) {
          const value = evaluate(declaration.initializer, new Set([...seen, declaration]));
          // Inline immutable string constants only; never duplicate a function call.
          if (value && value.every(term => term.text !== undefined)) return value;
        }
        return [{code: node.getText(source)}];
      }
      if (ts.isTemplateExpression(node)) {
        const terms = [{text: node.head.text, string: true}];
        for (const span of node.templateSpans) terms.push(...(evaluate(span.expression, seen) ?? [{code: span.expression.getText(source)}]), {text: span.literal.text});
        return terms;
      }
      if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
        if (ts.isNumericLiteral(node.left) && ts.isNumericLiteral(node.right)) return [{text: String(Number(node.left.text) + Number(node.right.text))}];
        const left = evaluate(node.left, seen), right = evaluate(node.right, seen);
        if (![...(left ?? []), ...(right ?? [])].some(term => term.string)) return null;
        return [...(left ?? [{code: node.left.getText(source)}]), ...(right ?? [{code: node.right.getText(source)}])];
      }
      if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) {
        const receiver = node.expression.expression, name = node.expression.name.text;
        if (name === 'concat') {
          const initial = evaluate(receiver, seen);
          if (!initial?.some(term => term.string)) return null;
          return [...initial, ...node.arguments.flatMap(arg => evaluate(arg, seen) ?? [{code: arg.getText(source)}])];
        }
        const array = name === 'join' && ts.isArrayLiteralExpression(receiver) ? receiver.elements : null;
        const pathJoin = /^(?:path\.)?(?:posix\.)?join$/.test(node.expression.getText(source));
        if (array || pathJoin) {
          const values = array ?? node.arguments;
          const separator = array ? node.arguments[0] ? evaluate(node.arguments[0], seen) : [{text: ','}] : [{text: '/'}];
          if (!separator?.every(term => term.text !== undefined)) return null;
          const terms = [{text: '', string: true}];
          values.forEach((value, index) => { if (index) terms.push(...separator); terms.push(...(evaluate(value, seen) ?? [{code: value.getText(source)}])); });
          return terms;
        }
      }
      return null;
    }

    const expression = node => ts.isStringLiteralLike(node) || ts.isTemplateExpression(node) || ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken || ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && ['concat', 'join'].includes(node.expression.name.text);
    function visit(node) {
      if (ts.isCallExpression(node) && node.expression.getText(source) === 'moduleAssetUrl' && node.arguments[0]) {
        const terms = evaluate(node.arguments[0]);
        if (!terms || terms.some(term => term.code) && !/\.[a-z\d]+(?:$|[?#])/i.test(terms.map(term => term.text ?? '${…}').join(''))) {
          unverified.push({file: slash(path.relative(course, file)), line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1,
            expression: node.getText(source), reason: 'Runtime-computed asset path: inspect its callers/data; no arbitrary functions are executed'});
        }
      }
      if (ts.isJsxAttribute(node) && node.name.getText(source).toLowerCase() === 'srcset' && node.initializer && ts.isStringLiteral(node.initializer)) {
        const value = node.initializer.text, replacements = [];
        for (const item of value.matchAll(/(?:^|,)\s*([^\s,]+)/g)) {
          const start = item.index + item[0].indexOf(item[1]);
          const next = replacement(item[1], file, node.initializer.getStart(source) + 1 + start);
          if (next !== null) replacements.push({start, end: start + item[1].length, value: next});
        }
        let next = value;
        for (const item of replacements.reverse()) next = next.slice(0, item.start) + item.value + next.slice(item.end);
        if (replacements.length) add(file, node.initializer.getStart(source), node.initializer.end, JSON.stringify(next));
        return;
      }
      if (expression(node)) {
        const terms = evaluate(node);
        if (terms) {
          const unknown = [];
          const pattern = terms.map(term => term.text !== undefined ? term.text : `\u0000${unknown.push(term.code) - 1}\u0000`).join('');
          const parent = node.parent;
          const disk = Boolean((ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent)) && parent.moduleSpecifier === node || (ts.isCallExpression(parent) || ts.isNewExpression(parent)) && ['require', 'import', 'URL'].includes(parent.expression.getText(source)) && parent.arguments?.[0] === node);
          const findings = unresolved.length;
          const next = replacement(pattern, file, node.getStart(source), disk);
          if (next !== null) {
            const literal = unknown.length ? '`' + next.split(/(\u0000\d+\u0000)/).map(part => /^\u0000\d+\u0000$/.test(part) ? '${' + unknown[Number(part.slice(1, -1))] + '}' : part.replaceAll('\\', '\\\\').replaceAll('`', '\\`').replaceAll('${', '\\${').replaceAll('\r', '\\r').replaceAll('\n', '\\n')).join('') + '`' : JSON.stringify(next);
            add(file, node.getStart(source), node.end, literal); return;
          }
          // Do not rewrite a fragment of a dynamic family that failed its coverage check.
          if (unresolved.length !== findings) return;
          // A local-looking suffix of a composed remote URL or prose is not a local reference.
          if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(pattern) && !inside(assets, path.resolve(pattern))) return;
          if (/\s/.test(pattern) && !/\burl\(/i.test(pattern)) return;
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
  }

  for (const [file, text] of originals) {
    if (CODE.test(file)) continue;
    const extension = path.extname(file).toLowerCase();
    const masked = text.replace(/\/\*[\s\S]*?\*\/|<!--[\s\S]*?-->/g, match => ' '.repeat(match.length));
    function literal(start, value, encode = next => next, disk = false) {
      const next = replacement(value, file, start, disk);
      if (next !== null) add(file, start, start + value.length, encode(next));
    }
    if (['.json', '.gltf'].includes(extension)) {
      JSON.parse(text.replace(/^\uFEFF/, ''));
      for (const match of text.matchAll(/"(?:[^"\\]|\\.)*"/g)) {
        const value = JSON.parse(match[0]), next = replacement(value, file, match.index);
        if (next !== null) add(file, match.index, match.index + match[0].length, JSON.stringify(next));
      }
    } else if (extension === '.md') {
      const markdown = masked.replace(/```[\s\S]*?```|~~~[\s\S]*?~~~/g, match => ' '.repeat(match.length));
      for (const match of markdown.matchAll(/!?\[[^\]\n]*\]\(<?([^\s)>]+)>?(?:\s+"[^"]*")?\)/g)) literal(match.index + match[0].indexOf(match[1]), match[1], undefined, match[1].startsWith('.'));
    } else {
      for (const match of masked.matchAll(/url\(\s*(?:(["'])(.*?)\1|([^\s)]+))\s*\)/gi)) {
        const value = match[2] ?? match[3]; literal(match.index + match[0].indexOf(value), value, undefined, value.startsWith('.'));
      }
      if (extension !== '.css') {
        for (const match of masked.matchAll(/\b(?:src|href|poster|srcset)\s*=\s*(["'])(.*?)\1/gi)) {
          const offset = match.index + match[0].indexOf(match[2]);
          if (/^srcset/i.test(match[0])) {
            for (const item of match[2].matchAll(/(?:^|,)\s*([^\s,]+)/g)) literal(offset + item.index + item[0].indexOf(item[1]), item[1], undefined, item[1].startsWith('.'));
          } else literal(offset, match[2], undefined, match[2].startsWith('.'));
        }
      }
    }
  }
  const updates = [...edits].map(([file, list]) => {
    let after = originals.get(file);
    for (const edit of list.sort((a, b) => b.start - a.start)) after = after.slice(0, edit.start) + edit.value + after.slice(edit.end);
    if (CODE.test(file)) {
      const parsed = ts.createSourceFile(file, after, ts.ScriptTarget.Latest, true);
      if (parsed.parseDiagnostics.length) throw Error('Rewrite would produce invalid syntax: ' + file);
    }
    return {file, before: originals.get(file), after, references: list.length};
  });
  return {updates, unresolved, unverified, matches};
}

export function applyPlan(course, updates) {
  if (!updates.length) return null;
  const backup = checked(course, path.join(course, '_scratchpad/asset-paths', randomUUID()), false);
  const staged = [], written = [];
  try {
    for (const item of updates) {
      checked(course, item.file);
      if (fs.readFileSync(item.file, 'utf8') !== item.before) throw Error('Source changed while planning: ' + item.file);
      const saved = checked(course, path.join(backup, path.relative(course, item.file)), false);
      fs.mkdirSync(path.dirname(saved), {recursive: true}); fs.writeFileSync(saved, item.before, {flag: 'wx'});
      const temporary = item.file + '.rewrite-' + randomUUID();
      fs.writeFileSync(temporary, item.after, {flag: 'wx', mode: fs.statSync(item.file).mode}); staged.push({...item, temporary});
    }
    for (const item of staged) {
      checked(course, item.file);
      if (fs.readFileSync(item.file, 'utf8') !== item.before) throw Error('Source changed before writing: ' + item.file);
      fs.renameSync(item.temporary, item.file); written.push(item);
    }
  } catch (error) {
    for (const item of written.reverse()) fs.writeFileSync(item.file, item.before);
    throw error;
  } finally {
    for (const item of staged) if (fs.existsSync(item.temporary)) fs.unlinkSync(item.temporary);
  }
  return backup;
}

export async function runTask(args) {
  if (!args.module) throw Error('--module is required');
  if (args.apply && args['dry-run']) throw Error('--apply and --dry-run are mutually exclusive');
  const root = getTargetRoot(), course = coursePaths.resolveModule(root, args.module);
  if (path.basename(course).toLowerCase() === 'shared') throw Error('Shared is read-only');
  checked(root, course, false);
  const assets = checked(course, path.join(course, 'assets'), false);
  if (!fs.statSync(assets).isDirectory()) throw Error('Course assets directory is missing');
  const report = args.report ? checked(path.join(course, '_scratchpad'), path.resolve(root, args.report), false) : null;
  const inventory = walk(assets).map(file => slash(path.relative(assets, file)));
  const changes = readChanges(args, root, assets, inventory);
  const {updates, unresolved, unverified, matches} = planReferences({course, changes, ts: loadTypeScript(root)});
  const result = {
    status: unresolved.length ? 'failed' : args.apply ? 'ok' : 'dry-run',
    course, mode: args.apply ? 'apply' : 'dry-run', mappings: changes.size,
    changedFiles: updates.map(item => ({file: slash(path.relative(course, item.file)), references: item.references})),
    referenceCount: matches.length, unresolved, unverified, matches, applied: false,
    coverage: 'Static syntax and known local asset families only; runtime code is never executed.',
  };
  if (args.apply && !unresolved.length) {
    result.backupDirectory = applyPlan(course, updates); result.applied = true;
    if (report) { checked(course, report, false); fs.mkdirSync(path.dirname(report), {recursive: true}); fs.writeFileSync(report, JSON.stringify(result, null, 2) + '\n'); }
  }
  return result;
}

export async function main(argv = process.argv.slice(2)) {
  try {
    const options = buildParser(), args = parseOptions(argv, options);
    if (args.help) { printHelp('usage: assets.rewrite --module <UUID|alias> (--changes <JSON> | --to-ext webp) [--apply]\nRewrite references only; default is read-only.', options); return 0; }
    const result = await runTask(args); emitResult(result); return result.status === 'failed' ? 1 : 0;
  } catch (error) { return reportError(error); }
}

if (isMain(import.meta.url)) process.exitCode = await main();
