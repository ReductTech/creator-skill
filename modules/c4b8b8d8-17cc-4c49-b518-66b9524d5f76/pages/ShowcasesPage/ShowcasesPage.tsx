import { Photo } from '../../FigureElements';
import type { PhotoKey } from '../../photos';

const cases: { content: PhotoKey; reference: PhotoKey; stylized: PhotoKey }[] = [
  { content: 'case-1-content', reference: 'case-1-reference', stylized: 'case-1-stylized' },
  { content: 'case-2-content', reference: 'case-2-reference', stylized: 'case-2-stylized' },
  { content: 'case-3-content', reference: 'case-3-reference', stylized: 'case-3-stylized' },
  { content: 'case-4-content', reference: 'case-4-reference', stylized: 'case-4-stylized' },
  { content: 'case-5-content', reference: 'case-5-reference', stylized: 'case-5-stylized' },
  { content: 'case-6-content', reference: 'case-6-reference', stylized: 'case-6-stylized' },
  { content: 'case-7-content', reference: 'case-7-reference', stylized: 'case-7-stylized' },
  { content: 'case-8-content', reference: 'case-8-reference', stylized: 'case-8-stylized' },
];

export function ShowcasesPage() {
  return <section className="ictone-figure-page ictone-showcases-page" aria-label="Tone style transfer showcases">
    <svg className="ictone-figure-svg" viewBox="0 0 2016 1052" role="img" aria-label="Eight independent content-reference-stylized triplets">
      <rect width="2016" height="1052" fill="white" />
      {cases.map((item, i) => {
        const x = [0, 508, 1015, 1522][i % 4], y = i < 4 ? 0 : 535;
        return <g key={item.content} data-case={i + 1}>
          <Photo asset={item.content} x={x} y={y} width={163} height={255} />
          <Photo asset={item.reference} x={x} y={y + 261} width={163} height={i < 4 ? 255 : 256} />
          <Photo asset={item.stylized} x={x + 170} y={y} width={325} height={i < 4 ? 516 : 517} />
        </g>;
      })}
    </svg>
  </section>;
}
