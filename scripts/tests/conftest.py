from pathlib import Path
import sys
import json
import os
import shutil
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(SCRIPTS),
    str(SCRIPTS / "common"),
]


@pytest.fixture(autouse=True)
def isolated_local_preferences(tmp_path, monkeypatch):
    """Tests isolate consent and basic-pack fixtures; adaptive tests explicitly use auto."""
    monkeypatch.setenv('CREATOR_SKILL_LOCAL_STATE',str(tmp_path/'local-state'))
    monkeypatch.setenv('CREATOR_SKILL_CHECK_MODE','basic')


@pytest.fixture
def isolated_skill(tmp_path):
    """CLI tests get their own configured Skill instead of overriding another one."""
    skill = tmp_path / "isolated skill"
    shutil.copytree(SCRIPTS, skill / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    return skill, {**os.environ, "CREATOR_SKILL_PROJECT_ROOT": str(tmp_path)}
