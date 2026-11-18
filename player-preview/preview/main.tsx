import React, {useState, type ComponentType} from 'react';
import {createRoot} from 'react-dom/client';
import courses from 'virtual:preview-catalog';
import './styles.css';

const root = createRoot(document.getElementById('root')!);
const params = new URLSearchParams(location.search);

function Catalog() {
  const [search, setSearch] = useState('');
  const visible = courses.filter(course => `${course.title} ${course.id}`.toLowerCase().includes(search.toLowerCase()));
  return <main className="preview-catalog">
    <header><span className="preview-eyebrow">Creator Paper</span><h1>论文图预览</h1>
      <p>选择图组，逐页查看或浏览整套论文配图。</p>
    </header>
    <label className="preview-search">查找图组<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="输入图组名称或 UUID" /></label>
    <p className="preview-count">共 {visible.length} 个图组</p>
    <div className="preview-grid">{visible.map(course => <article key={course.id}>
      <span className="preview-eyebrow">{course.badge || '论文配图'} · {course.pages.length} 页</span>
      <h2>{course.title}</h2><p>{course.description || '可编辑论文配图'}</p>
      <footer>{course.ppt?.entry && <a href={`?course=${course.id}&view=ppt`}>逐页查看 →</a>}
        {course.entry && <a href={`?course=${course.id}&view=guide`}>查看整套图 →</a>}
        {!course.entry && !course.ppt?.entry && <span>尚无可预览入口</span>}</footer>
    </article>)}</div>
    {!visible.length && <p>{courses.length ? '没有匹配的图组。' : '尚无可预览图组。请在 modules/ 中添加完整的图组源码与 outlines.json。'}</p>}
  </main>;
}

async function openCourse(id: string) {
  const course = courses.find(course => course.id === id);
  if (!course) throw Error('没有找到图组：' + id);
  document.title = course.title + ' · 本地预览';
  Reflect.set(globalThis, '__SHUKU_COURSE_ID__', course.assetId);
  Reflect.set(globalThis, '__SHUKU_ASSET_BASE__', location.origin);
  Reflect.set(globalThis, '__SHUKU_PAGE_CATALOG__', course);
  // Load only the selected course. Full page navigation keeps course CSS and state isolated.
  const module = await import(/* @vite-ignore */ `/@id/__x00__virtual:preview-course:${course.id}`);
  const mode = params.get('view') || (course.ppt?.entry ? 'ppt' : 'guide');
  const url = new URL(location.href);
  url.searchParams.set('mode', mode);
  history.replaceState(null, '', url);
  const notes = (id: string) => {
    const page = course.pages.find(page => page.id === id);
    return typeof page?.snippet === 'string' ? [{text: page.snippet, selectors: []}] : [];
  };
  if (mode === 'guide') {
    const guide = await module.loadGuide();
    const Guide = guide?.[module.guideExport] as ComponentType | undefined;
    if (!Guide) throw Error('Guide 入口必须导出与 TSX 文件名相同的命名组件。');
    root.render(<Guide />);
  } else if (mode === 'ppt') {
    const [presentation, {SceneDeck}] = await Promise.all([module.loadPresentation(), import('@preview/runtime')]);
    await import('@preview/runtime-styles');
    if (!presentation?.deck) throw Error('PPT 入口必须导出 deck。');
    root.render(<SceneDeck catalog={[{...presentation.deck, id: course.id}]} moduleId={course.id}
      assetId={course.assetId} progressKey={'shuku-preview:' + course.id} getNotes={notes} />);
  } else throw Error('不支持的播放模式：' + mode);
}

if (params.get('demo') === 'survey-template') {
  document.title = '标准问卷控件 · 本地预览';
  import('./survey-template-demo').then(({SurveyTemplateDemo}) => root.render(<SurveyTemplateDemo />));
} else if (params.get('demo') === 'survey') {
  document.title = '问卷与调研 · 本地效果预览';
  import('./survey-demo').then(({SurveyDemo}) => root.render(<SurveyDemo />));
} else if (params.has('demo')) {
  import('./demo').then(({Demo}) => root.render(<Demo />));
} else if (params.has('course')) {
  root.render(<p className="preview-status">正在加载论文图…</p>);
  openCourse(params.get('course')!).catch(error => root.render(<main className="preview-status" role="alert">
    <h1>图组加载失败</h1><p>{String(error.message || error)}</p><p>详细信息可查看终端和浏览器控制台。</p><a href="/">返回图组列表</a>
  </main>));
} else root.render(<Catalog />);
