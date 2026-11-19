import React, {type ComponentType,type ReactNode} from 'react';
import {createRoot} from 'react-dom/client';
import type {SceneDefinition} from '@shuku/course-runtime/react/presentation/types';
import {arrangeCoursePages} from '@shuku/course-runtime/react/pageCatalog';
import {missingScene} from '@shuku/course-runtime/react/presentation/missingScene';
import {CourseErrorBoundary} from '@shuku/course-runtime/react/reliability/CourseErrorBoundary';
import {loadGuide,loadPresentation,metadata,guideExport} from 'virtual:shuku-course';
import {loadStylePresentation} from 'virtual:shuku-style';
import './styles.css';

Reflect.set(globalThis,'__SHUKU_PAGE_CATALOG__',{id:metadata.id,pages:metadata.pages,pageSources:metadata.pageSources||{}});

const params=new URLSearchParams(location.search);
const mode=params.get('mode')||(metadata.modes.includes('guide')?'guide':'ppt');
// Each mode loads its own entry; loading a presentation must not eagerly execute
// the self-study application (and vice versa).
if(!metadata.modes.includes(mode))throw new Error('Unsupported course playback mode: '+mode);
const getNotes=(id:string)=>{
 const page=metadata.pages.find((page:{id:string;snippet?:string})=>page.id===id);
 return typeof page?.snippet==='string'?[{text:page.snippet,selectors:[]}]:[];
};
const Content=React.lazy(async()=>{
 if(mode==='guide'){
  const guide=await loadGuide();
  const Guide=guide?.[guideExport] as ComponentType|undefined;
  if(!Guide)throw new Error('Course entry does not export the selected playback mode');
  return {default:Guide};
 }
 const [presentation,style]=await Promise.all([loadPresentation(),loadStylePresentation()]);
 const SceneDeck=style?.SceneDeck;
 if(!presentation?.deck||!SceneDeck)throw new Error('Course or selected style does not export the selected playback mode');
 const deck={...presentation.deck,id:metadata.id,scenes:arrangeCoursePages(presentation.deck.scenes as SceneDefinition[],true,metadata.id,missingScene)};
 return {default:()=> <SceneDeck catalog={[deck]} moduleId={metadata.id} assetId={metadata.asset_id} progressKey={'shuku:'+metadata.id} getNotes={getNotes}/>};
});
document.title=metadata.title;
export function mountCourse(wrap:(node:ReactNode)=>ReactNode = node=>node){
 createRoot(document.getElementById('root')!).render(wrap(<CourseErrorBoundary page={params.get('page')||undefined}><React.Suspense fallback={<p role="status" data-capture-ready="false">正在打开课件…</p>}><Content/></React.Suspense></CourseErrorBoundary>));
}
