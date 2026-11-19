"""Check Shuku visual editing against source, a completed build and a real iframe.

Never uploads, publishes or writes course source. Replacement probes stay in memory.
Missing runtime/build/browser evidence is unverified, not a successful compatibility check.
"""
import argparse
import base64
import importlib
import io
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlencode, urlparse
from uuid import uuid4

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS / 'common')]
from _common import resolve_module

LEGACY = {'shuku-visual-edits.json', 'shuku-visual-edits-runtime.js'}
EXCLUDED = {'.git', '.shuku', 'node_modules', 'shared', 'vendor', 'dist', '_scratchpad', '__pycache__'}


def source_inventory(project, course):
    """Do not follow links or read asset bytes just to discover source bindings."""
    files, legacy = {}, []
    for directory, folders, names in os.walk(course, followlinks=False):
        parent = Path(directory)
        for name in [*folders, *names]:
            path = parent / name
            if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                raise ValueError('源码包含链接或 junction，未读取：' + str(path))
        folders[:] = [name for name in folders if name not in EXCLUDED]
        for name in names:
            path = parent / name
            logical = path.relative_to(project).as_posix()
            if name in LEGACY:
                legacy.append(logical)
            if path.suffix == '.tsx' or name in LEGACY:
                files[logical] = {'object_key': logical}
    return files, legacy


def load_runtime(shuku):
    if shuku is None:
        raise ImportError('未配置 Shuku Python 运行时；使用 --shuku-root 指定。')
    shuku = Path(shuku).resolve()
    paths = [shuku / 'backend/src/shuku/modules/authoring/source_editor.py',
             shuku / 'shared/courses/release_support.py',
             shuku / 'shared/courses/source_editor/runtime.js']
    if not all(path.is_file() for path in paths):
        raise ImportError('Shuku 缺少 SourceEditor、能力判定或 iframe 编辑运行时。')
    sys.path[:0] = [str(shuku), str(shuku / 'backend/src')]
    editor = importlib.import_module('shuku.modules.authoring.source_editor')
    support = importlib.import_module('shared.courses.release_support')
    if not all(Path(module.__file__).resolve().is_relative_to(shuku) for module in (editor, support)):
        raise ImportError('进程中已加载其他 Shuku 版本，请在独立进程运行本检查。')
    return editor.SourceEditor, support.detect_build, paths[2].read_text(encoding='utf-8')


def build_artifact(output, module_id):
    if output is None:
        return None
    root = Path(output).resolve()
    candidates = []
    for manifest in [root / module_id / 'artifact-manifest.json',
                     *(root / module_id).glob('*/artifact-manifest.json')]:
        if not manifest.is_file():
            continue
        doc = json.loads(manifest.read_text(encoding='utf-8'))
        directory = manifest.parent.resolve()
        if not directory.is_relative_to(root):
            raise ValueError('构建产物路径超出 --build-output。')
        if doc.get('module_id') == module_id and (directory / 'index.html').is_file():
            candidates.append((manifest.stat().st_mtime_ns, directory))
    return max(candidates)[1] if candidates else None


