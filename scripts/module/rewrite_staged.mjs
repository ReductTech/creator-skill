// Thin adapter around the original Node planner, including registered style assets.
import fs from 'node:fs';
import path from 'node:path';
import {loadTypeScript,planReferences,applyPlan} from '../media/rewrite_asset_paths.mjs';
const [root,prefix,mapping]=process.argv.slice(2);
if(process.argv.includes('--help')){console.log('Usage: rewrite_staged.mjs <snapshot-root> <modules-or-styles/uuid> <mapping.json>');process.exit(0);}
try{
 if(!root||!mapping||!/^(modules|styles)\/[a-f0-9-]{36}$/.test(prefix||''))throw Error('Select a staged course/style UUID');
 const course=path.resolve(root,prefix);
 if(!course.startsWith(path.resolve(root)+path.sep))throw Error('Staged scope leaves root');
 const changes=new Map(Object.entries(JSON.parse(fs.readFileSync(mapping,'utf8'))));
 const {updates,unresolved,unverified,matches}=planReferences({course,changes,ts:loadTypeScript(root)});
 if(!unresolved.length)applyPlan(course,updates);
 console.log(JSON.stringify({status:unresolved.length?'failed':'ok',applied:!unresolved.length,
  changedFiles:updates.map(item=>({file:path.relative(course,item.file),references:item.references})),unresolved,unverified,matches}));
 process.exitCode=unresolved.length?1:0;
}catch(error){console.log(JSON.stringify({status:'error',error:error.message}));process.exitCode=2;}
