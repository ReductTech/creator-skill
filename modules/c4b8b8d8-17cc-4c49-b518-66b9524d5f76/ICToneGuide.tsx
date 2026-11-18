import { useLayoutEffect, useRef, useState } from 'react';
import { ShowcasesPage } from './pages/ShowcasesPage/ShowcasesPage';
import { DatasetPipelinePage } from './pages/DatasetPipelinePage/DatasetPipelinePage';
import { ScorerTrainingPage } from './pages/ScorerTrainingPage/ScorerTrainingPage';
import './figures.css';

export function ICToneGuide() {
  const frame = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    if (!frame.current) return;
    const element = frame.current;
    const update = () => setScale(Math.min(1, element.clientWidth / 1600));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return <main ref={frame} className="ictone-guide" style={{ height: 2700 * scale }}>
    {[ShowcasesPage, DatasetPipelinePage, ScorerTrainingPage].map((Page, i) => <div key={i} className="ictone-guide-canvas" style={{ top: 900 * i * scale, transform: `scale(${scale})` }}><Page /></div>)}
  </main>;
}
