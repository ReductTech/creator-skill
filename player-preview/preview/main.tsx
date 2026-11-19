import {useState, type ReactNode} from 'react';
import {createRoot} from 'react-dom/client';
import courses, {shukuPublishOrigin} from 'virtual:preview-catalog';
import {LocalPreviewContext} from '../src/LocalPreviewContext';
import {PublishButton} from './PublishButton';

const container = document.getElementById('root')!;
const render = (element: ReactNode) => createRoot(container).render(
  <LocalPreviewContext.Provider value={{}}>{element}</LocalPreviewContext.Provider>
);
const params = new URLSearchParams(location.search);
if (!params.has('course') || params.has('demo')) void import('./styles.css');

function Catalog() {
  const [search, setSearch] = useState('');
  const visible = courses.filter(course => `${course.title} ${course.id}`.toLowerCase().includes(search.toLowerCase()));
  return <main className="preview-catalog">
    <header><span className="preview-eyebrow">术库 / 本地开发</span><h1>课程播放器预览</h1>
      <p>选择课程查看效果，或先打开播放器交互演示。</p>
      <a className="preview-demo" href="?demo=1">打开播放器交互演示 →</a>
      <a className="preview-demo" style={{marginLeft: 24}} href="?demo=survey">预览问卷与调研 →</a>
    </header>
    <label className="preview-search">查找课程<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="输入课程名称或 UUID" /></label>
    <p className="preview-count">共 {visible.length} 门课程</p>
    <div className="preview-grid">{visible.map(course => <article key={course.id}>
      <span className="preview-eyebrow">{course.badge || '教学课程'} · {course.pages.length} 页</span>
      <h2>{course.title}</h2><p>{course.description || '本地课件预览'}</p>
      <footer>{course.ppt?.entry && <a href={`?course=${course.id}&view=ppt`}>播放课件 →</a>}
        {course.entry && <a href={`?course=${course.id}&view=guide`}>课程导览</a>}
        {!course.entry && !course.ppt?.entry && <span>尚无可预览入口</span>}</footer>
    </article>)}</div>
    {!visible.length && <p>{courses.length ? '没有匹配的课程。' : '尚无可预览课程。请按使用说明配置课程工程，然后重启预览。'}</p>}
  </main>;
}

async function openCourse(id: string) {
  const course = courses.find(course => course.id === id);
  if (!course) throw Error('没有找到课程：' + id);
  const mode = params.get('view') || params.get('mode') || (course.ppt?.entry ? 'ppt' : 'guide');
  const url = new URL(location.href);
  url.searchParams.set('mode', mode);
  history.replaceState(null, '', url);
  Reflect.set(globalThis, '__SHUKU_COURSE_ID__', course.assetId);
  Reflect.set(globalThis, '__SHUKU_ASSET_BASE__', location.origin);
  const {mountCourse} = await import('@preview/course-entry');
  mountCourse(node => <LocalPreviewContext.Provider value={{
    publish: <PublishButton course={course.id} origin={shukuPublishOrigin} />,
  }}>{node}</LocalPreviewContext.Provider>);
}

if (params.get('demo') === 'survey-template') {
  document.title = '标准问卷控件 · 本地预览';
  import('virtual:preview-survey-template').then(({SurveyTemplateDemo}) => render(<SurveyTemplateDemo />));
} else if (params.get('demo') === 'survey') {
  document.title = '问卷与调研 · 本地效果预览';
  import('./survey-demo').then(({SurveyDemo}) => render(<SurveyDemo />));
} else if (params.has('demo')) {
  import('./demo').then(({Demo}) => render(<Demo />));
} else if (params.has('course')) {
  container.textContent = '正在加载课程…';
  openCourse(params.get('course')!).catch(async error => {
    await import('./styles.css');
    render(<main className="preview-status" role="alert">
      <h1>课程加载失败</h1><p>{String(error.message || error)}</p><p>详细信息可查看终端和浏览器控制台。</p><a href="/">返回课程列表</a>
    </main>);
  });
} else render(<Catalog />);
