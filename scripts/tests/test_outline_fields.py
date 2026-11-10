from uuid import UUID
import pytest
import json
from checks.outline_fields import process


def write_module(root, pages, source=""):
    directory = root / "modules" / "Example"
    directory.mkdir(parents=True)
    target = directory / "outlines.json"
    target.write_text(json.dumps({"pages": pages}), encoding="utf-8")
    (directory / "Ppt.tsx").write_text(source, encoding="utf-8")
    return target


def test_fix_reuses_scene_ids_and_is_idempotent(tmp_path):
    file = write_module(tmp_path, [{"title": "标题", "snippet": "实际讲稿"}],
                        "const deck={scenes:[{id:'11111111-1111-4111-8111-111111111111',title:outline.pages[0].title}]};")
    result = process(tmp_path, fix=True)
    assert result["errors"] == []
    assert json.loads(file.read_text())["pages"][0]["id"] == "11111111-1111-4111-8111-111111111111"
    before = file.read_bytes()
    assert process(tmp_path, fix=True)["filledIds"] == 0
    assert file.read_bytes() == before


def test_component_mapping_and_existing_ids_are_preserved(tmp_path):
    file = write_module(tmp_path, [{"id": "22222222-2222-4222-8222-222222222222", "title": "一", "snippet": "讲稿一"},
                                  {"title": "二", "snippet": "讲稿二"}],
                        "const pages=[{id:'33333333-3333-4333-8333-333333333333',Component:One},{id:'44444444-4444-4444-8444-444444444444',Component:Two}];const deck={scenes:pages.map(render)};")
    assert process(tmp_path, fix=True)["errors"] == []
    assert [p["id"] for p in json.loads(file.read_text())["pages"]] == ["22222222-2222-4222-8222-222222222222", "44444444-4444-4444-8444-444444444444"]


def test_missing_prose_and_duplicates_fail_without_writing(tmp_path):
    file = write_module(tmp_path, [{"id": "one", "title": "标题", "snippet": ""},
                                  {"id": "one", "title": "", "snippet": "讲稿"}])
    before = file.read_bytes()
    errors = process(tmp_path)["errors"]
    assert any("snippet" in error for error in errors)
    assert any("title" in error for error in errors)
    assert any("duplicate" in error for error in errors)
    assert file.read_bytes() == before


def test_planned_page_gets_stable_non_numbered_id(tmp_path):
    file = write_module(tmp_path, [{"title": "尚未实现", "snippet": "讲稿"}])
    assert process(tmp_path, fix=True)["errors"] == []
    value = json.loads(file.read_text())["pages"][0]["id"]
    assert str(UUID(value)) == value and UUID(value).version == 4
    assert process(tmp_path, fix=True)["filledIds"] == 0


@pytest.mark.parametrize("value", ["creator-workflow", "01", "11111111111141118111111111111111", "F2AC1473-665F-46F8-BCB1-53C9438F6482", "{11111111-1111-4111-8111-111111111111}"])
def test_invalid_existing_id_is_rejected_without_silent_migration(tmp_path, value):
    file = write_module(tmp_path, [{"id": value, "title": "Title", "snippet": "Notes"}])
    before = file.read_bytes()
    for fix in (False, True):
        assert any("canonical UUID" in error for error in process(tmp_path, fix=fix)["errors"])
        assert file.read_bytes() == before


def test_fix_rejects_invalid_scene_identity(tmp_path):
    file = write_module(tmp_path, [{"title": "Title", "snippet": "Notes"}],
                        "const deck={scenes:[{id:'creator-workflow',title:outline.pages[0].title}]};")
    before = file.read_bytes()
    assert any("canonical UUID" in error for error in process(tmp_path, fix=True)["errors"])
    assert file.read_bytes() == before


def test_same_title_planned_pages_get_distinct_persistent_uuids(tmp_path):
    file = write_module(tmp_path, [{"title": "Same", "snippet": "Notes"}] * 2)
    assert process(tmp_path, fix=True)["errors"] == []
    ids = [page["id"] for page in json.loads(file.read_text())["pages"]]
    assert len(set(ids)) == 2
    assert all(UUID(value).version == 4 for value in ids)
    assert process(tmp_path, fix=True)["filledIds"] == 0
