#!/usr/bin/env python3
"""Capture real 1600x900 术库 screenshots.

Reads: The selected module and requested browser states.
Writes: Evaluation PNGs remain 1600x900. Requested JPG thumbnails default to
320x180 in assets/scenedeck-thumbnails; the runtime first slide also gets an
800x450 JPG in assets/course-covers. No size/quality arguments are needed.
Owns its browser and completed-artifact preview server.
Thumbnail runs also save a report and batch contact sheet in module _scratchpad/thumbnails.
"""

from __future__ import annotations


import argparse
import io
import json
import os
import re
import sys
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs, urljoin
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from module_assets import asset_directory
from _common import get_target_root, read_modules, resolve_module as resolve_course, emit_result, report_error, scratchpad_path, project_path

ROOT = None

def repository_root():
    return ROOT or get_target_root()
SLIDE_SIZE = (1600, 900)


PlaywrightError = RuntimeError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module", required=True, help="module directory, deck ID or UUID"
    )
    parser.add_argument("--build-output", type=Path, help="completed build directory; default targetRoot/dist; may be outside the course source")
    parser.add_argument("--slide", help="one slide ID; default all slides")
    parser.add_argument("--page-directory", help="semantic directory under pages/ for single-slide intermediate outputs")
    parser.add_argument(
        "--max-chars",
        type=int,
        help="explicit per-state non-whitespace character limit; omitted means count only",
    )
    parser.add_argument(
        "--surface",
        default=".ppt-slide-surface",
        help="slide surface CSS selector for geometry and text checks; default .ppt-slide-surface",
    )
    parser.add_argument(
        "--format",
        choices=["screenshots", "thumbnails", "both"],
        default="screenshots",
        help="screenshots: module _scratchpad; thumbnails: official assets; both: write both (default screenshots)",
    )
    parser.add_argument(
        "--state",
        default="default",
        help="state name; use a non-default state with --actions",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="image directory relative to cwd, within module _scratchpad (screenshots/both) or official thumbnail directory (thumbnails)",
    )
    parser.add_argument(
        "--base-url", help="built preview service URL; omit to serve completed artifacts locally"
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="return actual slide IDs without writing screenshots",
    )
    parser.add_argument(
        "--actions",
        type=Path,
        help="JSON file mapping slide IDs to action arrays; relative to cwd",
    )
    parser.add_argument(
        "--settle-ms",
        type=int,
        default=None,
        help="explicit non-negative wait after actions; default: wait for assets and page readiness instead of a fixed delay",
    )
    parser.add_argument("--timeout-ms", type=int, default=15000,
                        help="page loading/readiness timeout in milliseconds; default 15000")
    return parser


def load_dependencies():
    global Image, PlaywrightError, sync_playwright
    try:
        from PIL import Image
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            f'Install capture dependencies: python -m pip install -r "{Path(__file__).resolve().parents[1] / "requirements-capture.txt"}"'
        ) from exc


def available_modules() -> list[tuple[Path, str, str]]:
    modules: list[tuple[Path, str, str]] = []
    for directory, metadata in read_modules(repository_root()):
        outline = directory / 'outlines.json'
        if metadata.get("ppt", {}).get("entry"):
            asset_id = metadata.get("moduleIdentity", {}).get("id")
            if not asset_id:
                raise ValueError(f"Missing module UUID in {outline.relative_to(repository_root())}")
            modules.append(
                (directory, metadata.get("id", directory.name.lower()), asset_id)
            )
    return sorted(modules, key=lambda entry: entry[1])


def resolve_module(requested: str) -> tuple[Path, str, str]:
    directory, metadata = resolve_course(requested, repository_root())
    if not metadata.get('ppt', {}).get('entry'):
        raise ValueError(f'Module has no PPT entry: {requested}')
    asset_id = metadata.get('moduleIdentity', {}).get('id')
    if not asset_id:
        raise ValueError(f'Missing module UUID: {requested}')
    return directory, metadata.get('id', directory.name.lower()), asset_id


