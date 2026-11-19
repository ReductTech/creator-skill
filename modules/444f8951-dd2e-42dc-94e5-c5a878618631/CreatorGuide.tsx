import { PiFocusPage } from './pages/PiFocusPage/PiFocusPage';
import { PiCompositionPage } from './pages/PiCompositionPage/PiCompositionPage';
import { PiHierarchyPage } from './pages/PiHierarchyPage/PiHierarchyPage';
import { PiColorPage } from './pages/PiColorPage/PiColorPage';
import { PiChartPage } from './pages/PiChartPage/PiChartPage';
import {ShukuCoCreationLoop} from './pages/ShukuCoCreationLoop';
import {ShukuWhyPage,ShukuParticipationPage,ShukuReviewPage,ShukuGrowthPage} from './pages/ShukuIntroPages/ShukuIntroPages';
import { NativeStudyPreview } from './components/NativeStudyPreview';
import './CreatorTypography.css';
import './DesignComparisonTheme.css';
import { TitlePage } from './pages/TitlePage/TitlePage';
import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import "@shuku/course-style/react/styles.css";
import "@shuku/course-style/react/ui-kit.css";
import { LearningGoalPage } from './pages/LearningGoalPage/LearningGoalPage';
import { EducationPathsPage } from './pages/EducationPathsPage/EducationPathsPage';
import { PopularSciencePage } from './pages/PopularSciencePage/PopularSciencePage';
import { ProfessionalEducationPage } from './pages/ProfessionalEducationPage/ProfessionalEducationPage';
import { IntuitiveLearningPage } from './pages/IntuitiveLearningPage/IntuitiveLearningPage';
import { MultiFormatPage } from './pages/MultiFormatPage/MultiFormatPage';
import { DiscoveryLearningPage } from './pages/DiscoveryLearningPage/DiscoveryLearningPage';
import { ProgressiveDisclosurePage } from './pages/ProgressiveDisclosurePage/ProgressiveDisclosurePage';
import { OptionalInteractionPage } from './pages/OptionalInteractionPage/OptionalInteractionPage';
import { CreationWorkflowPage } from './pages/CreationWorkflowPage/CreationWorkflowPage';
import { HumanCollaborationPage } from './pages/HumanCollaborationPage/HumanCollaborationPage';
import { PresentationComparisonPage } from './pages/PresentationComparisonPage/PresentationComparisonPage';
import { UIKitPage } from './pages/UIKitPage/UIKitPage';
import { SkillOverviewPage } from './pages/SkillOverviewPage/SkillOverviewPage';
import { SkillConstraintsPage } from './pages/SkillConstraintsPage/SkillConstraintsPage';
import { FrontendJourneyPage } from './pages/FrontendJourneyPage/FrontendJourneyPage';

