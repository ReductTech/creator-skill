import {useContext,useEffect,useRef,useState} from 'react';
import {Maximize,Smartphone} from 'lucide-react';
import {PlayerPages} from './PlayerPages';
import {PlayerHeader} from './PlayerHeader';
import {LocalPreviewContext} from './LocalPreviewContext';
import {FullscreenControls} from './FullscreenControls';
import {useLaserPointer} from './useLaserPointer';
import type {PlayerProps} from './contracts';
import './styles/narration.css';
import './styles/layout.css';
import './styles/header.css';
import './styles/fullscreen.css';
import './styles/PptPlayer.css';

// Course execution remains inside its sandbox.
export function PptPlayer({title,versionLabel,pages,activeId,notes,renderThumbnail,slide,narration,subtitle,error,download,actions,onPresenter,canEdit,onHome,onEdit,onSelect}:PlayerProps){
 const preview=useContext(LocalPreviewContext);
 const viewport=useRef<HTMLDivElement>(null),notesBody=useRef<HTMLDivElement>(null);
 const laser=useRef<HTMLSpanElement>(null);
 useLaserPointer(viewport,laser);
 const [fullscreenError,setFullscreenError]=useState('');
 const [scale,setScale]=useState(1),[presenting,setPresenting]=useState(false);
 const index=Math.max(0,pages.findIndex(page=>page.id===activeId)),page=pages[index];
 const snippet=page&&typeof page.snippet==='string'?page.snippet.trim():'';
 const step=(delta:number)=>{const target=pages[Math.max(0,Math.min(pages.length-1,index+delta))];if(target)onSelect(target.id);};
 useEffect(()=>{
  const element=viewport.current;if(!element)return;
  const fit=()=>setScale(Math.min(element.clientWidth/1600,element.clientHeight/900));
  const observer=new ResizeObserver(fit);observer.observe(element);fit();
  const fullscreen=()=>{setPresenting(document.fullscreenElement===element);requestAnimationFrame(fit);};
  document.addEventListener('fullscreenchange',fullscreen);
  return()=>{observer.disconnect();document.removeEventListener('fullscreenchange',fullscreen);};
 },[]);
 useEffect(()=>{notesBody.current?.scrollTo({top:0});},[activeId]);
 useEffect(()=>{
  const keyboard=(event:KeyboardEvent)=>{
   if(event.defaultPrevented||(event.target instanceof Element&&event.target.closest('input,textarea,select,[contenteditable=true]')))return;
   if(['ArrowRight','ArrowDown','PageDown'].includes(event.key)){event.preventDefault();step(1);}
   if(['ArrowLeft','ArrowUp','PageUp'].includes(event.key)){event.preventDefault();step(-1);}
  };
  window.addEventListener('keydown',keyboard);return()=>window.removeEventListener('keydown',keyboard);
 },[index,pages,onSelect]);
 async function present(){try{await viewport.current?.requestFullscreen();setFullscreenError('');}catch{setFullscreenError('暂时无法进入全屏，请再次点击。');}}
 return <div className={'cw-app cw-streamlined cw-viewing cw-reader shuku-ppt-reader'+(presenting?' cw-presenting':'')}>
  <PlayerHeader title={title} versionLabel={versionLabel} controls={preview ? undefined : narration} trailingAction={preview?.publish} showMenu={!preview} canEdit={canEdit} onHome={onHome} onEdit={onEdit} download={download}
   primaryAction={<><button className="cw-present-button" onClick={()=>void present()}><Maximize/>全屏放映</button>{!preview&&onPresenter&&<button className="cw-presenter-button" aria-label="演讲者模式" title="演讲者模式" onClick={onPresenter}><Smartphone/><span>演讲者模式</span></button>}</>}>{actions}</PlayerHeader>
  <PlayerPages pages={pages} activeId={activeId} renderThumbnail={renderThumbnail} onSelect={onSelect}/>
  <main className="cw-main"><header className="cw-page-heading"><div><span>{String(index+1).padStart(2,'0')}</span><strong>{page?.title||page?.id||title}</strong><small>网页</small></div></header>
   {(error||fullscreenError)&&<p role="alert" className="ppt-player-error">{error||fullscreenError}</p>}
   <div className="cw-viewport" ref={viewport} tabIndex={-1}><div className="cw-slide-wrap" style={{width:1600*scale,height:900*scale}}><div className="cw-slide" style={{transform:`scale(${scale})`}}>{slide}</div></div>
    <span className="cw-laser-dot" ref={laser} hidden aria-hidden="true"/>
    {presenting&&<FullscreenControls viewport={viewport} narration={preview ? undefined : narration} index={index} total={pages.length} onStep={step} onPresenter={preview ? undefined : onPresenter} onExit={()=>void document.exitFullscreen()}/>}
    {subtitle&&<p className="ppt-reader-subtitle" aria-live="polite">{subtitle}</p>}
   </div>
   <section className="cw-view-footer cw-notes-footer" aria-label="本页讲稿"><header><strong>本页讲稿</strong><div><span>{index+1} / {pages.length}</span><button aria-label="上一页" disabled={index===0} onClick={()=>step(-1)}>←</button><button aria-label="下一页" disabled={index>=pages.length-1} onClick={()=>step(1)}>→</button></div></header><div className="cw-inline-notes-body" ref={notesBody}><p>{snippet||notes||'本页暂无讲稿。'}</p></div></section>
  </main>
 </div>;
}

