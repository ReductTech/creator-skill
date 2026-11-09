import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import {getTargetRoot} from '../common/_target_root.mjs';
import coursePaths from '../common/_course_paths.cjs';

/** Assets are runtime resources regardless of extension or size. */
export function checkAssetImports(root, directories = ['modules', 'src']) {
  let ts;
  try { ts = createRequire(path.join(getTargetRoot(), 'package.json'))('typescript'); } catch { /* Shuku's source-only course repositories need no compiler for this check. */ }
  const errors = [];
  function reference(file, specifier, start, source) {
    if (!specifier.startsWith('.') && !specifier.startsWith('/')) return;
    const clean = specifier.split(/[?#]/)[0];
    let target = path.resolve(path.dirname(file), clean);
    // '../assets' may name the shared assets.ts URL helper, not an asset directory.
    if (!path.extname(target)) for (const extension of ['.ts','.tsx','.js','.mjs']) {
      if (fs.existsSync(target + extension)) { target += extension; break; }
    }
    const isResource=target.split(path.sep).includes('assets')||/\.(?:png|jpe?g|webp|gif|svg|mp[34]|webm|woff2?)$/i.test(target);
    if (!isResource) return;
    const inside=file=>file.startsWith(path.resolve(root)+path.sep);
    const valid=inside(target)&&fs.existsSync(target)&&fs.statSync(target).isFile()&&inside(fs.realpathSync(target));
    if(!valid)errors.push({file:path.relative(root,file).replaceAll('\\','/'),line:source.slice(0,start).split('\n').length,specifier,
      message:'资源引用必须指向工程内真实文件；课程素材使用 moduleAssetUrl。'});
  }
  function walk(directory) {
    if (!fs.existsSync(directory)) return;
    for (const entry of fs.readdirSync(directory,{withFileTypes:true})) {
      if (entry.isSymbolicLink() || ['assets','vendor','_scratchpad','node_modules'].includes(entry.name)) continue;
      const file = path.join(directory,entry.name);
      if (entry.isDirectory()) { walk(file); continue; }
      if (!/\.(?:[cm]?[jt]sx?|css)$/.test(file) || /(?:\.test\.|\.min\.|vite\.config\.)/.test(file)) continue;
      const source = fs.readFileSync(file,'utf8');
      if (file.endsWith('.css')) {
        for (const match of source.matchAll(/(?:url\(\s*|@import\s*)["']?([^\s"')]+)["']?\s*\)?/g)) reference(file,match[1],match.index,source);
        continue;
      }
      if (!ts) {
        const pattern=/(?:from\s*|import\s*\(|require\s*\(|new URL\s*\()\s*['"](\.{1,2}\/[^'"]+)['"]/g;
        for(const match of source.matchAll(pattern))reference(file,match[1],match.index,source);
        continue;
      }
      const ast = ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true);
      function visit(node) {
        if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier && ts.isStringLiteralLike(node.moduleSpecifier)) {
          reference(file,node.moduleSpecifier.text,node.getStart(ast),source);
        }
        if ((ts.isCallExpression(node) || ts.isNewExpression(node)) && node.arguments) {
          const name=node.expression.getText(ast);
          if (['import','require','URL','import.meta.glob'].includes(name)) {
            const argument=node.arguments[0];
            const values=argument&&ts.isArrayLiteralExpression(argument)?argument.elements:[argument];
            for (const value of values) if(value&&ts.isStringLiteralLike(value)) reference(file,value.text,node.getStart(ast),source);
          }
        }
        ts.forEachChild(node,visit);
      }
      visit(ast);
    }
  }
  for (const directory of directories) walk(path.resolve(root,directory));
  return errors;
}

export function main(args=process.argv.slice(2)) {
  if(args.includes('--help')||args.includes('-h')) { console.log('node asset_imports.mjs [--module ModuleDirectory] [--root targetRoot]'); return 0; }
  try {
    for(let i=0;i<args.length;i+=2)if(!['--module','--root'].includes(args[i])||!args[i+1])throw Error('Use --module NAME and/or --root targetRoot');
    const root=getTargetRoot();
    const selected=args.includes('--module')?args[args.indexOf('--module')+1]:undefined;
    if(selected&&!/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(selected))throw Error('Module must be a direct course directory name or UUID');
    if(args.includes('--root')&&fs.realpathSync(path.resolve(args[args.indexOf('--root')+1]))!==root)throw Error('--root must match targetRoot in target-root.json');
    const base=coursePaths.modulesDirectory(root);
    const errors=checkAssetImports(root,selected?[coursePaths.resolveModule(root,selected)]:[base]);
    console.log(JSON.stringify({status:errors.length?'failed':'ok',errors}));return errors.length?1:0;
  } catch(error) { console.log(JSON.stringify({status:'error',error:error.message}));return 2; }
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href)process.exitCode=main();
