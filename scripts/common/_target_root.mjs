import fs from 'node:fs';
import path from 'node:path';

export function getTargetRoot(configFile = new URL('../../target-root.json', import.meta.url)) {
  let document;
  try {
    document = JSON.parse(fs.readFileSync(configFile, 'utf8').replace(/^\uFEFF/, ''));
  } catch (error) {
    throw new Error(`Cannot read target-root.json: ${error.message}`);
  }
  if (!document || Array.isArray(document) || typeof document !== 'object' ||
      Object.keys(document).length !== 1 || !Object.hasOwn(document, 'targetRoot')) {
    throw new Error('target-root.json must contain only the targetRoot field');
  }
  const value = document.targetRoot;
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error("Set targetRoot in target-root.json to the target project's absolute directory");
  }
  if (!path.isAbsolute(value)) throw new Error('targetRoot must be an absolute directory');
  if (!fs.existsSync(value) || !fs.statSync(value).isDirectory()) {
    throw new Error(`targetRoot directory does not exist: ${value}`);
  }
  return fs.realpathSync(value);
}
