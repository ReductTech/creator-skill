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
from skzip import MANIFEST, seal, validate_manifest
from module.source_archive import write_source_archive
from test_delivery import course, snapshot


@pytest.mark.parametrize('name,raw', [
    ('run.SH', b'echo no'), ('assets/.env.local', b'secret'), ('assets/lib.so.1', b'x'),
    ('assets/readme.txt', b'\x7fELFhidden'), ('assets/picture.png', b'MZhidden'),
    ('assets/script', b'#!/usr/bin/env python3\nprint(1)'),
    ('assets/script.ts', b'#!/bin/bash\necho hidden'),
    ('assets/payload.bin', b'\x7fELFhidden'), ('assets/payload.py', b'MZhidden'),
    ('assets/shell.py', b'#!/bin/sh\necho hidden'), ('assets/run.EXE', b'plain'),
    ('assets/script.bin', b'#!/usr/bin/env python3\nprint(1)'),
    ('assets/macho.bin', b'\xce\xfa\xed\xfehidden'),
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
    ('lesson.py', 102400, True), ('lesson.py', 102401, False),
    ('data.bin', 102400, True), ('data.bin', 102401, False),
    ('assets/lesson.py', 102401, True), ('assets/data.bin', 102401, True),
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


@pytest.mark.parametrize('name,raw', [
    ('prelude.PY', b'print(1)'),
    ('assets/runtime/prelude.py', b'#!/usr/bin/env python3\nprint(1)'),
    ('assets/runtime/direct.py', b'#!/usr/bin/python3\nprint(1)'),
    ('assets/runtime/data.BIN', b'PK\x03\x04data'),
])
def test_python_and_binary_payloads_are_retained_and_marked_high_risk(tmp_path, name, raw):
    root = course(tmp_path/'source')
    path = root/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    before = snapshot(root)
    result = export_source([root])
    assert result['status'] == 'passed'
    assert snapshot(root) == before
    logical = 'modules/'+root.name+'/'+name
    assert result['riskLevel'] == 'high'
    assert result['highRiskFiles'][0]['path'] == logical
    assert any(w['code'] == 'HIGH_RISK_FILE' and w['riskLevel'] == 'high' for w in result['warnings'])
    with zipfile.ZipFile(result['output']) as archive:
        assert archive.read(logical) == raw
        assert MANIFEST not in archive.namelist()  # Ordinary ZIP needs no client attestation.
    assert result['serverPending'] and 'security' in result['serverPending']


def test_archive_verification_rejects_disguised_executable_payload(tmp_path):
    payload = tmp_path/'disguised.bin'
    payload.write_bytes(b'\x7fELFhidden')
    destination = tmp_path/'forbidden.zip'
    with pytest.raises(ValueError, match='Forbidden ZIP payload'):
        write_source_archive({'modules/test/assets/disguised.bin': payload},
                             {'images': {'status': 'passed'}}, destination, {'name': 'test'})
    assert not destination.exists()


def test_plain_zip_does_not_require_official_manifest(tmp_path):
    root = course(tmp_path/'source')
    result = export_source([root])
    assert result['status'] == 'passed' and result['output'].endswith('.zip')
    with zipfile.ZipFile(result['output']) as archive:
        assert MANIFEST not in archive.namelist()
        assert archive.testzip() is None


def test_excluded_dependency_warns_and_packages_without_deleting_it(tmp_path):
    root = course(tmp_path/'source')
    (root/'secret.sh').write_text('print(1)')
    (root/'Guide.tsx').write_text("import './secret.sh'; export function Guide(){return null;}")
    result = export_source([root])
    assert result['status'] == 'passed' and Path(result['output']).is_file()
    assert not result['issues']['serious']
    assert any(i['code'] == 'EXCLUDED_FILE_REFERENCED' and i['line'] == 1 for i in result['warnings'])
    with zipfile.ZipFile(result['output']) as archive:
        assert not any(n.endswith('/secret.sh') for n in archive.namelist())
        assert any(n.endswith('/Guide.tsx') for n in archive.namelist())
    assert (root/'secret.sh').is_file()


def test_long_source_literal_is_not_resolved_as_windows_path(tmp_path, monkeypatch):
    root = course(tmp_path/'source')
    (root/'unused.sh').write_text('print(1)')
    (root/'Guide.tsx').write_text('const payload = "' + 'x'*90000 + '";')
    original = Path.resolve

    def guarded_resolve(path, *args, **kwargs):
        if len(str(path)) > 32767:
            raise ValueError('stat: path too long for Windows')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'resolve', guarded_resolve)
    result = export_source([root])
    assert result['status'] == 'passed'
    assert result['outputCreated']


@pytest.mark.parametrize('reference', [
    "import prelude from './secret.sh?raw';",
    "import('./secret.sh?raw#fragment');",
    "const url = moduleAssetUrl(\n 'runtime/secret.sh');",
    "const data = moduleJson('runtime/secret.sh');",
])
def test_excluded_queried_and_module_asset_dependencies_are_reported(tmp_path, reference):
    root = course(tmp_path/'source')
    relative = 'assets/runtime/secret.sh' if 'module' in reference else 'secret.sh'
    secret = root/relative
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text('print(1)')
    (root/'Guide.tsx').write_text(reference)
    result = export_source([root])
    assert result['status'] == 'passed'
    assert result['outputCreated']
    assert not result['issues']['serious']
    problem = next(i for i in result['warnings'] if i['code'] == 'EXCLUDED_FILE_REFERENCED')
    assert problem['path'].endswith('/Guide.tsx')
    assert problem['line'] == reference.count('\n') + 1
    assert secret.is_file()


def test_raw_import_of_included_file_has_no_missing_import_warning(tmp_path):
    root = course(tmp_path/'source')
    (root/'message.txt').write_text('hello')
    (root/'Guide.tsx').write_text("import text from './message.txt?raw#fragment';")
    result = export_source([root])
    assert result['status'] == 'passed'
    assert not any(w.get('kind') == 'unverified-import' for w in result['warnings'])


@pytest.mark.parametrize('extension,kind', [('png','PNG'),('jpg','JPEG'),('avif','PNG'),('gif','GIF')])
def test_forbidden_images_block_without_mutating_author_source(tmp_path, extension, kind):
    root = course(tmp_path/'source'); assets = root/'assets'; assets.mkdir()
    Image.new('RGB',(30,20),'red').save(assets/('picture.'+extension),format=kind)
    before = snapshot(root)
    result = export_source([root])
    assert result['status'] != 'passed' and not result['outputCreated']
    assert snapshot(root) == before


@pytest.mark.parametrize('extension,kind', [('webp','WEBP'),('svg','SVG')])
def test_allowed_images_keep_exact_bytes_and_names_without_node(tmp_path, extension, kind):
    root = course(tmp_path/'source'); assets = root/'assets'; assets.mkdir()
    name='picture.'+extension
    if kind == 'SVG':
        (assets/name).write_bytes(b'\xef\xbb\xbf<?xml version="1.0"?><!-- keep -->\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 20"><path d="M0 0h30v20H0z" fill="red"/></svg>')
    else:
        Image.new('RGB',(30,20),'red').save(assets/name,format=kind)
    before=snapshot(root)
    cli=Path(__file__).resolve().parents[1]/'module/package_course.py'
    execution=subprocess.run([sys.executable,str(cli),str(root)],env={**os.environ,'PATH':''},capture_output=True,text=True,encoding='utf-8',check=True)
    result=json.loads(execution.stdout)
    assert result['images']['converted']==0 and result['images']['conversions']==[]
    assert snapshot(root)==before
    with zipfile.ZipFile(result['output']) as archive:
        assert archive.read('modules/'+root.name+'/assets/'+name)==before['assets/'+name]


@pytest.mark.parametrize('name,raw', [
    ('broken.svg', b'<svg><path></svg>'),
    ('wrong-root.svg', b'<html/>'),
    ('wrong-namespace.svg', b'<svg xmlns="urn:other"/>'),
    ('disguised.webp', b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
    ('disguised.dat', b'\xef\xbb\xbf<!-- comment --><svg/>'),
    ('disguised.svg', b'GIF89a'),
])
def test_invalid_or_disguised_svg_blocks_package(tmp_path, name, raw):
    root = course(tmp_path/'source')
    (root/'assets').mkdir()
    (root/'assets'/name).write_bytes(raw)
    before = snapshot(root)
    result = export_source([root])
    assert result['status'] != 'passed' and not result['outputCreated']
    assert snapshot(root) == before


def test_inline_svg_in_source_is_not_misclassified_as_image(tmp_path):
    root = course(tmp_path/'source')
    (root/'Guide.tsx').write_text('export function Guide(){return <svg viewBox="0 0 16 16"><path d="M0 0h16"/></svg>;}')
    result = export_source([root])
    assert result['status'] == 'passed' and result['outputCreated']


@pytest.mark.parametrize('excluded_name', [None, 'setup.sh', 'assets/tool.EXE'])
def test_explicit_custom_style_is_retained_instead_of_silently_replaced(tmp_path, excluded_name):
    root = course(tmp_path/'source'); project = root.parent
    style_id = '76018445-20ab-4dd9-9543-385d177eb158'
    shared = project/'shared'; shared.mkdir()
    (shared/'style.json').write_text(json.dumps({'id':style_id,'schema':1,'protocol':1,'name':'Custom'}))
    (shared/'index.ts').write_text('export const value = 1')
    if excluded_name:
        excluded = shared/excluded_name
        excluded.parent.mkdir(parents=True, exist_ok=True)
        excluded.write_text('not allowed')
    (project/'course-styles.json').write_text(json.dumps({'schema':1,'default_style':style_id,
        'styles':[{'id':style_id,'path':'shared'}]}))
    result = export_source([root])
    assert result['status'] == 'passed'
    if excluded_name:
        logical = f'styles/{style_id}/{excluded_name}'
        assert excluded.is_file()
        assert any(w['code'] == 'FILE_EXCLUDED' and w['path'] == logical for w in result['warnings'])
        assert any(row['path'] == logical for row in result['excludedFiles'])
    with zipfile.ZipFile(result['output']) as archive:
        if excluded_name:
            assert logical not in archive.namelist()
        assert f'styles/{style_id}/index.ts' in archive.namelist()
        registry = json.loads(archive.read('course-styles.json'))
        assert registry['default_style'] == style_id
