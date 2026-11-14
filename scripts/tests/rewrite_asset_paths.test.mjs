import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {test} from 'node:test';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {applyPlan, loadTypeScript, planReferences} from '../media/rewrite_asset_paths.mjs';

const ts = loadTypeScript();
const script = fileURLToPath(new URL('../media/rewrite_asset_paths.mjs', import.meta.url));

function fixture(t, sources, mapping = {'images/a.jpg': 'images/a.webp'}, extras = []) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'creator-paths-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const course = path.join(root, 'modules/course'), assets = path.join(course, 'assets');
  fs.mkdirSync(assets, {recursive: true});
  const write = (base, name, text) => { const p = path.join(base, name); fs.mkdirSync(path.dirname(p), {recursive: true}); fs.writeFileSync(p, text); };
  write(course, 'outlines.json', JSON.stringify({id: 'course', alias: 'demo', moduleIdentity: {id: 'course'}}));
  for (const [name, text] of Object.entries(sources)) write(course, name, text);
  for (const name of [...Object.values(mapping), ...extras]) write(assets, name, 'asset-bytes-' + name);
  const changes = new Map(Object.entries(mapping));
  const plan = () => planReferences({course, changes, ts});
  const config = path.join(root, 'target-root.json'); write(root, 'target-root.json', JSON.stringify({targetRoot: root}));
  write(root, 'changes.json', JSON.stringify(mapping));
  const cli = (...args) => spawnSync(process.execPath, [script, '--module', 'demo', '--changes', 'changes.json', ...args], {cwd: os.tmpdir(), env: {...process.env, CREATOR_SKILL_TARGET_CONFIG: config}, encoding: 'utf8'});
  return {root, course, assets, changes, plan, cli, write};
}

for (const [name, source, expected] of [
  ['static import', "import image from './assets/images/a.jpg';", './assets/images/a.webp'],
  ['re-export', "export {default} from './assets/images/a.jpg?url';", './assets/images/a.webp?url'],
  ['dynamic import', "const image=import('./assets/images/a.jpg');", './assets/images/a.webp'],
  ['require', "const image=require('./assets/images/a.jpg');", './assets/images/a.webp'],
  ['new URL', "const image=new URL('./assets/images/a.jpg#art',import.meta.url);", './assets/images/a.webp#art'],
  ['runtime helper', "const image=moduleAssetUrl('images/a.jpg?size=2#art');", 'images/a.webp?size=2#art'],
  ['JSX attribute', 'export const X=()=> <img src="assets/images/a.jpg"/>;', 'assets/images/a.webp'],
  ['nested import', "import image from '../../assets/images/a.jpg';", '../../assets/images/a.webp'],
  ['fixed template', 'const image=`images/a.jpg`;', 'images/a.webp'],
  ['constant prefix', "const base='images/'; const image=base+'a.jpg';", 'images/a.webp'],
  ['conditional branches', "const image=flag?'images/a.jpg':'https://cdn/a.jpg';", 'images/a.webp'],
]) {
  test(name, t => {
    const file = name === 'nested import' ? 'pages/Nested/Page.tsx' : 'page.tsx';
    const f = fixture(t, {[file]: source});
    const result = f.plan();
    assert.equal(result.unresolved.length, 0, JSON.stringify(result.unresolved));
    assert.equal(result.updates.length, 1);
    assert.ok(result.updates[0].after.includes(expected), result.updates[0].after);
    assert.equal(fs.readFileSync(path.join(f.course, file), 'utf8'), source, 'Planning is read-only');
  });
}

