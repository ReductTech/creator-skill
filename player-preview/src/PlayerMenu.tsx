import {useEffect,useRef,type ReactNode} from 'react';
import {MoreHorizontal,Pencil} from 'lucide-react';

export function PlayerMenu({children,canEdit,onEdit,download}:{children?:ReactNode;canEdit:boolean;onEdit:()=>void;download?:string}){
 const menu=useRef<HTMLDetailsElement>(null);
 useEffect(()=>{
  const close=(event:PointerEvent)=>{if(menu.current&&!menu.current.contains(event.target as Node))closeMenu();};
  const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'&&menu.current?.open){event.stopPropagation();closeMenu(true);}};
  const blur=()=>closeMenu();
  const element=menu.current;
  const toggle=(event:Event)=>{
   const group=event.target;
   if(!element||!(group instanceof HTMLDetailsElement))return;
   if(group===element&&!element.open)element.querySelectorAll('details[open]').forEach(item=>item.removeAttribute('open'));
   else if(group!==element&&group.open)element.querySelectorAll('details[open]').forEach(item=>{if(item!==group)item.removeAttribute('open');});
  };
  element?.addEventListener('toggle',toggle,true);
  document.addEventListener('pointerdown',close);document.addEventListener('keydown',escape,true);
  window.addEventListener('blur',blur);
  return()=>{element?.removeEventListener('toggle',toggle,true);document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',escape,true);window.removeEventListener('blur',blur);};
 },[]);
 function closeMenu(restoreFocus=false){
  if(!menu.current)return;
  menu.current.open=false;
  menu.current.querySelectorAll('details[open]').forEach(item=>item.removeAttribute('open'));
  if(restoreFocus)menu.current.querySelector('summary')?.focus();
 }
 return <details className="cw-player-menu" ref={menu}><summary aria-label="更多"><MoreHorizontal/><span>更多</span></summary><div className="cw-player-menu-content" onClick={event=>{if((event.target as Element).closest('button,a'))closeMenu(true);}}>
  {children}
  {download&&<a href={download} download>下载离线课件</a>}
  {canEdit&&<button onClick={onEdit}><Pencil/>编辑课件</button>}
 </div></details>;
}
