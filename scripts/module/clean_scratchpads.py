#!/usr/bin/env python3
"""Remove exact _scratchpad directories from an explicitly selected project scope.

Reads: The explicit absolute directory, or a path relative to configured targetRoot.
Writes: --apply recursively deletes matched directories and their contents.
Default/--dry-run only lists targets. No directory-name exclusions or depth limit.
No automatic backup is made; preserve required deliverables before running.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from _common import emit_result, get_target_root, report_error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path,
                        help="Required scan scope; any explicit absolute directory, or relative to targetRoot; no depth limit")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Delete listed _scratchpad directories permanently")
    mode.add_argument("--dry-run", action="store_true", help="Only list targets (the default)")
    return parser


def is_link(path: Path) -> bool:
    """Include Windows junctions/reparse points, not only symbolic links."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def check_path(path: Path, scope: Path) -> None:
    """Verify final absolute containment and reject links before recursive deletion."""
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(scope):
        raise ValueError(f"Cleanup path escapes selected scope: {path}")
    for ancestor in (path, *path.parents):
        if is_link(ancestor):
            raise ValueError(f"Cleanup cannot traverse a link/junction: {ancestor}")


def run_task(args: argparse.Namespace) -> dict:
    raw = args.directory.expanduser()
    raw = raw if raw.is_absolute() else get_target_root() / raw
    raw = Path(os.path.abspath(raw))
    scope = raw.resolve(strict=True)
    if not scope.is_dir():
        raise ValueError(f"Scan scope must be an existing directory: {scope}")
    check_path(raw, scope)
    targets: list[Path] = []
    skipped: list[str] = []

    def fail_walk(error: OSError) -> None:
        raise error

    if scope.name.casefold() == "_scratchpad":
        targets.append(scope)
    for base, directories, _ in os.walk(scope, topdown=True, followlinks=False, onerror=fail_walk):
        if scope in targets:
            break
        for name in list(directories):
            child = Path(base) / name
            if is_link(child):
                directories.remove(name)
                skipped.append(str(child))
            elif name.casefold() == "_scratchpad":
                check_path(child, scope)
                targets.append(child)
                # Removing an outer scratchpad already includes any nested ones.
                directories.remove(name)
    targets.sort()
    # Complete preflight first, so invalid input never triggers partial cleanup.
    for target in targets:
        check_path(target, scope)
    removed = []
    if args.apply:
        for target in targets:
            check_path(target, scope)
            shutil.rmtree(target)
            removed.append(str(target))
    return {"mode": "apply" if args.apply else "dry-run", "scope": str(scope),
            "targets": [str(path) for path in targets], "matched": len(targets),
            "removed": removed, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        emit_result(run_task(args))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        return report_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