for (const [name, source] of [
  ['template member access', 'const image=`images/${item.id}.jpg`;'],
  ['plus concatenation', "const image='images/'+id+'.jpg';"],
  ['split extension', "const image='images/'+id+'.'+'jpg';"],
  ['concat', "const image='images/'.concat(id,'.jpg');"],
  ['array join', "const image=['images', id+'.jpg'].join('/');"],
  ['path.join', "const image=path.join('images',id+'.jpg');"],
  ['constant extension', "const ext='.jpg';const image=`images/${id}${ext}`;"],
  ['dynamic query', 'const image=`images/${item.id}.jpg?v=${version}#art`;'],
  ['nested interpolation', 'const image=`images/${flag?one:two}.jpg`;'],
  ['numeric expression', "const image='images/'+(n+1)+'.jpg';"],
  ['glob', "const files=import.meta.glob('./assets/images/*.jpg');"],
  ['recursive glob', "const files=import.meta.glob('./assets/images/**/*.jpg');"],
]) {
  test('dynamic: ' + name, t => {
    const f = fixture(t, {'page.tsx': source}, {'images/a.jpg':'images/a.webp', 'images/b.jpg':'images/b.webp', 'images/nested/c.jpg':'images/nested/c.webp'});
    const result = f.plan();
    assert.equal(result.unresolved.length, 0, JSON.stringify(result.unresolved));
    assert.equal(result.updates.length, 1, source);
    assert.ok(result.updates[0].after.includes('.webp'), result.updates[0].after);
    if (name === 'numeric expression') assert.equal(new Function('n',result.updates[0].after+';return image;')(2),'images/3.webp');
  });
}

test('helper-relative bare paths work only for a unique asset', t => {
  const f=fixture(t, {'page.tsx': "const asset=(name)=>moduleAssetUrl(`workflow/${name}`); const image=asset('draft.jpg');"}, {'workflow/draft.jpg':'workflow/draft.webp'});
  const plan=f.plan();assert.ok(plan.updates[0].after.includes('draft.webp'));
  assert.equal(plan.unresolved.length,0);assert.equal(plan.unverified.length,1);
});

test('recursive globs include immediate files when checking complete migration', t => {
  const f=fixture(t, {'page.tsx':"const files=import.meta.glob('./assets/images/**/*.jpg');"}, {'images/nested/a.jpg':'images/nested/a.webp'}, ['images/b.jpg']);
  assert.equal(f.plan().unresolved[0].kind,'partial-family');
});

test('JSX srcSet migrates each entry and preserves descriptors', t => {
  const f=fixture(t, {'page.tsx':'export const X=()=> <img srcSet="images/a.jpg 1x, images/b.jpg 2x"/>;'}, {'images/a.jpg':'images/a.webp','images/b.jpg':'images/b.webp'});
  const plan=f.plan();assert.equal(plan.unresolved.length,0);
  assert.ok(plan.updates[0].after.includes('images/a.webp 1x, images/b.webp 2x'));
});

test('nested helper calls in CSS templates are still migrated', t => {
  const f=fixture(t, {'page.tsx':'const style=`url(${moduleAssetUrl("images/a.jpg")})`;'});
  assert.ok(f.plan().updates[0].after.includes('images/a.webp'));
});

test('unknown extension variables are reported', t => {
  const f=fixture(t, {'page.tsx':'const image=`images/${id}.${extension}`;'});
  assert.ok(f.plan().unresolved.length);
});

test('opaque runtime functions are listed as unverified without executing them', t => {
  const f=fixture(t, {'page.tsx':'const image=moduleAssetUrl(computePath());function computePath(){throw new Error("must not run")};'});
  assert.equal(f.plan().unverified.length,1);assert.equal(f.plan().updates.length,0);
});

test('failed multi-file transaction restores previously replaced source files', t => {
  const f=fixture(t, {'one.ts':'const image="images/a.jpg";','two.ts':'const image="images/a.jpg";'});
  const plan=f.plan(), rename=fs.renameSync;let calls=0;
  fs.renameSync=(...args)=>{if(++calls===2)throw Error('injected write failure');return rename(...args);};
  try {assert.throws(()=>applyPlan(f.course,plan.updates),/injected write failure/);}
  finally {fs.renameSync=rename;}
  for(const item of plan.updates)assert.equal(fs.readFileSync(item.file,'utf8'),item.before);
  assert.equal(fs.readdirSync(f.course).filter(name=>name.includes('.rewrite-')).length,0);
});

