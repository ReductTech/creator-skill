"""Discover and run existing local checks against a private delivery snapshot.

No cloud actions, project-global configuration writes or fixed preview ports.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from common.local_context import install_policy

SKILL = Path(__file__).resolve().parents[2]


def package_available(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def run_command(command, *, cwd, env, timeout=300, log=None):
    """Keep complete child logs on disk and a bounded diagnostic in the report."""
    process = subprocess.run(list(map(str, command)), cwd=cwd, env=env,
                             capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        Path(log).write_text(process.stdout+'\n'+process.stderr, encoding='utf-8')
    try:
        result = json.loads(process.stdout)
    except ValueError:
        result = {'message': (process.stderr or process.stdout)[-4000:]}
    return {'exitCode': process.returncode, 'result': result, 'log': str(log) if log else None}


def capabilities(*, shuku=None, media=False, buildable=True, images=False):
    """Probe actual tools and packages; Node presence alone is insufficient."""
    node = shutil.which('node')
    shuku = Path(shuku).expanduser().resolve() if shuku else Path(os.environ.get('SHUKU_ROOT') or SKILL.parent/'Shuku').resolve()
    runtime = (shuku/'tooling/course-build/scripts/build.mjs').is_file() and (shuku/'packages/course-runtime/react/index.ts').is_file()
    node_ok, typescript, babel, builder = False, False, False, False
    if node:
        script = """const {createRequire}=require('node:module'); const path=require('node:path');