@contextmanager
def vite_server(log_directory=None, output_root=None):
    """Compatibility name: serve completed artifacts, never launch source Vite."""
    from artifact_capture_server import artifact_server
    with artifact_server(output_root or repository_root() / 'dist') as address:
        _BUILD_OUTPUTS[address] = Path(output_root or repository_root() / 'dist')
        try:yield address
        finally:_BUILD_OUTPUTS.pop(address,None)

_BUILD_OUTPUTS = {}


def launch_browser(playwright):
    errors: list[str] = []
    for options in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
        try:
            return playwright.chromium.launch(headless=True, **options)
        except PlaywrightError as error:
            errors.append(str(error).splitlines()[0])
    raise RuntimeError(
        "No supported Chromium browser found. Run 'python -m playwright install chromium' first.\n"
        + "\n".join(errors)
    )


def built_entry(base_url: str, deck_id: str) -> str | None:
    """Resolve this checkout's fixed build; never infer a source route for IDL."""
    catalog = _BUILD_OUTPUTS.get(base_url.rstrip('/'), repository_root() / 'dist') / 'catalog.json'
    if not catalog.is_file():
        return None
    document = json.loads(catalog.read_text(encoding='utf-8'))
    if document.get('kind') != 'idl-built-catalog':
        return None
    for module in document.get('modules', []):
        if deck_id in {module.get('id'), module.get('alias')}:
            return urljoin(base_url.rstrip('/') + '/', module['base'] + 'index.html')
    return None


def capture_url(base_url: str, deck_id: str, slide_id: str | None = None) -> str:
    query = {"scenedeckCapture": "1", "deck": deck_id}
    if slide_id:
        query["slide"] = slide_id
    entry = built_entry(base_url, deck_id)
    if entry:
        query['mode'] = 'ppt'
    return (entry or base_url.rstrip('/') + '/scenedeck/') + '?' + urlencode(query)


def configure_module_capture(context, directory: Path, base_url: str) -> None:
    """The completed Shuku runtime owns capture metadata; never mount source."""
    if hasattr(context, "new_page"):
        context._idl_reuse_capture = True


def open_capture(context, url: str):
    page = getattr(context, "_idl_capture_page", None)
    reusable = page is not None and not page.is_closed()
    if not reusable:
        page = context.new_page()
    runtime_errors = []
    error_handler = lambda error: runtime_errors.append(str(error))
    page.on("pageerror", error_handler)
    timeout = getattr(context, "_idl_timeout_ms", 15000)
    try:
        query = parse_qs(urlparse(url).query)
        slide = query.get("slide", [None])[0]
        if reusable and page.evaluate("typeof window.__IDL_CAPTURE_NAVIGATE__ === 'function'"):
            page.evaluate("slide => window.__IDL_CAPTURE_NAVIGATE__(slide)", slide)
        else:
            page.goto(url, wait_until="commit", timeout=timeout)
        page.bring_to_front()
        page.wait_for_function("""slide => {
            if (window.__IDL_CAPTURE_ERROR__) return true;
            const node = document.querySelector('[data-scene-deck-capture]');
            return node && (!slide || node.dataset.sceneId === slide) && node.getBoundingClientRect().height > 0;
        }""", arg=slide, timeout=timeout)
        error = page.evaluate("window.__IDL_CAPTURE_ERROR__ || null")
        if error:
            raise RuntimeError(error)
        capture = page.locator("[data-scene-deck-capture]")
        if getattr(context, "_idl_reuse_capture", False):
            context._idl_capture_page = page
        return page, capture
    except Exception as exc:
        page.close()
        if runtime_errors:
            raise RuntimeError(f"Capture could not load {url}: {'; '.join(runtime_errors)}") from exc
        raise
    finally:
        page.remove_listener("pageerror", error_handler)


def release_capture(context, page):
    """Fixture pages close as before; the module's warm page lives to context.close()."""
    if page is not getattr(context, "_idl_capture_page", None):
        page.close()