test('concurrent source changes prevent all writes before staging', t => {
  const f=fixture(t, {'page.ts':'const image="images/a.jpg";'}), plan=f.plan();
  fs.writeFileSync(path.join(f.course,'page.ts'),'// changed by the author');
  assert.throws(()=>applyPlan(f.course,plan.updates),/Source changed/);
  assert.equal(fs.readFileSync(path.join(f.course,'page.ts'),'utf8'),'// changed by the author');
});

test('linked target assets cannot leave the course', t => {
  const f=fixture(t, {'page.ts':'const image="images/a.jpg";'});
  const outside=path.join(f.root,'outside');fs.mkdirSync(outside);fs.writeFileSync(path.join(outside,'a.webp'),'external');
  fs.symlinkSync(outside,path.join(f.assets,'escape'),'junction');
  f.write(f.root,'changes.json',JSON.stringify({'images/a.jpg':'escape/a.webp'}));
  assert.equal(f.cli('--apply').status,2);
});

test('output report cannot escape the selected course scratchpad', t => {
  const f=fixture(t, {'page.ts':'const image="images/a.jpg";'});
  assert.equal(f.cli('--apply','--report','outside.json').status,2);
  assert.equal(fs.readFileSync(path.join(f.course,'page.ts'),'utf8'),'const image="images/a.jpg";');
});

test('UTF-8 BOM and Unicode filenames survive migration', t => {
  const f=fixture(t, {'page.ts':'\uFEFFconst image="images/示意图.jpg";\r\n'}, {'images/示意图.jpg':'images/示意图.webp'});
  const run=f.cli('--apply');assert.equal(run.status,0,run.stderr);
  assert.equal(fs.readFileSync(path.join(f.course,'page.ts'),'utf8'),'\uFEFFconst image="images/示意图.webp";\r\n');
});

test('partial dynamic migration blocks the complete apply transaction', t => {
  const source="const direct='images/a.jpg'; const image=`images/${id}.jpg`;";
  const f=fixture(t, {'page.tsx': source}, undefined, ['images/b.jpg']);
  const result=f.cli('--apply');
  assert.equal(result.status, 1, result.stderr);
  assert.equal(JSON.parse(result.stdout).unresolved[0].kind, 'partial-family');
  assert.equal(fs.readFileSync(path.join(f.course,'page.tsx'),'utf8'),source);
  assert.ok(!fs.existsSync(path.join(f.course,'_scratchpad')));
});

test('repeated basenames in different directories are ambiguous', t => {
  const f=fixture(t, {'page.tsx': "const image=asset('a.jpg');"}, {'one/a.jpg':'one/a.webp','two/a.jpg':'two/a.webp'});
  assert.equal(f.plan().unresolved[0].kind,'ambiguous-path');
});

test('full paths disambiguate identical basenames', t => {
  const f=fixture(t, {'page.tsx': "const image=moduleAssetUrl('one/a.jpg');"}, {'one/a.jpg':'one/a.webp','two/a.jpg':'two/a.webp'});
  assert.equal(f.plan().unresolved.length,0);
  assert.ok(f.plan().updates[0].after.includes('one/a.webp'));
});

test('unknown directory prefix is reported instead of rewriting a possible remote URL', t => {
  const f=fixture(t, {'page.tsx': 'const image=`${base}/images/a.jpg`;'});
  assert.equal(f.plan().unresolved[0].kind,'unknown-base');
  assert.equal(f.plan().updates.length,0);
});

test('dynamic arbitrary renames are reported', t => {
  const f=fixture(t, {'page.tsx': 'const image=`images/${id}.jpg`;'}, {'images/a.jpg':'renamed/a.webp'});
  assert.equal(f.plan().unresolved[0].kind,'unsupported-dynamic-rename');
});

test('static arbitrary renames preserve relative import meaning', t => {
  const f=fixture(t, {'page.tsx': "import image from './assets/images/a.jpg';"}, {'images/a.jpg':'new/other.webp'});
  assert.ok(f.plan().updates[0].after.includes('./assets/new/other.webp'));
});

