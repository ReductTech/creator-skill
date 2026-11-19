"""Compatibility failures, honest missing evidence, and the real Shuku editor protocol."""
import base64
import io
import json
import os
from pathlib import Path

import pytest

from checks import check_source_editing as checker
from module import local_validation
from test_delivery import course, snapshot
from test_local_workflow import capability


@pytest.fixture
def runtime():
    root = os.environ.get('CREATOR_TEST_SHUKU_ROOT')
    if not root:
        pytest.skip('Set CREATOR_TEST_SHUKU_ROOT for actual Shuku editor integration')
    checker.load_runtime(root)
    return Path(root)


def editable_course(tmp_path, *, image=True):
    root = course(tmp_path / 'source')
    code = 'export function Guide(){return <><h1 shuku-edit-id="title-id">原文</h1>'
    if image:
        code += '<img shuku-edit-id="image-id" src="/original.webp" alt="原图" />'
    (root / 'Guide.tsx').write_text(code + '</>}', encoding='utf-8')
    return root


def artifact(tmp_path, root, *, markers=True, pages=None, html=None):
    output = tmp_path / 'build'
    folder = output / root.name
    folder.mkdir(parents=True)
    doc = json.loads((root / 'outlines.json').read_text())
    (folder / 'course.json').write_text(json.dumps({'id': doc['id'], 'pages': doc['pages'] if pages is None else pages, 'modes': ['guide']}))
    content = html or '<!doctype html><head></head><body><div id="root">' + ('<h1 shuku-edit-id="title-id">原文</h1>' if markers else 'No markers') + '</div></body>'
    (folder / 'index.html').write_text(content, encoding='utf-8')
    (folder / 'artifact-manifest.json').write_text(json.dumps({'module_id': root.name, 'files': []}))
    return output


@pytest.mark.parametrize('name', sorted(checker.LEGACY))
def test_legacy_blocks_even_without_runtime_and_never_deletes_edits(tmp_path, name):
    root = editable_course(tmp_path)
    (root / name).write_text('existing user edits', encoding='utf-8')
    before = snapshot(root)
    result = checker.check(root.parent, root.name)
    assert result['status'] == 'failed'
    assert result['checks'][0]['check'] == 'legacyScripts'
    assert snapshot(root) == before


def test_missing_runtime_is_unverified_not_passed(tmp_path):
    root = editable_course(tmp_path)
    result = checker.check(root.parent, root.name, shuku=tmp_path / 'missing')
    assert result['status'] == 'unverified'
    assert result['coverage']['sourceEditing'] is False


def test_literal_ids_without_a_build_cannot_claim_edit_compatibility(tmp_path, runtime):
    root = editable_course(tmp_path)
    before = snapshot(root)
    result = checker.check(root.parent, root.name, shuku=runtime, skip_browser=True)
    checks = {row['check']: row for row in result['checks']}
    assert checks['sourceBindings']['status'] == 'passed'
    assert checks['textRoundtrip']['status'] == checks['imageRoundtrip']['status'] == 'passed'
    assert result['status'] == 'unverified'
    assert snapshot(root) == before


def test_build_without_emitted_ids_fails_the_actual_support_detector(tmp_path, runtime):
    root = editable_course(tmp_path)
    output = artifact(tmp_path, root, markers=False)
    result = checker.check(root.parent, root.name, shuku=runtime, output=output, skip_browser=True)
    support = next(c for c in result['checks'] if c['check'] == 'supports_source_edit')
    assert result['status'] == 'failed' and support['value'] is False


def test_stale_build_with_other_pages_is_not_accepted(tmp_path, runtime):
    root = editable_course(tmp_path)
    output = artifact(tmp_path, root, pages=[])
    result = checker.check(root.parent, root.name, shuku=runtime, output=output, skip_browser=True)
    assert result['status'] == 'failed'
    assert any(c['check'] == 'buildIdentity' and c['status'] == 'failed' for c in result['checks'])


def test_text_only_course_has_no_false_image_success(tmp_path, runtime):
    root = editable_course(tmp_path, image=False)
    result = checker.check(root.parent, root.name, shuku=runtime, skip_browser=True)
    assert next(c for c in result['checks'] if c['check'] == 'imageRoundtrip')['status'] == 'not-applicable'


