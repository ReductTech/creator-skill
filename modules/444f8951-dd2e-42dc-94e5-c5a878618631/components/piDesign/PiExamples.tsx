import { useState } from 'react';
import { RangeControl, Typography } from '@shuku/course-style/react';
import { BoundReadout, BoundsTable, Formula, PiFrame, PiPanel, PolygonDiagram, SquareDiagram, TrendChart } from './PiPrimitives';
import { PI_COLORS, SIDES } from './piModel';

function MethodOverview() {
  return <div className="cg-pi-methods">
    <section><Typography as="h3" variant="h3" tone="accent">测量法</Typography>
      <svg viewBox="0 0 260 150" role="img" aria-label="测量圆的周长与直径"><circle cx="130" cy="75" r="62" fill="#e6f1ff" stroke="#28496e" strokeWidth="3"/><path d="M68 75h124m-118-5-6 5 6 5m112-10 6 5-6 5" stroke="#28496e" strokeWidth="2" fill="none"/><Typography as="text" variant="bodySmall" tone="accent" x="130" y="65" textAnchor="middle">直径</Typography></svg>
      <Typography variant="bodySmall" tone="accent" align="center">周长 ÷ 直径</Typography>
    </section>
    <section><Typography as="h3" variant="h3" tone="accent">割圆法</Typography><svg viewBox="0 0 260 150" role="img" aria-label="内接正六边形逼近圆"><circle cx="130" cy="75" r="62" fill="none" stroke="#28496e" strokeWidth="3"/><polygon points="192,75 161,128.694 99,128.694 68,75 99,21.306 161,21.306" fill="#fff0d9" stroke={PI_COLORS.upper} strokeWidth="3"/></svg><Typography variant="bodySmall" tone="accent" align="center">用多边形逼近圆</Typography></section>
    <section><Typography as="h3" variant="h3" tone="accent">无穷级数</Typography><div className="cg-pi-series"><Formula size="small" latex="\frac{\pi}{4}=1-\frac13+\frac15-\cdots"/></div><Typography variant="bodySmall" tone="accent" align="center">逐项累加</Typography></section>
    <section><Typography as="h3" variant="h3" tone="accent">随机撒点</Typography><svg viewBox="0 0 260 150" role="img" aria-label="四分之一圆与正方形内的示意样本"><rect x="70" y="10" width="130" height="130" fill="white" stroke="#536074" strokeWidth="2"/><path d="M70 10H200A130 130 0 0 1 70 140Z" fill="#e6f1ff" stroke={PI_COLORS.lower} strokeWidth="2"/>{Array.from({length:24},(_,i)=>{const x=((i*37+11)%97)/100,y=((i*53+7)%97)/100;return <circle key={i} cx={70+x*130} cy={10+y*130} r="3.5" fill={x*x+y*y<=1?PI_COLORS.lower:PI_COLORS.upper}/>;})}</svg><Typography variant="bodySmall" tone="accent" align="center">用面积比估算</Typography></section>
  </div>;
}

function IntervalIllustration() {
  return <svg className="cg-pi-interval" viewBox="0 0 700 260" role="img" aria-label="圆周率的真实值位于已保证的下界3.1410和上界3.1428之间，未指定真实值的位置">
    <Typography as="text" variant="display" tone="accent" x="350" y="70" textAnchor="middle">π</Typography>
    <Typography as="text" variant="bodySmall" tone="muted" x="350" y="115" textAnchor="middle">真实值在这个范围内</Typography>
    <path d="M35 198h630m-12-7 12 7-12 7" stroke="#27446e" strokeWidth="3" fill="none"/>
    <path d="M115 190h470" stroke="#d4e9ff" strokeWidth="20"/>
    <path d="M115 176v43" stroke={PI_COLORS.lower} strokeWidth="7" strokeLinecap="round"/>
    <path d="M585 176v43" stroke={PI_COLORS.upper} strokeWidth="7" strokeLinecap="round"/>
    <Typography as="text" variant="bodySmall" tone="inherit" x="115" y="132" textAnchor="middle" fill={PI_COLORS.lower}>下界</Typography>
    <Typography as="text" variant="h3" tone="inherit" x="115" y="170" textAnchor="middle" fill={PI_COLORS.lower}>3.1410</Typography>
    <Typography as="text" variant="bodySmall" tone="inherit" x="585" y="132" textAnchor="middle" fill={PI_COLORS.upper}>上界</Typography>
    <Typography as="text" variant="h3" tone="inherit" x="585" y="170" textAnchor="middle" fill={PI_COLORS.upper}>3.1428</Typography>
  </svg>;
}

export function PiFocusExample() {
  return <PiFrame kind="focus" title="先确定，这一页要回答什么" subtitle="同样讲圆周率：介绍一串方法，还是先讲透一个判断？">
    <PiPanel title="一页介绍四种计算方法" caption="方法都出现了，当前的理解任务却不明确。"><MethodOverview/></PiPanel>
    <PiPanel positive title="这一页只问：3.14有多准？" caption="先讲透一个判断，再介绍其他方法。">
      <div className="cg-pi-focus-good"><IntervalIllustration/>
        <Typography variant="bodySmall" tone="muted" align="center">内接、外切多边形算出一个保证区间：</Typography>
        <BoundReadout n={96}/>
        <Typography variant="bodySmall" tone="accent" align="center">区间两端保留两位小数，都是 3.14。</Typography>
        <Typography variant="body" tone="accent" align="center">因此，保留两位小数有保证。</Typography>
      </div>
    </PiPanel>
  </PiFrame>;
}

