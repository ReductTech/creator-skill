/** Course discovery shared by Node tools; importing this file reads no project. */
const fs = require('node:fs');
const path = require('node:path');

function outlines(directory) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, {withFileTypes: true})
    .filter(entry => entry.isDirectory() && fs.existsSync(path.join(directory, entry.name, 'outlines.json')))
    .map(entry => path.join(directory, entry.name, 'outlines.json')).sort();
}

function modulesDirectory(root) {
  root = path.resolve(root);
  const nested = path.join(root, 'modules');
  if (fs.existsSync(nested)) {
    if (!fs.statSync(nested).isDirectory()) throw Error('Course modules path is not a directory');
    if (outlines(root).length) throw Error('Mixed flat and modules/ course layouts; select one source root');
    const resolved = fs.realpathSync(nested);
    if (!resolved.startsWith(fs.realpathSync(root) + path.sep)) throw Error('Course modules directory leaves targetRoot');
    return nested;
  }
  return outlines(root).length ? root : nested;
}

function resolveModule(root, requested) {
  const matches = outlines(modulesDirectory(root)).filter(file => {
    const doc = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
    return [path.basename(path.dirname(file)), doc.id, doc.alias, doc.moduleIdentity?.id]
      .some(value => typeof value === 'string' && value.toLowerCase() === requested.toLowerCase());
  });
  if (matches.length !== 1) throw Error(`Expected one module matching ${requested}; found ${matches.length}`);
  return path.dirname(matches[0]);
}

exports.modulesDirectory = modulesDirectory;
exports.resolveModule = resolveModule;
