"""Source pipeline behavior: Python only, read-only inputs and honest server gates."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import zipfile

import pytest

from module.package_course import export_source
from module.source_inputs import default_output, discover_modules, source_paths
from module.source_checks import inspect_collection
from module.source_images import inspect_images
from module.source_archive import write_source_archive
from skzip import MANIFEST, canonical, seal, verify_archive

SCRIPTS = Path(__file__).resolve().parents[1]
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=')


def course(parent, *, draft=False):
    mid, page = str(uuid4()), str(uuid4())
    directory = parent / mid
    directory.mkdir(parents=True)
    doc = {'id': mid, 'title': 'Fixture', 'path': '/modules/' + mid,
           'moduleIdentity': {'version': 1, 'id': mid},
           'pages': [{'id': page, 'title': 'Opening', 'snippet': ''}]}
    if not draft:
        doc['entry'] = 'Guide.tsx'
        (directory / 'Guide.tsx').write_text('export function Guide(){return <p>Source only</p>}', encoding='utf-8')
    (directory / 'outlines.json').write_text(json.dumps(doc), encoding='utf-8')
    return directory


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('shape', ['single', 'collection', 'project', 'flat', 'multiple'])
@pytest.mark.parametrize('shared', [False, True])
def test_directory_shapes_pack_source_and_exclude_shared(tmp_path, shape, shared):
    project = tmp_path / 'source'
    collection = project / 'modules' if shape == 'project' else project
    first = course(collection)
    second = course(collection) if shape != 'single' else None
    if shared:
        folder = collection / 'ShArEd'
        folder.mkdir()
        (folder / 'must-not-ship.ts').write_text('export const x = 1')
        nested = first / 'components' / 'SHARED'
        nested.mkdir(parents=True)
        (nested / 'nested.ts').write_text('excluded')
    inputs = [first] if shape == 'single' else [first, second] if shape == 'multiple' else [project]
    before = {m.name: snapshot(m) for m in (first, second) if m}
    output = default_output(inputs)
    result = export_source(inputs)
    assert result['status'] == 'passed'
    expected = (first.with_name(first.name + '.zip') if shape == 'single' else
                collection / 'courses.zip' if shape == 'multiple' else
                project / 'modules.zip' if shape == 'project' else project.with_name(project.name + '.zip'))
    assert Path(result['output']) == expected
    assert len(result['modules']) == (1 if shape == 'single' else 2)
    assert {m.name: snapshot(m) for m in (first, second) if m} == before
    assert 'build' in result['serverPending']
    assert not result['coverage']['realBuild']
    with zipfile.ZipFile(output) as archive:
        assert f'modules/{first.name}/Guide.tsx' in archive.namelist()
        assert all('shared' not in p.lower().split('/') for p in archive.namelist())


def test_original_inputs_are_preserved_when_image_is_converted(tmp_path):
    directory=course(tmp_path/'source')
    assets=directory/'assets';assets.mkdir()
    (assets/'picture.png').write_bytes(PNG)
    before=snapshot(directory)
    result=export_source([directory])
    assert result['outputCreated'] and result['media']['counts']['imageConverted']==1
    assert snapshot(directory)==before


def test_single_pipeline_does_not_execute_subprocesses_or_source(tmp_path, monkeypatch):
    directory = course(tmp_path / 'source')
    (directory / 'Guide.tsx').write_text("import './missing'; throw new Error('must never execute');")
    def forbidden(*args, **kwargs):
        raise AssertionError('No process execution allowed')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(os, 'system', forbidden)
    result = export_source([directory])
    assert result['status'] == 'passed'
    assert any(w['kind'] == 'unverified-import' for w in result['warnings'])
    assert set(result['serverPending']) == {'classification', 'security', 'admission', 'build', 'rendering'}


def test_serious_module_errors_block_entire_request_and_drafts_can_ship_as_source(tmp_path):
    root = tmp_path / 'source'
    draft = course(root, draft=True)
    bad = course(root)
    (bad / 'outlines.json').write_text('{broken')
    report = export_source([root])
    assert report['status'] == 'failed'
    assert len(report['rejectedModules']) == 1
    assert report['seriousErrorCount'] == 1 and not report['uploadEligible']
    assert report['agentNextAction'] == 'repair-and-repack'
    assert not Path(report['output']).exists()
    assert json.loads(Path(report['reportPath']).read_text(encoding='utf-8'))['status'] == 'failed'
    # An explicitly selected valid scope can be packaged separately.
    result = export_source([draft])
    assert result['status'] == 'passed'
    assert any(w['kind'] == 'outline-only' for w in result['issues']['warnings'])
    (draft / 'outlines.json').write_text('{}')
    failed = export_source([draft])
    assert failed['status'] == 'failed' and failed['outputCreated'] is False
    assert not Path(failed['output']).exists()


@pytest.mark.parametrize('change', ['escape', 'missing', 'identity', 'duplicate-page', 'invalid-utf8'])
def test_invalid_source_never_publishes_a_package(tmp_path, change):
    directory = course(tmp_path / 'source')
    outline = directory / 'outlines.json'
    doc = json.loads(outline.read_text())
    if change == 'escape': doc['entry'] = '../outside.tsx'
    if change == 'missing': doc['entry'] = 'Missing.tsx'
    if change == 'identity': doc['moduleIdentity']['id'] = str(uuid4())
    if change == 'duplicate-page': doc['pages'].append(dict(doc['pages'][0]))
    if change == 'invalid-utf8': (directory / 'Guide.tsx').write_bytes(b'\xff\xfe')
    outline.write_text(json.dumps(doc))
    output = default_output([directory])
    assert export_source([directory])['status'] == 'failed'
    assert not output.exists()


def test_automatic_output_never_overwrites_and_cannot_enter_source(tmp_path):
    directory = course(tmp_path / 'source')
    first = export_source([directory])
    output = Path(first['output'])
    original = output.read_bytes()
    second = export_source([directory])
    assert first['status'] == second['status'] == 'passed'
    assert second['output'] != first['output']
    assert Path(second['output']).stem == output.stem + '-2'
    assert output.read_bytes() == original
    files, report = inspect_collection([directory])
    with pytest.raises(ValueError, match='outside'):
        write_source_archive(files, report, directory / 'forbidden.zip', {})
    assert not list(directory.glob('.source-pack-*'))


def test_cli_and_router_work_without_site_packages_node_config_or_shuku(tmp_path):
    directory = course(tmp_path / 'source with spaces')
    env = {**os.environ, 'PATH': '', 'CREATOR_SKILL_TARGET_CONFIG': str(tmp_path / 'missing-config.json')}
    direct = [sys.executable, '-S', str(SCRIPTS / 'module/package_course.py'), str(directory)]
    result = subprocess.run(direct, env=env,
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert len(result.stdout.splitlines()) == 1
    assert json.loads(result.stdout)['coverage']['realBuild'] is False
    router = subprocess.run([sys.executable, '-S', str(SCRIPTS / 'tools.py'), 'course.pack',
                             str(directory)], env=env,
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert router.returncode == 0, (router.stdout, router.stderr)
    with zipfile.ZipFile(json.loads(router.stdout)['output']) as archive:
        assert archive.testzip() is None and MANIFEST not in archive.namelist()


@pytest.mark.parametrize('tool', ['course.discover', 'course.inspect', 'course.images'])
def test_components_are_independently_callable_and_read_only(tmp_path, tool):
    directory = course(tmp_path / 'source')
    before = snapshot(directory)
    result = subprocess.run([sys.executable, '-S', str(SCRIPTS / 'tools.py'), tool, str(directory)],
                            env={**os.environ, 'PATH': '', 'CREATOR_SKILL_TARGET_CONFIG': 'not-a-config'},
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert json.loads(result.stdout)['status'] == 'passed'
    assert snapshot(directory) == before
    assert not list(tmp_path.rglob('*.zip'))


def test_plain_zip_contains_source_without_client_server_pass_claims(tmp_path):
    directory=course(tmp_path/'source')
    result=export_source([directory])
    with zipfile.ZipFile(result['output']) as archive:
        assert archive.testzip() is None
        assert MANIFEST not in archive.namelist()
        assert archive.read('modules/'+directory.name+'/Guide.tsx')==(directory/'Guide.tsx').read_bytes()
    assert not result['coverage']['securityReview'] and not result['coverage']['realBuild']


def test_symlinks_are_not_followed(tmp_path):
    directory = course(tmp_path / 'source')
    secret = tmp_path / 'secret.txt'
    secret.write_text('outside')
    try:
        (directory / 'linked.txt').symlink_to(secret)
    except OSError:
        pytest.skip('Symlinks unavailable for this user')
    result = export_source([directory])
    assert result['status'] == 'failed'
    assert not Path(result['output']).exists()


def test_duplicate_archive_paths_are_rejected(tmp_path):
    directory = course(tmp_path / 'source')
    source = directory / 'Guide.tsx'
    files = {'modules/x/Guide.tsx': source, 'modules/x/guide.tsx': source}
    with pytest.raises(ValueError, match='Duplicate'):
        write_source_archive(files, {}, tmp_path / 'duplicate.zip', {})


def test_shared_only_is_not_a_course(tmp_path):
    shared = tmp_path / 'Shared'
    shared.mkdir()
    with pytest.raises(ValueError, match='No course'):
        discover_modules([shared])


def test_detailed_report_allows_authorized_repairs_without_uploading(tmp_path):
    directory = course(tmp_path / 'source')
    assets = directory / 'assets'
    assets.mkdir()
    (directory/'Guide.tsx').write_text("import './missing'; export function Guide(){return null;}")
    result = export_source([directory])
    assert result['status'] == 'passed' and result['uploadEligible'] is True
    assert result['seriousErrorCount'] == 0 and result['warningCount'] == 1
    assert result['uploadAuthorized'] is False and result['requiresUserConfirmation'] is False
    assert result['userOptions'] == []
    assert [stage['name'] for stage in result['stages']] == ['source-checks', 'media-and-references', 'archive-and-integrity']
    assert result['stages'][0]['status'] == 'passed'
    assert json.loads(Path(result['reportPath']).read_text(encoding='utf-8')) == result
    assert result['summary']['zipBytes'] == Path(result['output']).stat().st_size


def test_clean_report_delivers_without_uploading(tmp_path):
    directory = course(tmp_path / 'source')
    doc = json.loads((directory / 'outlines.json').read_text())
    thumbnail = directory / 'assets/shuku-thumbnails' / (doc['pages'][0]['id'] + '.webp')
    thumbnail.parent.mkdir(parents=True)
    from PIL import Image
    Image.new('RGB',(1600,900),'red').save(thumbnail,format='WEBP')
    result = export_source([directory])
    assert result['status'] == 'passed' and result['warningCount'] == 0
    assert result['agentNextAction'] == 'deliver-package'
    assert result['userOptions'] == []


def test_archive_failure_returns_full_serious_error_report(tmp_path, monkeypatch):
    from module import package_course
    directory = course(tmp_path / 'source')
    def fail(*args, **kwargs):
        raise OSError('fixture disk failure')
    monkeypatch.setattr(package_course, 'write_source_archive', fail)
    result = export_source([directory])
    assert result['status'] == 'error' and result['uploadEligible'] is False
    assert result['outputCreated'] is False and result['seriousErrorCount'] == 1
    assert result['stages'][-1]['name'] == 'archive-and-integrity'
    assert 'disk failure' in result['issues']['serious'][0]['reason']
    assert Path(result['reportPath']).is_file()
    assert not Path(result['output']).exists()
