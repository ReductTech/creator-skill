import {execFile} from 'node:child_process';
import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {promisify} from 'node:util';

const pack = promisify(execFile);
const packScript = fileURLToPath(new URL('../../scripts/module/package_course.py', import.meta.url));
const loopback = /^(?:127\.0\.0\.1|localhost|\[::1\])(?::\d+)?$/;

export function publishOrigin(value = 'https://shuku.reduct.cn') {
  const url = new URL(value);
  if (url.username || url.password || (url.protocol !== 'https:' && (url.protocol !== 'http:' || !loopback.test(url.host)))) {
    throw new Error('术库发布地址必须使用 HTTPS 或本机 HTTP。');
  }
  return url.origin;
}

function json(response, status, data) {
  response.writeHead(status, {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'});
  response.end(JSON.stringify(data));
}

export function publishPackage(courses, env) {
  const pending = new Map();
  const packEnv = {...process.env, SHUKU_ROOT: env.SHUKU_ROOT || '', PYTHONIOENCODING: 'utf-8'};
  // Vite's dev server sets NODE_ENV. The packer's separate production build chooses its own mode.
  delete packEnv.NODE_ENV;
  async function prepare(course) {
    try {
      const result = await pack(env.CREATOR_SKILL_PYTHON || 'python', [packScript, course.directory], {
        env: packEnv,
        maxBuffer: 1024 * 1024,
        windowsHide: true,
      }).catch(error => {
        if (!error.stdout) throw error;
        return error;
      });
      const report = JSON.parse(result.stdout);
      if (!report.outputCreated || report.status !== 'passed' || !report.uploadEligible) {
        const problem = report.issues?.find(issue => issue.severity === 'serious');
        const missing = report.dependencySetup?.missing;
        const error = missing?.length
          ? '缺少本地打包依赖：' + missing.join('、') + '。请查看检查报告。'
          : problem?.message || '本地打包未通过。';
        return {error, report: report.readableReportPath};
      }
      const archive = path.resolve(report.output);
      if (path.dirname(archive) !== path.dirname(course.directory) || path.extname(archive) !== '.zip') {
        return {error: '打包工具返回了无效的 ZIP 路径。'};
      }
      return {archive};
    } catch (error) {
      if (error.code === 'ENOENT') return {error: '找不到 Python。请安装 Python 3.10+，然后重试。'};
      return {error: '本地打包未完成。请从终端运行 course.pack 查看详细原因。'};
    }
  }

  return (request, response, next) => {
    const url = new URL(request.url || '/', 'http://localhost');
    if (url.pathname !== '/__creator/publish-package') return next();
    const host = request.headers.host || '';
    if (request.method !== 'POST' || !loopback.test(host) || request.headers.origin !== 'http://' + host ||
        request.headers['sec-fetch-site'] !== 'same-origin') {
      return json(response, 403, {error: '请在本机 Creator Skill 预览中发起发布。'});
    }
    const course = courses.find(item => item.id === url.searchParams.get('course'));
    if (!course || !(course.ppt?.entry || course.entry)) {
      return json(response, 404, {error: '找不到可发布的课件。'});
    }
    let job = pending.get(course.id);
    if (!job) {
      job = prepare(course).finally(() => pending.delete(course.id));
      pending.set(course.id, job);
    }
    void job.then(async result => {
      if (response.destroyed) return;
      if (!result.archive) return json(response, 422, result);
      const {size} = await stat(result.archive);
      response.writeHead(200, {
        'Content-Type': 'application/zip',
        'Content-Length': size,
        'Content-Disposition': 'attachment; filename="' + path.basename(result.archive) + '"',
        'Cache-Control': 'no-store',
      });
      const stream = createReadStream(result.archive);
      stream.on('error', () => response.destroy());
      response.on('close', () => stream.destroy());
      stream.pipe(response);
    }).catch(() => {
      if (response.destroyed) return;
      if (response.headersSent) return response.destroy();
      return json(response, 500, {error: '无法读取生成的 ZIP。'});
    });
  };
}
