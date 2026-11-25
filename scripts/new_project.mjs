import {randomUUID} from 'node:crypto';
import {cp, mkdir, readFile, readdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const [requested, ...extra] = process.argv.slice(2);
if (!requested || extra.length) throw new Error('用法：npm run new -- <新工程目录>');
const project = path.resolve(requested);
const starter = fileURLToPath(new URL('../starter/', import.meta.url));
const starters = await readdir(path.join(starter, 'modules'), {withFileTypes: true});
const [starterId] = starters.filter(item => item.isDirectory()).map(item => item.name);
const source = path.join(starter, 'modules', starterId);
const outline = JSON.parse(await readFile(path.join(source, 'outlines.json'), 'utf8'));
const id = randomUUID();
outline.id = id;
outline.moduleIdentity.id = id;
outline.path = '/modules/' + id;
for (const page of outline.pages) page.id = randomUUID();

await mkdir(path.dirname(project), {recursive: true});
try {
  await mkdir(project);
} catch (error) {
  if (error.code === 'EEXIST') throw new Error('请选择一个尚未创建的工程目录：' + project, {cause: error});
  throw error;
}
const modulePath = path.join(project, 'modules', id);
await cp(source, modulePath, {recursive: true});
await cp(new URL('../shared/', import.meta.url), path.join(project, 'modules', 'shared'), {recursive: true});
await writeFile(path.join(modulePath, 'outlines.json'), JSON.stringify(outline, null, 2) + '\n');
console.log(JSON.stringify({project, modulePath, module: id}));
