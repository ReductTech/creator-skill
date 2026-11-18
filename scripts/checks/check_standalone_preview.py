"""Render a staged course with the bundled player in an isolated browser."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlencode

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS / "common")]
from _common import emit_result, report_error, resolve_module
from media.capture_slides import browser_session, open_capture


@contextmanager
def preview(node, project, evidence):
    ready = evidence / "preview-ready.json"
    env = {**os.environ, "CREATOR_SKILL_PREVIEW_CACHE": str(project.parent / "preview-cache"),
           "SHUKU_API_URL": ""}
    runner = SCRIPTS.parent / "player-preview/scripts/start.mjs"
    with (evidence / "preview-server.log").open("w", encoding="utf-8") as log:
        with subprocess.Popen(
            [node, str(runner), "--project", str(project), "--standalone", "--port", "0", "--ready-file", str(ready)],
            stdout=log, stderr=subprocess.STDOUT, env=env,
        ) as server:
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        raise RuntimeError("独立预览启动失败，见 preview-server.log。")
                    if ready.is_file():
                        try:
                            port = json.loads(ready.read_text(encoding="utf-8"))["port"]
                        except json.JSONDecodeError:
                            time.sleep(0.1)
                            continue
                        yield f"http://127.0.0.1:{port}"
                        return
                    time.sleep(0.1)
                raise RuntimeError("独立预览启动超时，见 preview-server.log。")
            finally:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        server.kill()


def check_pages(context, base_url, outline, evidence):
    checked, errors = [], []
    deadline = time.monotonic() + 200
    if outline.get("ppt", {}).get("entry"):
        for index, item in enumerate(outline["pages"], 1):
            if time.monotonic() >= deadline:
                errors.append({"error": "独立预览检查超时，剩余页面未验证。"})
                break
            query = urlencode({"course": outline["id"], "view": "ppt", "scenedeckCapture": "1", "page": item["id"]})
            try:
                page, capture = open_capture(context, f"{base_url}/?{query}")
                try:
                    filename = f"slide-{index:03}.png"
                    capture.screenshot(path=str(evidence / filename), timeout=15000)
                    checked.append({"id": item["id"], "screenshot": filename})
                finally:
                    page.close()
            except Exception as error:
                errors.append({"page": item["id"], "error": str(error)})
    if outline.get("entry"):
        page = context.new_page()
        try:
            page.on("pageerror", lambda error: errors.append({"page": "guide", "error": str(error)}))
            query = urlencode({"course": outline["id"], "view": "guide"})
            page.goto(f"{base_url}/?{query}", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_function("document.querySelector('#root > :not([aria-busy=true])')", timeout=15000)
            if page.locator("#root > [role=alert]").count():
                raise RuntimeError(page.locator("#root").inner_text())
            if not page.locator("#root").inner_text().strip() and not page.locator("#root canvas,#root svg,#root img").count():
                raise RuntimeError("导览没有可见的文字或图形内容。")
            page.screenshot(path=str(evidence / "guide.png"), timeout=15000)
            checked.append({"id": "guide", "screenshot": "guide.png"})
        except Exception as error:
            errors.append({"page": "guide", "error": str(error)})
        finally:
            page.close()
    if not checked and not errors:
        errors.append({"error": "课程没有可用于独立验证的页面。"})
    return {"pages": checked, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--node", required=True)
    args = parser.parse_args()
    try:
        _, outline = resolve_module(args.module, args.project)
        args.evidence.mkdir(parents=True)
        with preview(args.node, args.project, args.evidence) as address, browser_session(address) as (context, _):
            result = check_pages(context, address, outline, args.evidence)
    except (OSError, RuntimeError, ValueError) as error:
        return report_error(error)
    emit_result(result, status="failed" if result["errors"] else "passed")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
