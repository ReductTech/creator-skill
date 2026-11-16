"""Local resource savings and enforceable, actionable submission diagnostics."""
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from PIL import Image
import pytest

from module.package_course import export_source
from common.submission_policy import blocked_reason
from test_delivery import course, snapshot


@pytest.mark.parametrize('name,raw', [
    ('run.PY', b'print(1)'), ('assets/.env.local', b'secret'), ('assets/lib.so.1', b'x'),
    ('assets/readme.txt', b'\x7fELFhidden'), ('assets/picture.png', b'MZhidden'),
    ('assets/script', b'#!/usr/bin/env python3\nprint(1)'),
    ('assets/script.ts', b'#!/bin/bash\necho hidden'),
])
def test_blacklist_precedes_allowlist_and_preserves_originals(tmp_path, name, raw):
    root = course(tmp_path/'source')
    file = root/name; file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(raw)
    before = snapshot(root)
    result = export_source([root])
    assert result['status'] == 'passed'
    assert snapshot(root) == before
    assert any(w['code'] == 'FILE_EXCLUDED' and w['path'].endswith(name) for w in result['warnings'])
    with zipfile.ZipFile(result['output']) as archive:
        assert not any(n.endswith('/'+name) for n in archive.namelist())


@pytest.mark.parametrize('name,size,valid', [
    ('data.json', 102400, True), ('data.json', 102401, False),
    ('assets/data.json', 102401, True), ('large.tsx', 120000, True),
    ('large.css', 120000, True), ('data.txt', 102401, False),
])
def test_size_allowlist_and_json_use_same_rule(tmp_path, name, size, valid):
    root = course(tmp_path/'source')
    path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(' '*size)
    result = export_source([root])
    assert (result['status'] == 'passed') == valid
    if not valid:
        problem = next(i for i in result['issues']['serious'] if i['code'] == 'FILE_OUTSIDE_ASSETS')
        assert problem['size'] == size and problem['limitBytes'] == 102400
        assert all(problem.get(k) for k in ('path', 'message', 'impact', 'repair', 'recheck'))
        assert Path(result['readableReportPath']).is_file()


def test_excluded_dependency_blocks_package_without_deleting_it(tmp_path):
    root = course(tmp_path/'source')
    (root/'secret.py').write_text('print(1)')
    (root/'Guide.tsx').write_text("import './secret.py'; export function Guide(){return null;}")
    result = export_source([root])
    assert result['status'] == 'failed' and not Path(result['output']).exists()
    assert any(i['code'] == 'EXCLUDED_FILE_REFERENCED' and i['line'] == 1 for i in result['issues']['serious'])
    assert (root/'secret.py').is_file()


def test_image_optimization_saves_upload_bytes_without_node_or_source_edits(tmp_path):
    root = course(tmp_path/'source')
    assets = root/'assets'; assets.mkdir()
    Image.new('RGB', (2400, 1200), 'red').save(assets/'large.png')
    (root/'Guide.tsx').write_text("const url=moduleAssetUrl('assets/large.png');")
    before = snapshot(root)
    # The actual CLI runs with no node executable available on PATH.
    cli = Path(__file__).resolve().parents[1]/'module/package_course.py'
    execution = subprocess.run([sys.executable, str(cli), str(root)],
        env={**os.environ, 'PATH': ''}, capture_output=True, text=True, encoding='utf-8', check=True)
    result = json.loads(execution.stdout)
    assert result['images']['converted'] == 1 and result['images']['savedBytes'] > 0
    assert snapshot(root) == before
    with zipfile.ZipFile(result['output']) as archive:
        prefix = 'modules/'+root.name+'/'
        assert prefix+'assets/large.png' not in archive.namelist()
        assert archive.read(prefix+'Guide.tsx') == before['Guide.tsx']
        manifest = json.loads(archive.read('skzip-manifest.json'))
        conversion = manifest['imageConversions'][0]
        assert conversion['source'] == prefix+'assets/large.png'
        assert conversion['target'] == prefix+'assets/large.webp'
        assert conversion['width'] == 1600 and conversion['height'] == 800
        assert all(not Path(v).is_absolute() for v in (conversion['source'], conversion['target']))


def test_no_duplicate_original_when_target_is_preexisting(tmp_path):
    root = course(tmp_path/'source'); assets = root/'assets'; assets.mkdir()
    Image.new('RGB', (2400, 1200), 'red').save(assets/'large.png')
    Image.new('RGB', (20, 20), 'blue').save(assets/'large.webp')
    result = export_source([root])
    assert not result['images']['conversions']
    assert any(i['code'] == 'IMAGE_RETAINED' for i in result['warnings'])


def test_valid_jpeg_uses_pillow_without_frontend_tools(tmp_path):
    root = course(tmp_path/'source'); assets = root/'assets'; assets.mkdir()
    Image.new('RGB', (2000, 1000), 'green').save(assets/'photo.jpg')
    result = export_source([root])
    assert result['status'] == 'passed' and result['images']['converted'] == 1
    assert result['images']['conversions'][0]['target'].endswith('/photo.webp')


def test_explicit_custom_style_is_retained_instead_of_silently_replaced(tmp_path):
    root = course(tmp_path/'source'); project = root.parent
    style_id = '76018445-20ab-4dd9-9543-385d177eb158'
    shared = project/'shared'; shared.mkdir()
    (shared/'style.json').write_text(json.dumps({'id':style_id,'schema':1,'protocol':1,'name':'Custom'}))
    (shared/'index.ts').write_text('export const value = 1')
    (project/'course-styles.json').write_text(json.dumps({'schema':1,'default_style':style_id,
        'styles':[{'id':style_id,'path':'shared'}]}))
    result = export_source([root])
    assert result['status'] == 'passed'
    with zipfile.ZipFile(result['output']) as archive:
        assert f'styles/{style_id}/index.ts' in archive.namelist()
        registry = json.loads(archive.read('course-styles.json'))
        assert registry['default_style'] == style_id
