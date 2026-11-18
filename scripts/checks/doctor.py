#!/usr/bin/env python3
"""Diagnose tool dependencies without starting services.

Reads: Package availability, browser locations and repository dependencies.
Writes: None. Does not install packages or load models.
"""

from pathlib import Path
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from _common import SCRIPTS, TARGET_ROOT_CONFIG, get_target_root, modules_directory, emit_result, report_error

ROOT = None

GROUPS = {
    "core": [],
    "preview": [],
    "capture": ["playwright", "PIL"],
    "upload": ["oss2"],
    "skill": ["yaml"],
    "media": [],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group",
        choices=[*GROUPS, "all"],
        default="core",
        help="dependency group; default core",
    )
    parser.add_argument(
        "--tool", help="check dependencies declared by one catalog tool"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="compatibility flag; results are always JSON",
    )
    return parser


def diagnose(group: str, tool: str | None = None) -> list[dict]:
    """Return dependency availability without importing optional packages or models."""
    path_tools = {'course.pack', 'course.discover', 'course.inspect', 'course.images', 'course.videos', 'course.audio'}
    root = None
    if tool not in path_tools and (group != "preview" or tool is not None):
        if ROOT is not None or os.environ.get("CREATOR_SKILL_TARGET_CONFIG") or TARGET_ROOT_CONFIG.exists():
            root = ROOT or get_target_root()
    groups = (
        list(GROUPS)
        if group == "all"
        else ["core", group] if group != "core" else ["core"]
    )
    checks = [
        {
            "name": "Python >= 3.10",
            "available": sys.version_info >= (3, 10),
            "detail": sys.version.split()[0],
        },
    ]
    if root is not None:
        checks.append({"name": "repository modules", "available": modules_directory(root).is_dir()})
    if "preview" in groups:
        node = shutil.which("node")
        version, supported = "not found", False
        if node:
            try:
                result = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10, check=True)
                version = result.stdout.strip()
                supported = int(version.removeprefix("v").split(".", 1)[0]) >= 24
            except (OSError, ValueError, subprocess.SubprocessError):
                version = "version check failed"
        checks.extend([
            {"name": "Node.js >= 24", "available": supported, "detail": version},
            {"name": "npm", "available": bool(shutil.which("npm"))},
            {"name": "Player Preview dependencies",
             "available": (SCRIPTS.parent / "player-preview/node_modules/vite/package.json").is_file(),
             "optional": True, "detail": "npm run setup"},
        ])
    packages = {name for key in groups for name in GROUPS[key]}
    if tool:
        from tools import catalog

        selected = next((item for item in catalog() if item["id"] == tool), None)
        if selected is None:
            raise ValueError(f"Unknown tool: {tool}")
        if selected['runtime'] == 'node' or 'node' in selected['dependencies']:
            checks.append({'name': 'Node', 'available': bool(shutil.which('node'))})
        if tool == 'course.pack':
            checks.extend({'name': name, 'available': bool(shutil.which(name)), 'optional': True,
                           'detail': '仅处理音视频时需要；可通过打包参数指定可执行文件路径。'}
                          for name in ('ffmpeg', 'ffprobe'))
        packages.update(
            name for name in selected["dependencies"] if name not in {"ffmpeg", "ffprobe", "node"}
        )
        if "playwright" in packages and "capture" not in groups:
            groups.append("capture")
        if "ffmpeg" in selected["dependencies"] and "media" not in groups:
            groups.append("media")
    for name in sorted(packages):
        if name == 'typescript':
            node = shutil.which('node')
            probe = SCRIPTS / 'media/rewrite_asset_paths.mjs'
            available = False
            detail = 'Install Player Preview dependencies with npm ci'
            if node:
                try:
                    result = subprocess.run([node, '--input-type=module', '-e',
                        'const m=await import(process.argv[1]); console.log(m.loadTypeScript(process.argv[2]).version);',
                        probe.as_uri(), str(root)], capture_output=True, text=True, timeout=15)
                    available = result.returncode == 0
                    if available:
                        detail = result.stdout.strip()
                except (OSError, subprocess.TimeoutExpired):
                    pass
            checks.append({'name': name, 'available': available, 'detail': detail})
            continue
        try:
            present = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            present = False
        checks.append({"name": name, "available": present})
    if "capture" in groups:
        checks.append(
            {
                "name": "completed course build",
                "available": root is not None and (root / "dist").is_dir(),
                "detail": "default targetRoot/dist; external build output can be passed with --build-output",
            }
        )
        locations = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright",
            Path.home() / ".cache/ms-playwright",
        ]
        installed = any(
            any(path.glob("chromium*")) for path in locations if path.is_dir()
        )
        browser = any(
            (Path(os.environ.get(variable, "")) / suffix).is_file()
            for variable, suffix in [
                ("PROGRAMFILES", "Google/Chrome/Application/chrome.exe"),
                ("PROGRAMFILES(X86)", "Microsoft/Edge/Application/msedge.exe"),
            ]
        )
        checks.append(
            {
                "name": "Chromium/Chrome/Edge candidate",
                "available": installed or browser,
                "detail": "filesystem presence only; actual launch is checked by capture",
            }
        )
    if "media" in groups:
        checks.append({"name": "FFmpeg", "available": bool(shutil.which("ffmpeg"))})
    if tool and 'ffprobe' in selected['dependencies']:
        checks.append({'name': 'ffprobe', 'available': bool(shutil.which('ffprobe'))})
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        checks = diagnose(args.group, args.tool)
    except (ValueError, OSError) as exc:
        return report_error(exc)
    passed = all(check["available"] or check.get('optional') for check in checks)
    emit_result({"checks": checks}, status="passed" if passed else "failed")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
