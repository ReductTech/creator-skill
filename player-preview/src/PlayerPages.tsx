import {useRef,useState,type ReactNode} from 'react';
import type {PlayerPage} from './contracts';
import './styles/pages.css';

/** Shared navigation; the host owns page order and persistence. */
export function PlayerPages({pages,activeId,renderThumbnail,onSelect,onMove,disabled=false}:{pages:PlayerPage[];activeId:string;renderThumbnail?:(page:PlayerPage,active:boolean)=>ReactNode;onSelect:(id:string)=>void;onMove?:(moving:string,target:string,after:boolean)=>void;disabled?:boolean}){
 const [outline,setOutline]=useState(false),[drop,setDrop]=useState<{id:string;after:boolean}|null>(null);
 const dragging=useRef<string|null>(null);
 return <aside className="cw-sidebar cw-ppt-sidebar player-page-sidebar" aria-label="幻灯片导航"><header className="cw-pages-heading"><strong>幻灯片 <span>{pages.length}</span></strong><button aria-pressed={outline} onClick={()=>setOutline(!outline)}>{outline?'隐藏大纲':'显示大纲'}</button></header><div className="cw-unified-pages" data-player-thumbnail-list>
  {pages.map((item,index)=><article key={item.id} aria-label={`第${index+1}页`} className={'cw-ppt-page'+(item.id===activeId?' active':'')+(drop?.id===item.id?(drop.after?' drop-after':' drop-before'):'')}
   draggable={!!onMove&&!disabled} onDragStart={event=>{dragging.current=item.id;event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('application/x-shuku-page',item.id);}}
   onDragOver={event=>{if(!dragging.current||disabled||!onMove||dragging.current===item.id)return;event.preventDefault();const bounds=event.currentTarget.getBoundingClientRect();setDrop({id:item.id,after:event.clientY>bounds.top+bounds.height/2});}}
   onDrop={event=>{event.preventDefault();if(dragging.current&&drop&&!disabled)onMove?.(dragging.current,item.id,drop.after);dragging.current=null;setDrop(null);}}
   onDragEnd={()=>{dragging.current=null;setDrop(null);}}>
   <div className="cw-ppt-page-row"><span className="cw-ppt-index">{String(index+1).padStart(2,'0')}</span><button className="cw-ppt-thumb" aria-label={`打开第${index+1}页：${item.title||item.id}`} aria-current={item.id===activeId?'page':undefined} title={onMove?'拖动调整顺序 · Alt+↑ / ↓':item.title||undefined}
    aria-keyshortcuts={onMove?'Alt+ArrowUp Alt+ArrowDown':undefined} onClick={()=>onSelect(item.id)} onKeyDown={event=>{if(disabled||!onMove||!event.altKey||!['ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();const target=pages[index+(event.key==='ArrowUp'?-1:1)];if(target)onMove(item.id,target.id,event.key==='ArrowDown');}}>
    {renderThumbnail?.(item,item.id===activeId)??<span className="cw-ppt-placeholder">{item.title||item.id}</span>}
   </button></div>{outline&&<button className="cw-ppt-title" onClick={()=>onSelect(item.id)}>{item.title||item.id}</button>}
  </article>)}
 </div></aside>;
}
