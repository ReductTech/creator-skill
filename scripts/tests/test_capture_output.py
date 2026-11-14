"""Capture entry isolation, publish timing and official output boundaries."""
from contextlib import contextmanager
import io
import json

import pytest
from PIL import Image

from media import capture_slides as capture


def test_built_capture_never_mounts_source(tmp_path):
    class Context:
        def route(self,*args):pytest.fail('Must not mount source')
        def add_init_script(self,*args):pytest.fail('Must not inject source entry')
    capture.configure_module_capture(Context(),tmp_path,'http://localhost:5180')


def setup_capture(tmp_path, monkeypatch):
    monkeypatch.setattr(capture, "ROOT", tmp_path)
    monkeypatch.setattr(capture, "resolve_module", lambda _: (tmp_path, "fixture", "uuid"))
    monkeypatch.setattr(capture, "scene_ids", lambda *args: ["one", "two"])
    official = tmp_path / "assets/scenedeck-thumbnails"
    closed = False

    @contextmanager
    def session(*args, **kwargs):
        nonlocal closed
        yield object(), "http://localhost:5173"
        assert not official.exists(), "Publishing while Vite is watched can reload later captures"
        closed = True

    def take(*args):
        assert not closed
        assert not official.exists()
        args[6].update(status="passed", text={"status": "passed", "characters": 1})
        return Image.new("RGB", (1600, 900), "navy")

    monkeypatch.setattr(capture, "browser_session", session)
    monkeypatch.setattr(capture, "capture_slide", take)
    return official


def test_publish_after_close_uses_webp_and_ignores_legacy_mapping(tmp_path, monkeypatch):
    official = setup_capture(tmp_path, monkeypatch)
    index = tmp_path / "modules/shared/asset-index.json"
    index.parent.mkdir(parents=True)
    index.write_text(json.dumps({"formats": {"uuid/scenedeck-thumbnails/one.png": "scenedeck-thumbnails/one.jpg"}}))
    args = capture.build_parser().parse_args(["--module", "fixture", "--format", "thumbnails"])
    result = capture.capture_module(args)
    assert result["errors"] == []
    assert set(p.name for p in official.iterdir()) == {"one.webp", "two.webp"}
    with Image.open(official / "one.webp") as saved:
        assert saved.format == "WEBP" and saved.size == (1600, 900)
    with Image.open(official / "two.webp") as saved:
        assert saved.format == "WEBP"
    with Image.open(tmp_path / 'assets/course-covers/one.webp') as cover:
        assert cover.format == 'WEBP' and cover.size == (1600, 900)
    assert not (tmp_path / 'assets/course-covers/two.webp').exists()
    assert not (tmp_path / "_scratchpad/screenshots").exists()
    report = json.loads((tmp_path / '_scratchpad/thumbnails/report.json').read_text(encoding='utf-8'))
    assert report['generatedCount'] == report['requestedCount'] == 2
    assert report['generationStatus'] == 'ok' and report['checksStatus'] == 'passed'
    assert report['timing']['totalSeconds'] >= 0
    with Image.open(report['contactSheet']) as sheet:
        assert sheet.size == (1600, 252)


def test_obsolete_thumbnail_mapping_is_ignored(tmp_path, monkeypatch):
    setup_capture(tmp_path, monkeypatch)
    index = tmp_path / "modules/shared/asset-index.json"
    index.parent.mkdir(parents=True)
    index.write_text(json.dumps({"formats": {"uuid/scenedeck-thumbnails/one.png": "../../escaped.jpg"}}))
    args = capture.build_parser().parse_args(["--module", "fixture", "--format", "thumbnails"])
    result = capture.capture_module(args)
    assert result["errors"] == []
    assert not (tmp_path / "escaped.jpg").exists()
    assert len(result["files"]) == 2


def test_single_nonfirst_page_does_not_replace_home_cover(tmp_path, monkeypatch):
    setup_capture(tmp_path, monkeypatch)
    args = capture.build_parser().parse_args(['--module', 'fixture', '--slide', 'two', '--format', 'thumbnails'])
    result = capture.capture_module(args)
    assert result['generatedCount'] == result['requestedCount'] == 1
    assert result['coverFiles'] == []
    assert not (tmp_path / 'assets/course-covers').exists()


def test_external_thumbnail_output_rejected_before_browser(tmp_path, monkeypatch):
    monkeypatch.setattr(capture, "resolve_module", lambda _: (tmp_path, "fixture", "uuid"))
    monkeypatch.setattr(capture, "browser_session", lambda *a, **k: pytest.fail("must not launch"))
    args = capture.build_parser().parse_args(["--module", "fixture", "--format", "thumbnails", "--output", str(tmp_path / "outside")])
    with pytest.raises(ValueError, match="inside"):
        capture.capture_module(args)


@pytest.mark.parametrize('kind,matching,expected', [('creator-capture', True, True), ('creator-capture', False, False), ('other-service', True, False)])
def test_server_reuse_requires_this_exact_checkout(tmp_path, monkeypatch, kind, matching, expected):
    monkeypatch.setattr(capture, 'ROOT', tmp_path)
    info = {'kind': kind, 'root': str(tmp_path if matching else tmp_path / 'other-checkout')}
    monkeypatch.setattr(capture, 'urlopen', lambda *args, **kwargs: io.BytesIO(json.dumps(info).encode()))
    assert (capture.running_vite() is not None) is expected


def test_cold_optimizer_retry_is_bounded_and_does_not_repeat_captured_slides(tmp_path, monkeypatch):
    setup_capture(tmp_path, monkeypatch)
    class InitialTimeout(Exception):
        pass
    monkeypatch.setattr(capture, 'PlaywrightError', InitialTimeout)
    attempts = []
    def ids(*args):
        attempts.append(1)
        if len(attempts) == 1:
            raise InitialTimeout('cold dependency optimizer')
        return ['one', 'two']
    monkeypatch.setattr(capture, 'scene_ids', ids)
    args = capture.build_parser().parse_args(['--module', 'fixture', '--format', 'thumbnails'])
    result = capture.capture_module(args)
    assert len(attempts) == 2
    assert result['generatedCount'] == result['requestedCount'] == 2
    assert not result['errors']


def test_built_capture_keeps_uuid_urls_and_never_mounts_source(tmp_path, monkeypatch):
    uid = "2e5c4732-a40a-4d20-b954-a61507aabc75"
    module = tmp_path / "modules" / uid
    module.mkdir(parents=True)
    (module / "outlines.json").write_text(json.dumps({"id": uid}))
    (tmp_path / "dist").mkdir()
    built = tmp_path / 'dist' / uid
    built.mkdir()
    (built / 'artifact-manifest.json').write_text(json.dumps({'module_id':uid, 'revision':'a'*64, 'files':[]}))
    monkeypatch.setattr(capture, "ROOT", tmp_path)
    class Context:
        def route(self, *args): pytest.fail("Built capture must not mount source routes")
        def add_init_script(self, *args): pytest.fail("Built capture must not inject a source entry")
    capture.configure_module_capture(Context(), module, "http://localhost:5180")
    url = capture.capture_url("http://localhost:5180", uid, "opening")
    assert uid + "/index.html?" in url
    assert "mode=ppt" in url and "page=opening" in url and "slide=" not in url
    assert "/scenedeck/" not in url
