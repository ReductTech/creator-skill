import {useEffect,useRef,type RefObject} from 'react';
import {frozenPageCatalog} from '../pageCatalog';

type Page={id:string;title?:string};
const embeddedGuide=()=>parent!==window&&new URLSearchParams(location.search).get('mode')==='guide';
export function reportGuideProgress(completed:string[]){
 if(embeddedGuide())parent.postMessage({channel:'shuku-player-v1',action:'progress',completed},'*');
}

/** Course-owned guide layout stays intact. Only navigation and notes cross the frame. */
export function useGuidePlayback({pages,root,reveal,restore}:{pages:Page[];root:RefObject<HTMLDivElement|null>;reveal:(index:number)=>void;restore:(ids:string[])=>void}){
 const latest=useRef({pages,reveal,restore});latest.current={pages,reveal,restore};
 const pageOrder=JSON.stringify(pages.map(page=>page.id));
 useEffect(()=>{
  if(!embeddedGuide())return;
  const catalog=frozenPageCatalog();
  if(!catalog?.pages.some(page=>latest.current.pages.some(step=>step.id===page.id)))return;
  let current='',frame=0,navigation=0,scrollingTo:string|undefined;
  const element=(id:string)=>Array.from(root.current?.querySelectorAll<HTMLElement>('[data-step-id]')||[]).find(node=>node.dataset.stepId===id);
  const publish=(id:string)=>{
   if(id===current)return;current=id;
   const text=catalog.pages.find(page=>page.id===id)?.snippet;
   parent.postMessage({channel:'shuku-player-v1',action:'page',page:id},'*');
   parent.postMessage({channel:'shuku-player-v1',action:'notes',page:id,text:typeof text==='string'?text:''},'*');
  };
  const navigate=(id:string)=>{
   const index=latest.current.pages.findIndex(page=>page.id===id);if(index<0)return;
   cancelAnimationFrame(navigation);scrollingTo=id;latest.current.reveal(index);
   // Reveal first, then scroll after React commits the newly visible section.
   navigation=requestAnimationFrame(()=>{navigation=requestAnimationFrame(()=>{
    const target=element(id);target?.scrollIntoView({block:'start',behavior:'instant'});
    if(target)publish(id);scrollingTo=undefined;
   });});
  };
  const observe=()=>{
   if(scrollingTo)return;
   cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{
    const nodes=Array.from(root.current?.querySelectorAll<HTMLElement>('[data-step-id]')||[]);
    const line=innerHeight*.3;
    const known=nodes.filter(node=>latest.current.pages.some(page=>page.id===node.dataset.stepId));
    const target=known.find(node=>{const rect=node.getBoundingClientRect();return rect.top<=line&&rect.bottom>line;})||known.find(node=>node.getBoundingClientRect().bottom>0);
    if(target?.dataset.stepId)publish(target.dataset.stepId);
   });
  };
  const receive=(event:MessageEvent)=>{
   if(event.source!==parent||event.data?.channel!=='shuku-player-v1')return;
   if(event.data.action==='navigate'&&typeof event.data.page==='string'&&event.data.page!==current)navigate(event.data.page);
   if(event.data.action==='progress'&&Array.isArray(event.data.completed))latest.current.restore(event.data.completed.filter((id:unknown)=>latest.current.pages.some(page=>page.id===id)));
  };
  addEventListener('message',receive);addEventListener('scroll',observe,{passive:true,capture:true});addEventListener('resize',observe);
  parent.postMessage({channel:'shuku-player-v1',action:'outline',pages:catalog.pages},'*');
  parent.postMessage({channel:'shuku-player-v1',action:'ready',capabilities:['guide-navigation']},'*');
  const requested=new URLSearchParams(location.search).get('page');
  if(requested)navigate(requested);else observe();
  return()=>{cancelAnimationFrame(frame);cancelAnimationFrame(navigation);removeEventListener('message',receive);removeEventListener('scroll',observe,true);removeEventListener('resize',observe);};
 // New array/callback instances after progress or layout changes must not replay
 // the iframe's initial URL and scroll the learner back to its first page.
 },[pageOrder,root]);
}
