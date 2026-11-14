"""Cleanup must delete only selected scratchpads, with dry-run and link guards."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SKILL = Path(__file__).resolve().parents[2]


def invoke(tmp_path, target, *args):
    config = tmp_path / "target.json"
    config.write_text(json.dumps({"targetRoot": str(target)}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SKILL / "scripts/tools.py"), "scratchpad.clean", *map(str, args)],
        cwd=tmp_path, env={**os.environ, "CREATOR_SKILL_TARGET_CONFIG": str(config)},
        capture_output=True, text=True, encoding="utf-8", timeout=15)
    return result


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("keep or remove", encoding="utf-8")


def test_preview_apply_nested_and_idempotence(tmp_path):
    target = tmp_path / "课程 工程"
    touch(target / "modules/Course/_scratchpad/nested/_scratchpad/draft.txt")
    touch(target / "modules/Course/pages/Page/_scratchpad/design.png")
    touch(target / "modules/Course/assets/keep.webp")
    touch(target / "modules/Course/_scratchpad-backup/keep.txt")
    preview = invoke(tmp_path, target, "modules/Course")
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert json.loads(preview.stdout)["matched"] == 2
    assert (target / "modules/Course/_scratchpad").exists()
    applied = invoke(tmp_path, target, "modules/Course", "--apply")
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert len(json.loads(applied.stdout)["removed"]) == 2
    assert not list(target.rglob("_scratchpad"))
    assert (target / "modules/Course/assets/keep.webp").is_file()
    assert (target / "modules/Course/_scratchpad-backup/keep.txt").is_file()
    assert json.loads(invoke(tmp_path, target, ".", "--apply").stdout)["matched"] == 0


def test_page_scope_and_no_directory_exclusions(tmp_path):
    target = tmp_path / "project"
    for path in ["pages/A/_scratchpad/a", "pages/B/_scratchpad/b",
                 "shared/_scratchpad/s", "modules/shared/_scratchpad/s",
                 "node_modules/vendor/_scratchpad/s", ".git/_scratchpad/s"]:
        touch(target / path)
    assert invoke(tmp_path, target, "pages/A", "--apply").returncode == 0
    assert not (target / "pages/A/_scratchpad").exists()
    assert (target / "pages/B/_scratchpad").exists()
    result = invoke(tmp_path, target, ".", "--apply")
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(json.loads(result.stdout)["removed"]) == 5
    for path in ["shared", "modules/shared", "node_modules/vendor", ".git"]:
        assert not (target / path / "_scratchpad").exists()
    assert invoke(tmp_path, target, "modules/shared", "--apply").returncode == 0


def test_requires_scope_and_rejects_escape(tmp_path):
    target = tmp_path / "project"
    touch(target / "_scratchpad/keep")
    touch(tmp_path / "outside/_scratchpad/keep")
    for args in [(), ("missing", "--apply")]:
        assert invoke(tmp_path, target, *args).returncode == 2
    assert (target / "_scratchpad/keep").exists()
    assert (tmp_path / "outside/_scratchpad/keep").exists()


def test_never_follows_link_or_junction(tmp_path):
    target = tmp_path / "project"
    touch(target / "real/_scratchpad/local")
    outside = tmp_path / "outside"
    touch(outside / "_scratchpad/keep")
    link = target / "linked"
    if os.name == "nt":
        # Native PowerShell creates a directory junction without symlink privileges.
        result = subprocess.run(["powershell", "-NoProfile", "-Command",
                                 "New-Item -ItemType Junction -Path '" + str(link).replace("'", "''")
                                 + "' -Target '" + str(outside).replace("'", "''") + "' | Out-Null"], capture_output=True)
        if result.returncode:
            pytest.skip("Directory junction creation unavailable")
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        result = invoke(tmp_path, target, ".", "--apply")
        assert result.returncode == 0, result.stdout + result.stderr
        assert str(link) in json.loads(result.stdout)["skipped"]
        assert (outside / "_scratchpad/keep").is_file()
        assert invoke(tmp_path, target, "linked", "--apply").returncode == 2
    finally:
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()


def test_absolute_path_without_configuration_and_deep_nesting(tmp_path):
    chosen = tmp_path / "指定路径"
    deep = chosen.joinpath(*(["d"] * 20))
    touch(deep / "_scratchpad/outer/_scratchpad/draft")
    touch(chosen / "other/_scratchpad/draft")
    touch(chosen / "_scratchpad-backup/keep")
    touch(tmp_path / "outside/_scratchpad/keep")
    result = subprocess.run(
        [sys.executable, str(SKILL / "scripts/tools.py"), "scratchpad.clean", str(chosen), "--apply"],
        env={**os.environ, "CREATOR_SKILL_TARGET_CONFIG": str(tmp_path / "missing.json")},
        capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(json.loads(result.stdout)["removed"]) == 2
    assert not list(chosen.rglob("_scratchpad"))
    assert (chosen / "_scratchpad-backup/keep").is_file()
    assert (tmp_path / "outside/_scratchpad/keep").is_file()


def test_selected_scratchpad_itself_can_be_removed(tmp_path):
    target = tmp_path / "project"
    touch(target / "_scratchpad/nested/_scratchpad/file")
    result = invoke(tmp_path, target, "_scratchpad", "--apply")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (target / "_scratchpad").exists()
    assert target.is_dir()
