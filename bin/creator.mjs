#!/usr/bin/env node
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const [command, ...arguments_] = process.argv.slice(2);
const root = new URL('../', import.meta.url);
if (command === '--version' || command === '-v') {
  const {readFile} = await import('node:fs/promises');
  console.log(JSON.parse(await readFile(new URL('package.json', root), 'utf8')).version);
} else if (!command || ['help', '--help', '-h'].includes(command)) {
  console.log(`Creator Skill
  creator demo                         打开内置示例
  creator init <目录>                  创建课件工程
  creator preview [目录]               预览课件工程
  demo / preview 支持 --port <端口>、--no-open
`);
} else {
  let script;
  let args;
  if (command === 'init') {
    script = new URL('scripts/new_project.mjs', root);
    args = arguments_;
  } else if (command === 'demo' || command === 'preview') {
    script = new URL('player-preview/scripts/start.mjs', root);
    const options = arguments_.filter(value => value !== '--no-open');
    if (command === 'demo') {
      args = ['--demo', ...options];
    } else {
      const project = options[0] && !options[0].startsWith('-') ? options.shift() : '.';
      args = ['--project', project, ...options];
    }
    process.env.CREATOR_SKILL_OPEN = arguments_.includes('--no-open') ? '0' : '1';
  } else {
    console.error('未知命令，请运行 creator --help。');
    process.exit(1);
  }
  const child = spawn(process.execPath, [fileURLToPath(script), ...args], {
    stdio: 'inherit', env: process.env,
  });
  child.on('error', error => { console.error(error.message); process.exitCode = 1; });
  child.on('exit', (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
}
