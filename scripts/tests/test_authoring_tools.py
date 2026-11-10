import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from checks.validate_module import validate_modules
from checks.validate_skill import validate_skill

TOOLS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("oss_uploader", TOOLS / "media/upload-assets-oss.py")
uploader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uploader)
UUID = "2e5c4732-a40a-4d20-b954-a61507aabc75"


def course(root, name=UUID, module_id=UUID):
    directory = root / "modules" / name
    directory.mkdir(parents=True)
    (directory / "Guide.tsx").write_text("export function Guide() { return null; }")
    outline = {"id": name.lower(), "title": "Example", "path": "/modules/" + name.lower(),
               "entry": "Guide.tsx", "moduleIdentity": {"version": 1, "id": module_id},
               "pages": [{"id": "f2ac1473-665f-46f8-bcb1-53c9438f6482", "title": "Question", "snippet": "Narration"}]}
    (directory / "outlines.json").write_text(json.dumps(outline))
    return directory


@pytest.mark.parametrize("layout", ["module", "legacy"])
def test_valid_course_and_literal_asset_are_accepted(tmp_path, layout):
    directory = course(tmp_path)
    assets = directory / "assets" if layout == "module" else tmp_path / "assets" / UUID
    assets.mkdir(parents=True)
    (assets / "image.png").write_bytes(b"image")
    (directory / "asset.ts").write_text(f"moduleAssetUrl('{UUID}', 'image.png')")
    assert validate_modules(tmp_path) == [] if layout == "module" else any("missing" in e for e in validate_modules(tmp_path))


@pytest.mark.parametrize("field", ["interaction", "next", "section", "implementationStatus"])
def test_obsolete_outline_fields_are_rejected(tmp_path, field):
    directory = course(tmp_path)
    path = directory / "outlines.json"
    doc = json.loads(path.read_text())
    doc["pages"][0][field] = "legacy value"
    path.write_text(json.dumps(doc))
    assert any("obsolete outline fields" in error and field in error for error in validate_modules(tmp_path, strict_authoring=True))
    assert not any("obsolete outline fields" in error for error in validate_modules(tmp_path))


def test_missing_and_escaping_assets_are_rejected(tmp_path):
    directory = course(tmp_path)
    (directory / "asset.ts").write_text(f"moduleAssetUrl('{UUID}', '../../outside.png')")
    (tmp_path / "outside.png").write_bytes(b"must not be accepted")
    assert any("escaping asset" in error for error in validate_modules(tmp_path))


def test_uuid_duplicates_detected_even_when_selecting_one_module(tmp_path):
    course(tmp_path, "A")
    course(tmp_path, "B")
    assert any("Duplicate course UUID" in error for error in validate_modules(tmp_path, "A"))


def test_unknown_module_reports_failure(tmp_path):
    course(tmp_path)
    assert any("Unknown module" in error for error in validate_modules(tmp_path, "typo"))


def test_missing_entry_and_duplicate_pages_are_rejected(tmp_path):
    directory = course(tmp_path)
    (directory / "Guide.tsx").unlink()
    path = directory / "outlines.json"
    doc = json.loads(path.read_text())
    doc["pages"] *= 2
    path.write_text(json.dumps(doc))
    errors = validate_modules(tmp_path)
    assert any("existing module TSX" in error for error in errors)
    assert any("duplicate page" in error for error in errors)


def test_module_local_assets_are_allowed_but_wrong_asset_id_is_rejected(tmp_path):
    directory = course(tmp_path)
    (directory / "assets").mkdir()
    (directory / "assets/picture.png").write_bytes(b"image")
    (directory / "Deck.tsx").write_text('const element = <SceneDeck assetId="example" />')
    errors = validate_modules(tmp_path)
    assert not any("module-local" in error for error in errors)
    assert any("assetId must" in error for error in errors)


