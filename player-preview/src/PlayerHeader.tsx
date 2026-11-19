import type {ReactNode} from 'react';
import {Maximize} from 'lucide-react';
import {PlayerMenu} from './PlayerMenu';
import './styles/header.css';

const brandUrl = new URL('./assets/shuku-cn-black.svg', import.meta.url).href;

export interface PlayerHeaderProps {
 title:string;
 versionLabel?:string;
 modeIndicator?:ReactNode;
 controls?:ReactNode;
 primaryAction?:ReactNode;
 tone?:'default'|'editing';
 children?:ReactNode;
 fullscreenLabel?:string;
 trailingAction?:ReactNode;
 showMenu?:boolean;
 canEdit?:boolean;
 download?:string;
 onHome:()=>void;
 onFullscreen?:()=>void;
 onEdit?:()=>void;
}

/** Shared course chrome; modes supply their own controls and menu actions. */
export function PlayerHeader({title,versionLabel,modeIndicator,controls,primaryAction,tone='default',children,fullscreenLabel='全屏放映',canEdit=false,download,onHome,onFullscreen,onEdit,trailingAction,showMenu=true}:PlayerHeaderProps){
 return <div className="shuku-ppt-reader cw-streamlined shuku-player-header-host" data-tone={tone}>
  <header className="cw-topbar">
   <div className="cw-header-identity"><a href="/" className="cw-brand cw-shuku-brand" aria-label="术库首页" onClick={event=>{event.preventDefault();onHome();}}><img className="cw-brand-image" src={brandUrl} alt="术库" width={57.2} height={30} draggable={false}/></a><div className="cw-course-context"><strong className="cw-managed-title" title={title}>{title}</strong>{versionLabel&&<span className="cw-version-label">{versionLabel}</span>}</div>{modeIndicator}</div>
   <div className="cw-actions">{controls}{primaryAction??(onFullscreen&&<button className="cw-present-button" onClick={onFullscreen}><Maximize/>{fullscreenLabel}</button>)}{trailingAction}{showMenu&&<PlayerMenu canEdit={canEdit} onEdit={()=>onEdit?.()} download={download}>{children}</PlayerMenu>}</div>
  </header>
 </div>;
}
