import { photos, type PhotoKey } from './photos';
import './figures.css';

export function Photo({ asset, x, y, width, height, rounded = 0 }: { asset: PhotoKey; x: number; y: number; width: number; height: number; rounded?: number }) {
  return <svg x={x} y={y} width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={rounded ? { borderRadius: rounded } : undefined}>
    <image data-photo={asset} href={photos[asset]} width={width} height={height} preserveAspectRatio="none" />
  </svg>;
}

export function FigureDefs({ id }: { id: string }) {
  return <defs>
    {['gray', 'black', 'green', 'red'].map(color => <marker key={color} id={`${id}-${color}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill={{ gray: '#8e8e8e', black: '#252525', green: '#537741', red: '#a9404e' }[color]} /></marker>)}
  </defs>;
}

export function FatArrow({ x, y, width = 54, height = 46, color = '#c4c4c4' }: { x: number; y: number; width?: number; height?: number; color?: string }) {
  return <path d={`M${x} ${y + height * .3}H${x + width * .5}V${y}L${x + width} ${y + height / 2}L${x + width * .5} ${y + height}V${y + height * .7}H${x}Z`} fill={color} />;
}

export function Reject({ x, y }: { x: number; y: number }) {
  return <g stroke="#ff555a" strokeWidth="9" strokeLinecap="round"><path d={`M${x - 9} ${y - 9}L${x + 9} ${y + 9}M${x + 9} ${y - 9}L${x - 9} ${y + 9}`} /></g>;
}

export function ColorCube({ x, y }: { x: number; y: number }) {
  return <g>{Array.from({ length: 216 }, (_, i) => {
    const a = i % 6, b = Math.floor(i / 6) % 6, c = Math.floor(i / 36);
    return <circle key={i} cx={x + a * 5 + c * 5} cy={y + b * 5 + a * 2 - c * 2} r="1.5" fill={`hsl(${(a * 42 + c * 27 + b * 13) % 360} 90% ${48 + b * 4}%)`} />;
  })}</g>;
}
