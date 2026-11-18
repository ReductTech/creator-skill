import { Photo, FigureDefs, FatArrow } from '../../FigureElements';

function DatasetIcon() {
  return <g transform="translate(98 100)" fill="none" stroke="#285e8c" strokeWidth="3.6" strokeLinejoin="round">
    <rect width="70" height="51" rx="4" /><circle cx="12" cy="12" r="4" fill="#285e8c" />
    <path d="M8 43L25 19L39 35L49 25L64 43Z" fill="#285e8c" />
    <ellipse cx="76" cy="22" rx="18" ry="6" fill="white" /><path d="M58 22V49C58 57 94 57 94 49V22M58 35C58 43 94 43 94 35" fill="white" />
    <ellipse cx="76" cy="22" rx="18" ry="6" fill="white" />
  </g>;
}

function HumanIcon() {
  return <g transform="translate(1138 77)" fill="none" stroke="#414d3f" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 44V31Q-2 21 5 8Q16-1 25 8Q31 21 24 31V43M53 44V31Q45 21 52 8Q63-1 72 8Q78 21 71 31V43M5 42L-5 48V66M26 42L35 47M53 42L43 48M72 42L83 48V66" />
    <path d="M29 71V58Q21 48 28 35Q39 26 48 35Q54 48 47 58V70M29 70L17 78V92M47 70L59 78V92M5 67V60Q-2 50 3 43M72 66V59Q79 49 74 42" />
  </g>;
}

function Encoder({ x, frozen = false }: { x: number; frozen?: boolean }) {
  return <g>
    <path d={`M${x} 48L${x + 47} 142V411L${x} 503Z`} fill="#fff" fillOpacity=".35" stroke="#416696" strokeWidth="4" />
    <text transform={`translate(${x + 30} 278) rotate(-90)`} textAnchor="middle" fontSize="31">Clip Image Encoder</text>
    <rect x={x + 54} y="142" width="44" height="269" fill="#fff" fillOpacity=".4" stroke="#416696" strokeWidth="4" />
    <text transform={`translate(${x + 86} 277) rotate(-90)`} textAnchor="middle" fontSize="30">Projection Head</text>
    <text className="ictone-emoji" x={x + 1} y="57" fontSize="32">{frozen ? '❄️' : '🔥'}</text>
    <text className="ictone-emoji" x={x + 55} y="129" fontSize="31">🔥</text>
  </g>;
}

