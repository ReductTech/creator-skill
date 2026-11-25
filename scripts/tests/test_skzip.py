"""Delivery failures must never produce an official package or modify the author."""
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from skzip import CHECKS, MANIFEST, canonical, digest, envelope, seal, verify_archive
from module.delivery_prepare import prepare, resource_review, choose_resources

MID = 'e4b9181d-8c80-49a2-a625-16715ca23f14'
PAGE = 'f19b5e5d-c846-4244-bab5-f42e94223ccf'
SCRIPTS = Path(__file__).resolve().parents[1]


def fixture(root, code='export function Guide(){return <p>Hello</p>}'):
    course = root/'modules'/MID
    course.mkdir(parents=True)
    doc = {'id': MID, 'moduleIdentity': {'version': 1, 'id': MID}, 'title': 'Fixture',
           'path': '/modules/'+MID, 'entry': 'Guide.tsx',
           'pages': [{'id': PAGE, 'title': 'Hello', 'snippet': 'Hello'}]}
    (course/'outlines.json').write_text(json.dumps(doc), encoding='utf-8')
    (course/'Guide.tsx').write_text(code, encoding='utf-8')
    return course, {'path': 'modules/'+MID, 'module_id': MID}


def archive(path, files, mutate=None):
    checks = {name: {'status': 'passed'} for name in CHECKS}
    document = envelope(files, checks, {'confirmed': True}, {'name': 'test'})
    if mutate:
        mutate(document)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as out:
        for name, raw in files.items():
            out.writestr(name, raw)
        out.writestr(MANIFEST, canonical(document))
    return document


def test_envelope_actual_bytes_and_tamper(tmp_path):
    path = tmp_path/'valid.skzip'
    archive(path, {'modules/a/data.txt': b'hello'})
    assert verify_archive(path)['checks']['images']['status'] == 'passed'
    # Same size changed bytes, with a valid old workflow tag, must fail.
    original = path.read_bytes()
    with zipfile.ZipFile(path) as src:
        doc = src.read(MANIFEST)
    with zipfile.ZipFile(path, 'w') as out:
        out.writestr('modules/a/data.txt', b'other')
        out.writestr(MANIFEST, doc)
    with pytest.raises(ValueError, match='hash differs'):
        verify_archive(path)
    path.write_bytes(original)
    renamed = tmp_path/'not.zip'
    renamed.write_bytes(original)
    with pytest.raises(ValueError, match='.skzip'):
        verify_archive(renamed)


@pytest.mark.parametrize('change', ['unlisted', 'tag'])
def test_missing_or_fabricated_receipts_fail(tmp_path, change):
    path = tmp_path/'bad.skzip'
    def mutate(d):
        if change == 'missing-check': del d['checks']['admission']
        elif change == 'failed-check': d['checks']['build']['status'] = 'failed'
        elif change == 'unconfirmed': d['resourceReview']['confirmed'] = False
        elif change == 'unlisted': d['files'] = []
        elif change == 'tag': d['producer']['name'] = 'changed'
        if change != 'tag': d.update(seal(d))
    archive(path, {'entry.tsx': b'export const x=1'}, mutate)
    with pytest.raises(ValueError): verify_archive(path)


def test_resource_decisions_are_complete_snapshot_bound_and_never_delete(tmp_path):
    course, record = fixture(tmp_path)
    (course/'assets').mkdir()
    (course/'assets/unused.txt').write_text('leave original alone')
    review = resource_review(tmp_path, [record], set(), 'snapshot')
    assert choose_resources(review) is None
    assert (course/'assets/unused.txt').exists()
    with pytest.raises(ValueError, match='Unconfirmed'): choose_resources(review, review)
    review['resources'][0]['decision'] = 'exclude'
    selection = choose_resources(review, review)
    assert selection['excludedBytes'] > 0
    assert (course/'assets/unused.txt').exists()
    with pytest.raises(ValueError, match='stale'):
        choose_resources({**review, 'sourceSnapshot': 'new'}, review)
    assert choose_resources(review, policy='keep-all')['decisions'][0]['decision'] == 'keep'
    with pytest.raises(ValueError, match='stale'): choose_resources(review, [])
    with pytest.raises(ValueError, match='full current inventory'):
        choose_resources(review, {**review, 'resources':[None]})


