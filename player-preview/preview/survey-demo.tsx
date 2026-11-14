import {useId, useState, type ReactNode} from 'react';
import {ArrowDown, ArrowUp, ArrowUpRight, BarChart3, Check, CheckCircle2, ClipboardList, Download, Image, LockKeyhole, ShieldCheck, SlidersHorizontal, Table2, Users} from 'lucide-react';
import {PptPlayer, type PlayerPage} from '../src';
import './survey-demo.css';

// This is a player UI demonstration, not a registered course or a live survey.
const pages: PlayerPage[] = [
  {id:'12c45ebd-ae37-4da0-9b3e-641741af0d99', title:'科研场景 · 图片偏好投票', snippet:'问卷可以直接嵌入课件。图片卡片只是单选题的一种外观，作者可以自由设计布局、素材和实验过程。点击图片，再提交一次示例投票。'},
  {id:'130f6757-7bee-4460-9428-395e831f7607', title:'常见题型 · 综合调研问卷', snippet:'同一份问卷支持单选、多选、填空和评分。顶栏可以切换游客、登录、记名与匿名四种组合；本地演示不会验证账号或保存个人信息。'},
  {id:'2ef7d74f-3e37-474b-b3b8-c3cbc118bcbd', title:'自由组合 · 表格、矩阵与排序', snippet:'表格可以填写数值和文字；矩阵量表统一评价维度；排序题保留偏好顺序。这些控件可以分布在课件不同页面，数据由一份问卷统一收集。'},
  {id:'40516790-d46f-4b51-9e05-d43bbf393714', title:'管理者视角 · 问卷结果与统计', snippet:'课程管理者在课程详情查看答卷数量、选项分布、评分和明细，并导出数据。当前画面是放在播放器中的管理界面示意，所有统计都是示例数据，不连接数据库。'},
];
const identityModes = ['无需登录 · 匿名','无需登录 · 记名','需要登录 · 匿名','需要登录 · 记名'];

function Heading({eyebrow,title,description,children}:{eyebrow:string;title:string;description:string;children?:ReactNode}) {
  return <header className="survey-demo-heading"><div><span className="survey-demo-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div><div className="survey-demo-heading-extra">{children}</div></header>;
}
function Chip({children}:{children:ReactNode}) {return <span className="survey-demo-chip">{children}</span>;}
function Landscape({variant}:{variant:'a'|'b'}) {
  const id=useId().replace(/:/g,'');
  const a=variant==='a';
  return <svg viewBox="0 0 640 360" role="img" aria-label={a?'候选图 A：暖色晨光中的山湖':'候选图 B：冷色暮光中的山湖'}>
    <defs><linearGradient id={id+'sky'} x2="0" y2="1"><stop stopColor={a?'#edd8bf':'#bacddd'}/><stop offset="1" stopColor={a?'#f7eadd':'#e7e8e3'}/></linearGradient><linearGradient id={id+'water'} x2="0" y2="1"><stop stopColor={a?'#abc3c3':'#89b1bb'}/><stop offset="1" stopColor={a?'#6a9d9d':'#517f91'}/></linearGradient></defs>
    <rect width="640" height="360" fill={'url(#'+id+'sky)'}/><circle cx={a?445:188} cy={a?94:75} r="36" fill={a?'#fff5d8':'#f3f1de'} opacity=".9"/>
    <path d={a?'M0 220 108 85 203 185 324 63 486 230 640 125 640 300 0 300Z':'M0 180 153 51 277 199 401 101 490 178 588 64 640 115 640 300 0 300Z'} fill={a?'#9baea9':'#839ca7'}/>
    <path d={a?'M0 250 116 145 238 243 352 138 482 252 578 176 640 214 640 300 0 300Z':'M0 237 132 138 258 245 365 168 505 238 640 154 640 300 0 300Z'} fill={a?'#567f7e':'#4f7787'}/>
    <path d="M0 272Q120 240 260 264T640 258V360H0Z" fill={'url(#'+id+'water)'}/>
    <path d="M0 287Q80 267 156 278L102 304 0 315Z" fill={a?'#385b57':'#38545d'}/>
    <path d="M640 256 558 246 501 266 555 283 640 285Z" fill={a?'#476d63':'#3a6269'}/>
    {[0,1,2,3,4].map(i=><path key={i} d={`M${190+i*15} ${292+i*12}h${170-i*18}`} stroke={a?'#dae2cf':'#d0dee0'} strokeWidth="2" opacity={.6-i*.07}/>)}
    <path d="M0 335 51 318 91 326 146 317 188 336 224 360H0Z" fill={a?'#355b53':'#324e59'}/>
    {[28,62,104].map((x,i)=><g key={x} transform={`translate(${x},${290+i*8})`} fill={a?'#294d46':'#294650'}><rect x="-2" y="-24" width="4" height="57"/><path d="M0-54-19-15H19ZM0-36-24 4H24Z"/></g>)}
  </svg>;
}
function Scale({label,value,onChange}:{label:string;value:number;onChange:(value:number)=>void}) {
  return <div className="survey-demo-scale" role="group" aria-label={label}>{[1,2,3,4,5].map(n=><button type="button" key={n} aria-pressed={value===n} onClick={()=>onChange(n)}>{n}</button>)}</div>;
}