def test_no_editable_ids_is_a_definite_failure(tmp_path, runtime):
    root = course(tmp_path / 'source')
    result = checker.check(root.parent, root.name, shuku=runtime)
    assert result['status'] == 'failed'
    assert next(c for c in result['checks'] if c['check'] == 'sourceBindings')['status'] == 'failed'


def test_script_embedding_does_not_close_the_script_tag():
    value = '</script><script>bad()</script>\u2028'
    escaped = checker.json_for_script(value)
    assert '</script>' not in escaped and '\u2028' not in escaped
    assert json.loads(escaped) == value


def test_iframe_really_selects_text_and_image_after_a_zero_marker_snapshot(tmp_path, runtime):
    pytest.importorskip('playwright.sync_api')
    from PIL import Image
    stream = io.BytesIO()
    Image.new('RGB', (8, 8), 'blue').save(stream, format='WEBP')
    image_url = 'data:image/webp;base64,' + base64.b64encode(stream.getvalue()).decode()
    root = editable_course(tmp_path)
    source = (root / 'Guide.tsx').read_text(encoding='utf-8').replace('/original.webp', image_url)
    (root / 'Guide.tsx').write_text(source, encoding='utf-8')
    markup = '<h1 shuku-edit-id="title-id">原文</h1><img shuku-edit-id="image-id" style="width:100px;height:100px" src="' + image_url + '">'
    html = '<!doctype html><head></head><body><div id="root"><span>Loading</span></div><script>setTimeout(()=>document.getElementById("root").innerHTML=' + checker.json_for_script(markup) + ',1500)</script></body>'
    output = artifact(tmp_path, root, html=html)
    before = snapshot(root)
    result = checker.check(root.parent, root.name, shuku=runtime, output=output, evidence=tmp_path / 'evidence')
    assert result['status'] == 'passed', result
    browser = next(c for c in result['checks'] if c['check'] == 'iframeSelection')
    assert set(browser['selected']) == {'text', 'image'}
    assert any(s['rendered'] and s['coverage']['marked'] == 0 for p in browser['snapshots'] for s in p['snapshots'])
    assert (tmp_path / 'evidence/iframe-text.png').is_file()
    assert snapshot(root) == before


@pytest.mark.parametrize('has_build', [False, True])
def test_dispatch_records_edit_failure_and_blocks_source_package(tmp_path, monkeypatch, has_build):
    root = editable_course(tmp_path)
    files = {'modules/' + root.name + '/' + p.name: p for p in root.iterdir() if p.is_file()}
    cap = capability(build=has_build)
    cap['shukuRoot'] = str(tmp_path / 'shuku')
    cap['node'] = 'node'
    commands = []
    def run(command, **kwargs):
        if any('check_source_editing.py' in str(arg) for arg in command):
            commands.append(command)
            return {'exitCode': 1, 'result': {'status': 'failed', 'errors': ['legacy'], 'coverage': {'sourceEditing': False}}, 'log': None}
        return {'exitCode': 0, 'result': {}, 'log': None}
    monkeypatch.setattr(local_validation, 'run_command', run)
    stage = tmp_path / 'stage'
    stage.mkdir()
    _, report = local_validation.local_checks(files, stage, cap, tmp_path / 'evidence')
    assert commands and ('--build-output' in commands[0]) == has_build
    assert '--skip-browser' in commands[0]
    assert report['coverage']['sourceEditing'] is False
    assert any(i['blocking'] and i['path'].endswith('/source-editing') for i in report['issues'])


def test_dispatch_missing_editor_evidence_stays_unverified(tmp_path, monkeypatch):
    root = editable_course(tmp_path)
    files = {'modules/' + root.name + '/' + p.name: p for p in root.iterdir() if p.is_file()}
    def run(command, **kwargs):
        if any('check_source_editing.py' in str(arg) for arg in command):
            return {'exitCode': 2, 'result': {'status': 'unverified', 'coverage': {'sourceEditing': False}}, 'log': None}
        return {'exitCode': 0, 'result': {}, 'log': None}
    monkeypatch.setattr(local_validation, 'run_command', run)
    stage = tmp_path / 'stage'
    stage.mkdir()
    _, report = local_validation.local_checks(files, stage, capability(), tmp_path / 'evidence')
    assert report['coverage']['sourceEditing'] is False
    assert any(c['status'] == 'unverified' for c in report['checks'] if c['check'].endswith('/source-editing'))
    assert not any(i['blocking'] for i in report['issues'])
