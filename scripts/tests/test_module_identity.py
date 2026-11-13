import json
import uuid

import pytest

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("authoring_identity", Path(__file__).resolve().parents[1] / "module/module_identity.py")
identity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(identity)

MODULE_ID = "2e5c4732-a40a-4d20-b954-a61507aabc75"


@pytest.fixture
def modules(tmp_path, monkeypatch):
    root = tmp_path / "modules"
    root.mkdir()
    monkeypatch.setattr(identity, "ROOT", tmp_path)
    monkeypatch.setattr(identity, "MODULES_DIR", root)
    return root


def outline(modules, name=MODULE_ID, module_identity=None, *, missing=False):
    path = modules / name / "outlines.json"
    path.parent.mkdir()
    document = {"id": name, "path": "/modules/" + name.lower(), "title": "Example"}
    if not missing:
        document["moduleIdentity"] = module_identity
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_generate_missing_uuid_without_keys_and_preserve_on_rerun(modules):
    path = outline(modules, missing=True)
    assert identity.process_outlines() == 0
    document = json.loads(path.read_text())
    value = document["moduleIdentity"]
    assert set(value) == {"version", "id"}
    assert value["version"] == 1
    assert uuid.UUID(value["id"]).version == 4
    original = path.read_bytes()
    assert identity.process_outlines() == 0
    assert identity.process_outlines(check_only=True) == 0
    assert path.read_bytes() == original
    assert value["id"] == path.parent.name == document["id"]


def test_check_missing_is_read_only_and_loader_rejects_missing(modules):
    path = outline(modules, missing=True)
    original = path.read_bytes()
    assert identity.process_outlines(check_only=True) == 1
    assert path.read_bytes() == original


@pytest.mark.parametrize("value", [
    None, {}, {"id": MODULE_ID},
    {"version": True, "id": MODULE_ID}, {"version": 2, "id": MODULE_ID},
    {"version": 1, "id": None}, {"version": 1, "id": "invalid"},
    {"version": 1, "id": MODULE_ID.upper()},
    {"version": 1, "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"},
])
def test_invalid_identity_stops_before_generating_anything(modules, value):
    missing = outline(modules, "A", missing=True)
    invalid = outline(modules, "Z", value)
    originals = [p.read_bytes() for p in (missing, invalid)]
    for check_only in (False, True):
        with pytest.raises(identity.IdentityError, match="Invalid"):
            identity.process_outlines(check_only=check_only)
    assert [p.read_bytes() for p in (missing, invalid)] == originals


def test_duplicate_uuid_stops_without_writes(modules):
    missing = outline(modules, "A", missing=True)
    for name in ("B", "C"):
        outline(modules, name, {"version": 1, "id": MODULE_ID})
    original = missing.read_bytes()
    for check_only in (False, True):
        with pytest.raises(identity.IdentityError, match="Duplicate"):
            identity.process_outlines(check_only=check_only)
    assert missing.read_bytes() == original


def test_legacy_signature_is_rejected_without_silent_rewrite(modules):
    path = outline(modules, module_identity={"version": 1, "id": MODULE_ID, "signature": "old"})
    original = path.read_bytes()
    for check_only in (True, False):
        with pytest.raises(identity.IdentityError, match="Invalid moduleIdentity"):
            identity.process_outlines(check_only=check_only)
    assert path.read_bytes() == original


def test_semantic_directory_requires_explicit_migration(modules):
    path = outline(modules, "Semantic", module_identity={"version": 1, "id": MODULE_ID})
    original = path.read_bytes()
    for check_only in (True, False):
        with pytest.raises(identity.IdentityError, match="canonical UUID"):
            identity.process_outlines(check_only=check_only)
    assert path.read_bytes() == original
