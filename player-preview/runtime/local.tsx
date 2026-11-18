import {Component, useEffect, useMemo, useState, type ReactNode} from 'react';

export type SpeakerNote = {text: string; selectors: string[]};
export type LessonContext = {complete: () => void; reset: () => void; isComplete: boolean; next?: () => void};
export type SceneDefinition = {id: string; title: string; section?: string; render: (context: LessonContext) => ReactNode};
export type DeckDefinition = {id: string; title: string; subtitle?: string; scenes: SceneDefinition[]};
export type SceneDeckProps = {
  catalog: readonly [DeckDefinition, ...DeckDefinition[]];
  moduleId: string | ((deckId: string) => string);
  assetId?: string | ((deckId: string) => string);
  progressKey: string | ((deckId: string) => string);
  getNotes?: (sceneId: string, deckId?: string) => SpeakerNote[];
};

type Page = {id: string; title?: string; snippet?: string};
type PreviewContext = typeof globalThis & {
  __SHUKU_COURSE_ID__?: string;
  __SHUKU_ASSET_BASE__?: string;
  __SHUKU_PAGE_CATALOG__?: {pages: Page[]};
};
const preview = globalThis as PreviewContext;

export function moduleAssetUrl(relativePath: string): string {
  const parts = relativePath.split('/');
  if (arguments.length !== 1 || /[\\:?#]/.test(relativePath) || parts.some(part => !part || part === '.' || part === '..')) {
    throw new Error('请提供一个完整的课件素材相对路径');
  }
  if (!preview.__SHUKU_COURSE_ID__ || !preview.__SHUKU_ASSET_BASE__) throw new Error('课件素材上下文尚未加载');
  return [preview.__SHUKU_ASSET_BASE__, preview.__SHUKU_COURSE_ID__, ...parts.map(encodeURIComponent)].join('/');
}

export function courseAssetDirectory(relativePath: string): string {
  return moduleAssetUrl(relativePath) + '/';
}

export interface JsonAsset<T> {
  readonly ready: boolean;
  load(): Promise<T>;
  read(): T;
}

export function moduleJson<T>(relativePath: string): JsonAsset<T> {
  let loaded: {value: T} | undefined;
  let request: Promise<T> | undefined;
  return {
    get ready() { return loaded !== undefined; },
    load() {
      request ??= fetch(moduleAssetUrl(relativePath)).then(async response => {
        if (!response.ok) throw new Error(`素材加载失败（HTTP ${response.status}）`);
        const value = await response.json() as T;
        loaded = {value};
        return value;
      }).catch(error => {
        request = undefined;
        throw error;
      });
      return request;
    },
    read() {
      if (!loaded) throw new Error('素材尚未加载');
      return loaded.value;
    },
  };
}

function stateKey(key: string): string {
  return `creator-preview:${preview.__SHUKU_COURSE_ID__}:${key}`;
}

export function readCourseState<T>(key: string): T | undefined {
  try {
    const value = localStorage.getItem(stateKey(key));
    return value === null ? undefined : JSON.parse(value) as T;
  } catch { return undefined; }
}

export function writeCourseState(key: string, value: unknown): void {
  try { localStorage.setItem(stateKey(key), JSON.stringify(value)); } catch { /* Preview still works with storage disabled. */ }
}

export function emitCourseEvent(event: string, detail: unknown): void {
  window.dispatchEvent(new CustomEvent('creator-preview:course-event', {detail: {event, data: detail}}));
}

export async function evaluateShortAnswer(_input: unknown): Promise<{verdict: string; explanation: string}> {
  throw new Error('AI 评阅需要术库服务');
}

export function arrangeCoursePages<T extends {id: string}>(pages: readonly T[]): T[] {
  const order = new Map(preview.__SHUKU_PAGE_CATALOG__?.pages.map(({id}, index) => [id, index]));
  return [...pages].sort((left, right) => (order.get(left.id) ?? Infinity) - (order.get(right.id) ?? Infinity));
}

export class CourseErrorBoundary extends Component<{page: string; children: ReactNode}, {error?: Error}> {
  state: {error?: Error} = {};
  static getDerivedStateFromError(error: Error) { return {error}; }
  componentDidCatch(error: Error) { Reflect.set(window, '__SHUKU_CAPTURE_ERROR__', error.message); }
  render() {
    return this.state.error
      ? <p role="alert">页面加载失败：{this.state.error.message}</p>
      : this.props.children;
  }
}

export function useCoursePlayback({catalog, progressKey, getNotes}: SceneDeckProps) {
  const params = new URLSearchParams(location.search);
  const requestedDeck = params.get('deck');
  const source = requestedDeck ? catalog.find(item => item.id === requestedDeck) : catalog[0];
  if (!source) throw new Error('找不到指定的演示文稿');
  const deck = useMemo(() => ({...source, scenes: arrangeCoursePages(source.scenes)}), [source]);
  const [active, setActive] = useState(() => params.get('page') ?? deck.scenes[0]?.id);
  const key = typeof progressKey === 'function' ? progressKey(deck.id) : progressKey;
  const [completed, setCompleted] = useState(() => readCourseState<string[]>(key) ?? []);
  const capture = params.get('scenedeckCapture') === '1';
  const scene = deck.scenes.find(item => item.id === active);
  useEffect(() => {
    if (!capture) return;
    Reflect.set(window, '__SHUKU_CAPTURE__', {select(id: string) {
      Reflect.deleteProperty(window, '__SHUKU_CAPTURE_ERROR__');
      setActive(id);
    }});
    return () => { Reflect.deleteProperty(window, '__SHUKU_CAPTURE__'); };
  }, [capture]);
  useEffect(() => {
    if (!active || capture) return;
    const url = new URL(location.href);
    url.searchParams.set('page', active);
    history.replaceState(null, '', url);
  }, [active, capture]);
  if (!scene) throw new Error('找不到指定的页面');
  const notes = (getNotes?.(scene.id, deck.id) ?? []).map(note => note.text).join('\n');
  function update(ids: string[]) {
    setCompleted(ids);
    writeCourseState(key, ids);
  }
  const context = {
    isComplete: completed.includes(scene.id),
    complete: () => update([...new Set([...completed, scene.id])]),
    reset: () => update(completed.filter(id => id !== scene.id)),
    next: () => setActive(deck.scenes[deck.scenes.indexOf(scene) + 1]?.id ?? scene.id),
  };
  return {deck, scene, notes, capture, select: setActive, context, home: () => location.assign('/'), edit: () => {}};
}
