import type {ReactNode} from 'react';

export interface PlayerPage {id:string;title?:string|null;snippet?:unknown}

/** UI contract only. The host owns authentication, APIs, storage and navigation. */
export interface PlayerProps {
 title:string;
 pages:PlayerPage[];
 activeId:string;
 notes?:string;
 slide:ReactNode;
 error?:string;
 download?:string;
 actions?:ReactNode;
 renderThumbnail?:(page:PlayerPage,active:boolean)=>ReactNode;
 onHome:()=>void;
 onSelect:(id:string)=>void;
}