def scene_ids(context, base_url: str, deck_id: str) -> list[str]:
    page, capture = open_capture(context, capture_url(base_url, deck_id))
    try:
        actual_deck_id = capture.get_attribute("data-deck-id")
        if actual_deck_id != deck_id:
            raise RuntimeError(
                f"Requested deck {deck_id}, but 术库 opened {actual_deck_id}."
            )
        ids = json.loads(capture.get_attribute("data-scene-ids") or "[]")
        if not ids or any(not isinstance(slide_id, str) for slide_id in ids):
            raise RuntimeError("术库 did not expose a valid slide list.")
        return ids
    finally:
        release_capture(context, page)


def capture_slide(
    context,
    base_url: str,
    deck_id: str,
    slide_id: str,
    settle_ms: int | None,
    actions=None,
    inspection: dict | None = None,
    max_chars: int | None = None,
    surface: str = ".ppt-slide-surface",
) -> Image.Image:
    page, capture = open_capture(context, capture_url(base_url, deck_id, slide_id))
    try:
        if capture.get_attribute("data-scene-id") != slide_id:
            raise RuntimeError(f"术库 could not open slide {slide_id}.")
        timeout = getattr(context, "_idl_timeout_ms", 15000)
        page.wait_for_function("Array.from(document.images).every(image => image.complete)", timeout=timeout)
        page.evaluate("""async timeout => {
          await Promise.race([(async () => {
            await document.fonts.ready;
            await Promise.all(Array.from(document.images, image => image.decode().catch(() => undefined)));
          })(), new Promise((_,reject) => setTimeout(() => reject(Error('Fonts/images did not become ready')),timeout))]);
        }""", timeout)
        apply_actions(page, actions or [])
        if settle_ms is not None:
            page.wait_for_timeout(settle_ms)
        else:
            # Small debounce covers mount effects; long work exposes a ready flag.
            page.wait_for_timeout(200)
            page.wait_for_function("""() => {
                if (window.__IDL_CAPTURE_ERROR__) throw Error(window.__IDL_CAPTURE_ERROR__);
                const surface = document.querySelector('[data-scene-deck-capture]');
                const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
                return ![...surface.querySelectorAll('[data-capture-ready="false"],[aria-busy="true"]')].some(visible);
            }""", timeout=timeout)
        runtime_error = page.evaluate("window.__IDL_CAPTURE_ERROR__ || null")
        if runtime_error:
            raise RuntimeError(runtime_error)
        if inspection is not None:
            inspection.update(inspect_page(page, slide_id, max_chars, surface))
        screenshot = capture.screenshot(
            type="png", animations="disabled", timeout=30000
        )
        with Image.open(io.BytesIO(screenshot)) as image:
            if image.size != SLIDE_SIZE:
                raise RuntimeError(
                    f"Slide {slide_id} captured at {image.size}, expected {SLIDE_SIZE}."
                )
            return image.convert("RGB").copy()
    finally:
        release_capture(context, page)


def inspect_page(
    page,
    slide_id: str,
    max_chars: int | None = None,
    surface: str = ".ppt-slide-surface",
) -> dict:
    """Inspect the current state with the same browser expression as check.bounds."""
    checker = (
        Path(__file__).resolve().parents[1] / "common/_page_checks.js"
    ).read_text(encoding="utf-8")
    options = {
        "surfaceSelector": surface,
        "expectedId": slide_id,
        "maxChars": max_chars,
    }
    try:
        page.wait_for_function(
            f"options => {{ const result = ({checker})(options); return result.ready || result.status === 'failed'; }}",
            arg=options,
            timeout=15000,
        )
    except PlaywrightError:
        # Return the observed missing/hidden/loading state, never a zero-word success.
        result = page.evaluate(checker, options)
        result["readinessTimedOut"] = True
        return result
    return page.evaluate(checker, options)