def test_prepare_converts_small_png_rewrites_and_adds_ids(tmp_path):
    from PIL import Image
    root = tmp_path/'source'
    course, record = fixture(root, "import {moduleAssetUrl} from '@shuku/course-runtime/react/assets';export function Guide(){return <img src={moduleAssetUrl('image.png')}/>} ")
    (course/'assets').mkdir()
    Image.new('RGBA', (20, 30), (1, 2, 3, 40)).save(course/'assets/image.png')
    work = tmp_path/'work'; work.mkdir()
    rows, originals = prepare(root, [record], work, 30)
    source = (course/'Guide.tsx').read_text()
    assert 'moduleAssetUrl("image.webp")' in source and 'shuku-edit-id=' in source
    assert rows[0]['idsAdded'] == 1
    assert 'modules/'+MID+'/assets/image.png' in originals
    assert (course/'assets/image.png').exists()  # Author decides whether this goes in the package.
    with Image.open(course/'assets/image.webp') as im:
        assert im.size == (20, 30) and im.mode == 'RGBA'


def test_opaque_references_are_reported_without_blocking_preparation(tmp_path):
    root = tmp_path/'source'
    course, record = fixture(root, "import {moduleAssetUrl} from '@shuku/course-runtime/react/assets';export function Guide(){return <img src={moduleAssetUrl(location.hash)}/>} ")
    work = tmp_path/'work'; work.mkdir()
    rows, _ = prepare(root, [record], work, 30)
    assert rows[0]['references'].get('unverified') or rows[0]['references'].get('unresolved')


def test_id_check_rejects_duplicates_and_missing_ids(tmp_path):
    course, _ = fixture(tmp_path)
    script = SCRIPTS/'module/add_edit_ids.mjs'
    def check(): return subprocess.run(['node', str(script), str(course), '--check'], capture_output=True, text=True)
    assert check().returncode == 1
    (course/'Guide.tsx').write_text('export const x=<div shuku-edit-id="same"><p shuku-edit-id="same"/></div>')
    report = check()
    assert report.returncode == 1 and json.loads(report.stdout)['idIssues']


def test_id_cannot_be_overridden_by_a_later_spread(tmp_path):
    course, _ = fixture(tmp_path, 'export const x=<div shuku-edit-id="stable" {...props}/>')
    command = ['node', str(SCRIPTS/'module/add_edit_ids.mjs'), str(course), '--check']
    report = subprocess.run(command, capture_output=True, text=True)
    assert report.returncode == 1 and 'override' in report.stdout
    (course/'Guide.tsx').write_text('export const x=<div {...props} shuku-edit-id="stable"/>')
    assert subprocess.run(command, capture_output=True).returncode == 0


def test_python_browser_manifest_and_zip_verifier_agree(tmp_path):
    path = tmp_path/'fixture.skzip'
    archive(path, {'modules/a/中文.txt': '你好'.encode()})
    script = SCRIPTS/'browser/verify_skzip.mjs'
    js = """import fs from 'node:fs';import {File} from 'node:buffer';
      const {verifySkzip}=await import(process.argv[1]);
      const result=await verifySkzip(new File([fs.readFileSync(process.argv[2])],'fixture.skzip'));
      console.log(result.status);
    """
    result = subprocess.run(['node', '--input-type=module', '-e', js, script.as_uri(), str(path)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'passed'


def test_verifier_runs_in_a_real_browser_before_any_upload(tmp_path):
    import base64
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    import threading
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path/'browser.skzip'
    archive(path, {'modules/a/中文.txt': '你好'.encode()})
    (tmp_path/'verify_skzip.mjs').write_bytes((SCRIPTS/'browser/verify_skzip.mjs').read_bytes())
    (tmp_path/'index.html').write_text('<!doctype html><title>Verifier test</title>')
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(tmp_path)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                uploads = []
                page.on('request', lambda request: uploads.append(request.url) if request.method != 'GET' else None)
                page.goto('http://127.0.0.1:'+str(server.server_port))
                result = page.evaluate('''async raw => {
                  const {verifySkzip}=await import('/verify_skzip.mjs');
                  const file=new File([Uint8Array.from(atob(raw),c=>c.charCodeAt(0))],'browser.skzip');
                  const progress=[];
                  const valid=await verifySkzip(file,{onProgress:p=>progress.push(p.completed)});
                  let rejected=false;
                  try {await verifySkzip(new File([file],'renamed.zip'));}catch{rejected=true;}
                  return {status:valid.status,rejected,progress};
                }''', base64.b64encode(path.read_bytes()).decode())
                assert result == {'status':'passed', 'rejected':True, 'progress':[1]}
                assert not uploads
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
