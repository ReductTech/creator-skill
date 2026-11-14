"""Configured targets stay stable across Skill locations, cwd and old env vars."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

SKILL = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("target_root_common", SKILL / "scripts/common/_common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


@pytest.mark.parametrize("value", [None, [], {}, {"targetRoot": "", "extra": 1},
                                  {"targetRoot": ""}, {"targetRoot": 1},
                                  {"targetRoot": "relative/project"}])
def test_invalid_configuration_is_rejected(tmp_path, value):
    config = tmp_path / "target-root.json"
    config.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError):
        common.get_target_root(config)


def test_missing_malformed_and_missing_directory_are_rejected(tmp_path):
    config = tmp_path / "target-root.json"
    with pytest.raises(ValueError):
        common.get_target_root(config)
    config.write_text("{invalid", encoding="utf-8")
    with pytest.raises(ValueError):
        common.get_target_root(config)
    config.write_text(json.dumps({"targetRoot": str(tmp_path / "missing")}), encoding="utf-8")
    with pytest.raises(ValueError):
        common.get_target_root(config)
    assert not (tmp_path / "missing").exists()


def prepare_skill(tmp_path, name, target):
    skill = tmp_path / name
    shutil.copytree(SKILL / "scripts", skill / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    (skill / "target-root.json").write_text(json.dumps({"targetRoot": str(target)}), encoding="utf-8")
    return skill


def run(skill, cwd, *arguments):
    return subprocess.run([sys.executable, str(skill / "scripts/tools.py"), *arguments],
                          cwd=cwd, env={**os.environ, "IDL_REPOSITORY_ROOT": str(cwd)},
                          capture_output=True, text=True, encoding="utf-8", timeout=20)


def test_writes_use_config_even_after_moving_skill(tmp_path):
    target = tmp_path / "课程 工程"
    module = target / "modules/Demo"
    module.mkdir(parents=True)
    outline = module / "outlines.json"
    outline.write_text(json.dumps({"pages": [{"title": "Test", "snippet": "Narration"}]}), encoding="utf-8")
    decoy = tmp_path / "other-project"
    decoy.mkdir()
    skill = prepare_skill(tmp_path, "separate skill", target)
    relocated = tmp_path / "moved skill"
    skill.rename(relocated)
    result = run(relocated, decoy, "check.outlines", "--fix")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(outline.read_text())["pages"][0]["id"]
    assert not (decoy / "modules").exists()


def test_empty_target_blocks_work_but_allows_discovery(tmp_path):
    skill = prepare_skill(tmp_path, "skill", "")
    result = run(skill, tmp_path, "check.outlines", "--fix")
    assert result.returncode == 2
    assert "targetRoot" in result.stdout + result.stderr
    result = run(skill, tmp_path, "list", "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout)
    assert not (tmp_path / "modules").exists()


def test_conflicting_target_override_is_rejected(tmp_path):
    target = tmp_path / "project"
    target.mkdir()
    skill = prepare_skill(tmp_path, "skill", target)
    result = run(skill, tmp_path, "check.outlines", "--fix", "--repository", str(tmp_path))
    assert result.returncode == 2
    assert "must match" in result.stdout


def test_node_tool_uses_the_same_target(tmp_path):
    target = tmp_path / "课程 工程"
    pages = target / "modules/Demo/pages"
    pages.mkdir(parents=True)
    (pages.parent / 'outlines.json').write_text(json.dumps({'id':'demo'}),encoding='utf-8')
    (pages / "Demo.tsx").write_text('export const Demo = () => <div className="demo-panel" />;', encoding="utf-8")
    skill = prepare_skill(tmp_path, "skill", target)
    result = run(skill, tmp_path, "check.styles", "--module", "Demo")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["pages"] == 1


def test_direct_script_cannot_override_json(tmp_path):
    target = tmp_path / 'configured'
    target.mkdir()
    skill = prepare_skill(tmp_path, 'skill', target)
    result = subprocess.run([sys.executable, str(skill / 'scripts/checks/outline_fields.py'),
                             '--repository', str(tmp_path), '--fix'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 2
    assert 'must match' in result.stdout
    assert not (tmp_path / 'modules').exists()


def test_relative_paths_ignore_cwd_and_reject_escape(tmp_path, monkeypatch):
    target = tmp_path / 'configured'
    target.mkdir()
    config = tmp_path / 'target-root.json'
    config.write_text(json.dumps({'targetRoot': str(target)}), encoding='utf-8')
    monkeypatch.setattr(common, 'TARGET_ROOT_CONFIG', config)
    monkeypatch.chdir(tmp_path)
    assert common.project_path('modules/Demo') == target / 'modules/Demo'
    with pytest.raises(ValueError, match='inside targetRoot'):
        common.project_path('../outside')


def test_image_tool_does_not_search_parent_projects(tmp_path):
    from PIL import Image
    import random
    outer = tmp_path / 'parent-project'
    target = outer / 'course'
    assets = target / 'assets'
    assets.mkdir(parents=True)
    parent_index = outer / 'modules/shared/asset-index.json'
    parent_index.parent.mkdir(parents=True)
    original = json.dumps({'roots': {'demo': 'course/assets'}, 'formats': {}})
    parent_index.write_text(original, encoding='utf-8')
    Image.frombytes('RGB', (1000, 500), random.Random(0).randbytes(1000*500*3)).save(assets / 'picture.png')
    skill = prepare_skill(tmp_path, 'skill', target)
    result = run(skill, tmp_path, 'assets.compress', 'assets', '--report', 'report.json')
    assert result.returncode == 0, result.stdout + result.stderr
    assert (assets / 'picture.webp').is_file()
    assert (target / 'report.json').is_file()
    assert not (tmp_path / 'report.json').exists()
    assert parent_index.read_text(encoding='utf-8') == original


@pytest.mark.parametrize('value', ['', 'relative/project', {'unexpected': 1}])
def test_node_root_rejects_invalid_configuration(tmp_path, value):
    config = tmp_path / 'target-root.json'
    config.write_text(json.dumps({'targetRoot': value}), encoding='utf-8')
    helper = (SKILL / 'scripts/common/_target_root.mjs').as_uri()
    code = f'import {{getTargetRoot}} from {json.dumps(helper)}; getTargetRoot(process.argv[1]);'
    result = subprocess.run(['node', '--input-type=module', '-e', code, str(config)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'targetRoot' in result.stderr