def test_skill_rejects_empty_description_and_broken_reference(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text('---\nname: example\ndescription: ""\n---\n')
    assert not validate_skill(tmp_path)[0]
    path.write_text('---\nname: example\ndescription: Does something\n---\n[missing](missing.md)\n')
    assert not validate_skill(tmp_path)[0]


def test_upload_reuses_verified_content_and_forbids_overwrite(tmp_path):
    import hashlib
    path = tmp_path / "picture.png"
    path.write_bytes(b"image")
    calls = []
    bucket = SimpleNamespace(object_exists=lambda key: True,
        head_object=lambda key: SimpleNamespace(content_length=5, headers={"x-oss-meta-sha256": hashlib.sha256(b"image").hexdigest()}),
        put_object=lambda *a, **kw: calls.append((a, kw)))
    assert uploader.upload_one(bucket, tmp_path, path)[0] == "skipped"
    assert calls == []
    with pytest.raises(ValueError, match="overwritten"):
        uploader.upload_one(bucket, tmp_path, path, True)
    bucket.object_exists = lambda key: False
    uploader.upload_one(bucket, tmp_path, path)
    assert calls[-1][1]["headers"]["x-oss-forbid-overwrite"] == "true"
    assert calls[-1][1]["headers"]["x-oss-object-acl"] == "public-read"


def test_dry_run_groups_duplicates_and_retains_paths_without_oss(tmp_path, monkeypatch):
    import sys
    directory = tmp_path / "modules" / UUID / "assets"
    directory.mkdir(parents=True)
    (directory.parent / "outlines.json").write_text(json.dumps({"moduleIdentity": {"id": UUID}}))
    for name in ["image.png", "copy.png"]:
        (directory / name).write_bytes(b"same image")
    monkeypatch.setattr(uploader, "get_target_root", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "oss2", None)
    args = uploader.build_parser().parse_args(["--module", UUID, "--dry-run"])
    result = uploader.upload_assets(args)
    assert result["unique_objects"] == 1
    assert {r["path"] for r in result["manifest"]["files"]} == {UUID + "/image.png", UUID + "/copy.png"}
    assert len({r["object_key"] for r in result["manifest"]["files"]}) == 1
    assert result["objects"][0].startswith("shuku-oss/assets/sha256/")


def test_upload_rejects_bytes_changed_after_manifest(tmp_path):
    path = tmp_path / 'picture.png'
    path.write_bytes(b'original')
    key = uploader.object_key(tmp_path, path)
    path.write_bytes(b'changed while editing')
    with pytest.raises(ValueError, match='changed after manifest'):
        uploader.upload_one(SimpleNamespace(), tmp_path, path, expected_key=key)


def test_all_files_explicitly_placed_in_public_assets_are_uploaded(tmp_path):
    for name in ["course/view.npz", "datasets/full.npy", "course/models/model.pt", "course/digit-training/job/result.npz"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"data")
    assert {path.relative_to(tmp_path).as_posix() for path in uploader.visualization_files(tmp_path)} == {
        "course/view.npz", "datasets/full.npy", "course/models/model.pt", "course/digit-training/job/result.npz"
    }


def test_legacy_outline_without_slug_is_preserved(tmp_path):
    directory = course(tmp_path)
    path = directory / "outlines.json"
    doc = json.loads(path.read_text())
    del doc["id"]
    path.write_text(json.dumps(doc))
    assert validate_modules(tmp_path) == []


@pytest.mark.parametrize("layout", ["module", "legacy"])
def test_atlas_virtual_image_requires_a_real_mapped_sheet(tmp_path, layout):
    directory = course(tmp_path)
    assets = directory / "assets" if layout == "module" else tmp_path / "assets" / UUID
    (assets / "image-atlases").mkdir(parents=True)
    (assets / "image-atlases/index.json").write_text(json.dumps({"virtual.png": {"sheet": "image-atlases/sheet.png"}}))
    (directory / "asset.ts").write_text(f"atlasCropUrl(moduleAssetUrl('{UUID}', 'virtual.png'))")
    assert any("missing" in error for error in validate_modules(tmp_path))
    (assets / "image-atlases/sheet.png").write_bytes(b"sheet")
    assert validate_modules(tmp_path) == [] if layout == "module" else any("missing" in e for e in validate_modules(tmp_path))
    (directory / "asset.ts").write_text(f"moduleAssetUrl('{UUID}', 'virtual.png')")
    assert any("missing" in error for error in validate_modules(tmp_path))


def test_module_assets_take_precedence_over_legacy_root(tmp_path):
    from module_assets import asset_directory
    directory = course(tmp_path)
    (directory / "assets").mkdir()
    legacy = tmp_path / "assets" / UUID
    legacy.mkdir(parents=True)
    (legacy / "old.png").write_bytes(b"old")
    (directory / "asset.ts").write_text(f"moduleAssetUrl('{UUID}', 'old.png')")
    assert asset_directory(tmp_path, UUID) == directory / "assets"
    assert any("missing" in error for error in validate_modules(tmp_path))
    (directory / "assets/old.png").write_bytes(b"current")
    assert validate_modules(tmp_path) == []


def test_default_upload_discovers_module_assets_and_preserves_uuid(tmp_path, monkeypatch):
    directory = course(tmp_path)
    (directory / "assets/images").mkdir(parents=True)
    (directory / "assets/images/picture.jpg").write_bytes(b"image")
    (directory / "_scratchpad").mkdir()
    (directory / "_scratchpad/draft.png").write_bytes(b"draft")
    shared = tmp_path / "modules/shared"
    (shared / "assets").mkdir(parents=True)
    (shared / "assets/common.svg").write_bytes(b"shared")
    (shared / "asset-index.json").write_text(json.dumps({
        "roots": {UUID: "modules/" + UUID + "/assets", "shared": "modules/shared/assets"},
        "formats": {},
    }))
    monkeypatch.setattr(uploader, "get_target_root", lambda: tmp_path)
    monkeypatch.setattr(uploader, "DEFAULT_ASSETS_DIR", tmp_path / "modules")
    args = uploader.build_parser().parse_args(["--module", UUID, "--dry-run"])
    result = uploader.upload_assets(args)
    assert result["objects"] == [uploader.object_key(directory, directory / "assets/images/picture.jpg")]
    args.module = None
    result = uploader.upload_assets(args)
    assert set(result["objects"]) == {
        uploader.object_key(directory, directory / "assets/images/picture.jpg"),
        uploader.object_key(shared, shared / "assets/common.svg"),
    }


@pytest.mark.parametrize("page_id", ["creator-workflow", "01", "F2AC1473-665F-46F8-BCB1-53C9438F6482", "f2ac1473665f46f8bcb153c9438f6482"])
def test_module_rejects_noncanonical_page_uuid(tmp_path, page_id):
    directory = course(tmp_path)
    path = directory / "outlines.json"
    doc = json.loads(path.read_text())
    doc["pages"][0]["id"] = page_id
    path.write_text(json.dumps(doc))
    before = path.read_bytes()
    assert any("canonical UUID" in error for error in validate_modules(tmp_path))
    assert path.read_bytes() == before
