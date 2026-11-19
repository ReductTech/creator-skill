import {useEffect,useMemo,useState} from 'react';
import {arrangeCoursePages,frozenPageCatalog} from '../pageCatalog';
import type {SceneDeckProps,SceneDefinition} from './types';
import {missingScene} from './missingScene';

function initialPage(scenes:SceneDefinition[]){
 const params=new URLSearchParams(location.search),id=params.get('page');
 if(params.has('slide'))throw new Error('Use the current page parameter');
 if(!id)return 0;
 const index=scenes.findIndex(scene=>scene.id===id);
 if(index<0)throw new Error('课程中不存在此页面：'+id);
 return index;
}
function completedPages(key:string):string[]{try{const value=JSON.parse(localStorage.getItem(key)||'null');return Array.isArray(value?.completedIds)?value.completedIds.filter((id:unknown)=>typeof id==='string'):[];}catch{return [];}}
const resolve=(value:string|((id:string)=>string),id:string)=>typeof value==='function'?value(id):value;

/** Transport and page state only. A style owns all rendering and controls. */
export function useCoursePlayback({catalog,moduleId,progressKey,getNotes}:SceneDeckProps){
 const params=new URLSearchParams(location.search),requested=params.get('deck');
 const source=requested?catalog.find(item=>item.id===requested):catalog[0];
 if(!source)throw new Error('课程中不存在指定的演示文稿。');
 const deck=useMemo(()=>({...source,scenes:arrangeCoursePages(source.scenes,true,source.id,missingScene)}),[source]);
 const [index,setIndex]=useState(()=>initialPage(deck.scenes));
 const key=resolve(progressKey,deck.id),[completed,setCompleted]=useState(()=>completedPages(key));
 const capture=params.get('scenedeckCapture')==='1',embedded=params.get('shukuViewer')==='1';
 const scene=deck.scenes[index];
 if(!scene)throw new Error('课程中不存在指定的页面。');
 const configured=frozenPageCatalog()?.pages.find(page=>page.id===scene.id);
 const notes=typeof configured?.snippet==='string'?configured.snippet:(getNotes?.(scene.id,deck.id)||[]).map(note=>note.text).join('\n');
 const select=(id:string)=>{
  const next=deck.scenes.findIndex(page=>page.id===id);if(next<0)throw new Error('课程中不存在此页面：'+id);
  setIndex(next);
 };
 const persist=(ids:string[])=>{setCompleted(ids);try{localStorage.setItem(key,JSON.stringify({completedIds:ids}));}catch{}if(parent!==window)parent.postMessage({channel:'shuku-player-v1',action:'progress',completed:ids},'*');};
 // A capture batch keeps one document alive; normal viewers expose no control.
 useEffect(()=>{
  if(!capture||embedded)return;
  const control={select:(id:string)=>{
   const next=deck.scenes.findIndex(page=>page.id===id);
   if(next<0)throw new Error('课程中不存在此页面：'+id);
   Reflect.deleteProperty(window,'__SHUKU_CAPTURE_ERROR__');
   const url=new URL(location.href);url.searchParams.set('page',id);history.replaceState(null,'',url);
   setIndex(next);
  }};
  Reflect.set(window,'__SHUKU_CAPTURE__',control);
  return()=>{if(Reflect.get(window,'__SHUKU_CAPTURE__')===control)Reflect.deleteProperty(window,'__SHUKU_CAPTURE__');};
 },[deck,capture,embedded]);
 useEffect(()=>{
  if(parent===window||capture&&!embedded)return;
  parent.postMessage({channel:'shuku-player-v1',action:'outline',pages:deck.scenes.map(({id,title})=>({id,title}))},'*');
  parent.postMessage({channel:'shuku-player-v1',action:'page',page:scene.id},'*');
  parent.postMessage({channel:'shuku-player-v1',action:'notes',page:scene.id,text:notes},'*');
 },[deck,scene.id,notes,capture,embedded]);
 useEffect(()=>{
  const receive=(event:MessageEvent)=>{
   if(event.source!==parent||event.data?.channel!=='shuku-player-v1')return;
   if(event.data.action==='speaker-notes'){
    const frozen=frozenPageCatalog();
    const pages=deck.scenes.map(({id,title})=>{const snippet=frozen?.pages.find(page=>page.id===id)?.snippet;return {id,title,notes:typeof snippet==='string'?snippet:(getNotes?.(id,deck.id)||[]).map(note=>note.text).join('\n')};});
    parent.postMessage({channel:'shuku-player-v1',action:'speaker-notes',pages},'*');
   }
   if(event.data.action==='navigate')select(event.data.page);
   if(event.data.action==='progress'&&Array.isArray(event.data.completed))setCompleted(event.data.completed.filter((id:unknown)=>deck.scenes.some(page=>page.id===id)));
  };
  const keyboard=(event:KeyboardEvent)=>{
   if(capture&&!embedded||event.defaultPrevented||(event.target instanceof Element&&event.target.closest('input,textarea,select,[contenteditable=true]')))return;
   const delta=['ArrowRight','ArrowDown','PageDown'].includes(event.key)?1:['ArrowLeft','ArrowUp','PageUp'].includes(event.key)?-1:0;
   if(delta){event.preventDefault();setIndex(current=>Math.max(0,Math.min(deck.scenes.length-1,current+delta)));}
  };
  addEventListener('message',receive);addEventListener('keydown',keyboard);
  if(parent!==window)parent.postMessage({channel:'shuku-player-v1',action:'ready'},'*');
  return()=>{removeEventListener('message',receive);removeEventListener('keydown',keyboard);};
 },[deck,capture,embedded,getNotes]);
 useEffect(()=>{if(capture)return;const url=new URL(location.href);url.searchParams.set('page',scene.id);try{history.replaceState(null,'',url);}catch{}},[scene.id,capture]);
 return {deck,scene,index,notes,capture,embedded,select,
  context:{complete:()=>{if(!capture||embedded)persist([...new Set([...completed,scene.id])]);},reset:()=>{if(!capture||embedded)persist(completed.filter(id=>id!==scene.id));},isComplete:completed.includes(scene.id),next:()=>setIndex(current=>Math.min(deck.scenes.length-1,current+1))},
  home:()=>{if(parent!==window)parent.postMessage({channel:'shuku-player-v1',action:'back'},'*');else location.assign('/');},
  edit:()=>parent.postMessage({channel:'shuku-player-v1',action:'edit',module:resolve(moduleId,deck.id)},'*')};
}
