import type {SceneDefinition} from './types';

/** A missing implementation fails its own page and capture, preserving other pages. */
export function missingScene(page:{id:string;title?:string}):SceneDefinition {
 return {id:page.id,title:page.title||'尚未实现的页面',section:'',render:()=>{throw new Error('此页面尚未提供渲染组件：'+page.id);}};
}