const locations=JSON.parse(process.argv[1]);
function has(names, dirs){return dirs.some(dir=>{try{const r=createRequire(path.join(dir,'package.json'));for(const n of names)r.resolve(n);return true;}catch{return false;}})}
console.log(JSON.stringify({supported:Number(process.versions.node.split('.')[0])>=24,
typescript:has(['typescript'],locations),babel:has(['@babel/parser'],[locations[0]]),
preview:has(['vite','@vitejs/plugin-react','@tailwindcss/vite','react','react-dom'],[locations[0]]),
builder:has(['vite','typescript','react','react-dom','@vitejs/plugin-react','@tailwindcss/vite'],[locations[1]])}));"""
        probe = run_command([node, '-e', script, json.dumps([str(SKILL/'player-preview'), str(shuku/'tooling/course-build')])],
                            cwd=SKILL, env=os.environ.copy(), timeout=15)['result']
        node_ok = bool(probe.get('supported'))
        typescript, babel, builder = (bool(probe.get(n)) for n in ('typescript', 'babel', 'builder'))
    browser = False
    if package_available('playwright'):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as playwright:
                browser = Path(playwright.chromium.executable_path).is_file()
            browser = browser or any((Path(os.environ.get(key, ''))/relative).is_file() for key, relative in (
                ('PROGRAMFILES', 'Google/Chrome/Application/chrome.exe'),
                ('PROGRAMFILES', 'Microsoft/Edge/Application/msedge.exe'),
                ('PROGRAMFILES(X86)', 'Microsoft/Edge/Application/msedge.exe')))
        except (OSError, RuntimeError):
            pass
    preview = node_ok and bool(probe.get('preview')) and (SKILL/'player-preview/scripts/start.mjs').is_file()
    available = {'node': node_ok, 'typescript': node_ok and typescript, 'preview': preview,
                 'babel': node_ok and babel, 'runtime': runtime,
                 'build': node_ok and builder and runtime,
                 'browser': browser and package_available('PIL'),
                 'statistics': node_ok and package_available('numpy') and package_available('PIL'),
                 'pillow': package_available('PIL'),
                 'pythonAst': all(package_available(n) for n in ('tree_sitter', 'tree_sitter_typescript', 'tree_sitter_javascript')),
                 'ffmpeg': bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))}
    missing = []
    if (buildable or images) and not available['pillow']: missing.append('python-images')
    if buildable and not node_ok: missing.append('node')
    elif buildable and (not typescript or not babel or (not runtime and not preview)): missing.append('preview-packages')
    if buildable:
        if runtime and node_ok and not builder: missing.append('builder-packages')
        if not available['browser']: missing.append('browser')
    if buildable and not available['statistics']: missing.append('statistics-packages')
    if media and not available['ffmpeg']: missing.append('ffmpeg')
    return {'available': available, 'missing': list(dict.fromkeys(missing)), 'node': node,
            'shukuRoot': str(shuku) if runtime else None,
            'configurationMissing': ['shukuRoot'] if buildable and not runtime else []}


def dependency_gate(capability, *, owner=None):
    policy = install_policy(missing=capability['missing'], owner=owner)
    pending = bool(capability['missing'] and policy['installation'] in {'pending', 'allowed'})
    return {'policy': policy, 'missing': capability['missing'], 'configurationMissing': capability['configurationMissing'],
            'blockedForSetup': pending,
            'nextAction': ('ask-once-and-save-answer' if policy['askUser'] else
                           'await-saved-answer' if pending and policy['installation']=='pending' else
                           'install-authorized-dependencies-and-retry' if pending else 'continue-available-checks')}


def snapshot_files(files, root):
    result = {}
    for name, source in files.items():
        target = root/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        result[name] = target
    return result


def target_environment(root, directory):
    config = directory/'target-root.json'
    config.write_text(json.dumps({'targetRoot': str(root.resolve())}), encoding='utf-8')
    env = os.environ.copy()
    env['CREATOR_SKILL_TARGET_CONFIG'] = str(config)
    # Never inherit switches that archive/upload source or invoke platform storage.
    for key in ('SHUKU_SOURCE_PYTHON', 'SHUKU_ASSET_PYTHON', 'SHUKU_BUILD_MODE', 'SHUKU_CONFIG', 'SHUKU_COLLECTION_ID', 'SHUKU_COLLECTION_TITLE'):
        env.pop(key, None)
    return env


def node_references(files, changes, directory, capability):
    """Prefer the original, more complete Node planner when it is available."""
    if not changes:
        return files, {'engine':'node','changedFiles':0,'replacements':0,'records':[],'issues':[],'runtimeVerified':False}
    root = directory/'tree'
    root.mkdir(parents=True)
    staged = snapshot_files(files, root)
    env = target_environment(root, directory)
    if capability.get('shukuRoot'):
        env['SHUKU_ROOT'] = capability['shukuRoot']
    records, issues, changed = [], [], 0
    for prefix in sorted({'/'.join(name.split('/')[:2]) for name in changes}):
        scope = {old[len(prefix+'/assets/'):]: new[len(prefix+'/assets/'):] for old, new in changes.items()
                 if old.startswith(prefix+'/assets/') and new.startswith(prefix+'/assets/')}
        if not scope:
            issues.append({'code':'REFERENCE_SCOPE','path':prefix,'message':'转换不在所属 assets 内，需移入 assets 后重试。','blocking':True})
            continue
        mapping = directory/(prefix.replace('/', '-')+'-changes.json')
        mapping.write_text(json.dumps(scope), encoding='utf-8')
        completed = run_command([capability['node'], SKILL/'scripts/module/rewrite_staged.mjs',root,prefix,mapping], cwd=root, env=env)
        result = completed['result']
        for key, blocking in (('unresolved', True), ('unverified', False)):
            for row in result.get(key, []):
                issues.append({'code':'REFERENCE_'+key.upper(), 'path':prefix+'/'+row.get('file',''),
                    'line':row.get('line'), 'message':row.get('reason',str(row)), 'expression':row.get('expression',row.get('sourceLine')),
                    'repair':row.get('nextAction','检查实际消费者并改成完整真实路径。'), 'blocking':blocking})
        if completed['exitCode'] and not result.get('unresolved'):
            issues.append({'code':'REFERENCE_NODE_FAILED','path':prefix,'message':result.get('error',result.get('message','Node引用迁移失败。')),'blocking':True})
        if result.get('applied'):
            changed += len(result['changedFiles'])
            records.extend({'module':prefix, **row} for row in result.get('matches', []))
    return staged, {'engine':'node', 'changedFiles':changed, 'replacements':len(records),
                     'records':records, 'issues':issues, 'runtimeVerified':False}


def local_checks(files, directory, capability, evidence, *, shared=None, actions=None):
    """Run available checks on exactly the final delivery source, returning its modified copy."""
    root = directory/'checked-source'
    root.mkdir(parents=True)
    staged = snapshot_files(files, root)
    default_style = root/'modules/shared'
    if shared:
        shutil.copytree(shared, default_style)
    env = target_environment(root, directory)
    if capability.get('shukuRoot'): env['SHUKU_ROOT'] = capability['shukuRoot']
    results, issues = [], []
    available = capability['available']
    modules = [name.split('/')[1] for name in files if name.count('/')==2 and name.endswith('/outlines.json')]
    evidence.mkdir(parents=True, exist_ok=False)

    def execute(name, command, *, blocking=True, extra_env=None):
        try:
            completed = run_command(command, cwd=root, env={**env, **(extra_env or {})}, log=evidence/(name.replace('/','-')+'.log'))
            status = 'passed' if completed['exitCode']==0 else 'failed' if completed['exitCode']==1 else 'unverified'
            if completed['result'].get('errors'):
                # Capture can use exit 2 for a page that failed after browser startup.
                # Actual recorded page errors must not be downgraded to a missing dependency.
                status = 'failed'
            results.append({'check':name,'status':status, **completed})
            if status != 'passed':
                issues.append({'code':'LOCAL_CHECK_FAILED' if status=='failed' else 'LOCAL_CHECK_UNVERIFIED',
                    'path':name,'message':completed['result'].get('error',completed['result'].get('message',name+'未通过，见完整检查记录。')),
                    'blocking':blocking and status=='failed','repair':'按检查报告修复后重跑；环境错误核对依赖与配置，不重复询问已保存的安装意愿。'})
            return status, completed['result']
        except (OSError, subprocess.TimeoutExpired) as error:
            results.append({'check':name,'status':'unverified','message':str(error)})
            issues.append({'code':'LOCAL_CHECK_UNVERIFIED','path':name,'message':str(error),'blocking':False})
            return 'unverified', {}

    def source_editing(module, build_output=None):
        command = [sys.executable, SKILL/'scripts/checks/check_source_editing.py',
                   '--project', root, '--module', module,
                   '--evidence', evidence/'source-editing'/module]
        if capability.get('shukuRoot'):
            command.extend(['--shuku-root', capability['shukuRoot']])
        if build_output is not None:
            command.extend(['--build-output', build_output])
        if not available['browser']:
            command.append('--skip-browser')
        return execute(module+'/source-editing', command)

    for module in modules:
        doc = json.loads((root/'modules'/module/'outlines.json').read_text(encoding='utf-8-sig'))
        execute(module+'/metadata',[sys.executable,SKILL/'scripts/checks/validate_module.py','--module',module])
        if available['node']:
            execute(module+'/asset-imports',[capability['node'],SKILL/'scripts/checks/asset_imports.mjs','--module',module])
            execute(module+'/styles',[capability['node'],SKILL/'scripts/checks/analyze_module_styles.mjs','--module',module],blocking=False)
        else:
            results.append({'check':module+'/node-static','status':'unverified','reason':'Node不可用'})
        if available['babel']:
            status, _ = execute(module+'/edit-ids',[capability['node'],SKILL/'scripts/module/add_edit_ids.mjs',root/'modules'/module,
                '--apply','--backup-dir',directory/'id-backups'])
            if status == 'passed':
                execute(module+'/edit-id-check',[capability['node'],SKILL/'scripts/module/add_edit_ids.mjs',root/'modules'/module,'--check'])
        if available['statistics'] and doc.get('ppt',{}).get('entry'):
            execute(module+'/statistics',[sys.executable,SKILL/'scripts/analysis/page_statistics.py','--module',module],blocking=False)
        elif not doc.get('ppt',{}).get('entry'):
            results.append({'check':module+'/statistics','status':'not-applicable','reason':'原统计器面向PPT场景，此模块只有Guide或大纲'})
        buildable = bool(doc.get('entry') or doc.get('ppt',{}).get('entry'))
        if not buildable:
            results.append({'check':module+'/build-and-browser','status':'not-applicable','reason':'只有大纲，没有实现入口'})
            results.append({'check':module+'/source-editing','status':'not-applicable','reason':'只有大纲，没有可编辑的实现页面'})
            continue
        if available['typescript'] and available['runtime']:
            execute(module+'/typecheck',[capability['node'],SKILL/'scripts/checks/typecheck_course.mjs',str(root),module,capability['shukuRoot']])
        else:
            results.append({'check':module+'/typecheck','status':'unverified','reason':'缺少TypeScript或对应课程运行时'})
        if not available['build']:
            source_editing(module)
            results.append({'check':module+'/build','status':'unverified','reason':'构建依赖或Shuku运行时不可用'})
            results.append({'check':module+'/browser','status':'unverified','reason':'没有本次副本的构建产物'})
            if available.get('preview') and available['browser']:
                execute(module+'/standalone-preview', [sys.executable, SKILL/'scripts/checks/check_standalone_preview.py',
                    '--project',root,'--module',module,'--evidence',evidence/'standalone'/module,
                    '--node',capability['node']], blocking=False)
            continue
        build_output = evidence/'build'
        status, _ = execute(module+'/build',[capability['node'],Path(capability['shukuRoot'])/'tooling/course-build/scripts/build.mjs','--module',module],
            extra_env={'SHUKU_COURSE_SOURCE':str(root),'SHUKU_COURSE_OUTPUT':str(build_output)})
        source_editing(module, build_output if status == 'passed' else None)
        if status != 'passed' or not available['browser']:
            results.append({'check':module+'/browser','status':'unverified','reason':'构建未通过或浏览器依赖不可用'})
            continue
        capture = [sys.executable,SKILL/'scripts/media/capture_slides.py','--module',module,'--build-output',build_output]
        if doc.get('ppt',{}).get('entry'):
            execute(module+'/browser',capture)
            if actions:
                execute(module+'/interactions',[*capture,'--actions',actions,'--state','interactions'])
            else:
                results.append({'check':module+'/interactions','status':'unverified','reason':'已检查默认页面；未提供课程专属操作清单，未自动猜测操作'})
            execute(module+'/course-order',[sys.executable,SKILL/'scripts/checks/course_consistency.py','--module',module,'--build-output',build_output])
        if doc.get('entry'):
            execute(module+'/guide-browser',[sys.executable,SKILL/'scripts/checks/check_guide.py','--module',module,'--build-output',build_output])
            if not doc.get('ppt',{}).get('entry'):
                results.append({'check':module+'/interactions','status':'unverified','reason':'Guide已检查首屏；课程专属操作和滚动完成条件仍待验证'})
    # Keep screenshots/source-local check reports after TemporaryDirectory is removed.
    for module in modules:
        scratch = root/'modules'/module/'_scratchpad'
        if scratch.is_dir(): shutil.copytree(scratch,evidence/'pages'/module)
    def permanent(value):
        if isinstance(value,str):
            for module in modules:
                scratch=str(root/'modules'/module/'_scratchpad')
                if value.startswith(scratch):
                    return str(evidence/'pages'/module)+value[len(scratch):]
            return value.replace(str(root)+os.sep,'')
        if isinstance(value,list):return [permanent(item) for item in value]
        if isinstance(value,dict):return {key:permanent(item) for key,item in value.items()}
        return value
    results=permanent(results)
    build_checks=[r for r in results if r['check'].endswith('/build')]
    browser_checks=[r for r in results if r['check'].endswith(('/browser','/guide-browser'))]
    preview_checks=[r for r in results if r['check'].endswith('/standalone-preview')]
    editing_checks=[r for r in results if r['check'].endswith('/source-editing') and r['status']!='not-applicable']
    return {name:root/name for name in files}, {'checks':results,'issues':issues,'evidenceDirectory':str(evidence),
            'coverage':{'localBuild':bool(build_checks) and all(r['status']=='passed' for r in build_checks),
                        'rendering':bool(browser_checks) and all(r['status']=='passed' for r in browser_checks),
                        'standaloneRendering':bool(preview_checks) and all(r['status']=='passed' for r in preview_checks),
                        'sourceEditing':bool(editing_checks) and all(r['status']=='passed' and r.get('result',{}).get('coverage',{}).get('sourceEditing') is True for r in editing_checks)}}
