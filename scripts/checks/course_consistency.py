#!/usr/bin/env python3
"""Compare outline order and notes against Guide and 术库.

Reads: The selected outline and runtime pages, or a saved snapshot.
Writes: Only --save-snapshot writes a file; a temporary isolated browser and completed-artifact server may be used.
"""

from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from _common import resolve_module, emit_result, report_error, scratchpad_path, project_path
from media.capture_slides import browser_session, capture_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-output", type=Path, help="completed build directory; default targetRoot/dist")
    parser.add_argument(
        "--module", required=True, help="module directory, slug or UUID"
    )
    parser.add_argument(
        "--base-url", help="completed-course preview service URL; omit to serve local build artifacts"
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="compare a previously captured runtime snapshot without a browser",
    )
    parser.add_argument(
        "--save-snapshot",
        type=Path,
        help="write snapshot inside the module's _scratchpad; path relative to cwd",
    )
    return parser


def compare_course(outline: dict, snapshot: dict) -> dict:
    """Return order errors and note/title warnings for a captured runtime snapshot."""
    errors = []
    warnings = []
    unverified = []
    expected = [page["id"] for page in outline["pages"]]
    scenes = snapshot.get("scenes")
    guide = snapshot.get("guideIds")
    if not isinstance(scenes, list) or any(
        not isinstance(scene, dict) or not isinstance(scene.get("id"), str)
        for scene in scenes
    ):
        return {
            "errors": ["Runtime scenes must be an array of objects with IDs"],
            "warnings": [],
        }
    actual = [scene["id"] for scene in scenes]
    if actual != expected:
        errors.append(f"PPT order differs: expected {expected}, got {actual}")
    if len(set(actual)) != len(actual):
        errors.append("Duplicate PPT scene IDs")
    if guide is None and snapshot.get('guideApplicable', True):
        unverified.append('Guide does not expose readable page order')
    elif snapshot.get('guideApplicable', True) and guide != expected:
        errors.append(
            f"Guide order differs or is unavailable: expected {expected}, got {guide}"
        )
    by_id = {scene["id"]: scene for scene in scenes}
    normalize = lambda value: " ".join(str(value).split())
    for page in outline["pages"]:
        scene = by_id.get(page["id"])
        if not scene:
            continue
        if scene.get("title") != page.get("title"):
            warnings.append(f"{page['id']}: outline and PPT titles differ")
        if normalize(page.get("snippet", "")) and normalize(
            scene.get("notesText", "")
        ) != normalize(page["snippet"]):
            warnings.append(
                f"{page['id']}: speaker notes differ from the outline or are unavailable"
            )
    return {"errors": errors, "warnings": warnings, **({'unverified':unverified} if unverified else {})}


def runtime_snapshot(context, base_url, outline):
    from media.capture_slides import built_entry
    entry = built_entry(base_url, outline.get('id', ''))
    page = context.new_page()
    try:
        page.goto(
            capture_url(base_url, outline.get("id") or outline["path"].split("/")[-1]),
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.locator("[data-scene-deck-capture]").wait_for(timeout=60000)
        snapshot = page.evaluate("""() => {
            const node=document.querySelector('[data-scene-deck-capture]');
            const catalog=globalThis.__SHUKU_PAGE_CATALOG__;
            if(!node||!catalog)return null;
            const ids=JSON.parse(node.dataset.sceneIds||'[]');
            return {scenes:ids.map(id=>{const p=catalog.pages.find(p=>p.id===id);return {id,title:p?.title,notesText:p?.snippet};}),
                    metadataSource:'Shuku frozen page catalog; not independent source-note validation'};
        }""")
        if not snapshot:
            raise ValueError('Rebuild this course to expose the capture metadata')
        if not outline.get('entry'):
            return {**snapshot, 'guideIds':None, 'guideApplicable':False}
        page.goto(
            (entry + '?mode=guide') if entry else base_url + outline["path"], wait_until="domcontentloaded", timeout=60000
        )
        flow = page.locator(".edu-lesson-flow").first
        page.locator('#root > :not([role="status"])').first.wait_for(timeout=15000)
        if not flow.count():
            ids = page.locator('[data-step-id]').evaluate_all("elements=>elements.map(element=>element.dataset.stepId)")
            return {**snapshot, 'guideIds':ids or None}
        key = flow.get_attribute("data-state-key")
        if not key:
            raise ValueError("Guide does not expose a LessonFlow state key")
        page.evaluate(
            """({key,ids})=>localStorage.setItem('shuku-runtime-state:'+JSON.stringify([globalThis.__SHUKU_COURSE_ID__,key]),JSON.stringify({version:1,value:{visibleCount:1000000,completedIds:ids,completed:false}}))""",
            {"key": key, "ids": [p["id"] for p in outline["pages"]]},
        )
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "count => document.querySelectorAll('.edu-lesson-flow-step').length >= Math.min(2,count)",
            arg=len(outline["pages"]),
            timeout=15000,
        )
        page.wait_for_timeout(500)
        snapshot["guideIds"] = page.locator(".edu-lesson-flow-step").evaluate_all(
            "elements=>elements.map(element=>element.dataset.stepId)"
        )
        return snapshot
    finally:
        page.close()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        directory, outline = resolve_module(args.module)
        saved = (
            scratchpad_path(
                directory, args.save_snapshot, default="snapshots/course.json"
            )
            if args.save_snapshot
            else None
        )
        if args.snapshot:
            snapshot = json.loads(project_path(args.snapshot, external=True).read_text(encoding="utf-8-sig"))
        else:
            with browser_session(
                args.base_url,
                reset_storage=False,
                build_output=project_path(args.build_output, external=True) if args.build_output else None,
                scratchpad=scratchpad_path(directory, default=""),
            ) as (
                context,
                address,
            ):
                snapshot = runtime_snapshot(context, address, outline)
        result = compare_course(outline, snapshot)
        if snapshot.get('metadataSource'):
            result['coverage'] = {'metadataSource': snapshot['metadataSource'], 'independentSourceNotes': False}
        if saved:
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            result["snapshot"] = str(saved)
        emit_result(result, status="failed" if result["errors"] else "unverified" if result.get('unverified') else "passed")
        return 1 if result["errors"] else 2 if result.get('unverified') else 0
    except Exception as exc:
        return report_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
