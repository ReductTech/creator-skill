import {useCallback,useEffect,useRef,useState} from 'react';
import {readSurvey,submitSurvey,surveyRequestKey,visibleSurveyAnswers} from './surveys';
import type {SurveyAnswers,SurveySession} from './surveys';

/** Optional React state adapter. Rendering and local draft storage belong to the author. */
export function useCourseSurvey(key:string){
 const [session,setSession]=useState<SurveySession|null>(null),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const lifetime=useRef<{key:string;controller:AbortController}|null>(null),request=useRef({signature:'',key:''}),pending=useRef(false);
 const reload=useCallback(async()=>{
  const current=lifetime.current;if(!current||current.key!==key||current.controller.signal.aborted||pending.current)return;
  const signal=current.controller.signal;
  setLoading(true);setError('');
  try{const value=await readSurvey(key,signal);if(!signal.aborted)setSession(value);}
  catch(e){if(!signal.aborted)setError(e instanceof Error?e.message:'问卷暂时无法读取。');}
  finally{if(!signal.aborted)setLoading(false);}
 },[key]);
 useEffect(()=>{const controller=new AbortController();lifetime.current={key,controller};setSession(null);setBusy(false);pending.current=false;request.current={signature:'',key:''};void reload();return()=>controller.abort();},[key,reload]);
 const submit=async(answers:SurveyAnswers,displayName='')=>{
  const current=lifetime.current,signal=current?.controller.signal;
  if(!session||session.survey.key!==key||current?.key!==key||!signal||signal.aborted||pending.current||loading)return null;
  pending.current=true;setBusy(true);setError('');
  try{
   const payload={definition_version:session.survey.definition_version,answers:visibleSurveyAnswers(session.survey.definition,answers),
    display_name:displayName,...(session.my_response?{expected_response_version:session.my_response.version}:{})};
   let signature:string;
   try{signature=JSON.stringify(payload);}catch{setError('答案需要使用可保存的 JSON 数据，请检查自定义交互的答案。');return null;}
   if(request.current.signature!==signature)request.current={signature,key:surveyRequestKey()};
   const response=await submitSurvey(key,{...payload,request_key:request.current.key},signal);
   if(!signal.aborted)setSession({...session,my_response:response});
   return response;
  }catch(e){if(!signal.aborted)setError(e instanceof Error?e.message:'提交未完成，请重试。');return null;}
  finally{if(lifetime.current===current){pending.current=false;if(!signal.aborted)setBusy(false);}}
 };
 return {session,loading,busy,error,reload,submit};
}