export function PiCompositionExample() {
  return <PiFrame kind="composition" title="把关系，直接画在对象之间" subtitle="需要比较的对象，应放进同一个参照。">
    <PiPanel title="对象分开放，关系靠文字补" caption="分开看见了对象，仍需想象它们的关系。"><div className="cg-pi-composition-content"><SquareDiagram separate/><div className="cg-pi-composition-copy"><Typography variant="body" tone="accent" align="center">内接周长小于圆周长。</Typography><Typography variant="body" tone="accent" align="center">外切周长大于圆周长。</Typography></div></div></PiPanel>
    <PiPanel positive title="共用一个圆，内外直接可见" caption="共同参照，让位置本身承担解释。"><div className="cg-pi-composition-content"><SquareDiagram/><Formula latex={`{\\color{${PI_COLORS.lower}}\\text{内接周长}}<\\text{圆周长}<{\\color{${PI_COLORS.upper}}\\text{外切周长}}`}/></div></PiPanel>
  </PiFrame>;
}

export function PiHierarchyExample() {
  const [index,setIndex]=useState(1);
  const n=SIDES[index];
  return <PiFrame kind="hierarchy" title="让第一眼，先找到观察对象" subtitle="定义、图形与解释都需要，但不必同样醒目。">
    <PiPanel title="边数增加，估计为何更准确？" caption="信息都重要，却没有安排观看顺序。">
      <div className="cg-pi-hierarchy-bad">
        <div className="cg-pi-definition"><Typography variant="body" tone="accent">圆周率：周长与直径之比</Typography><Formula latex="\pi=\frac{C}{d}"/></div>
        <div className="cg-pi-hierarchy-equal"><PolygonDiagram labels={false}/><div><Typography variant="body" tone="accent">内接周长给出<Typography as="strong" variant="body" tone="inherit" className="cg-pi-blue">下界</Typography></Typography><Typography variant="body" tone="accent">外切周长给出<Typography as="strong" variant="body" tone="inherit" className="cg-pi-orange">上界</Typography></Typography></div></div>
        <div className="cg-pi-derivation"><Typography variant="body" tone="accent">边长如何翻倍？</Typography><Formula size="small" latex="s_{2n}=\frac{s_n}{\sqrt{2+2\sqrt{1-s_n^2/4}}}"/></div>
        <BoundReadout/>
      </div>
    </PiPanel>
    <PiPanel positive title="边数增加，估计为何更准确？" caption="先看几何变化，再连接定义：圆周长 ÷ 直径。">
      <div className="cg-pi-hierarchy-good"><PolygonDiagram n={n}/><BoundReadout n={n}/>
        <RangeControl label="边数" aria-label="调整多边形边数" min={0} max={4} step={1} value={index} formatValue={value=>SIDES[Number(value)]} scale={[...SIDES]} discrete onChange={event=>setIndex(Number(event.currentTarget.value))}/>
        <Typography variant="bodySmall" tone="muted" align="center">拖动边数，观察间隙与区间一起缩小。</Typography>
      </div>
    </PiPanel>
  </PiFrame>;
}

function ColorExample({ positive = false }: { positive?: boolean }) {
  return <PiPanel positive={positive} title={positive?'同一含义，始终一种颜色':'每个区域，各配一套颜色'} caption={positive?'颜色连续，图形、数值与趋势自然对应。':'每换一种表达，都要重新核对标签。'}>
    <div className="cg-pi-color-content">
      <div className="cg-pi-color-row"><Typography variant="body" tone="accent">图形标识</Typography><svg viewBox="0 0 520 110" role="img" aria-label="内接使用蓝色线标识，外切使用橙色线标识；线段长度不表示数值"><Typography as="text" variant="body" tone="accent" x="25" y="38">内接</Typography><Typography as="text" variant="body" tone="accent" x="25" y="91">外切</Typography><path d="M115 30h150" stroke={PI_COLORS.lower} strokeWidth="7" strokeLinecap="round"/><path d="M115 83h150" stroke={PI_COLORS.upper} strokeWidth="7" strokeLinecap="round"/></svg></div>
      <div className="cg-pi-color-row"><Typography variant="body" tone="accent">数值</Typography><div><BoundReadout lowerColor={positive?PI_COLORS.lower:'#1b9e22'} upperColor={positive?PI_COLORS.upper:'#8c24be'} size="normal"/><div className="cg-pi-color-labels"><Typography variant="bodySmall" tone="muted">下界</Typography><Typography variant="bodySmall" tone="muted">上界</Typography></div></div></div>
      <div className="cg-pi-color-row cg-pi-color-trend"><Typography variant="body" tone="accent">变化</Typography><TrendChart qualitative inconsistent={!positive}/></div>
    </div>
  </PiPanel>;
}

export function PiColorExample() {
  return <PiFrame kind="color" title="颜色一致，对应关系就清楚" subtitle="同一个对象，换一种表达也不换身份。"><ColorExample/><ColorExample positive/></PiFrame>;
}

export function PiChartExample() {
  return <PiFrame kind="chart" title="要看变化，就让趋势直接可见" subtitle="当前任务：观察多边形边数增加时，上下界如何靠近。">
    <PiPanel title="数值齐全，趋势需逐行比较" caption="查一个具体数值，表格很合适。"><div className="cg-pi-chart-table"><BoundsTable/><Typography variant="bodySmall" tone="muted">保守上下界，均向外取整。</Typography></div></PiPanel>
    <PiPanel positive title="上下界越来越近，一眼可见" caption="看整体变化，图形更直接。"><div className="cg-pi-chart-content"><TrendChart/><div className="cg-pi-chart-readout"><Typography variant="bodySmall" tone="accent">96边形</Typography><BoundReadout n={96}/></div><Typography variant="bodySmall" tone="muted" align="center">区间越来越窄，近似值就更有保证。</Typography></div></PiPanel>
  </PiFrame>;
}
