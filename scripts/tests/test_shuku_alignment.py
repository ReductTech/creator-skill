"""Observable Shuku contracts, independent of a platform checkout or credentials."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest

from artifact_capture_server import artifact_server
from asset_protocol import record, put_bucket
from checks.validate_module import validate_modules
from module_assets import asset_directory

MID = '11111111-1111-4111-8111-111111111111'
REV = 'a' * 64


@pytest.mark.parametrize('versioned', [False, True])
def test_completed_artifacts_only_with_checksum_and_server_cleanup(tmp_path, versioned):
    folder = tmp_path / MID / REV if versioned else tmp_path / MID
    folder.mkdir(parents=True)
    raw = b'<html>compiled lesson</html>'
    (folder / 'index.html').write_bytes(raw)
    (folder / 'secret.tsx').write_text('source must not be served')
    (folder / 'artifact-manifest.json').write_text(json.dumps({
        'module_id': MID, 'revision': REV,
        'files': [{'path': 'index.html', 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}],
    }))
    with artifact_server(tmp_path) as address:
        for route in ['/scenedeck/?deck=' + MID, '/modules/' + MID]:
            assert urlopen(address + route).read() == raw
        base = '/' + MID + ('/' + REV if versioned else '')
        for route in [base + '/secret.tsx', '/%2e%2e/shuku.json', '/.staging/input.tsx']:
            with pytest.raises(HTTPError) as error:
                urlopen(address + route)
            assert error.value.code == 404
        # Same size corruption must still be detected, not only length changes.
        (folder / 'index.html').write_bytes(raw.replace(b'lesson', b'broken'))
        with pytest.raises(HTTPError) as error:
            urlopen(address + base + '/index.html')
        assert error.value.code == 409
    with pytest.raises(URLError):
        urlopen(address, timeout=1)


def test_public_wire_identity_includes_format_and_final_bytes():
    raw = b'example'
    digest = hashlib.sha256(raw).hexdigest()
    jpg = record('picture.jpeg', raw)
    assert jpg['object_key'] == f'shuku-oss/assets/sha256/{digest[:2]}/{digest}.jpg'
    assert jpg['mime'] == 'image/jpeg'
    assert record('renamed.jpg', raw)['object_key'] == jpg['object_key']
    assert record('picture.png', raw)['object_key'] != jpg['object_key']
    assert record('picture.png', b'\xff\xd8converted')['object_key'].endswith('.jpg')
    for name in ['index.html', 'entry.js', 'styles.css']:
        with pytest.raises(ValueError, match='Compiled code'):
            record(name, raw)


def test_upload_collision_verifies_existing_object():
    raw = b'example'
    key = record('picture.jpg', raw)['object_key']
    bucket = SimpleNamespace(
        object_exists=lambda _: False,
        head_object=lambda _: SimpleNamespace(content_length=len(raw), headers={'x-oss-meta-sha256': 'bad'}),
    )
    class Collision(Exception):
        status = 409
    def put(*args, **kwargs):
        raise Collision()
    bucket.put_object = put
    with pytest.raises(ValueError, match='invalid hash'):
        put_bucket(bucket, key, raw)


@pytest.mark.parametrize('flat', [False, True])
def test_nested_entry_and_new_asset_helper_forms(tmp_path, flat):
    folder = (tmp_path if flat else tmp_path / 'modules') / MID
    (folder / 'pages').mkdir(parents=True)
    (folder / 'assets').mkdir()
    (folder / 'assets/image.png').write_bytes(b'image')
    (folder / 'pages/Page.tsx').write_text("moduleAssetUrl('image.png'); moduleAssetUrl(moduleIdentity.id, 'image.png');")
    outline = {'id': MID, 'title': 'Course', 'path': '/modules/' + MID,
               'moduleIdentity': {'version': 1, 'id': MID}, 'ppt': {'entry': 'pages/Page.tsx'},
               'pages': [{'id': 'f2ac1473-665f-46f8-bcb1-53c9438f6482', 'title': 'One', 'snippet': 'Narration'}]}
    (folder / 'outlines.json').write_text(json.dumps(outline))
    assert validate_modules(tmp_path) == []
    assert asset_directory(tmp_path, MID) == folder / 'assets'
    (folder / 'pages/Page.tsx').write_text("moduleAssetUrl('../outside.png')")
    assert any('escaping asset' in error for error in validate_modules(tmp_path))


def test_record_only_dry_run_has_no_config_or_sdk_dependency(tmp_path, monkeypatch):
    file = Path(__file__).resolve().parents[1] / 'media/upload-assets-oss.py'
    spec = importlib.util.spec_from_file_location('aligned_uploader', file)
    uploader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(uploader)
    assets = tmp_path / MID / 'assets'
    assets.mkdir(parents=True)
    (assets.parent / 'outlines.json').write_text(json.dumps({'moduleIdentity': {'id': MID}}))
    (assets / 'record.json').write_text('{}')
    monkeypatch.setattr(uploader, 'get_target_root', lambda: tmp_path)
    args = uploader.build_parser().parse_args(['--module', MID, '--records-only', '--dry-run', '--config', 'missing.json'])
    result = uploader.upload_assets(args)
    assert result['unique_objects'] == 1
    assert result['manifest']['files'][0]['path'] == MID + '/record.json'
    assert not (tmp_path / 'asset-index.json').exists()


def test_source_only_flat_course_media_check_uses_configured_root(tmp_path):
    scripts = Path(__file__).resolve().parents[1]
    skill = tmp_path / 'independent skill'
    for name in ['checks/asset_imports.mjs', 'common/_target_root.mjs', 'common/_course_paths.cjs']:
        target = skill / 'scripts' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(scripts / name, target)
    root = tmp_path / 'course sources'
    module = root / MID
    module.mkdir(parents=True)
    (module / 'outlines.json').write_text(json.dumps({'id': MID}))
    (module / 'page.tsx').write_text("import image from './media/image.png';")
    (skill / 'target-root.json').write_text(json.dumps({'targetRoot': str(root)}))
    tool = skill / 'scripts/checks/asset_imports.mjs'
    def run(*extra):
        return subprocess.run(['node', str(tool), *extra], cwd=tmp_path, text=True, capture_output=True, timeout=15)
    assert run('--module', MID).returncode == 1
    (module / 'media').mkdir()
    (module / 'media/image.png').write_bytes(b'image')
    assert run('--module', MID).returncode == 0
    assert run('--module', '../../outside').returncode == 2
    assert run('--root', str(tmp_path)).returncode == 2
