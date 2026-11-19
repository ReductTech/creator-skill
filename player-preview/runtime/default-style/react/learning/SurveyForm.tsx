import {useId,useRef,useState} from 'react';
import type {ReactNode} from 'react';
import {isSurveyQuestionVisible,visibleSurveyAnswers} from '@shuku/course-runtime/react/surveys';
import type {SurveyAnswers,SurveyDefinition,SurveyQuestion} from '@shuku/course-runtime/react/surveys';
import {useCourseSurvey} from '@shuku/course-runtime/react/useCourseSurvey';
import './SurveyForm.css';

type Props={definition:SurveyDefinition;answers:SurveyAnswers;onChange:(answers:SurveyAnswers)=>void;disabled?:boolean;
 renderQuestion?:(question:SurveyQuestion,value:unknown,onChange:(value:unknown)=>void)=>ReactNode};

/** Optional baseline controls; override any question, including image/experiment inputs. */
export function SurveyFields({definition,answers,onChange,disabled=false,renderQuestion}:Props){
 const prefix=useId(),active=visibleSurveyAnswers(definition,answers);
 return <div className="shuku-survey-fields">{definition.questions.filter(q=>isSurveyQuestionVisible(q,active)).map(q=>{
  const value=answers[q.key],options=q.options||[],rows=q.rows||[];
  const change=(next:unknown)=>onChange({...answers,[q.key]:next});
  const choice=(v:unknown,set:(next:unknown)=>void,multiple=false,name=q.key)=>options.map(o=><label key={o.key} className="shuku-survey-choice"><input type={multiple?'checkbox':'radio'} name={prefix+name} value={o.key}
   checked={multiple?Array.isArray(v)&&v.includes(o.key):v===o.key} onChange={e=>set(multiple?(e.target.checked?[...(Array.isArray(v)?v:[]),o.key]:(Array.isArray(v)?v:[]).filter(x=>x!==o.key)):o.key)}/>{o.label}</label>);
  const matrix=value&&typeof value==='object'?value as Record<string,unknown>:{};
  let control=renderQuestion?.(q,value,change);
  if(control===undefined){
   if(q.kind==='single'||q.kind==='multiple')control=choice(value,change,q.kind==='multiple');
   else if(q.kind==='text')control=<textarea aria-label={q.title} value={typeof value==='string'?value:''} maxLength={q.max_length||4000} required={q.required} onChange={e=>change(e.target.value)}/>;
   else if(q.kind==='number'||q.kind==='rating')control=<input aria-label={q.title} type="number" step={q.kind==='rating'?1:'any'} min={q.minimum??undefined} max={q.maximum??undefined} required={q.required} value={typeof value==='number'?value:''} onChange={e=>change(e.target.value===''?null:e.target.valueAsNumber)}/>;
   else if(q.kind==='ranking'){
    const ordered=Array.isArray(value)?value as string[]:options.map(o=>o.key);
    control=<><p>按偏好从高到低排列。</p><ol>{ordered.map((key,index)=><li key={key}><span>{options.find(o=>o.key===key)?.label}</span>{[-1,1].map(direction=><button type="button" key={direction} disabled={disabled||index+direction<0||index+direction>=ordered.length} aria-label={`${options.find(o=>o.key===key)?.label}${direction===-1?'上移':'下移'}`} onClick={()=>{const next=[...ordered];[next[index],next[index+direction]]=[next[index+direction],next[index]];change(next);}}>{direction===-1?'↑':'↓'}</button>)}</li>)}</ol><button type="button" onClick={()=>change(ordered)}>确认当前顺序</button>{Array.isArray(value)&&<small>顺序已记录</small>}</>;
   }else if(q.kind==='matrix_single'||q.kind==='matrix_multiple')control=rows.map(row=><fieldset key={row.key}><legend>{row.label}</legend>{choice(matrix[row.key],v=>change({...matrix,[row.key]:v}),q.kind==='matrix_multiple',q.key+':'+row.key)}</fieldset>);
   else if(q.kind==='table')control=<div className="shuku-survey-table"><table><thead><tr><th scope="col">项目</th>{q.columns?.map(c=><th scope="col" key={c.key}>{c.label}</th>)}</tr></thead><tbody>{rows.map(row=><tr key={row.key}><th scope="row">{row.label}</th>{q.columns?.map(c=>{
    const cells=(matrix[row.key]||{}) as Record<string,unknown>,v=cells[c.key];
    const set=(next:unknown)=>change({...matrix,[row.key]:{...cells,[c.key]:next}});
    return <td key={c.key}>{c.kind==='single'?<select aria-label={row.label+' '+c.label} value={typeof v==='string'?v:''} required={q.required} onChange={e=>set(e.target.value)}><option value="">请选择</option>{c.options?.map(o=><option key={o.key} value={o.key}>{o.label}</option>)}</select>
     :<input aria-label={row.label+' '+c.label} type={c.kind==='number'?'number':'text'} step="any" maxLength={q.max_length||4000} required={q.required} value={typeof v==='number'||typeof v==='string'?v:''} onChange={e=>set(c.kind==='number'?(e.target.value===''?null:e.target.valueAsNumber):e.target.value)}/>}</td>;
   })}</tr>)}</tbody></table></div>;
   else control=<p>此题需要课件作者提供交互控件。</p>;
  }
  return <fieldset key={q.key} disabled={disabled} className="shuku-survey-question"><legend>{q.title}{q.required&&<span aria-label="必填"> *</span>}</legend>{q.description&&<p>{q.description}</p>}{control}</fieldset>;
 })}</div>;
}

