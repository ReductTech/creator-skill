import {useEffect,type RefObject} from 'react';

const channel='shuku-player-pointer-v1';
/** UI-only pointer input, including normalized coordinates from sandboxed slides. */
export function useLaserPointer(viewport:RefObject<HTMLDivElement|null>,dot:RefObject<HTMLSpanElement|null>){
 useEffect(()=>{
  const element=viewport.current;if(!element)return;
  let frame=0,point:{x:number;y:number}|undefined;
  const active=()=>document.fullscreenElement===element&&!document.hidden;
  const hide=()=>{
   point=undefined;cancelAnimationFrame(frame);frame=0;delete element.dataset.laserActive;
   if(dot.current)dot.current.hidden=true;
  };
  const show=(x:number,y:number)=>{
   if(!active()){hide();return;}
   point={x,y};if(frame)return;
   frame=requestAnimationFrame(()=>{frame=0;if(!point||!dot.current)return;
    dot.current.style.transform=`translate3d(${point.x}px,${point.y}px,0) translate(-50%,-50%)`;
    dot.current.hidden=false;element.dataset.laserActive='';
   });
  };
  const configure=(target?:Window|null)=>{
   const message={channel,action:'configure',enabled:active()};
   if(target)target.postMessage(message,'*');else element.querySelectorAll('iframe').forEach(frame=>frame.contentWindow?.postMessage(message,'*'));
  };
  const sync=()=>{hide();configure();};
  const pointer=(event:PointerEvent)=>{
   if(!active()||(event.target as Element).closest('.cw-fullscreen-controls'))return;
   if(!(event.buttons&2)){hide();return;}
   event.preventDefault();event.stopPropagation();
   const rect=element.getBoundingClientRect();show(event.clientX-rect.left,event.clientY-rect.top);
  };
  const release=(event:PointerEvent)=>{if(!(event.buttons&2))hide();};
  const context=(event:MouseEvent)=>{if(active()&&!(event.target as Element).closest('.cw-fullscreen-controls')){event.preventDefault();event.stopPropagation();}};
  const mouse=(event:MouseEvent)=>{if(active()&&event.button===2&&!(event.target as Element).closest('.cw-fullscreen-controls')){event.preventDefault();event.stopPropagation();}};
  const receive=(event:MessageEvent)=>{
   if(event.data?.channel!==channel)return;
   const owner=Array.from(element.querySelectorAll('iframe')).find(frame=>frame.contentWindow===event.source);if(!owner)return;
   if(event.data.action==='ready'){configure(owner.contentWindow);return;}
   if(!active())return;
   if(event.data.action!=='pointer')return;
   const {pressed,x,y}=event.data;
   if(pressed!==true){hide();return;}
   if(!Number.isFinite(x)||!Number.isFinite(y)||x<0||x>1||y<0||y>1)return;
   const rect=owner.getBoundingClientRect(),base=element.getBoundingClientRect();
   show(rect.left-base.left+x*rect.width,rect.top-base.top+y*rect.height);
  };
  element.addEventListener('pointerdown',pointer,true);element.addEventListener('pointermove',pointer,true);
  element.addEventListener('pointerleave',hide);element.addEventListener('contextmenu',context,true);
  element.addEventListener('mousedown',mouse,true);element.addEventListener('mouseup',mouse,true);
  document.addEventListener('pointerup',release,true);document.addEventListener('pointercancel',hide,true);
  document.addEventListener('fullscreenchange',sync);document.addEventListener('visibilitychange',sync);
  window.addEventListener('blur',hide);window.addEventListener('message',receive);configure();
  return()=>{
   hide();element.querySelectorAll('iframe').forEach(frame=>frame.contentWindow?.postMessage({channel,action:'configure',enabled:false},'*'));
   element.removeEventListener('pointerdown',pointer,true);element.removeEventListener('pointermove',pointer,true);
   element.removeEventListener('pointerleave',hide);element.removeEventListener('contextmenu',context,true);
   element.removeEventListener('mousedown',mouse,true);element.removeEventListener('mouseup',mouse,true);
   document.removeEventListener('pointerup',release,true);document.removeEventListener('pointercancel',hide,true);
   document.removeEventListener('fullscreenchange',sync);document.removeEventListener('visibilitychange',sync);
   window.removeEventListener('blur',hide);window.removeEventListener('message',receive);
  };
 },[viewport,dot]);
}
