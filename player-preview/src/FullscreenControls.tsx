import {useEffect,useRef,useState,type PointerEvent,type ReactNode,type RefObject} from 'react';
import {ArrowLeft,ArrowRight,EyeOff,GripVertical,Smartphone,X} from 'lucide-react';

type Position={x:number;y:number};
type Props={viewport:RefObject<HTMLDivElement|null>;narration?:ReactNode;index:number;total:number;onStep:(delta:number)=>void;onExit:()=>void;onPresenter?:()=>void};

/** Mounted for one fullscreen visit; hiding and placement are intentionally temporary. */
export function FullscreenControls({viewport,narration,index,total,onStep,onExit,onPresenter}:Props){
 const bar=useRef<HTMLDivElement>(null),drag=useRef<{id:number;x:number;y:number;origin:Position}|null>(null);
 const [hidden,setHidden]=useState(false),[position,setPosition]=useState<Position|null>(null),[dragging,setDragging]=useState(false);
 function clamp(value:Position):Position{
  const host=viewport.current,element=bar.current;if(!host||!element)return value;
  return {x:Math.max(8,Math.min(value.x,host.clientWidth-element.offsetWidth-8)),y:Math.max(8,Math.min(value.y,host.clientHeight-element.offsetHeight-8))};
 }
 function currentPosition(){
  const element=bar.current,host=viewport.current;if(!element||!host)return {x:8,y:8};
  const bounds=element.getBoundingClientRect(),parent=host.getBoundingClientRect();return {x:bounds.left-parent.left,y:bounds.top-parent.top};
 }
 useEffect(()=>{
  const observer=new ResizeObserver(()=>setPosition(value=>value?clamp(value):null));
  if(viewport.current)observer.observe(viewport.current);if(bar.current)observer.observe(bar.current);
  return()=>observer.disconnect();
 },[viewport]);
 function start(event:PointerEvent<HTMLButtonElement>){
  if(event.button!==0)return;event.preventDefault();event.stopPropagation();
  const origin=currentPosition();drag.current={id:event.pointerId,x:event.clientX,y:event.clientY,origin};
  setPosition(clamp(origin));setDragging(true);event.currentTarget.setPointerCapture(event.pointerId);
 }
 function move(event:PointerEvent<HTMLButtonElement>){
  const state=drag.current;if(!state||state.id!==event.pointerId)return;
  setPosition(clamp({x:state.origin.x+event.clientX-state.x,y:state.origin.y+event.clientY-state.y}));
 }
 function stop(event:PointerEvent<HTMLButtonElement>){
  drag.current=null;setDragging(false);if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);
 }
 if(hidden)return null;
 return <div ref={bar} className="cw-fullscreen-controls" role="toolbar" aria-label="全屏播放控制" data-dragging={dragging||undefined}
  data-menu-direction={position&&position.y<(viewport.current?.clientHeight||0)/2?'below':'above'}
  style={position?{left:position.x,top:position.y,right:'auto',bottom:'auto'}:undefined}>
  <button className="cw-controls-drag" aria-label="移动悬浮控制栏" title="拖动移动；方向键微调，Home 复位" onPointerDown={start} onPointerMove={move} onPointerUp={stop} onPointerCancel={stop} onLostPointerCapture={stop}
   onKeyDown={event=>{
    if(event.key==='Home'){event.preventDefault();event.stopPropagation();setPosition(null);return;}
    const directions:Record<string,Position>={ArrowLeft:{x:-1,y:0},ArrowRight:{x:1,y:0},ArrowUp:{x:0,y:-1},ArrowDown:{x:0,y:1}};
    const direction=directions[event.key];if(!direction)return;event.preventDefault();event.stopPropagation();const value=currentPosition(),step=event.shiftKey?20:8;
    setPosition(clamp({x:value.x+direction.x*step,y:value.y+direction.y*step}));
   }}><GripVertical/></button>
  <button aria-label="退出全屏放映" title="退出全屏放映" onClick={onExit}><X/></button>
  <span className="cw-fullscreen-divider"/>{narration}
  <button aria-label="上一页" title="上一页" disabled={index===0} onClick={()=>onStep(-1)}><ArrowLeft/></button>
  <button aria-label="下一页" title="下一页" disabled={index>=total-1} onClick={()=>onStep(1)}><ArrowRight/></button>
  <span className="cw-fullscreen-count">{index+1} / {total}</span>
  {onPresenter&&<button onClick={onPresenter} aria-label="手机提词" title="手机提词"><Smartphone/></button>}
  <button aria-label="本次隐藏控制栏" title="隐藏控制栏，下次进入全屏恢复" onClick={()=>{setHidden(true);viewport.current?.focus({preventScroll:true});}}><EyeOff/></button>
 </div>;
}
