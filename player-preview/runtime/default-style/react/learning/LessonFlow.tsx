import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {arrangeCoursePages} from "@shuku/course-runtime/react/pageCatalog";
import {useGuidePlayback,reportGuideProgress} from '@shuku/course-runtime/react/guide/useGuidePlayback';
import { classNames } from '../utils';
import {emitCourseEvent} from "@shuku/course-runtime/react/courseRequests";
import {readCourseState,writeCourseState} from "@shuku/course-runtime/react/courseState";
import { ScrollCue } from './ScrollCue';

export type LessonFlowRevealMode = 'immediate' | 'scroll' | 'cue';

export interface LessonStepContext {
  complete: () => void;
  reset: () => void;
  isComplete: boolean;
}

export interface LessonFlowStep {
  id: string;
  revealMode?: LessonFlowRevealMode;
  /** Completing this step marks the whole module as learned. */
  completesLesson?: boolean;
  render: (context: LessonStepContext) => ReactNode;
}

export interface LessonFlowProps {
  steps: LessonFlowStep[];
  className?: string;
  cueText?: ReactNode;
  /** Stable module-level key used to restore completed lesson steps after a revisit. */
  persistenceKey?: string;
  /** Number of steps shown before completion, e.g. in an embedded demonstration. */
  initialVisibleCount?: number;
}

interface LessonProgressState { completedIds?: string[]; visibleCount?: number; completed?: boolean; }

/** Manages lesson-step visibility; individual blocks only report their own completion. */
export function LessonFlow({
  steps: sourceSteps,
  className,
  cueText = '下一段内容已经准备好，向下滚动继续学习',
  persistenceKey,
  initialVisibleCount = 1,
}: LessonFlowProps) {
  const steps = useMemo(() => arrangeCoursePages(sourceSteps), [sourceSteps]);
  const latestSteps=useRef(steps);latestSteps.current=steps;
  const pageOrder=JSON.stringify(steps.map(step=>step.id));
  const moduleKey = persistenceKey || 'lesson';
  const progressKey = `lesson-flow:${moduleKey}`;
  const requestedPage=new URLSearchParams(location.search).get('mode')==='guide'?new URLSearchParams(location.search).get('page'):null;
  const initialCount = Math.min(steps.length, Math.max(1, Number.isFinite(initialVisibleCount) ? Math.floor(initialVisibleCount) : 1));
  const restoredStart=Math.max(initialCount,steps.findIndex(step=>step.id===requestedPage)+1);
  const [completedIds, setCompletedIds] = useState<string[]>([]);
  const [visibleCount, setVisibleCount] = useState(restoredStart);
  const [, setHydrated] = useState(false);
  const [revealedIndex, setRevealedIndex] = useState<number | null>(null);
  const [cueIndex, setCueIndex] = useState<number | null>(null);
  const completedIdsRef = useRef<string[]>([]);
  const visibleCountRef = useRef(restoredStart);
  const hydratedRef = useRef(false);
  const stepRefs = useRef<Array<HTMLElement | null>>([]);
  const cueTargetRef = useRef<HTMLElement | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useGuidePlayback({pages:steps,root:rootRef,
    reveal:index=>{setVisibleCount(count=>{const next=Math.max(count,index+1);visibleCountRef.current=next;return next;});},
    restore:ids=>{
      if(JSON.stringify(completedIdsRef.current)===JSON.stringify(ids))return;
      completedIdsRef.current=ids;setCompletedIds(ids);
      const count=Math.min(steps.length,Math.max(visibleCountRef.current,...ids.map(id=>steps.findIndex(step=>step.id===id)+2)));
      visibleCountRef.current=count;setVisibleCount(count);
      writeCourseState(progressKey,{completedIds:ids,visibleCount:count});
    }});

  const reset = useCallback(() => {
    completedIdsRef.current = [];
    visibleCountRef.current = initialCount;
    setCompletedIds([]);
    setVisibleCount(initialCount);
    setRevealedIndex(null);
    setCueIndex(null);
    reportGuideProgress([]);
    writeCourseState(progressKey, { completedIds: [], visibleCount: initialCount, completed: false });
    emitCourseEvent('lesson_reset', { state_key: progressKey, state: { completedIds: [], visibleCount: initialCount, completed: false } });
  }, [progressKey, initialCount]);

  const complete = useCallback((id: string) => {
    const index = steps.findIndex((step) => step.id === id);
    if (!hydratedRef.current || index < 0 || completedIdsRef.current.includes(id)) return;
    const nextIndex = index + 1;
    const nextCompleted = [...completedIdsRef.current, id];
    const nextVisibleCount = Math.min(steps.length, Math.max(visibleCountRef.current, nextIndex + 1));
    const lessonCompleted = Boolean(steps[index]?.completesLesson);
    completedIdsRef.current = nextCompleted;
    visibleCountRef.current = nextVisibleCount;
    setCompletedIds(nextCompleted);
    reportGuideProgress(nextCompleted);
    writeCourseState(progressKey, { completedIds: nextCompleted, visibleCount: nextVisibleCount, completed: lessonCompleted });
    emitCourseEvent('lesson_progress', { state_key: progressKey, state: { completedIds: nextCompleted, visibleCount: nextVisibleCount, completed: lessonCompleted } });
    if (lessonCompleted) emitCourseEvent('module_complete', { state_key: `module:${moduleKey}`, state: { completed: true, completedIds: nextCompleted } });
    if (nextIndex < steps.length) {
      setVisibleCount(nextVisibleCount);
      setRevealedIndex(nextIndex);
    }
  }, [moduleKey, progressKey, steps]);

  useEffect(() => {
    if (revealedIndex === null) return;
    const mode = steps[revealedIndex]?.revealMode ?? 'immediate';
    const target = stepRefs.current[revealedIndex];
    if (!target) return;
    if (mode === 'scroll') {
      requestAnimationFrame(() => target.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth', block: 'start' }));
    } else if (mode === 'cue') {
      setCueIndex(revealedIndex);
    }
    setRevealedIndex(null);
  }, [revealedIndex, steps]);

  useEffect(() => {
    const steps=latestSteps.current;
    const restoredState=readCourseState<LessonProgressState>(progressKey);
    if(restoredState){
      const restoredIds=Array.isArray(restoredState.completedIds)?restoredState.completedIds.filter(id=>steps.some(step=>step.id===id)):[];
      const restoredVisible=Number(restoredState.visibleCount);
      const count=Math.min(steps.length,Math.max(restoredStart,Number.isFinite(restoredVisible)?restoredVisible:initialCount));
      completedIdsRef.current=restoredIds;visibleCountRef.current=count;
      setCompletedIds(restoredIds);setVisibleCount(count);
    }
    hydratedRef.current=true;setHydrated(true);
  }, [moduleKey, progressKey, pageOrder, initialCount, restoredStart]);

  return (
    <div className={classNames('edu-lesson-flow', className)} ref={rootRef} data-state-key={progressKey}>
      {steps.slice(0, visibleCount).map((step, index) => (
        <section
          className={classNames('edu-lesson-flow-step', index > 0 && 'is-revealed')}
          key={step.id}
          ref={(node) => { stepRefs.current[index] = node; if (index === cueIndex) cueTargetRef.current = node; }}
          data-step-id={step.id}
        >
          {step.render({
            complete: () => complete(step.id),
            reset,
            isComplete: completedIds.includes(step.id),
          })}
        </section>
      ))}
      {cueIndex !== null && (
        <ScrollCue targetRef={cueTargetRef} onDismiss={() => setCueIndex(null)}>{cueText}</ScrollCue>
      )}
    </div>
  );
}
