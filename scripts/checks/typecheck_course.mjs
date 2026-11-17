// Typecheck actual staged course entries. Never execute course configs or source.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const [root,moduleId,shuku]=process.argv.slice(2);
if(!root||!moduleId||!shuku||process.argv.includes('--help')){
 console.log('Usage: node typecheck_course.mjs <staged-root> <module-uuid> <shuku-root>');
 process.exit(process.argv.includes('--help')?0:2);
}
try{
 const tooling=path.join(shuku,'tooling/course-build');
 let ts;for(const base of [tooling,path.resolve(import.meta.dirname,'../../player-preview')]){
  try{ts=createRequire(path.join(base,'package.json'))('typescript');break;}catch{}
 }
 if(!ts)throw Error('TypeScript is unavailable');
 const directory=path.join(root,'modules',moduleId),doc=JSON.parse(fs.readFileSync(path.join(directory,'outlines.json'),'utf8').replace(/^\uFEFF/,''));
 let style=path.join(root,'modules/shared');
 const registryFile=path.join(root,'course-styles.json');
 if(fs.existsSync(registryFile)){
  const registry=JSON.parse(fs.readFileSync(registryFile,'utf8'));
  const selected=registry.styles.find(row=>row.id===(doc.style_id||registry.default_style));
  if(selected)style=path.resolve(root,selected.path);
 }
 const options={noEmit:true,target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,
  moduleResolution:ts.ModuleResolutionKind.Bundler,jsx:ts.JsxEmit.ReactJSX,skipLibCheck:true,
  resolveJsonModule:true,allowSyntheticDefaultImports:true,esModuleInterop:true,types:[],baseUrl:root,
  paths:{'@shuku/course-style/*':[path.join(style,'*')],
   '@shuku/course-runtime/*':[path.join(shuku,'packages/course-runtime/*')],
   '@shuku/player':[path.join(shuku,'packages/player/src/index.ts')],
   react:[path.join(tooling,'node_modules/@types/react/index.d.ts')],
   'react/*':[path.join(tooling,'node_modules/@types/react/*')],
   '*':[path.join(tooling,'node_modules/*'),path.join(tooling,'node_modules/@types/*')]}};
 const entries=[doc.entry,doc.ppt?.entry].filter(Boolean).map(file=>path.join(directory,file));
 function declarations(folder){
  if(!fs.existsSync(folder))return [];
  return fs.readdirSync(folder,{withFileTypes:true}).flatMap(item=>{
   if(['node_modules','assets','vendor','_scratchpad'].includes(item.name))return [];
   const file=path.join(folder,item.name);
   return item.isDirectory()?declarations(file):item.name.endsWith('.d.ts')?[file]:[];
  });
 }
 const program=ts.createProgram([...entries,...declarations(path.join(style,'types')),...declarations(directory)],options);
 const issues=ts.getPreEmitDiagnostics(program).filter(item=>item.category===ts.DiagnosticCategory.Error).map(item=>({
  file:item.file?path.relative(root,item.file.fileName):null,line:item.file&&item.start!==undefined?item.file.getLineAndCharacterOfPosition(item.start).line+1:null,
  code:item.code,message:ts.flattenDiagnosticMessageText(item.messageText,'\n')}));
 console.log(JSON.stringify({status:issues.length?'failed':'passed',issues,coverage:'Actual course entry dependency graph; not a rendered-page check.'}));
 process.exitCode=issues.length?1:0;
}catch(error){console.log(JSON.stringify({status:'error',error:error.message}));process.exitCode=2;}
