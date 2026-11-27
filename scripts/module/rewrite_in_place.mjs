// Reuse the original planner directly against author files; no disk copies.
import fs from 'node:fs';
import path from 'node:path';
import {loadTypeScript, planReferences} from '../media/rewrite_asset_paths.mjs';
let input='';
for await (const chunk of process.stdin) input+=chunk;
try {
 const {scopes, apply=true}=JSON.parse(input);
 let ts;
 try {ts=loadTypeScript();} catch(error) {console.log(JSON.stringify({unavailable:true,error:error.message}));process.exit(0);}
 const plans=scopes.map(scope=>({...scope,...planReferences({course:scope.course,changes:new Map(Object.entries(scope.changes)),ts})}));
 const issues=plans.flatMap(p=>[...p.unresolved.map(row=>({...row,prefix:p.prefix,blocking:true})),...p.unverified.map(row=>({...row,prefix:p.prefix,blocking:true}))]);
 const updates=plans.flatMap(p=>p.updates);
 if(apply && !issues.length){
  const written=[];
  try {
   for(const item of updates) if(fs.readFileSync(item.file,'utf8')!==item.before)throw Error('Source changed: '+item.file);
   for(const item of updates){written.push(item);fs.writeFileSync(item.file,item.after);}
  }catch(error){for(const item of written.reverse())fs.writeFileSync(item.file,item.before);throw error;}
 }
 console.log(JSON.stringify({engine:'node',applied:apply&&!issues.length,changedFiles:updates.length,
  replacements:updates.reduce((n,u)=>n+u.references,0),issues,
  records:plans.flatMap(p=>p.matches.map(row=>({module:p.prefix,...row})))}));
}catch(error){console.log(JSON.stringify({error:error.message}));process.exitCode=1;}