function GuideCanvas({ children, pageId, anchor }: { children: ReactNode; pageId: string; anchor: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const frame = ref.current;
    if (!frame) return;
    const update = () => setScale(Math.min(1, frame.clientWidth / 1600));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(frame);
    return () => observer.disconnect();
  }, []);
  return <div ref={ref} id={pageId} data-step-id={pageId} className="cg-guide-frame" style={{ height: 900 * scale }}><div id={anchor} className="cg-guide-surface" style={{ transform: `scale(${scale})` }}>{children}</div></div>;
}
export function CreatorGuide() {
  if (new URLSearchParams(window.location.search).get('studyPreview') === 'convolution') return <NativeStudyPreview/>;
  return <main className="cg-guide">
    <GuideCanvas pageId="36a07f33-67e6-4506-ac5d-899713539767" anchor="creator-guide-title"><TitlePage /></GuideCanvas>
    <GuideCanvas pageId="c1766733-2d0c-49c0-9acf-98b5f2bf3a29" anchor="learning-goals"><LearningGoalPage /></GuideCanvas>
    <GuideCanvas pageId="abe35996-1789-4f4f-9175-8996da3ed46b" anchor="education-paths"><EducationPathsPage /></GuideCanvas>
    <GuideCanvas pageId="82deb7aa-8b4a-43b8-b809-2827b01458dd" anchor="popular-science"><PopularSciencePage /></GuideCanvas>
    <GuideCanvas pageId="db916416-104c-42c0-95ad-8c66bb75b0d0" anchor="professional-education"><ProfessionalEducationPage /></GuideCanvas>
    <GuideCanvas pageId="70a617c1-ef45-4e65-8a64-2aac06667897" anchor="intuitive-learning"><IntuitiveLearningPage /></GuideCanvas>
    <GuideCanvas pageId="46a6fcd1-df79-4298-9f8e-de7d5462a846" anchor="frontend-journey"><FrontendJourneyPage /></GuideCanvas>
    <GuideCanvas pageId="20270d29-3f3c-44f3-ac02-a8bf362ff3ec" anchor="skill-overview"><SkillOverviewPage /></GuideCanvas>
    <GuideCanvas pageId="a8ecfc2e-62b7-4f0e-8996-f5668b1e95f6" anchor="skill-constraints"><SkillConstraintsPage /></GuideCanvas>
    <GuideCanvas pageId="74e76127-5081-4903-92e9-e1bb04c27fe9" anchor="ui-kit"><UIKitPage /></GuideCanvas>
    <GuideCanvas pageId="8a1ba192-783a-4a0e-8f42-9fedb3ddce5b" anchor="multi-format"><MultiFormatPage /></GuideCanvas>
    <GuideCanvas pageId="e85b60a5-f071-44f7-9a02-70c80fce87df" anchor="human-collaboration"><HumanCollaborationPage /></GuideCanvas>
    <GuideCanvas pageId="ba969d5f-76cf-40d8-b766-2c6d3b9a9aac" anchor="presentation-comparison"><PresentationComparisonPage /></GuideCanvas>
    <GuideCanvas pageId="3e17188f-cfcc-4b53-a359-8a8eb0b6bc27" anchor="creation-workflow"><CreationWorkflowPage /></GuideCanvas>
    <GuideCanvas pageId="0a3d818c-ae0c-432a-b244-5e9a6129ec22" anchor="optional-interaction"><OptionalInteractionPage /></GuideCanvas>
    <GuideCanvas pageId="1ab0d195-ccc9-4bc8-ac9d-7d88e7240d74" anchor="progressive-disclosure"><ProgressiveDisclosurePage /></GuideCanvas>
    <GuideCanvas pageId="ad7cdb0d-2834-48ba-a537-36e0b38a1e07" anchor="discovery-learning"><DiscoveryLearningPage /></GuideCanvas>
    <GuideCanvas pageId="10f545bb-1b25-49c7-b6f5-a2c9e5046cab" anchor="pi-focus"><PiFocusPage /></GuideCanvas>
    <GuideCanvas pageId="8531d6ed-2b24-4164-980e-933cea01485a" anchor="pi-composition"><PiCompositionPage /></GuideCanvas>
    <GuideCanvas pageId="7807ce0b-86ba-45e9-aaa1-14b3f95554b4" anchor="pi-hierarchy"><PiHierarchyPage /></GuideCanvas>
    <GuideCanvas pageId="d7a79b5d-75c6-4890-8d8f-b5b596c2e346" anchor="pi-color"><PiColorPage /></GuideCanvas>
    <GuideCanvas pageId="c4aa222a-9cbb-44b8-9641-08d506a1f64d" anchor="pi-chart"><PiChartPage /></GuideCanvas>
    <GuideCanvas pageId="4f7f611a-cb68-48f9-895a-ef3ca2aa73a0" anchor="shuku-why"><ShukuWhyPage /></GuideCanvas>
    <GuideCanvas pageId="b4c2ce9c-1fc2-4b62-bba5-4b93a43beee6" anchor="shuku-participation"><ShukuParticipationPage /></GuideCanvas>
    <GuideCanvas pageId="472981bb-4fb2-464b-993a-1229db64efea" anchor="shuku-review"><ShukuReviewPage /></GuideCanvas>
    <GuideCanvas pageId="ce06694c-ba51-42af-9871-781cdaff679c" anchor="shuku-growth"><ShukuGrowthPage /></GuideCanvas>
    <GuideCanvas pageId="3ccbfdd4-22de-40ea-a6f3-613bcc668199" anchor="shuku-cocreation-loop"><ShukuCoCreationLoop /></GuideCanvas>
  </main>;
}
