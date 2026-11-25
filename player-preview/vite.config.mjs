import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {defineConfig, loadEnv, normalizePath} from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';
import {readCourses} from './scripts/courses.mjs';
import {publishOrigin, publishPackage} from './scripts/publish-package.mjs';

const root = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig(({mode}) => {
  const env = {...loadEnv(mode, root, ''), ...process.env};
  let targetRoot;
  if (env.CREATOR_SKILL_DEMO === '1') {
    targetRoot = path.resolve(root, '../starter');
  } else if (env.CREATOR_SKILL_PROJECT_ROOT) {
    targetRoot = path.resolve(env.CREATOR_SKILL_PROJECT_ROOT);
    if (!fs.statSync(targetRoot, {throwIfNoEntry: false})?.isDirectory()) {
      throw Error(`预览工程目录不存在：${targetRoot}`);
    }
  }
  targetRoot ??= path.resolve(root, '../starter');
  const coursesRoot = targetRoot && (fs.existsSync(path.join(targetRoot, 'modules')) ? path.join(targetRoot, 'modules') : targetRoot);
  const bundledRuntime = path.join(root, 'runtime/course-runtime');
  const bundledStyle = path.join(root, 'runtime/default-style');
  const shukuRoot = env.SHUKU_ROOT && path.resolve(root, env.SHUKU_ROOT);
  const useExternalRuntime = !!shukuRoot && env.CREATOR_SKILL_STANDALONE !== '1';
  const runtime = useExternalRuntime ? path.join(shukuRoot, 'packages/course-runtime') : bundledRuntime;
  if (!fs.existsSync(path.join(runtime, 'react/index.ts'))) {
    throw Error(`未找到 Shuku 课程运行时：${runtime}`);
  }
  const externalStyle = useExternalRuntime && path.join(shukuRoot, 'packages/course-styles/default');
  const platformStyle = externalStyle && fs.existsSync(path.join(externalStyle, 'style.json'))
    ? externalStyle : bundledStyle;
  const surveyTemplate = path.join(platformStyle, 'react/learning/SurveyTemplate.tsx');
  const surveyExample = path.join(platformStyle, 'examples/survey/SurveyExample.tsx');
  const style = [path.join(targetRoot, 'shared'), path.join(coursesRoot, 'shared')]
    .find(directory => fs.existsSync(path.join(directory, 'style.json'))) || bundledStyle;
  const styleManifest = JSON.parse(fs.readFileSync(path.join(style, 'style.json'), 'utf8'));
  const courses = readCourses(coursesRoot);
  const shukuPublishOrigin = publishOrigin(env.CREATOR_SKILL_SHUKU_ORIGIN);
  const localPlayer = normalizePath(path.join(root, 'src/index.ts'));
  const sharedRoot = normalizePath(style);
  const plugin = {
    name: 'local-course-preview', enforce: 'pre',
    async resolveId(id, importer) {
      if (id.startsWith('virtual:preview-')) return '\0' + id;
      if (id === 'virtual:creator-skill-documents') return '\0preview-documents';
      if (id === 'virtual:shuku-course' || id === 'virtual:shuku-style') return '\0' + id;
      if (importer && (id.startsWith('.') || path.isAbsolute(id))) {
        const target = normalizePath(path.resolve(path.dirname(importer.split('?')[0]), id));
        if (target === sharedRoot || target.startsWith(sharedRoot + '/')) {
          return this.resolve(target, importer, {skipSelf: true});
        }
      }
      // Courses and the external runtime must resolve packages from this project's node_modules.
      if (importer && !id.startsWith('.') && !id.startsWith('/') && !id.startsWith('\0') &&
          !id.startsWith('virtual:') && !id.startsWith('node:') && !/^[A-Za-z]:/.test(id)) {
        return this.resolve(id, path.join(root, 'package.json'), {skipSelf: true});
      }
    },
    load(id) {
      if (id === '\0virtual:preview-survey-template') {
        return `export {SurveyTemplateDemo} from ${JSON.stringify(normalizePath(path.join(root, 'preview/survey-template-demo.tsx')))};`;
      }
      if (id === '\0virtual:preview-catalog') return `export default ${JSON.stringify(courses.map(({directory, ...course}) => course))};
        export const shukuPublishOrigin = ${JSON.stringify(shukuPublishOrigin)};`;
      if (id === '\0virtual:shuku-course') {
        const loaders = courses.map(course =>
          `${JSON.stringify(course.id)}: () => import(${JSON.stringify('virtual:preview-course:' + course.id)})`);
        const guideExports = Object.fromEntries(courses
          .filter(course => course.entry)
          .map(course => [course.id, path.basename(course.entry, path.extname(course.entry))]));
        return `import courses from 'virtual:preview-catalog';
          const selectedId = new URLSearchParams(location.search).get('course');
          const course = courses.find(item => item.id === selectedId);
          const loaders = {${loaders.join(',')}};
          const load = loaders[selectedId];
          export const metadata = {...course, asset_id: course.assetId,
            modes: [...(course.entry ? ['guide'] : []), ...(course.ppt?.entry ? ['ppt'] : [])]};
          export const guideExport = ${JSON.stringify(guideExports)}[selectedId] || '';
          export const loadGuide = async () => (await load()).loadGuide();
          export const loadPresentation = async () => (await load()).loadPresentation();`;
      }
      if (id === '\0virtual:shuku-style') {
        const source = entry => JSON.stringify(normalizePath(path.join(style, entry)));
        return (styleManifest.bootstrap ? `import ${source(styleManifest.bootstrap)};\n` : '') +
          (styleManifest.presentation
            ? `export const loadStylePresentation = () => import(${source(styleManifest.presentation)});`
            : 'export const loadStylePresentation = async () => null;');
      }
      if (id === '\0preview-documents') {
        const creator = courses.find(course => course.alias === 'creator-guide');
        const file = creator && path.join(creator.directory, 'assets/creator-skill-documents.json');
        return `export default ${file && fs.existsSync(file) ? JSON.stringify(JSON.parse(fs.readFileSync(file, 'utf8')).documents || []) : '[]'};`;
      }
      if (id.startsWith('\0virtual:preview-course:')) {
        const course = courses.find(course => course.id === id.slice('\0virtual:preview-course:'.length));
        if (!course) throw Error('未知课程');
        const imports = [];
        for (const [key, entry] of [['loadGuide', course.entry], ['loadPresentation', course.ppt?.entry]]) {
          imports.push(entry
            ? `export const ${key}=()=>import(${JSON.stringify(normalizePath(path.join(course.directory, entry)))});`
            : `export const ${key}=async()=>null;`);
        }
        return imports.join('\n');
      }
    },
    transform(css, id) {
      const playbackCss = normalizePath(path.join(root, 'runtime/styles.css'));
      if (normalizePath(id.split('?')[0]) !== playbackCss) return;
      const sources = [...new Set([coursesRoot, style])];
      return css + '\n' + sources.map(source => `@source ${JSON.stringify(normalizePath(source))};`).join('\n');
    },
    configureServer(server) {
      server.middlewares.use(publishPackage(courses, env));
      server.watcher.add(courses.map(course => path.join(course.directory, 'outlines.json')));
      server.watcher.on('change', file => {
        if (file.endsWith('outlines.json')) void server.restart();
      });
      server.middlewares.use((request, _response, next) => {
        const url = new URL(request.url || '/', 'http://localhost');
        // Single-argument moduleAssetUrl uses the current course identity.
        let pathname;
        try { pathname = decodeURIComponent(url.pathname); } catch { return next(); }
        for (const course of courses) {
          const prefix = `/${course.assetId}/`;
          if (pathname.startsWith(prefix)) {
            const base = path.join(course.directory, 'assets');
            const file = path.resolve(base, pathname.slice(prefix.length));
            if (file.startsWith(base + path.sep) && fs.existsSync(file) && fs.statSync(file).isFile()) {
              // Serve course assets directly: Windows drive URLs can otherwise
              // fall through Vite's SPA fallback and return index.html as an image.
              const mime = {'.webp':'image/webp','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.svg':'image/svg+xml','.json':'application/json','.glb':'model/gltf-binary'};
              _response.setHeader('Content-Type', mime[path.extname(file).toLowerCase()] || 'application/octet-stream');
              _response.setHeader('Cache-Control', 'no-cache');
              _response.end(fs.readFileSync(file));
              return;
            }
            break;
          }
        }
        next();
      });
    },
  };
  return {
    root, envDir: root, publicDir: false,
    cacheDir: env.CREATOR_SKILL_PREVIEW_CACHE || path.join(root, 'node_modules/.vite'),
    plugins: [plugin, react(), tailwind()],
    resolve: {
      dedupe: ['react', 'react-dom', 'lucide-react'],
      alias: [
        {find: '@preview/survey-template', replacement: normalizePath(surveyTemplate)},
        {find: '@preview/survey-example', replacement: normalizePath(surveyExample)},
        {find: '@preview/course-entry', replacement: normalizePath(path.join(root, 'runtime/entry.tsx'))},
        {find: '@shuku/course-runtime', replacement: normalizePath(runtime)},
        {find: '@shuku/course-style', replacement: normalizePath(style)},
        {find: '@shuku/player', replacement: localPlayer},
      ],
    },
    server: {
      host: '127.0.0.1', port: 5174, strictPort: true,
      fs: {strict: true, allow: [root, style, coursesRoot, runtime, platformStyle]},
      proxy: env.SHUKU_API_URL ? {'/api': {target: env.SHUKU_API_URL, changeOrigin: true}} : undefined,
    },
  };
});
