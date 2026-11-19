import path from 'node:path';
import {readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {parseArgs} from 'node:util';
import {createServer} from 'vite';

const {values} = parseArgs({options: {
  project: {type: 'string'},
  context: {type: 'string'},
  port: {type: 'string'},
  demo: {type: 'boolean'},
  standalone: {type: 'boolean'},
  'ready-file': {type: 'string'},
}});
if ([values.project, values.context, values.demo].filter(Boolean).length > 1) {
  throw new Error('请选择 --project、--context 或 --demo。');
}
if (values.project || values.context || values.demo) {
  delete process.env.CREATOR_SKILL_PROJECT_ROOT;
  delete process.env.CREATOR_SKILL_TARGET_CONFIG;
  delete process.env.CREATOR_SKILL_DEMO;
}
if (values.project) process.env.CREATOR_SKILL_PROJECT_ROOT = path.resolve(values.project);
if (values.context) {
  const config = path.resolve(values.context);
  process.env.CREATOR_SKILL_TARGET_CONFIG = config;
  if (!values.standalone) {
    const sidecar = await readFile(path.join(path.dirname(config), 'context.json'), 'utf8').catch(error => {
      if (error.code !== 'ENOENT') throw error;
    });
    if (sidecar) {
      const {shukuRoot} = JSON.parse(sidecar);
      if (shukuRoot) process.env.SHUKU_ROOT = shukuRoot;
    }
  }
}
if (values.demo) process.env.CREATOR_SKILL_DEMO = '1';
if (values.standalone) process.env.CREATOR_SKILL_STANDALONE = '1';
const port = values.port === undefined ? undefined : Number(values.port);
if (port !== undefined && (!values.port.trim() || !Number.isInteger(port) || port < 0 || port > 65535)) {
  throw new Error('--port 必须是 0 至 65535 之间的整数，0 表示自动寻找可用端口。');
}
const server = await createServer({
  configFile: fileURLToPath(new URL('../vite.config.mjs', import.meta.url)),
  server: {...(port ? {port, strictPort: true} : {strictPort: false}),
    open: process.env.CREATOR_SKILL_OPEN === '1'},
});
await server.listen();
if (values['ready-file']) {
  const address = server.httpServer.address();
  await writeFile(values['ready-file'], JSON.stringify({port: address.port}), {flag: 'wx'});
}
server.printUrls();
