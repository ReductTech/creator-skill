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


@pytest.fixture
def isolated_skill(tmp_path):
    """CLI tests get their own configured Skill instead of overriding another one."""
    from _common import get_target_root
    runtime = get_target_root()
    skill = tmp_path / "isolated skill"
    shutil.copytree(SCRIPTS, skill / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    (skill / "target-root.json").write_text(json.dumps({"targetRoot": str(tmp_path)}), encoding="utf-8")
    return skill, {**os.environ, "PYTHONPATH": str(runtime / "backend/src")}
