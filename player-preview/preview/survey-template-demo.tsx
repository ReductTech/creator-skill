import {useState} from 'react';
import {SurveyTemplate, type PreviewQuestion} from '@preview/survey-template';
import {SurveyExample, surveyExampleDefinition} from '@preview/survey-example';
import {PptPlayer, type PlayerPage} from '../src';
import './survey-template-demo.css';

const pages: PlayerPage[] = [
  {id:'9ae40cab-8d83-4bf7-93b0-8abf7c942f1d',title:'标准问卷 · 复制即可修改',snippet:'这张页面使用平台标准问卷控件和可复制的 SurveyExample。作者修改题目、选项和说明即可。这里的提交回调只展示本地答案，不连接数据库。'},
  {id:'33ff17e5-3088-46b9-9583-fd38ef2f0a1d',title:'自定义外观 · 保留相同答案',snippet:'只替换 preference 这一题的显示方式：普通单选变成图片卡片。两个页面使用同一份题目定义，选项标识仍是 a 和 b，题目、答案和收集协议均未改变。'},
  {id:'2d62c9c2-6485-467e-a0be-2774e69f3977',title:'题型控件 · 对照选择和修改',snippet:'右侧选择题型，左侧查看标准控件。它们都复用现有 SurveyFields。自定义题通过相同的 renderQuestion 回调提供界面，最后返回题目约定的值。'},
];
const options=[{key:'a',label:'方案 A'},{key:'b',label:'方案 B'},{key:'c',label:'方案 C'}];
const questions: {label:string;question:PreviewQuestion}[] = [
  {label:'单选',question:{key:'answer',title:'你更喜欢哪一个方案？',kind:'single',required:true,options}},
  {label:'多选',question:{key:'answer',title:'哪些特点对你比较重要？',kind:'multiple',options:[{key:'quality',label:'画面质量'},{key:'speed',label:'生成速度'},{key:'control',label:'可控程度'}]}},
  {label:'填空',question:{key:'answer',title:'写下你的理由或补充意见',kind:'text',max_length:1000}},
  {label:'数值',question:{key:'answer',title:'你愿意花多长时间等待？（秒）',kind:'number',minimum:0,maximum:300}},
  {label:'评分',question:{key:'answer',title:'你会给这次体验打几分？',description:'请输入 1 到 5 之间的整数。',kind:'rating',minimum:1,maximum:5}},
  {label:'排序',question:{key:'answer',title:'请按偏好从高到低排序',kind:'ranking',options}},
  {label:'矩阵单选',question:{key:'answer',title:'对每个方案作出评价',kind:'matrix_single',rows:options.slice(0,2),options:[{key:'low',label:'一般'},{key:'good',label:'满意'},{key:'great',label:'非常满意'}]}},
  {label:'矩阵多选',question:{key:'answer',title:'每个方案分别有哪些特点？',kind:'matrix_multiple',rows:options.slice(0,2),options:[{key:'clear',label:'清晰'},{key:'natural',label:'自然'},{key:'creative',label:'有创意'}]}},
  {label:'表格',question:{key:'answer',title:'记录各方案的比较结果',kind:'table',rows:options,columns:[{key:'score',label:'评分',kind:'number'},{key:'note',label:'评价',kind:'text'}]}},
  {label:'Custom',question:{key:'answer',title:'作者自定义的输入区',kind:'custom',description:'示例返回一个结构化值；显示方式由作者决定。'}},
];

export function SurveyTemplateDemo() {
  const [activeId,setActiveId]=useState(pages[0].id),[answers,setAnswers]=useState<Record<string,unknown>>({}),[result,setResult]=useState<Record<string,unknown>|null>(null),[kind,setKind]=useState(0);
  const custom=activeId===pages[1].id,gallery=activeId===pages[2].id;
  const definition=gallery?{title:questions[kind].label+'题示例',description:'标准外观可以直接使用，也可以由作者替换。',questions:[questions[kind].question]}:surveyExampleDefinition;
  const onSelect=(id:string)=>{setActiveId(id);setResult(null);setAnswers({});};
  const renderer=(question:PreviewQuestion,value:unknown,onChange:(value:unknown)=>void)=>{
    if(custom&&question.key==='preference')return <div className="survey-template-preview-cards">{question.options?.map(option=><button type="button" key={option.key} aria-pressed={value===option.key} onClick={()=>onChange(option.key)}><div className={'survey-template-preview-picture picture-'+option.key}><i/><span>替换成你的图片</span></div><strong>{option.label}</strong><small>{value===option.key?'已选择':'点击选择'}</small></button>)}</div>;
    if(question.kind==='custom')return <div className="survey-template-preview-custom"><p>这里可以放图片标注、坐标选择或其他实验交互。</p><button type="button" onClick={()=>onChange({format:'annotation-example',version:1,data:{x:120,y:80}})}>记录一个示例标注</button><small>{value?'标注已记录':'等待操作'}</small></div>;
    return undefined;
  };
  return <PptPlayer title="标准问卷控件 · 可复制模板" pages={pages} activeId={activeId} onSelect={onSelect} canEdit={false} onEdit={()=>{}} onHome={()=>location.assign('/')} actions={<a className="survey-template-preview-back" href="?demo=survey">问卷场景预览</a>}
    renderThumbnail={page=><div className="survey-template-preview-thumbnail"><span>标准问卷控件</span><strong>{page.title?.split(' · ')[0]}</strong></div>}
    slide={<main className="survey-template-preview cw-native"><header><div><span>SHUKU / 标准控件与作者模板</span><h1>{gallery?'选一种题型，对着改就行':custom?'换一种外观，仍然是同一道题':'一份标准控件，作为大家的起点'}</h1></div><span className="survey-template-preview-badge">本地控件预览</span></header><div className="survey-template-preview-grid"><div className="survey-template-preview-control">
      {!custom&&!gallery?<SurveyExample onSubmit={setResult}/>:<SurveyTemplate key={gallery?kind:'custom'} definition={definition} answers={answers} onChange={setAnswers} renderQuestion={renderer} onSubmit={setResult} footer="本地演示：只展示答案，不保存到平台。"/>}
    </div><aside><h2>{gallery?'选择题型':custom?'只改这一个地方':'作者通常改这三处'}</h2>
      {gallery?<label className="survey-template-preview-picker">题型<select aria-label="查看题型" value={kind} onChange={e=>{setKind(Number(e.target.value));setAnswers({});setResult(null);}}>{questions.map((item,index)=><option key={item.label} value={index}>{item.label}</option>)}</select></label>:<ol>{(custom?['保留同一份题目定义','为指定题目返回自己的界面','把选中的值交回 onChange']:['问卷标题与说明','题目文字与选项','提交按钮对应的回调']).map(text=><li key={text}>{text}</li>)}</ol>}
      <p>{custom?'图片怎么摆、怎么选，由作者决定。提交的 preference 仍然是 a 或 b。':'控件负责显示；作者持有答案，决定提交时做什么。'}</p>
      <h3>{result?'本次提交的答案':'配置示意'}</h3><pre aria-label="配置与答案" data-ppt-viewport="配置与本地答案示意">{JSON.stringify(result|| (gallery?questions[kind].question:custom?{preference:'a',reason:'喜欢它的色彩'}:{title:'图片偏好调研',question:'你更喜欢哪一个方案？',options:['方案 A','方案 B']}),null,2)}</pre>
      {result&&<p className="survey-template-preview-success" role="status">已收到本地回调，没有发送网络请求。</p>}
    </aside></div></main>}/>;
}
