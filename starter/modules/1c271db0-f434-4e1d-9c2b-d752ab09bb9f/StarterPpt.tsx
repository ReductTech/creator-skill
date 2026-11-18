import type {DeckDefinition} from '@shuku/course-style/react/presentation';
import {CoverPage} from './pages/CoverPage/CoverPage';
import {ScalePage} from './pages/ScalePage/ScalePage';
import outline from './outlines.json';

const [cover, scale] = outline.pages;
export const deck: DeckDefinition = {
  id: outline.id,
  title: outline.title,
  scenes: [
    {id: cover.id, title: cover.title, render: () => <CoverPage title={cover.title} />},
    {id: scale.id, title: scale.title, render: () => <ScalePage title={scale.title} />},
  ],
};