export function ScorerTrainingPage() {
  return <section className="ictone-figure-page ictone-training-page" aria-label="Two-stage tone style scorer training">
    <svg className="ictone-figure-svg" viewBox="0 0 2048 563" role="img" aria-label="Weakly supervised contrastive learning followed by preference learning">
      <FigureDefs id="training" />
      <rect width="2048" height="563" fill="white" />
      <rect x="2" y="2" width="1046" height="547" rx="29" fill="#fcf8f5" stroke="#e7dcd5" strokeWidth="1.3" strokeDasharray="2 3" />
      <rect x="1064" y="2" width="982" height="547" rx="29" fill="#f1f8ef" stroke="#acc58f" strokeWidth="1.3" strokeDasharray="2 3" />

      <g data-stage="weak-supervision">
        <text x="47" y="51" fontSize="29">Images after AWB</text>
        <text x="47" y="83" fontSize="29">and Filter Removal</text>
        <DatasetIcon />
        <path d="M145 158V184" stroke="#292929" strokeWidth="2" markerEnd="url(#training-black)" />
        <rect x="33" y="186" width="229" height="309" fill="none" stroke="#456a9a" strokeWidth="4" strokeDasharray="17 10" />
        <Photo asset="train-input-1" x={47} y={196} width={202} height={137} />
        <Photo asset="train-input-2" x={47} y={346} width={202} height={136} />
        <path d="M262 341L355 164M262 341L355 385" fill="none" stroke="#292929" strokeWidth="2" markerEnd="url(#training-black)" />
        <text transform="translate(296 246) rotate(-62)" fontSize="31" fontStyle="italic">preset<tspan baselineShift="sub" fontSize="21">m</tspan></text>
        <text transform="translate(267 377) rotate(26)" fontSize="31" fontStyle="italic" fill="#929292">preset<tspan baselineShift="sub" fontSize="21">n</tspan></text>

        <Photo asset="train-m-1" x={365} y={116} width={212} height={113} />
        <Photo asset="train-m-2" x={587} y={90} width={212} height={139} />
        <Photo asset="train-n-1" x={366} y={315} width={211} height={138} />
        <Photo asset="train-n-2" x={587} y={315} width={212} height={138} />
        <rect x="355" y="82" width="454" height="163" fill="none" stroke="#2c2a28" strokeWidth="4" strokeDasharray="18 11" />
        <rect x="355" y="304" width="454" height="159" fill="none" stroke="#8d8d85" strokeWidth="4" strokeDasharray="18 11" />
        <path d="M475 83C516 33 646 34 692 83M475 461C522 509 647 509 694 461" fill="none" stroke="#537741" strokeWidth="4" markerStart="url(#training-green)" markerEnd="url(#training-green)" />
        <text x="678" y="52" fontSize="29" fill="#537741">Positive Pair</text>
        <g fill="none" stroke="#a9404e" strokeWidth="3.8" markerStart="url(#training-red)" markerEnd="url(#training-red)">
          <path d="M474 234V311" /><path d="M693 234V311" />
          <path d="M474 234L693 311" /><path d="M693 234L474 311" />
        </g>
        <text x="306" y="277" fontSize="29" fill="#c32329">Negative Pair</text>
        <FatArrow x={813} y={251} width={42} height={50} color="#9eafc9" />
        <Encoder x={857} />
        <FatArrow x={968} y={251} width={38} height={50} color="#9eafc9" />
        <text transform="translate(1030 280) rotate(-90)" textAnchor="middle" fontSize="32">Contrastive Loss</text>
        <text x="48" y="536" fontSize="31">Stage1: Weakly Supervised Contrastive Learning</text>
      </g>

      <g data-stage="preference-learning">
        <text x="1142" y="61" fontSize="31">Human</text>
        <HumanIcon />
        <text x="1098" y="216" fontSize="28">Which is Similar ?</text>
        <Photo asset="rank-top-1" x={1074} y={241} width={100} height={66} />
        <Photo asset="rank-top-3" x={1174} y={241} width={128} height={90} />
        <Photo asset="rank-top-2" x={1125} y={297} width={61} height={113} />
        <Photo asset="rank-top-1" x={1074} y={307} width={51} height={70} />
        <Photo asset="rank-bottom-2" x={1074} y={377} width={113} height={110} />
        <Photo asset="rank-bottom-1" x={1187} y={331} width={115} height={156} />
        <FatArrow x={1312} y={253} width={46} height={50} color="#9eb9c6" />

        <Photo asset="rank-top-1" x={1370} y={124} width={148} height={96} />
        <Photo asset="rank-top-2" x={1523} y={124} width={144} height={96} />
        <Photo asset="rank-top-3" x={1671} y={121} width={148} height={99} />
        <Photo asset="rank-bottom-1" x={1375} y={243} width={120} height={180} />
        <Photo asset="rank-bottom-2" x={1501} y={296} width={190} height={127} />
        <Photo asset="rank-bottom-3" x={1698} y={243} width={121} height={180} />
        <g fill="none" strokeWidth="4">
          <path d="M1447 122C1487 84 1559 84 1593 122M1445 430C1488 465 1558 464 1593 430" stroke="#537741" markerStart="url(#training-green)" markerEnd="url(#training-green)" />
          <path d="M1599 122C1644 85 1705 85 1742 122M1600 431C1646 468 1713 467 1753 431" stroke="#a9404e" markerStart="url(#training-red)" markerEnd="url(#training-red)" />
        </g>
        <text x="1447" y="77" fontSize="29" fill="#537741">Positive Pair</text>
        <text x="1640" y="76" fontSize="29" fill="#c32329">Negative Pair</text>
        <FatArrow x={1823} y={251} width={36} height={50} color="#9eb9c6" />
        <Encoder x={1860} frozen />
        <FatArrow x={1966} y={251} width={28} height={50} color="#9eb9c6" />
        <text transform="translate(2015 280) rotate(-90)" textAnchor="middle" fontSize="32">Triplet Loss</text>
        <text x="1080" y="536" fontSize="31">Stage2: Preference Learning with Human Ranking Annotations</text>
      </g>
    </svg>
  </section>;
}
