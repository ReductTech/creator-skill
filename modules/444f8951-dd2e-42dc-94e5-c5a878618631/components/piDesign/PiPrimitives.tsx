import type { ReactNode } from 'react';
import { ContentBlock, MathFormulaBlock, MathFormulaStatic, Typography } from '@shuku/course-style/react';
import { bounds, displayedBounds, PI_COLORS, polygonPoints, SIDES } from './piModel';
import './PiDesign.css';

export function Formula({ latex, label, size = 'normal' }: { latex: string; label?: string; size?: 'normal' | 'large' | 'small' }) {
  return <div className={`cg-pi-formula cg-pi-formula--${size}`}><MathFormulaBlock appearance="plain" ariaLabel={label ?? latex}><MathFormulaStatic latex={latex}/></MathFormulaBlock></div>;
}

export function PiFrame({ title, subtitle, kind, children }: { title: string; subtitle: string; kind: string; children: ReactNode }) {
  return <ContentBlock title={title} subtitle={subtitle} headingLevel={1}
    className={`cg-pi-page cg-pi-${kind} cg-creator-typography`} bodyClassName="cg-pi-body"
    onKeyDown={event => {
      if (event.target instanceof Element && event.target.closest('input') && ['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End',' '].includes(event.key)) event.stopPropagation();
    }}><div className="cg-pi-panels">{children}</div></ContentBlock>;
}

export function PiPanel({ positive, title, caption, children }: { positive?: boolean; title: string; caption: string; children: ReactNode }) {
  return <section className={`cg-pi-panel ${positive ? 'is-positive' : 'is-negative'}`} aria-label={positive ? '正面案例' : '反面案例'}>
    <Typography as="div" variant="bodySmall" tone="muted" className="cg-pi-case-label">{positive ? '正面案例' : '反面案例'}</Typography>
    <Typography as="h2" variant="h2" tone="accent" className="cg-pi-panel-title">{title}</Typography>
    <div className="cg-pi-stage">{children}</div>
    <Typography variant="bodySmall" tone="muted" className="cg-pi-caption">{caption}</Typography>
  </section>;
}

export function BoundReadout({ n = 12, lowerColor = PI_COLORS.lower, upperColor = PI_COLORS.upper, size = 'large' }: {
  n?: number; lowerColor?: string; upperColor?: string; size?: 'normal' | 'large' | 'small';
}) {
  const b = displayedBounds(n);
  return <div className="cg-pi-readout" aria-live="polite" data-n={n}>
    <Formula size={size} label={`下界${b.lower}，圆周率，上界${b.upper}`}
      latex={`{\\color{${lowerColor}}${b.lower}} < \\pi < {\\color{${upperColor}}${b.upper}}`}/>
  </div>;
}

export function PolygonDiagram({ n = 12, labels = true }: { n?: number; labels?: boolean }) {
  return <svg className="cg-pi-polygon-diagram" viewBox="0 0 660 330" role="img" aria-label={`同一个圆的内接与外切正${n}边形`} data-sides={n}>
    <circle cx="290" cy="165" r="142" fill="#f7faff" stroke={PI_COLORS.circle} strokeWidth="2"/>
    <polygon points={polygonPoints(n,true,290,165,142)} fill="none" stroke={PI_COLORS.upper} strokeWidth="4" strokeLinejoin="round"/>
    <polygon points={polygonPoints(n,false,290,165,142)} fill="#e1efff" stroke={PI_COLORS.lower} strokeWidth="4" strokeLinejoin="round"/>
    {labels && <>
      <path d="M420 102h63" stroke={PI_COLORS.upper} fill="none" strokeWidth="2"/>
      <Typography as="text" variant="body" tone="inherit" x="492" y="111" fill={PI_COLORS.upper}>外切</Typography>
      <path d="M432 165h51" stroke={PI_COLORS.lower} fill="none" strokeWidth="2"/>
      <Typography as="text" variant="body" tone="inherit" x="492" y="174" fill={PI_COLORS.lower}>内接</Typography>
    </>}
  </svg>;
}

