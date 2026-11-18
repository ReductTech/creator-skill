import { Photo, FigureDefs, FatArrow, Reject, ColorCube } from '../../FigureElements';
import type { PhotoKey } from '../../photos';

const matrix: PhotoKey[][] = [
  ['pipeline-r1-c1', 'pipeline-r1-c2', 'pipeline-r1-c3', 'pipeline-r1-c4'],
  ['pipeline-r2-c1', 'pipeline-r2-c2', 'pipeline-r2-c3', 'pipeline-r2-c4'],
  ['pipeline-r3-c1', 'pipeline-r3-c2', 'pipeline-r3-c3', 'pipeline-r3-c4'],
  ['pipeline-r4-c1', 'pipeline-r4-c2', 'pipeline-r4-c3', 'pipeline-r4-c4'],
];
const triplets: PhotoKey[][] = [
  ['triplet-r1-c1', 'triplet-r1-c2', 'triplet-r1-c3'],
  ['triplet-r2-c1', 'triplet-r2-c2', 'triplet-r2-c3'],
  ['triplet-r3-c1', 'triplet-r3-c2', 'triplet-r3-c3'],
  ['triplet-r4-c1', 'triplet-r4-c2', 'triplet-r4-c3'],
];

export function DatasetPipelinePage() {
  return <section className="ictone-figure-page ictone-dataset-page" aria-label="Dataset construction pipeline">
    <svg className="ictone-figure-svg" viewBox="0 0 2048 765" role="img" aria-label="Data collection, normalization, presets, quality filtering, and filtered triplets">
      <FigureDefs id="dataset" />
      <rect width="2048" height="765" fill="white" />
      <g fontSize="31" fill="#181818">
        <rect x="218" y="0" width="720" height="64" fill="#ededed" />
        <rect x="1290" y="0" width="584" height="64" fill="#ededed" />
        <text x="578" y="43" textAnchor="middle">Data Collection and Preprocessing</text>
        <text x="1582" y="43" textAnchor="middle">High-Quality Dataset Filtering</text>
        <path d="M42 103Q42 80 48 80H552L558 65L564 80H1067Q1074 80 1074 103M1119 103Q1119 80 1126 80H1577L1583 65L1589 80H2040Q2047 80 2047 103" fill="none" stroke="#242424" strokeWidth="1.8" />
        <text x="33" y="124">Images Collection &amp; Normalization</text>
        <text x="638" y="124">Preset Application</text>
        <text x="1135" y="125">Aesthetic &amp; Tone Style Filtering</text>
        <text x="1881" y="125" textAnchor="middle">Filtered Triplets</text>
      </g>

      <g data-stage="collection">
        <Photo asset="raw-1" x={65} y={142} width={128} height={100} rounded={17} />
        <Photo asset="raw-2" x={194} y={142} width={124} height={100} rounded={17} />
        <Photo asset="raw-3" x={105} y={225} width={133} height={100} rounded={17} />
        <Photo asset="raw-4" x={241} y={225} width={130} height={100} rounded={17} />
        <text x="339" y="185" fontSize="33">…</text>
        <path d="M219 326V375" stroke="#868686" strokeWidth="3" markerEnd="url(#dataset-gray)" />
        <rect x="90" y="378" width="258" height="74" fill="white" stroke="black" strokeWidth="4" />
        <text x="219" y="408" textAnchor="middle" fontSize="30">White Balance</text>
        <text x="219" y="442" textAnchor="middle" fontSize="30">/ Filter Removal</text>
        <path d="M219 453V500" stroke="#868686" strokeWidth="3" markerEnd="url(#dataset-gray)" />
        <Photo asset="pipeline-r1-c1" x={65} y={506} width={128} height={100} rounded={17} />
        <Photo asset="pipeline-r2-c1" x={194} y={506} width={130} height={100} rounded={17} />
        <Photo asset="pipeline-r3-c1" x={105} y={584} width={133} height={100} rounded={17} />
        <Photo asset="pipeline-r4-c1" x={241} y={584} width={125} height={100} rounded={17} />
        <text x="339" y="550" fontSize="33">…</text>
      </g>
      <FatArrow x={378} y={430} width={54} height={49} />

      <g data-stage="presets">
        <rect x="442" y="202" width="150" height="488" fill="none" stroke="#aaa" strokeWidth="1.5" strokeDasharray="8 6" />
        <text x="517" y="241" textAnchor="middle" fontSize="26">Content</text>
        {matrix.map((row, r) => row.map((asset, c) => <Photo key={asset} asset={asset} x={[454, 612, 754, 920][c]} y={[255, 366, 474, 582][r]} width={[129, 128, 127, 131][c]} height={[100, 101, 99, 100][r]} />))}
        {[{ x: 646, center: 676, label: '1' }, { x: 788, center: 818, label: '2' }, { x: 956, center: 986, label: 'k' }].map(item => <g key={item.label}>
          <ColorCube x={item.x} y={152} />
          <path d={`M${item.center} 203V250`} stroke="#868686" strokeWidth="3" markerEnd="url(#dataset-gray)" />
          <text x={item.center + 12} y="238" fontSize="28" fontStyle="italic">Preset<tspan baselineShift="sub" fontSize="19">{item.label}</tspan></text>
        </g>)}
        <text x="866" y="180" fontSize="30">…</text>
        {[308, 419, 527, 635].map(y => <text key={y} x="881" y={y} fontSize="25">…</text>)}
      </g>

      <FatArrow x={1072} y={333} width={54} height={49} />
      <FatArrow x={1072} y={486} width={54} height={49} />
      <g data-stage="quality-filtering">
        <rect x="1136" y="138" width="415" height="544" rx="47" fill="#f5faff" stroke="#292929" strokeWidth="1.8" />
        <path d="M1171 181H1523L1454 240H1244Z" fill="none" stroke="#355a91" strokeWidth="4" />
        <text x="1347" y="220" textAnchor="middle" fontSize="30">Aesthetic Scorer</text>
        <path d="M1347 241V281" stroke="#868686" strokeWidth="3" markerEnd="url(#dataset-gray)" />
        <Photo asset="pipeline-r3-c4" x={1154} y={291} width={141} height={127} />
        <Photo asset="pipeline-r4-c4" x={1204} y={313} width={142} height={127} />
        <Photo asset="pipeline-r2-c2" x={1304} y={290} width={142} height={125} />
        <Photo asset="pipeline-r1-c4" x={1353} y={309} width={141} height={126} />
        <Reject x={1521} y={408} />
        <path d="M1168 477H1523L1455 530H1243Z" fill="none" stroke="#355a91" strokeWidth="4" />
        <text x="1347" y="513" textAnchor="middle" fontSize="30">Tone Style Scorer</text>
        <path d="M1340 533V577" stroke="#868686" strokeWidth="3" markerEnd="url(#dataset-gray)" />
        <Reject x={1520} y={550} />
        <Photo asset="pipeline-r3-c3" x={1143} y={585} width={94} height={82} rounded={12} />
        <Photo asset="pipeline-r1-c3" x={1238} y={585} width={92} height={82} rounded={12} />
        <rect x="1140" y="581" width="194" height="90" rx="17" fill="none" stroke="#656565" strokeWidth="4" />
        <Photo asset="pipeline-r4-c2" x={1348} y={585} width={92} height={82} rounded={12} />
        <Photo asset="pipeline-r1-c2" x={1440} y={585} width={91} height={82} rounded={12} />
        <rect x="1344" y="581" width="192" height="90" rx="17" fill="none" stroke="#656565" strokeWidth="4" />
      </g>
      <FatArrow x={1553} y={431} width={51} height={49} />
      <g data-stage="triplets">
        <rect x="1601" y="138" width="438" height="545" fill="none" stroke="#aaa" strokeWidth="1.5" strokeDasharray="8 6" />
        {triplets.map((row, r) => row.map((asset, c) => <Photo key={asset} asset={asset} x={[1610, 1754, 1898][c]} y={[146, 254, 378, 532][r]} width={136} height={[100, 115, 112, 113][r]} />))}
        {[1678, 1822, 1966].map(x => <text key={x} x={x} y="526" textAnchor="middle" fontSize="31">⋮</text>)}
        <text x="1678" y="677" textAnchor="middle" fontSize="25">Content</text>
        <text x="1822" y="677" textAnchor="middle" fontSize="25">Reference</text>
        <text x="1966" y="677" textAnchor="middle" fontSize="25">Stylized</text>
      </g>
    </svg>
  </section>;
}