export function SurveyForm(props:{surveyKey:string;renderQuestion?:Props['renderQuestion']}){
 return <SurveyFormSession key={props.surveyKey} {...props}/>;
}

function SurveyFormSession({surveyKey,renderQuestion}:{surveyKey:string;renderQuestion?:Props['renderQuestion']}){
 const {session,loading,busy,error,reload,submit}=useCourseSurvey(surveyKey);
 const [answers,setAnswers]=useState<SurveyAnswers>({}),[dirty,setDirty]=useState(false),[name,setName]=useState<string|null>(null);
 const definition=session?.survey.definition;
 const saved=session?.my_response;
 const disabled=loading||busy||!session||session.survey.status!=='open'||!!definition?.login_required&&!session.is_logged_in||!!saved&&!definition?.allow_update;
 const form=useRef<HTMLFormElement>(null);
 async function send(){
  if(disabled||!form.current?.reportValidity())return;
  const result=await submit(dirty?answers:(saved?.answers||{}),name??saved?.display_name??'');
  if(result)setDirty(false);
 }
 return <section className="shuku-survey" aria-busy={loading||busy}>
  {loading&&<p role="status">正在读取问卷…</p>}
  {definition&&<form ref={form} onSubmit={event=>event.preventDefault()} onKeyDown={event=>{
   // Player sandboxes deliberately omit allow-forms. Send only through host
   // RPC; never rely on the browser's native form submission algorithm.
   if(event.key==='Enter'&&(event.target as HTMLElement).tagName==='INPUT'){event.preventDefault();void send();}
  }}>
   <h2>{definition.title}</h2>{definition.description&&<p>{definition.description}</p>}
   <p>{definition.login_required?'需要登录':'允许游客填写'} · {definition.identity_mode==='named'?'记名问卷：管理者可查看账号或填写的称呼':'匿名问卷：管理者看不到账号身份'}{definition.allow_update?' · 提交后可修改':''}</p>
   {definition.login_required&&!session.is_logged_in&&<p role="status">请在术库页面登录后填写。</p>}
   {session.survey.status!=='open'&&<p role="status">当前问卷已停止收集。</p>}
   {definition.identity_mode==='named'&&!session.is_logged_in&&<label>姓名或称呼（自行填写）<input required maxLength={100} value={name??saved?.display_name??''} disabled={disabled} onChange={e=>setName(e.target.value)}/></label>}
   <SurveyFields definition={definition} answers={dirty?answers:(saved?.answers||{})} onChange={value=>{setAnswers(value);setDirty(true);}} disabled={disabled} renderQuestion={renderQuestion}/>
   {saved&&<p role="status">已提交 · 回执 {saved.receipt}{definition.allow_update?' · 可以修改后再次保存':''}</p>}
   <button type="button" disabled={disabled} onClick={()=>void send()}>{busy?'正在提交…':saved?(definition.allow_update?'保存修改':'已提交'):'提交问卷'}</button>
  </form>}
  {error&&<p role="alert">{error}</p>}
  <button type="button" disabled={loading||busy} onClick={()=>void reload()}>重新读取问卷</button>
 </section>;
}