def replacements(Editor, files, read, root, pages, model):
    """Reparse replaced source to verify bindings survive; never persist these bytes."""
    checks = []
    def fresh(changes):
        overlay = {**files, **{key: {'object_key': key} for key in changes}}
        return Editor(overlay, lambda key: changes[key] if key in changes else read(key), root, pages)
    text = next((b for b in model.bindings.values() if b.kind == 'text' and b.text.strip()), None)
    if text:
        value = '文字替换验证 ' + uuid4().hex
        changed = model.apply({'schema': 2, 'release_id': 'local-check', 'changes': [
            {'id': text.uid, 'kind': 'text', 'original': text.text, 'text': value}]})
        replaced = fresh(changed)
        if replaced.bindings[text.uid].text != value:
            raise ValueError('文字替换后无法通过同一 ID 读取新值。')
        restored = replaced.apply({'schema': 2, 'release_id': 'local-check', 'changes': [
            {'id': text.uid, 'kind': 'text', 'original': value, 'text': text.text}]})
        if fresh({**changed, **restored}).bindings[text.uid].text != text.text:
            raise ValueError('文字替换无法恢复原始文本。')
        checks.append({'check': 'textRoundtrip', 'status': 'passed', 'id': text.uid})
    else:
        checks.append({'check': 'textRoundtrip', 'status': 'not-applicable', 'reason': '没有可替换的非空静态文字。'})
    image = next((b for b in model.bindings.values() if b.kind == 'image'), None)
    if image:
        from PIL import Image
        def webp(color):
            stream = io.BytesIO()
            Image.new('RGB', (2, 2), color).save(stream, format='WEBP')
            return stream.getvalue()
        overlay = {}
        first = webp('white')
        for raw in (first, webp('black'), first):
            current = fresh(overlay)
            changed = current.apply({'schema': 2, 'release_id': 'local-check', 'changes': [
                {'id': image.uid, 'kind': 'image', 'original': current.bindings[image.uid].text,
                 'src': 'data:image/webp;base64,' + base64.b64encode(raw).decode()}]})
            if not any(value == raw for value in changed.values()):
                raise ValueError('图片替换未返回对应的 WebP 资源。')
            overlay.update(changed)
            if fresh(overlay).bindings[image.uid].kind != 'image':
                raise ValueError('图片替换后丢失原编辑 ID。')
        checks.append({'check': 'imageRoundtrip', 'status': 'passed', 'id': image.uid,
                       'scope': '内存中两张测试 WebP 往返替换；不改写原图或源码。'})
    else:
        checks.append({'check': 'imageRoundtrip', 'status': 'not-applicable', 'reason': '没有可替换的静态图片绑定。'})
    return checks


