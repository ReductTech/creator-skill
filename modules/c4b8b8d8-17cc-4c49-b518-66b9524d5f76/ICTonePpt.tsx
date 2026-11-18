import { SceneDeck, type DeckDefinition } from '@shuku/course-style/react/presentation';
import { ShowcasesPage } from './pages/ShowcasesPage/ShowcasesPage';
import { DatasetPipelinePage } from './pages/DatasetPipelinePage/DatasetPipelinePage';
import { ScorerTrainingPage } from './pages/ScorerTrainingPage/ScorerTrainingPage';
import outline from './outlines.json';

export const deck: DeckDefinition = {
  id: outline.id,
  title: outline.title,
  scenes: [
    { id: outline.pages[0].id, title: outline.pages[0].title, render: () => <ShowcasesPage /> },
    { id: outline.pages[1].id, title: outline.pages[1].title, render: () => <DatasetPipelinePage /> },
    { id: outline.pages[2].id, title: outline.pages[2].title, render: () => <ScorerTrainingPage /> },
  ],
};

export function ICTonePpt() {
  return <SceneDeck catalog={[deck]} moduleId={outline.id} assetId={outline.id} progressKey={`lesson-flow:${outline.id}`} />;
}
