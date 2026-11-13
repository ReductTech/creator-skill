import fs from 'node:fs';
import path from 'node:path';

export function readCourses(root) {
  return fs.readdirSync(root, {withFileTypes: true}).flatMap(item => {
    if (!item.isDirectory() || !/^[a-f0-9-]{36}$/.test(item.name)) return [];
    const directory = path.join(root, item.name);
    const file = path.join(directory, 'outlines.json');
    if (!fs.existsSync(file)) return [];
    const outline = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
    for (const entry of [outline.entry, outline.ppt?.entry].filter(Boolean)) {
      const resolved = path.resolve(directory, entry);
      if (!resolved.startsWith(directory + path.sep)) throw Error('课程入口越界：' + entry);
    }
    return [{...outline, id: item.name, directory, assetId: outline.moduleIdentity?.id || item.name}];
  }).sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'));
}

// Match the platform builder's named-export convention.
export function entryExport(course, entry) {
  return path.basename(entry, path.extname(entry));
}