for (const [name, source] of [
  ['comments', '// images/a.jpg\n/* images/a.jpg */const count=1;'],
  ['remote URLs', "const a='https://cdn/images/a.jpg';const b='data:image/png;base64,anything';"],
  ['composed remote URLs', "const a='https://cdn/'+'images/a.jpg'; const base='https://cdn/';const b=`${base}images/a.jpg`;"],
  ['composed prose', "const a='Example: '+'images/a.jpg';const b='Example '+name+': '+'images/a.jpg';"],
  ['prose', "const prompt='Please use images/a.jpg for the next page';"],
  ['unrelated template', 'const label=`${count}`;const label2=`hello ${name}`;'],
]) test('preserve ' + name, t => {
  const f=fixture(t, {'page.tsx': source});
  assert.equal(f.plan().updates.length,0);assert.equal(f.plan().unresolved.length,0);
});

test('scoped constants respect shadowing', t => {
  const f=fixture(t, {'page.tsx': "const base='images/';function example(base){return `${base}/images/a.jpg`;}const picture=base+'a.jpg';"});
  const plan=f.plan();assert.equal(plan.unresolved[0].kind,'unknown-base');
  assert.ok(plan.updates.some(item=>item.after.includes('images/a.webp')));
});

for (const [file, source, expected] of [
  ['style.css', '.image{background:url("./assets/images/a.jpg?v=1")}/*url(images/a.jpg)*/', './assets/images/a.webp?v=1'],
  ['data.json', JSON.stringify({image:'images/a.jpg',text:'Use images/a.jpg here',url:'https://cdn/images/a.jpg'}), 'images/a.webp'],
  ['scene.gltf', JSON.stringify({images:[{uri:'images/a.jpg'}]}), 'images/a.webp'],
  ['page.html', '<img src="assets/images/a.jpg"><video poster="assets/images/a.jpg"></video>', 'assets/images/a.webp'],
  ['page.html', '<img srcset="assets/images/a.jpg 1x, assets/images/a.jpg 2x">', 'assets/images/a.webp 2x'],
  ['README.md', '![image](./assets/images/a.jpg)\n```js\nconst example="images/a.jpg"\n```', './assets/images/a.webp'],
]) test('structured text: '+file+': '+source.slice(0,20), t=>{
  const f=fixture(t,{[file]:source});const result=f.plan();
  assert.equal(result.unresolved.length,0,JSON.stringify(result.unresolved));
  assert.ok(result.updates[0].after.includes(expected),result.updates[0].after);
  if(file==='README.md')assert.ok(result.updates[0].after.includes('const example="images/a.jpg"'));
});

test('apply changes source only, preserves CRLF, backs up and is idempotent', t => {
  const source="const image=moduleAssetUrl('images/a.jpg');\r\nconst count=1;\r\n";
  const f=fixture(t,{'page.tsx':source});
  const asset=fs.readFileSync(path.join(f.assets,'images/a.webp'));
  let run=f.cli();assert.equal(run.status,0,run.stderr);assert.equal(JSON.parse(run.stdout).applied,false);
  assert.equal(fs.readFileSync(path.join(f.course,'page.tsx'),'utf8'),source);
  run=f.cli('--apply');assert.equal(run.status,0,run.stderr);
  const result=JSON.parse(run.stdout);assert.equal(result.applied,true);
  assert.equal(fs.readFileSync(path.join(result.backupDirectory,'page.tsx'),'utf8'),source);
  assert.ok(fs.readFileSync(path.join(f.course,'page.tsx'),'utf8').endsWith('\r\n'));
  assert.deepEqual(fs.readFileSync(path.join(f.assets,'images/a.webp')),asset);
  run=f.cli('--apply');assert.equal(run.status,0,run.stderr);assert.equal(JSON.parse(run.stdout).changedFiles.length,0);
});

