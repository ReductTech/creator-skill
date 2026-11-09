"""Configuration-free discovery, consistent layouts and honest typecheck reports."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from _common import read_modules
from course_paths import modules_directory
from checks.outline_fields import process
from checks.validate_module import validate_modules
from media import capture_slides
from module.init_module import ensure_outline
from tools import catalog

MID = '11111111-1111-4111-8111-111111111111'
SCRIPTS = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('flat', [False, True])
def test_discovery_creation_validation_capture_and_node_styles_agree(tmp_path, isolated_skill, monkeypatch, flat):
    skill, env = isolated_skill
    base = tmp_path if flat else tmp_path / 'modules'
    folder = base / MID
    (folder / 'pages/Opening').mkdir(parents=True)
    (folder / 'pages/Opening/Opening.tsx').write_text('export const Page=()=> <p className="demo-page">Opening</p>')
    doc = {'id': MID, 'alias': 'friendly', 'title': 'Demo', 'path': '/modules/' + MID,
           'moduleIdentity': {'version': 1, 'id': MID},
           'ppt': {'entry': 'pages/Opening/Opening.tsx'},
           'pages': [{'id': 'opening', 'title': 'Opening', 'snippet': 'Narration'}]}
    (folder / 'outlines.json').write_text(json.dumps(doc))
    assert modules_directory(tmp_path) == base
    assert list(read_modules(tmp_path))[0][0] == folder
    assert process(tmp_path, module='friendly')['modules'] == 1
    assert validate_modules(tmp_path, 'friendly') == []
    monkeypatch.setattr(capture_slides, 'ROOT', tmp_path)
    assert capture_slides.resolve_module('friendly')[0] == folder
    result = subprocess.run([sys.executable, str(skill / 'scripts/tools.py'), 'check.styles', '--module', 'friendly'],
                            cwd=skill, env=env, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['pages'] == 1
    created = ensure_outline(tmp_path, '22222222-2222-4222-8222-222222222222')
    assert Path(created['path']).parent.parent == base


def test_mixed_course_layout_is_reported_instead_of_silently_skipping_courses(tmp_path):
    for base in [tmp_path, tmp_path / 'modules']:
        folder = base / MID
        folder.mkdir(parents=True)
        (folder / 'outlines.json').write_text('{}')
    with pytest.raises(ValueError, match='Mixed'):
        modules_directory(tmp_path)


def test_every_catalog_help_and_python_import_work_without_a_target(tmp_path, isolated_skill):
    skill, env = isolated_skill
    (skill / 'target-root.json').unlink()
    env = {**env, 'CREATOR_SKILL_TARGET_CONFIG': str(tmp_path / 'missing-target-root.json')}
    for tool in catalog():
        result = subprocess.run([sys.executable, '-S', str(skill / 'scripts/tools.py'), tool['id'], '--help'],
                                env=env, cwd=tmp_path, text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, (tool['id'], result.stdout, result.stderr)
    # Actual work still fails before creating a course when no target is configured.
    result = subprocess.run([sys.executable, str(skill / 'scripts/tools.py'), 'module.init', '--title', 'Must not create'],
                            env=env, cwd=tmp_path, text=True, capture_output=True, timeout=15)
    assert result.returncode == 2
    assert not (tmp_path / 'modules').exists()


def test_typecheck_attributes_real_new_errors_and_missing_environment(tmp_path):
    runner = SCRIPTS / 'tests/typecheck_scaffold.mjs'
    result = subprocess.run(['node', str(runner)], input=json.dumps({'Broken.tsx': 'export const count: number = "wrong";'}),
                            text=True, capture_output=True, timeout=60)
    report = json.loads(result.stdout)
    assert result.returncode == 1 and report['status'] == 'failed'
    assert any(issue['code'] == 2322 for issue in report['newIssues'])
    assert report['environmentErrors'] == []
    result = subprocess.run(['node', str(runner)], input='{}', text=True, capture_output=True, timeout=15,
                            env={**os.environ, 'CREATOR_SKILL_TARGET_CONFIG': str(tmp_path / 'missing.json')})
    report = json.loads(result.stdout)
    assert result.returncode == 2 and report['status'] == 'error'
    assert report['environmentErrors'] and report['unverified']