def json_for_script(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def iframe_selection(output, artifact, doc, bindings, runtime, evidence, *, max_pages=12, timeout_ms=10000):
    from media.capture_slides import browser_session
    from playwright.sync_api import TimeoutError as BrowserTimeout
    kinds = {b['kind'] for b in bindings if b['kind'] == 'image' or b.get('text', '').strip()}
    nonce = uuid4().hex
    selected, visited, snapshots, errors = {}, [], [], []
    deadline = time.monotonic() + 90
    html = (artifact / 'index.html').read_text(encoding='utf-8')
    injected = '<script>window.__SHUKU_VISUAL_BOOT__={nonce:' + json_for_script(nonce) + '};</script><script>' + runtime + '</script>'
    if '<head>' not in html:
        raise ValueError('构建入口缺少 head，无法注入实际编辑运行时。')
    frame_html = html.replace('<head>', '<head>' + injected, 1)
    with browser_session(build_output=output) as (context, address):
        entry = address.rstrip('/') + '/' + artifact.relative_to(Path(output).resolve()).as_posix() + '/index.html'
        parent_url = address.rstrip('/') + '/__creator_source_editing__/parent.html'
        parent_html = '''<!doctype html><meta charset="utf-8"><iframe id="course" style="border:0;width:1600px;height:900px"></iframe><script>
const nonce=NONCE,model=MODEL,frame=document.getElementById('course');
window.probe={snapshots:[],selected:[]};
addEventListener('message',event=>{const m=event.data;if(event.source!==frame.contentWindow||m?.channel!=='source-demo'||m.nonce!==nonce)return;
if(m.action==='bridge-ready')frame.contentWindow.postMessage({channel:'source-demo',nonce,action:'configure',editing:true,model:{bindings:model,patches:[]}},'*');
if(m.action==='snapshot')probe.snapshots.push({rendered:m.rendered,coverage:m.coverage});
if(m.action==='selected')probe.selected.push(m.selection);
});</script>'''.replace('NONCE', json_for_script(nonce)).replace('MODEL', json_for_script(bindings))
        context.route(lambda url: url.split('?')[0] == parent_url,
                      lambda route: route.fulfill(status=200, content_type='text/html', body=parent_html))
        context.route(lambda url: url.split('?')[0] == entry,
                      lambda route: route.fulfill(status=200, content_type='text/html', body=frame_html))
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(parent_url, wait_until='domcontentloaded', timeout=timeout_ms)
        modes = json.loads((artifact / 'course.json').read_text(encoding='utf-8')).get('modes', [])
        mode = 'ppt' if 'ppt' in modes else 'guide'
        for item in doc['pages'][:max_pages]:
            if set(selected) == kinds or time.monotonic() >= deadline:
                break
            visited.append(item['id'])
            page.evaluate('src=>{probe.snapshots=[];probe.selected=[];document.getElementById("course").src=src;}',
                          entry + '?' + urlencode({'mode': mode, 'page': item['id']}))
            try:
                # A lazy loader may report rendered=true, marked=0 first. Never fail on that transient snapshot.
                page.wait_for_function('probe.snapshots.some(s=>s.rendered&&s.coverage?.marked>0)', timeout=timeout_ms)
            except BrowserTimeout:
                snapshots.append({'page': item['id'], 'snapshots': page.evaluate('probe.snapshots')})
                continue
            frame = page.frame_locator('#course')
            candidates = frame.locator('[shuku-edit-id]').evaluate_all('''(elements,model)=>{
const byId=new Map(model.map(b=>[b.id,b])),counts=new Map();for(const e of elements){const id=e.getAttribute('shuku-edit-id');counts.set(id,(counts.get(id)||0)+1);}
return elements.flatMap(e=>{const id=e.getAttribute('shuku-edit-id'),b=byId.get(id);if(!b||counts.get(id)!==1)return [];
const r=e.getBoundingClientRect(),s=getComputedStyle(e),x=Math.max(1,Math.min(innerWidth-1,r.x+r.width/2)),y=Math.max(1,Math.min(innerHeight-1,r.y+r.height/2));
if(!r.width||!r.height||r.bottom<=0||r.right<=0||r.top>=innerHeight||r.left>=innerWidth||s.visibility==='hidden'||s.display==='none'||s.opacity==='0')return [];
if(b.kind==='text'&&!e.hasAttribute('data-shuku-editable-text'))return [];
if(b.kind==='image'&&(e.tagName!=='IMG'||!e.complete||!e.naturalWidth))return [];
const hit=document.elementFromPoint(x,y);if(hit?.closest('[shuku-edit-id]')?.getAttribute('shuku-edit-id')!==id)return [];
return [{id,kind:b.kind}];});}''', bindings)
            for candidate in candidates:
                kind, uid = candidate['kind'], candidate['id']
                if kind in selected or kind not in kinds:
                    continue
                try:
                    frame.locator('[shuku-edit-id="' + uid + '"]').click(timeout=1500)
                    page.wait_for_function('c=>probe.selected.some(s=>s.id===c.id&&s.kind===c.kind)', arg=candidate, timeout=1500)
                    selected[kind] = {'id': uid, 'page': item['id']}
                    if evidence:
                        page.screenshot(path=str(evidence / ('iframe-' + kind + '.png')), timeout=timeout_ms)
                    page.keyboard.press('Escape')
                except BrowserTimeout:
                    continue
            snapshots.append({'page': item['id'], 'snapshots': page.evaluate('probe.snapshots')})
        page.close()
    return {'check': 'iframeSelection', 'status': 'failed' if errors else 'passed' if set(selected) == kinds else 'unverified',
            'selected': selected, 'requiredKinds': sorted(kinds), 'pagesChecked': visited,
            'pageLimit': max_pages, 'snapshots': snapshots, 'errors': errors,
            'reason': None if set(selected) == kinds else '默认状态未找到全部可选样本；需要课程专属操作或增加 --max-pages 后复查。'}


def check(project, module, *, shuku=None, output=None, evidence=None, skip_browser=False, max_pages=12, timeout_ms=10000):
    project = Path(project).resolve()
    course, doc = resolve_module(module, project)
    course = course.resolve()
    if not course.is_relative_to(project):
        raise ValueError('课程不属于指定工程。')
    checks, errors, unverified = [], [], []
    report = {'module': doc['id'], 'checks': checks, 'errors': errors, 'unverified': unverified,
              'sourceFilesWritten': False, 'scope': '本地源码、构建能力和隔离 iframe；不代替服务器入库、审核、发布或全部交互验收。'}
    def finish():
        report['status'] = 'failed' if any(c['status'] == 'failed' for c in checks) or errors else 'unverified' if any(c['status'] == 'unverified' for c in checks) else 'passed'
        report['coverage'] = {'sourceEditing': report['status'] == 'passed'}
        if evidence:
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return report
    try:
        files, legacy = source_inventory(project, course)
    except ValueError as error:
        checks.append({'check': 'sourcePaths', 'status': 'failed', 'reason': str(error)})
        return finish()
    checks.append({'check': 'legacyScripts', 'status': 'failed' if legacy else 'passed', 'paths': legacy})
    if legacy:
        errors.append('存在旧版编辑脚本；须先迁移有效修改并移除旧依赖，不能直接删除以丢弃用户编辑。')
        return finish()
    try:
        Editor, detect, runtime = load_runtime(shuku)
    except (ImportError, SyntaxError) as error:
        checks.append({'check': 'shukuRuntime', 'status': 'unverified', 'reason': str(error)})
        unverified.append(str(error))
        return finish()
    pages = [p['id'] for p in doc['pages']]
    root = course.relative_to(project).as_posix()
    def read(key):
        path = (project / key).resolve()
        if not path.is_relative_to(course):
            raise ValueError('编辑器请求读取课程范围外的源码。')
        return path.read_bytes()
    model = Editor(files, read, root, pages)
    counts = {kind: sum(b.kind == kind for b in model.bindings.values()) for kind in ('text', 'image')}
    checks.append({'check': 'sourceBindings', 'status': 'passed' if model.bindings and not model.blocked else 'failed', **counts, 'blocked': model.blocked})
    artifact = build_artifact(output, doc['id'])
    if artifact:
        built = json.loads((artifact / 'course.json').read_text(encoding='utf-8'))
        if built.get('id') != doc['id'] or [p['id'] for p in built.get('pages', [])] != pages:
            checks.append({'check': 'buildIdentity', 'status': 'failed', 'reason': '构建课程或页序与当前源码不同。'})
        flags = detect(project, artifact, module_prefix=root, source_available=True)
        checks.append({'check': 'supports_source_edit', 'status': 'passed' if flags.get('supports_source_edit') is True else 'failed', 'value': flags.get('supports_source_edit')})
        report['artifact'] = str(artifact)
    else:
        checks.append({'check': 'supports_source_edit', 'status': 'unverified', 'reason': '没有本次课程的完整构建产物。'})
    if model.bindings and not model.blocked:
        try:
            checks.extend(replacements(Editor, files, read, root, pages, model))
        except ImportError as error:
            checks.append({'check': 'replacementRoundtrip', 'status': 'unverified', 'reason': str(error)})
        except Exception as error:
            checks.append({'check': 'replacementRoundtrip', 'status': 'failed', 'reason': str(error)})
    if not any(c['status'] == 'failed' for c in checks) and artifact and not skip_browser:
        try:
            if evidence:
                evidence.mkdir(parents=True, exist_ok=True)
            result = iframe_selection(Path(output).resolve(), artifact, doc, list(model.capabilities().values()), runtime, evidence, max_pages=max_pages, timeout_ms=timeout_ms)
            checks.append(result)
            errors.extend(result['errors'])
        except (ImportError, RuntimeError, OSError) as error:
            checks.append({'check': 'iframeSelection', 'status': 'unverified', 'reason': str(error)})
        except Exception as error:
            checks.append({'check': 'iframeSelection', 'status': 'failed', 'reason': str(error)})
    else:
        checks.append({'check': 'iframeSelection', 'status': 'unverified', 'reason': '源码/构建未通过，或浏览器未启用；未执行真实选中。'})
    return finish()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--module', required=True)
    parser.add_argument('--shuku-root', type=Path, default=os.environ.get('SHUKU_ROOT'))
    parser.add_argument('--build-output', type=Path)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--skip-browser', action='store_true', help='Record iframe selection as unverified')
    parser.add_argument('--max-pages', type=int, default=12)
    parser.add_argument('--timeout-ms', type=int, default=10000)
    args = parser.parse_args(argv)
    try:
        if args.max_pages < 1 or args.timeout_ms < 1:
            raise ValueError('页面数量和超时必须大于零。')
        report = check(args.project, args.module, shuku=args.shuku_root, output=args.build_output,
                       evidence=args.evidence, skip_browser=args.skip_browser, max_pages=args.max_pages, timeout_ms=args.timeout_ms)
    except (OSError, ValueError, ImportError, RuntimeError) as error:
        report = {'status': 'unverified', 'errors': [], 'unverified': [str(error)],
                  'message': str(error), 'coverage': {'sourceEditing': False}, 'sourceFilesWritten': False}
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['status'] == 'passed' else 1 if report['status'] == 'failed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