export function SquareDiagram({ separate = false }: { separate?: boolean }) {
  if (separate) return <svg className="cg-pi-square-diagram" viewBox="0 0 700 430" role="img" aria-label="内接正方形、圆与外切正方形独立排列">
    <polygon points="110,102 198,190 110,278 22,190" fill="#e1efff" stroke={PI_COLORS.lower} strokeWidth="5"/>
    <circle cx="350" cy="190" r="88" fill="#f0f3f7" stroke={PI_COLORS.circle} strokeWidth="4"/>
    <rect x="510" y="110" width="160" height="160" fill="#fff0dd" stroke={PI_COLORS.upper} strokeWidth="5"/>
    <Typography as="text" variant="bodySmall" tone="accent" x="110" y="335" textAnchor="middle">内接正方形</Typography>
    <Typography as="text" variant="bodySmall" tone="accent" x="350" y="335" textAnchor="middle">圆</Typography>
    <Typography as="text" variant="bodySmall" tone="accent" x="590" y="335" textAnchor="middle">外切正方形</Typography>
  </svg>;
  return <svg className="cg-pi-square-diagram" viewBox="0 0 700 430" role="img" aria-label="同圆内接菱形正方形的四顶点在圆上，外切正方形四边与圆相切">
    <rect x="200" y="50" width="300" height="300" fill="none" stroke={PI_COLORS.upper} strokeWidth="4"/>
    <circle cx="350" cy="200" r="150" fill="none" stroke={PI_COLORS.circle} strokeWidth="3"/>
    <polygon points="350,50 500,200 350,350 200,200" fill="#dfedff" stroke={PI_COLORS.lower} strokeWidth="4"/>
    {[ [350,50],[500,200],[350,350],[200,200] ].map(([x,y],i)=><circle key={i} cx={x} cy={y} r="5.5" fill={PI_COLORS.upper} stroke="white" strokeWidth="2"/>)}
    <path d="M264 130 175 110H80" fill="none" stroke={PI_COLORS.lower} strokeWidth="2"/>
    <Typography as="text" variant="body" tone="inherit" x="12" y="94" fill={PI_COLORS.lower}>内接：下界</Typography>
    <path d="M473 114 545 75h24" fill="none" stroke={PI_COLORS.circle} strokeWidth="2"/>
    <Typography as="text" variant="body" tone="accent" x="570" y="82">圆周长</Typography>
    <path d="M500 285h52" fill="none" stroke={PI_COLORS.upper} strokeWidth="2"/>
    <Typography as="text" variant="body" tone="inherit" x="557" y="294" fill={PI_COLORS.upper}>外切：上界</Typography>
  </svg>;
}

export function TrendChart({ qualitative = false, inconsistent = false }: { qualitative?: boolean; inconsistent?: boolean }) {
  const left = qualitative ? 24 : 62, right = qualitative ? 548 : 624;
  const top = 24, bottom = qualitative ? 194 : 282;
  const x=(i:number)=>left+(right-left)*i/4;
  const y=(v:number)=>bottom-(v-3)/.5*(bottom-top);
  const colors={lower:inconsistent?'#e63a4e':PI_COLORS.lower,upper:inconsistent?'#1bb4b7':PI_COLORS.upper};
  const points=(key:'lower'|'upper')=>SIDES.map((n,i)=>`${x(i)},${y(bounds(n)[key])}`).join(' ');
  return <svg className={`cg-pi-trend ${qualitative?'is-qualitative':''}`} viewBox={qualitative?'0 0 660 240':'0 0 700 350'} role="img" aria-label="边数按档翻倍时，下界逐步上升、上界逐步下降，区间收窄">
    {!qualitative && [3,3.1,3.2,3.3,3.4,3.5].map(v=><g key={v}>
      <line x1={left} x2={right+8} y1={y(v)} y2={y(v)} stroke="#d9e4f1"/>
      <Typography as="text" variant="bodySmall" tone="accent" x="48" y={y(v)+7} textAnchor="end">{v.toFixed(1)}</Typography>
    </g>)}
    {!qualitative && <polygon points={`${points('upper')} ${[...SIDES].reverse().map((n,j)=>`${x(4-j)},${y(bounds(n).lower)}`).join(' ')}`} fill="#e5f1ff"/>}
    <path d={`M${left} ${top-8}V${bottom}H${right+10}`} fill="none" stroke="#354c6b" strokeWidth="2"/>
    {(['upper','lower'] as const).map(key=><g key={key}>
      <polyline points={points(key)} fill="none" stroke={colors[key]} strokeWidth="5" strokeLinejoin="round"/>
      {SIDES.map((n,i)=><circle key={n} cx={x(i)} cy={y(bounds(n)[key])} r={qualitative?4:6} fill={qualitative?colors[key]:'white'} stroke={colors[key]} strokeWidth="3"/>)}
      <Typography as="text" variant="body" tone="inherit" fill={colors[key]}
        x={qualitative?566:240} y={qualitative?y(bounds(96)[key])+(key==='upper'?-12:33):y(bounds(12)[key])+(key==='upper'?-30:43)}>{key==='lower'?'下界':'上界'}</Typography>
    </g>)}
    {!qualitative && SIDES.map((n,i)=><Typography as="text" key={n} variant="bodySmall" tone="accent" x={x(i)} y="314" textAnchor="middle">{n}</Typography>)}
    <Typography as="text" variant="bodySmall" tone="muted" x={qualitative?640:355} y={qualitative?235:349} textAnchor={qualitative?'end':'middle'}>{qualitative?'边数增加':'边数（每档翻倍）'}</Typography>
  </svg>;
}

export function BoundsTable() {
  return <table className="cg-pi-table"><thead><tr>{['边数','下界','上界'].map(text=><th scope="col" key={text}><Typography as="span" variant="body" tone="accent">{text}</Typography></th>)}</tr></thead>
    <tbody>{SIDES.map(n=>{const b=displayedBounds(n);return <tr key={n}>{[n,b.lower,b.upper].map((value,i)=><td key={i}><Typography as="span" variant="body" tone="accent">{value}</Typography></td>)}</tr>;})}</tbody></table>;
}
