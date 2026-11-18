import {QuestionModeProvider} from '../learning/QuestionMode';
import {PptPlayer} from '@shuku/player';
import type {SceneDeckProps,SceneDefinition,LessonContext} from "@shuku/course-runtime/react/presentation/types";
import {CourseErrorBoundary} from "@shuku/course-runtime/react/reliability/CourseErrorBoundary";
import {useCoursePlayback} from '@shuku/course-runtime/react/presentation/useCoursePlayback';
import '../styles.css';
import '../presentation.css';
import './workspace/NativePlayer.css';
export type {DeckDefinition,LessonContext,SceneDeckProps,SceneDefinition,SpeakerNote} from '@shuku/course-runtime/react/presentation/types';

function SceneContent({scene,context}:{scene:SceneDefinition;context:LessonContext}){return <>{scene.render(context)}</>;}

/** The CourseWorkspace viewer is shared by the site, published builds and exports. */
export function SceneDeck({catalog,moduleId,progressKey,getNotes}:SceneDeckProps){
 const {deck,scene,notes,capture,select,context,home}=useCoursePlayback({catalog,moduleId,progressKey,getNotes} as SceneDeckProps);
 const surface=<QuestionModeProvider mode="ppt"><div className="course-shell course-page-surface ppt-slide-surface"><CourseErrorBoundary key={scene.id} page={scene.id}><SceneContent scene={scene} context={context}/></CourseErrorBoundary></div></QuestionModeProvider>;
 if(capture)return <main className="scenedeck-capture" data-scene-deck-capture data-deck-id={deck.id} data-scene-id={scene.id} data-scene-ids={JSON.stringify(deck.scenes.map(item=>item.id))}><div className="ppt-canvas scenedeck-stage" data-ppt-canvas>{surface}</div></main>;
 return <PptPlayer title={deck.title} pages={deck.scenes.map(item=>({id:item.id,title:item.title}))} activeId={scene.id} notes={notes} slide={<div className="cw-native ppt-native-surface" data-ppt-canvas>{surface}</div>} onSelect={select}
  onHome={home}/>;
}
