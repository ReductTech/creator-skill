/** The current course RPC contract. No HTTP URL aliases or localhost services. */
import {moduleAssetUrl} from './assets.ts';
import {randomUuid} from './uuid.ts';
import type {SurveySubmission} from './surveys.ts';
export type CourseRequest =
 | {action:'survey.read';key:string}
 | {action:'survey.submit';key:string;submission:SurveySubmission}
 | {action:'compute';endpoint:string;payload:Record<string,unknown>;async?:boolean}
 | {action:'record';name:string;payload:Record<string,unknown>}
 | {action:'status';task:string}
 | {action:'event';payload:Record<string,unknown>};

export function requestCourse<T=unknown>(request:CourseRequest,signal?:AbortSignal):Promise<T>{
 // Isolated screenshot jobs have no host or credentials. Read only an explicitly
 // named frozen demonstration fixture; ordinary playback always uses host RPC.
 if(window.parent===window&&new URLSearchParams(location.search).get('scenedeckCapture')==='1'&&request.action==='record'){
  if(!/^[a-z0-9_-]+$/i.test(request.name)||Object.keys(request.payload).length)return Promise.reject(new Error('截图所需的参数化演示记录尚未提供。'));
  return fetch(moduleAssetUrl('precomputed/'+request.name+'.json'),{signal}).then(async response=>{
   if(!response.ok)throw new Error('截图所需的演示记录尚未提供：'+request.name);
   return {ok:true,result:await response.json(),cached:true} as T;
  });
 }
 return new Promise((resolve,reject)=>{
  if(window.parent===window){reject(new Error('此操作需要在术库学习页面中运行。'));return;}
  if(signal?.aborted){reject(new DOMException('Request aborted','AbortError'));return;}
  const id=randomUuid();
  const cleanup=()=>{clearTimeout(timer);window.removeEventListener('message',receive);signal?.removeEventListener('abort',abort);};
  const abort=()=>{cleanup();reject(new DOMException('Request aborted','AbortError'));};
  const receive=(event:MessageEvent)=>{
   if(event.source!==window.parent||event.data?.channel!=='shuku-course-v1'||event.data.id!==id)return;
   const {status,body}=event.data;cleanup();
   if(typeof status!=='number'||status<200||status>=300){reject(new Error(typeof body?.error==='string'?body.error:'课件请求失败。'));return;}
   resolve(body as T);
  };
  const timer=setTimeout(()=>{cleanup();reject(new Error('课件请求超时。'));},request.action.startsWith('survey.')?30000:1800000);
  window.addEventListener('message',receive);signal?.addEventListener('abort',abort,{once:true});
  window.parent.postMessage({channel:'shuku-course-v1',id,...request},'*');
 });
}

export function emitCourseEvent(event:string,detail:Record<string,unknown>){
 if(window.parent===window)return;
 void requestCourse({action:'event',payload:{event,detail}}).catch(()=>{});
}
