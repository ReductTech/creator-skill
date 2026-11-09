// Typecheck generated files against the real Shared contracts without writing a module into the app.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {getTargetRoot} from '../common/_target_root.mjs';
const report={status:'error',newIssues:[],existingIssues:[],environmentErrors:[],unverified:[]};
const diagnostic=issue=>({file:issue.file?.fileName||null,line:issue.file&&issue.start!==undefined?issue.file.getLineAndCharacterOfPosition(issue.start).line+1:null,code:issue.code,message:ts.flattenDiagnosticMessageText(issue.messageText,'\n')});
let ts;
try {
let input='';for await(const chunk of process.stdin)input+=chunk;
const files=JSON.parse(input);
const root=getTargetRoot();
ts=createRequire(path.join(root,'package.json'))('typescript');
const virtualRoot=path.join(root,fs.existsSync(path.join(root,'modules'))?'modules':'.','__toolkit_scaffold_test__');
const normalized=value=>path.resolve(value).replaceAll('\\','/');
const virtual=new Map(Object.entries(files).map(([name,text])=>[normalized(path.join(virtualRoot,name)),text]));
const configFile=path.join(root,'tsconfig.json');
const config=fs.existsSync(configFile)?ts.readConfigFile(configFile,ts.sys.readFile):{config:{compilerOptions:{target:'ES2022',module:'ESNext',moduleResolution:'Bundler',jsx:'react-jsx',resolveJsonModule:true,allowSyntheticDefaultImports:true,esModuleInterop:true,skipLibCheck:true,types:['vite/client']}}};
if(config.error)throw Error(ts.flattenDiagnosticMessageText(config.error.messageText,'\n'));
const parsed=ts.parseJsonConfigFileContent(config.config,ts.sys,root);
const options={...parsed.options,noEmit:true,composite:false,incremental:false};
const host=ts.createCompilerHost(options);
const originalExists=host.fileExists.bind(host), originalRead=host.readFile.bind(host), originalSource=host.getSourceFile.bind(host);
host.fileExists=name=>virtual.has(normalized(name))||originalExists(name);
host.directoryExists=name=>normalized(name)===normalized(virtualRoot)||ts.sys.directoryExists(name);
host.readFile=name=>virtual.get(normalized(name))??originalRead(name);
host.getSourceFile=(name,version,onError,createNew)=>virtual.has(normalized(name))?ts.createSourceFile(name,virtual.get(normalized(name)),version,true,name.endsWith('.json')?ts.ScriptKind.JSON:ts.ScriptKind.TSX):originalSource(name,version,onError,createNew);
// Include the project's ambient declarations in both runs (for custom JSX elements).
const declarations=parsed.fileNames.filter(name=>name.endsWith('.d.ts'));
const generated=[...virtual.keys()].filter(name=>/\.tsx?$/.test(name));
const program=ts.createProgram([...generated,...declarations],options,host);
// Compile the same real dependencies independently, without generated files.
const dependencies=program.getSourceFiles().filter(file=>!file.isDeclarationFile&&!virtual.has(normalized(file.fileName))).map(file=>file.fileName);
const baseline=ts.createProgram([...dependencies,...declarations],options);
const key=issue=>JSON.stringify([issue.file&&normalized(issue.file.fileName),issue.start,issue.code,ts.flattenDiagnosticMessageText(issue.messageText,'\n')]);
const previous=ts.getPreEmitDiagnostics(baseline);
const known=new Set(previous.map(key));
const current=ts.getPreEmitDiagnostics(program);
report.newIssues=current.filter(issue=>!known.has(key(issue))).map(diagnostic);
report.existingIssues=current.filter(issue=>known.has(key(issue))).map(diagnostic);
report.status=report.newIssues.length?'failed':report.existingIssues.length?'blocked':'passed';
report.coverage={generatedFiles:generated.length,dependencyFiles:dependencies.length,baselineCompared:true,projectWide:false};
report.unverified.push('This checks the generated scaffold and its dependencies; it does not check every course or rendered interaction.');
process.exitCode=report.newIssues.length?1:report.existingIssues.length?2:0;
} catch(error) {
report.environmentErrors.push({message:error.message});
report.unverified.push('Type checking could not complete.');
process.exitCode=2;
}
console.log(JSON.stringify(report));