test('missing target is rejected before any write', t => {
  const f=fixture(t,{'page.tsx':"const image='images/a.jpg';"});
  fs.unlinkSync(path.join(f.assets,'images/a.webp'));
  const result=f.cli('--apply');assert.equal(result.status,2);assert.ok(!fs.existsSync(path.join(f.course,'_scratchpad')));
});

test('source traversal outside assets is rejected', t => {
  const f=fixture(t,{'page.tsx':"const image='images/a.jpg';"});
  f.write(f.root,'changes.json',JSON.stringify({'../outside.jpg':'images/a.webp'}));
  assert.equal(f.cli('--apply').status,2);
});

test('malformed source blocks all writes', t => {
  const f=fixture(t,{'page.tsx':"const image='images/a.jpg';",'broken.ts':'const x = ;'});
  assert.equal(f.cli('--apply').status,2);assert.ok(!fs.existsSync(path.join(f.course,'_scratchpad')));
});

test('accepts conversion reports without touching skipped images', t => {
  const f=fixture(t,{'page.tsx':"const a='images/a.jpg';const b='images/small.png';"},undefined,['images/small.png']);
  f.write(f.root,'changes.json',JSON.stringify({images:[{status:'converted',source:path.join(f.assets,'images/a.jpg'),target:path.join(f.assets,'images/a.webp')},{status:'skipped',source:'images/small.png',target:'images/small.webp'}]}));
  const run=f.cli('--apply');assert.equal(run.status,0,run.stderr);
  assert.ok(fs.readFileSync(path.join(f.course,'page.tsx'),'utf8').includes('images/small.png'));
});

test('discovery works even when old assets are already removed', t => {
  const f=fixture(t,{'page.tsx':"const a='images/a.jpg';"});
  const run=spawnSync(process.execPath,[script,'--module','demo','--to-ext','webp'],{encoding:'utf8',env:{...process.env,CREATOR_SKILL_TARGET_CONFIG:path.join(f.root,'target-root.json')}});
  assert.equal(run.status,0,run.stderr);assert.equal(JSON.parse(run.stdout).changedFiles.length,1);
});

test('help does not require configured targets or optional libraries', () => {
  const result=spawnSync(process.execPath,[script,'--help'],{encoding:'utf8',env:{...process.env,CREATOR_SKILL_TARGET_CONFIG:'missing.json'}});
  assert.equal(result.status,0,result.stderr);assert.ok(result.stdout.includes('usage:'));
});

test('dry-run with an explicit report still writes no report or backup', t => {
  const f=fixture(t,{'page.ts':"const image='images/a.jpg';"});
  const run=f.cli('--dry-run','--report','modules/course/_scratchpad/plan.json');
  assert.equal(run.status,0,run.stderr);assert.ok(!fs.existsSync(path.join(f.course,'_scratchpad')));
});

test('from/to row lists work and successful apply can write its report', t => {
  const f=fixture(t,{'page.ts':"const image='images/a.jpg';"});
  f.write(f.root,'changes.json',JSON.stringify([{from:'images/a.jpg',to:'images/a.webp'}]));
  const run=f.cli('--apply','--report','modules/course/_scratchpad/plan.json');
  assert.equal(run.status,0,run.stderr);
  const report=JSON.parse(fs.readFileSync(path.join(f.course,'_scratchpad/plan.json'),'utf8'));
  assert.equal(report.applied,true);assert.equal(report.referenceCount,1);
});

test('conflicting and chained replacements are rejected before writing', t => {
  const f=fixture(t,{'page.ts':"const image='images/a.jpg';"},undefined,['images/b.webp']);
  f.write(f.root,'changes.json',JSON.stringify([{from:'images/a.jpg',to:'images/a.webp'},{from:'images/a.jpg',to:'images/b.webp'}]));
  assert.equal(f.cli('--apply').status,2);
  f.write(f.root,'changes.json',JSON.stringify({'images/a.jpg':'images/a.webp','images/a.webp':'images/b.webp'}));
  assert.equal(f.cli('--apply').status,2);
  assert.ok(!fs.existsSync(path.join(f.course,'_scratchpad')));
});