def apply_actions(page, actions):
    for action in actions:
        kind = action.get("action")
        if kind == "wait":
            delay = action.get("ms", 0)
            if type(delay) is not int or not 0 <= delay <= 10000:
                raise ValueError("Action wait must be an integer from 0 to 10000 ms.")
            page.wait_for_timeout(delay)
        elif kind in {"click", "fill", "press"}:
            locator = page.locator(action["selector"])
            if kind == "click":
                locator.click(timeout=10000)
            elif kind == "fill":
                locator.fill(str(action["value"]), timeout=10000)
            else:
                locator.press(str(action["value"]), timeout=10000)
        else:
            raise ValueError(f"Unknown capture action: {kind}")


def safe_slide_id(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]*", value
    ):
        raise ValueError(f"Unsafe slide ID: {value!r}")
    return value


@contextmanager
def browser_session(base_url=None, reset_storage=True, scratchpad=None, build_output=None):
    """One isolated browser context; never touches the user's browser profile."""
    load_dependencies()
    address = base_url
    with (
        (
            nullcontext(address.rstrip("/")) if address else vite_server(scratchpad, build_output)
        ) as address,
        sync_playwright() as playwright,
    ):
        browser = launch_browser(playwright)
        try:
            context = browser.new_context(
                viewport={"width": 1600, "height": 900},
                device_scale_factor=1,
                reduced_motion="reduce",
            )
            if reset_storage:
                context.add_init_script(
                    "try { localStorage.clear(); sessionStorage.clear(); } catch {}"
                )
            yield context, address
        finally:
            # This tool owns the browser and has already buffered screenshots.
            # Closing each page/context first can wait on workers and sockets.
            browser.close()


def running_vite() -> str | None:
    """Reuse the normal dev port only when the server confirms this exact checkout."""
    address = "http://127.0.0.1:5173"
    try:
        with urlopen(address + "/__creator_capture__/info", timeout=.5) as response:
            info = json.load(response)
        if info.get("kind") == "creator-capture" and Path(info["root"]).resolve() == repository_root().resolve():
            return address
    except (OSError, ValueError, KeyError):
        pass
    return None