export function SurveyDemo() {
  const [activeId,setActiveId]=useState(pages[0].id),[identity,setIdentity]=useState(0),[choice,setChoice]=useState<'a'|'b'>('a'),[sent,setSent]=useState(false),[toast,setToast]=useState('');
  const [purpose,setPurpose]=useState('科研实验'),[reasons,setReasons]=useState(['图像质量']),[score,setScore]=useState(4),[name,setName]=useState(''),[comment,setComment]=useState('');
  const [matrix,setMatrix]=useState([4,5,4]),[ranking,setRanking]=useState(['画面质量','内容准确性','生成速度']);
  const [table,setTable]=useState([{name:'方案 A',score:'4.5',comment:'光影自然，层次丰富'},{name:'方案 B',score:'3.8',comment:'色彩舒服，细节略少'},{name:'方案 C',score:'',comment:''}]);
  const named=identity%2===1,login=identity>=2;
  function inform(message:string){setToast(message);window.setTimeout(()=>setToast(''),3500);}
  function go(id:string){setActiveId(id);setToast('');}
  function exportExample(){
    const text='\ufeff答卷,偏好,评分\n匿名答卷 7c2a,方案 A,5\n匿名答卷 9b13,方案 B,4\n匿名答卷 f08d,方案 A,4\n';
    const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'})),link=document.createElement('a');link.href=url;link.download='问卷示例答卷.csv';link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  const footer=(button:string,onClick:()=>void)=><footer className="survey-demo-footer"><span><ShieldCheck size={20}/>{named?(login?'记名填写 · 使用登录账号身份':'记名填写 · 姓名或称呼由参与者填写'):'匿名填写 · 管理者看不到你的账号身份'}</span><button type="button" className="survey-demo-primary" onClick={onClick}>{button}<ArrowUpRight size={20}/></button></footer>;
  const slide=activeId===pages[0].id?<section className="survey-demo">
    <Heading eyebrow="图像偏好研究 / 交互式问卷" title="两种生成结果，你更喜欢哪一个？" description="想象它们来自两种不同的生成模型。选择更符合你审美的一张，留下你的判断。"><Chip><Image size={17}/>图片单选</Chip><Chip><ShieldCheck size={17}/>{identityModes[identity]}</Chip></Heading>
    <div className="survey-demo-image-grid">{(['a','b'] as const).map(key=><button type="button" className={'survey-demo-image-card'+(choice===key?' is-selected':'')} aria-pressed={choice===key} key={key} onClick={()=>{setChoice(key);setSent(false);}}>
      <div className="survey-demo-art"><Landscape variant={key}/><span>候选图 {key.toUpperCase()}</span></div><div className="survey-demo-image-caption"><div><h2>方案 {key.toUpperCase()}</h2><p>{key==='a'?'暖色晨光 · 丰富的前后景层次':'冷色暮光 · 更克制的色彩表达'}</p></div><span className="survey-demo-radio">{choice===key&&<Check size={22}/>}</span></div>
    </button>)}</div>
    <div className="survey-demo-image-note"><span><SlidersHorizontal size={21}/>图片、卡片、画布或交互实验，都可以成为问卷的一部分。</span><span>这里展示的是图片单选的一个例子</span></div>
    {footer(sent?'已记录你的选择':'提交选择',()=>{setSent(true);inform('已记录：方案 '+choice.toUpperCase()+'（仅本地演示）');})}
  </section>:activeId===pages[1].id?<section className="survey-demo">
    <Heading eyebrow="综合调研 / 常见题型" title="把问卷，自然地放进你的课件" description="不打断内容，也不限制表达。像普通网页一样，组织你需要收集的信息。"><Chip><ClipboardList size={17}/>单选 / 多选 / 填空 / 评分</Chip></Heading>
    <div className="survey-demo-form-grid"><div className="survey-demo-panel survey-demo-form-panel">
      {named&&<label className="survey-demo-field"><span>{login?'登录账号':'姓名或称呼'} <em>必填</em></span><input aria-label="姓名或称呼" placeholder={login?'已登录：研究参与者':'请输入你的姓名或称呼'} value={name} onChange={e=>setName(e.target.value)}/></label>}
      <div className="survey-demo-field"><span>你通常在什么场景使用生成式 AI？ <em>单选</em></span><div className="survey-demo-options">{['科研实验','设计创作','日常工作','学习探索'].map(item=><label key={item}><input type="radio" name="purpose" checked={purpose===item} onChange={()=>setPurpose(item)}/>{item}</label>)}</div></div>
      <div className="survey-demo-field"><span>选择模型时，你最关注哪些因素？ <em>多选</em></span><div className="survey-demo-options">{['图像质量','生成速度','使用成本','可控程度'].map(item=><label key={item}><input type="checkbox" checked={reasons.includes(item)} onChange={e=>setReasons(e.target.checked?[...reasons,item]:reasons.filter(x=>x!==item))}/>{item}</label>)}</div></div>
      <label className="survey-demo-field"><span>还有哪些期待，想告诉我们？ <em>填空</em></span><textarea aria-label="补充意见" value={comment} onChange={e=>setComment(e.target.value)} placeholder="可以写下一个使用场景，或者你希望改进的地方…"/></label>
    </div><aside className="survey-demo-panel survey-demo-rating-panel"><span className="survey-demo-eyebrow">整体评价</span><h2>这次体验，你会打几分？</h2><p>从不太满意，到非常满意。</p><Scale label="体验评分" value={score} onChange={setScore}/><div className="survey-demo-scale-labels"><span>不太满意</span><span>非常满意</span></div><div className="survey-demo-score"><strong>{score}</strong><span>/ 5</span></div><div className="survey-demo-identity"><ShieldCheck size={28}/><h3>{named?'这是一份记名问卷':'这是一份匿名问卷'}</h3><p>{named?'管理者可以看到账号身份或你填写的称呼。':'管理者可以查看你的答案，但看不到账号身份。'}{login?' 填写前需要登录。':' 可以直接填写，无需登录。'}</p></div></aside></div>
    {footer('提交问卷',()=>inform(named&&!login&&!name.trim()?'请先填写姓名或称呼。':'问卷已提交（仅本地演示，刷新后恢复初始状态）。'))}
  </section>:activeId===pages[2].id?<section className="survey-demo">
    <Heading eyebrow="组合调研 / 结构化输入" title="从一张表格，到一套研究量表" description="同一个问题，可以选择最适合的表达方式。表格、矩阵与排序也能放在一起。"><Chip><Table2 size={17}/>表格 / 矩阵 / 排序</Chip></Heading>
    <div className="survey-demo-structured-grid"><div className="survey-demo-structured-left"><article className="survey-demo-panel"><div className="survey-demo-section-title"><h2>记录各方案的评估结果</h2><span>表格填写</span></div><table className="survey-demo-table"><thead><tr><th>比较对象</th><th>评分</th><th>评价或观察</th></tr></thead><tbody>{table.map((row,index)=><tr key={row.name}><th scope="row">{row.name}</th><td><input type="number" aria-label={row.name+'评分'} min={0} max={5} step="0.1" value={row.score} placeholder="0–5" onChange={e=>setTable(table.map((item,i)=>i===index?{...item,score:e.target.value}:item))}/></td><td><input aria-label={row.name+'评价'} value={row.comment} placeholder="输入你的观察" onChange={e=>setTable(table.map((item,i)=>i===index?{...item,comment:e.target.value}:item))}/></td></tr>)}</tbody></table></article>
      <article className="survey-demo-panel"><div className="survey-demo-section-title"><h2>这些描述，符合你的感受吗？</h2><span>矩阵量表</span></div><div className="survey-demo-matrix-header"><span>评价维度</span><span>不符合 → 非常符合</span></div>{['画面内容容易理解','生成结果符合预期','视觉风格保持一致'].map((label,index)=><div className="survey-demo-matrix-row" key={label}><span>{label}</span><Scale label={label} value={matrix[index]} onChange={v=>setMatrix(matrix.map((x,i)=>i===index?v:x))}/></div>)}</article>
    </div><aside className="survey-demo-panel survey-demo-ranking"><span className="survey-demo-eyebrow">偏好排序</span><h2>什么对你更重要？</h2><p>把最重要的一项排在最前面。</p><ol>{ranking.map((item,index)=><li key={item}><span className="survey-demo-rank-number">{index+1}</span><strong>{item}</strong><div>{[-1,1].map(direction=><button type="button" key={direction} disabled={index+direction<0||index+direction>=ranking.length} aria-label={item+(direction<0?'上移':'下移')} onClick={()=>{const next=[...ranking];[next[index],next[index+direction]]=[next[index+direction],next[index]];setRanking(next);}}>{direction<0?<ArrowUp size={18}/>:<ArrowDown size={18}/>}</button>)}</div></li>)}</ol><div className="survey-demo-ranking-note"><CheckCircle2 size={23}/><p>保存的是偏好顺序，<br/>也可以统计平均名次。</p></div></aside></div>
    {footer('保存这一组回答',()=>inform('表格、量表与排序已记录（仅本地演示）。'))}
  </section>:<section className="survey-demo survey-demo-results">
    <Heading eyebrow="课程详情 / 问卷与调研 / 管理者视角" title="生成图像偏好研究" description="从每一份回答，看到整体趋势。以下为示例数据。"><Chip><span className="survey-demo-status-dot"/>收集中</Chip><button type="button" className="survey-demo-secondary" onClick={exportExample}><Download size={18}/>导出示例 CSV</button></Heading>
    <div className="survey-demo-metrics"><div><span><Users size={20}/>有效答卷</span><strong>128 <small>份</small></strong></div><div><span><Image size={20}/>更偏好方案 A</span><strong>68<small>%</small></strong></div><div><span><BarChart3 size={20}/>整体平均评分</span><strong>4.2 <small>/ 5</small></strong></div><div><span><ShieldCheck size={20}/>收集方式</span><strong className="survey-demo-metric-mode">匿名调研</strong><small>结果不展示账号身份</small></div></div>
    <div className="survey-demo-results-grid"><article className="survey-demo-panel"><div className="survey-demo-section-title"><h2>你更喜欢哪一张图？</h2><span>单选 · 128 份回答</span></div>{[{label:'方案 A',count:87},{label:'方案 B',count:41}].map(item=><div className="survey-demo-result-bar" key={item.label}><div><span>{item.label}</span><strong>{item.count} <small>份 · {Math.round(item.count/128*100)}%</small></strong></div><div className="survey-demo-bar-track"><i style={{width:item.count/128*100+'%'}}/></div></div>)}<p className="survey-demo-chart-note">方案 A 获得了更多偏好选择。</p></article>
      <article className="survey-demo-panel"><div className="survey-demo-section-title"><h2>整体体验评分</h2><span>平均 4.2 / 5</span></div><div className="survey-demo-histogram">{[2,6,15,43,62].map((count,index)=><div key={index}><span>{count}</span><i style={{height:count/62*130+'px'}}/><strong>{index+1} 分</strong></div>)}</div></article></div>
    <article className="survey-demo-panel survey-demo-responses"><div className="survey-demo-section-title"><h2>答卷明细</h2><span><LockKeyhole size={15}/>仅课程管理者可见</span></div><table className="survey-demo-table"><thead><tr><th>答卷</th><th>图片偏好</th><th>整体评分</th><th>提交时间</th><th/></tr></thead><tbody>{[{id:'7c2a',choice:'A',score:5,time:'11-14 10:42'},{id:'9b13',choice:'B',score:4,time:'11-14 10:39'},{id:'f08d',choice:'A',score:4,time:'11-14 10:36'}].map(row=><tr key={row.id}><td><span className="survey-demo-response-avatar"><ClipboardList size={16}/></span>匿名答卷 · {row.id}</td><td>方案 {row.choice}</td><td>{row.score} / 5</td><td>{row.time}</td><td><button type="button" className="survey-demo-text-button" onClick={()=>inform('示例答卷 '+row.id+'：偏好方案 '+row.choice+'，评分 '+row.score+' / 5。')}>查看回答 <ArrowUpRight size={15}/></button></td></tr>)}</tbody></table></article>
  </section>;
  return <PptPlayer title="问卷与调研 · 界面效果预览" pages={pages} activeId={activeId} onSelect={go} canEdit={false} onEdit={()=>{}} onHome={()=>location.assign('/')} actions={<><select className="survey-demo-mode-select" aria-label="填写身份模式" value={identity} onChange={e=>setIdentity(Number(e.target.value))}>{identityModes.map((mode,index)=><option key={mode} value={index}>{mode}</option>)}</select><button type="button" className="survey-demo-view-button" onClick={()=>go(activeId===pages[3].id?pages[0].id:pages[3].id)}><BarChart3 size={16}/>{activeId===pages[3].id?'返回填写视角':'看管理者结果'}</button></>}
    renderThumbnail={(page)=><div className={'survey-demo-thumbnail survey-demo-thumbnail-'+pages.indexOf(page)}>{pages.indexOf(page)===0?<Image/>:pages.indexOf(page)===1?<ClipboardList/>:pages.indexOf(page)===2?<Table2/>:<BarChart3/>}<strong>{page.title?.split(' · ')[1]}</strong><span>问卷与调研</span></div>}
    slide={<>{slide}{toast&&<div className="survey-demo-toast" role="status"><CheckCircle2 size={20}/>{toast}</div>}</>}/>;
}