def capture_module(args: argparse.Namespace, context_setup=None) -> dict:
    """Capture the requested states, returning saved paths and any per-slide errors."""
    started = time.perf_counter()
    if args.settle_ms is not None and args.settle_ms < 0:
        raise ValueError("--settle-ms must be non-negative")
    if args.timeout_ms <= 0:
        raise ValueError("--timeout-ms must be positive")
    if args.max_chars is not None and args.max_chars < 0:
        raise ValueError("--max-chars must be non-negative")
    safe_slide_id(args.state)
    if args.actions and args.state == "default":
        raise ValueError(
            "Use --state <name> with --actions to preserve the default screenshot."
        )
    directory, deck_id, asset_id = resolve_module(args.module)
    page_directory = getattr(args, "page_directory", None)
    if page_directory and not args.slide:
        raise ValueError("Use --slide with --page-directory to keep each page's outputs separate")
    if args.format in {"thumbnails", "both"} and args.state != "default":
        raise ValueError(
            "Interactive states are evaluation screenshots; use --format screenshots"
        )
    thumbnail_root = (directory / "assets" / "scenedeck-thumbnails").resolve()
    if not thumbnail_root.is_relative_to(directory.resolve()):
        raise ValueError(f"Thumbnail directory must stay inside {directory}")
    report_dir = None
    if args.format in {"thumbnails", "both"} and not args.inspect:
        report_dir = scratchpad_path(directory, default="thumbnails")
        safe_slide_id(args.slide) if args.slide else None
        report_path = scratchpad_path(directory, report_dir / (f"{args.slide}.json" if args.slide else "report.json"), default="")
        contact_path = scratchpad_path(directory, report_dir / "contact-sheet.jpg", default="")
    destinations = []
    if not args.inspect:
        if args.format in {"screenshots", "both"}:
            destinations.append(
                scratchpad_path(directory, args.output, default="screenshots", page_directory=page_directory)
            )
        if args.format in {"thumbnails", "both"}:
            thumbnail_output = (
                args.output
                if args.format == "thumbnails" and args.output
                else thumbnail_root
            ).resolve()
            if not thumbnail_output.is_relative_to(thumbnail_root):
                raise ValueError(f"Thumbnail output must be inside {thumbnail_root}")
            destinations.append(thumbnail_output)
    actions = (
        json.loads(project_path(args.actions, external=True).read_text(encoding="utf-8-sig")) if args.actions else {}
    )
    if not isinstance(actions, dict) or any(
        not isinstance(items, list) or any(not isinstance(item, dict) for item in items)
        for items in actions.values()
    ):
        raise ValueError("Actions must map slide IDs to arrays of action objects.")
    from media.thumbnail_profiles import save_thumbnail, save_cover
    files, errors, checks, captured, cover_files = [], [], [], [], []
    with browser_session(
        args.base_url, scratchpad=scratchpad_path(directory, default="", page_directory=page_directory),
        build_output=project_path(args.build_output, external=True) if args.build_output else None
    ) as (context, base_url):
        browser_ready = time.perf_counter()
        # Test fixtures and compatibility callers can supply minimal contexts.
        if hasattr(context, "new_page"):
            context._idl_timeout_ms = args.timeout_ms
        configure_module_capture(context, directory, base_url)
        if context_setup is not None:
            context_setup(context, asset_id)
        try:
            ids = scene_ids(context, base_url, deck_id)
        except PlaywrightError:
            # A cold Vite optimizer can replace dependency URLs during the first
            # navigation. Retry that bootstrap once, keeping its now-warm server.
            print("Initial load timed out; retrying once with the warm dependency cache.", file=sys.stderr, flush=True)
            ids = scene_ids(context, base_url, deck_id)
        for value in ids:
            safe_slide_id(value)
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate runtime slide IDs.")
        if args.inspect:
            return {"deck": deck_id, "uuid": asset_id, "slides": ids}
        first_scene_id = ids[0] if ids else None
        if args.slide:
            if args.slide not in ids:
                raise ValueError(f"Unknown slide: {args.slide}")
            ids = [args.slide]
        if set(actions) - set(ids):
            raise ValueError(
                "Actions include slides outside the requested capture range."
            )
        for number, slide_id in enumerate(ids, 1):
            slide_started = time.perf_counter()
            inspection = {"page": slide_id, "state": args.state}
            checks.append(inspection)
            try:
                image = capture_slide(
                    context,
                    base_url,
                    deck_id,
                    slide_id,
                    args.settle_ms,
                    actions.get(slide_id),
                    inspection,
                    args.max_chars,
                    args.surface,
                )
                inspection["elapsedMs"] = round((time.perf_counter() - slide_started) * 1000)
                captured.append((slide_id, image, inspection))
                print(f"[{number}/{len(ids)}] Captured {slide_id} ({inspection['elapsedMs']} ms)", file=sys.stderr, flush=True)
            except Exception as exc:
                inspection.update(
                    status="unverified",
                    text={"status": "unverified", "characters": None},
                    error=str(exc),
                )
                errors.append({"slide": slide_id, "error": str(exc)})
                print(f"FAILED {slide_id}: {exc}", file=sys.stderr)
        captures_finished = time.perf_counter()
    browser_closed = time.perf_counter()
    # Writing watched assets during capture can reload a different page via HMR.
    # Publish the buffered images only after the isolated browser is closed.
    for slide_id, image, inspection in captured:
        try:
            for screenshots in destinations:
                is_thumbnail = screenshots.is_relative_to(thumbnail_root)
                extension = "jpg" if is_thumbnail else "png"
                target = (
                    screenshots / f"{slide_id}.{extension}"
                    if args.state == "default"
                    else screenshots / slide_id / f"{args.state}.png"
                )
                if screenshots.is_relative_to(thumbnail_root):
                    if not target.resolve().is_relative_to(thumbnail_root):
                        raise ValueError(f"Thumbnail path escapes output directory: {target}")
                else:
                    target = scratchpad_path(directory, target, default="")
                target.parent.mkdir(parents=True, exist_ok=True)
                if is_thumbnail:
                    save_thumbnail(image, target)
                    if slide_id == first_scene_id:
                        cover = directory / 'assets/course-covers' / f'{slide_id}.jpg'
                        save_cover(image, cover)
                        cover_files.append(str(cover))
                else:
                    image.save(target, format="PNG", compress_level=3)
                files.append(str(target))
        except Exception as exc:
            errors.append({"slide": slide_id, "error": str(exc)})
            print(f"FAILED saving {slide_id}: {exc}", file=sys.stderr)
    result = {
        "deck": deck_id,
        "uuid": asset_id,
        "state": args.state,
        "files": files,
        "coverFiles": cover_files,
        "errors": errors,
        "checks": checks,
        "timing": {
            "startupSeconds": round(browser_ready - started, 2),
            "captureSeconds": round(captures_finished - browser_ready, 2),
            "shutdownSeconds": round(browser_closed - captures_finished, 2),
            "totalSeconds": round(time.perf_counter() - started, 2),
        },
    }
    if report_dir is not None:
        report_dir.mkdir(parents=True, exist_ok=True)
        result["report"] = str(report_path)
        thumbnail_files = [file for file in files if Path(file).is_relative_to(thumbnail_root)]
        result["generatedCount"] = len(thumbnail_files)
        result["requestedCount"] = len(ids)
        # A successful image write and a layout finding are distinct outcomes.
        result["generationStatus"] = "error" if errors else "ok"
        result["checksStatus"] = (
            "unverified" if any(c.get("status") == "unverified" for c in checks)
            else "failed" if any(c.get("status") == "failed" for c in checks) else "passed"
        )
        if not args.slide and thumbnail_files:
            result["contactSheet"] = str(contact_path)
            make_contact_sheet(thumbnail_files, contact_path)
        result["timing"]["totalSeconds"] = round(time.perf_counter() - started, 2)
        result["timing"]["writeSeconds"] = round(time.perf_counter() - browser_closed, 2)
        Path(result["report"]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def make_contact_sheet(files: list[str], target: Path) -> None:
    """Assemble real captures for review; this is not a generated design mockup."""
    from PIL import Image, ImageDraw, ImageFont
    unique = list(dict.fromkeys(files))
    sheet = Image.new("RGB", (1600, ((len(unique) + 3) // 4) * 252), "#e9eef5")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=14)
    for index, file in enumerate(unique):
        x, y = (index % 4) * 400 + 8, (index // 4) * 252 + 8
        with Image.open(file) as image:
            sheet.paste(image.convert("RGB").resize((384, 216), Image.Resampling.LANCZOS), (x, y))
        draw.text((x, y + 220), f"{index + 1:02d} {Path(file).stem}"[:48], font=font, fill="#26456f")
    sheet.save(target, quality=90)


def main(argv: list[str] | None = None, context_setup=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = capture_module(args, context_setup)
        failed = any(
            check.get("status") == "failed" for check in result.get("checks", [])
        )
        unverified = any(
            check.get("status") == "unverified"
            or check.get("text", {}).get("status") == "unverified"
            for check in result.get("checks", [])
        )
        status = (
            "error"
            if result.get("errors")
            else "unverified" if unverified else "failed" if failed else "ok"
        )
        emit_result(result, status=status)
        if failed and result.get("generationStatus") == "ok":
            print("Thumbnails were written. Exit 1 reports layout findings; inspect checks/report before deciding whether any slide needs recapture.", file=sys.stderr)
        return 2 if status in {"error", "unverified"} else 1 if failed else 0
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        ImportError,
        PlaywrightError,
    ) as exc:
        return report_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
