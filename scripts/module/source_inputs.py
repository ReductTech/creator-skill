#!/usr/bin/env python3
"""Discover source modules and collect files without executing or modifying them.

Standalone discovery accepts module directories, collections and project roots.
Shared, caches, archives and local environment files are excluded from delivery.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.submission_policy import blocked_reason

SKIP = {'.git', 'node_modules', 'dist', '__pycache__', '_scratchpad',
        '.pytest_cache', '.venv', 'creator-skill'}


def default_output(directories):
    """Place the package beside the selected modules, without an output argument."""
    roots = [Path(p).expanduser().absolute().resolve() for p in directories]
    first = roots[0]
    if len(roots) > 1:
        try:
            parent = Path(os.path.commonpath([str(p.parent) for p in roots]))
        except ValueError:  # Inputs on different Windows drives use the first input.
            parent = first.parent
        candidate = parent / 'courses.zip'
    elif (first / 'outlines.json').is_file():
        candidate = first.with_name(first.name + '.zip')
    elif (first / 'modules').is_dir():
        candidate = first / 'modules.zip'
    else:
        candidate = first.with_name(first.name + '.zip')
    original, number = candidate, 2
    while (candidate.exists() or candidate.is_symlink() or candidate.with_suffix('.lock').exists() or candidate.with_suffix('.checks').exists() or candidate.with_suffix('.report.json').exists()
           or candidate.with_suffix('.report.md').exists()):
        candidate = original.with_name(original.stem + '-' + str(number) + '.zip')
        number += 1
    return candidate


def linked(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def discover_modules(directories):
    """Resolve a single module, flat collection, modules/ collection, or several inputs."""
    modules, shared = [], []
    for given in directories:
        given = Path(given).expanduser().absolute()
        if linked(given):
            raise ValueError('Input cannot be a link/junction: ' + str(given))
        root = given.resolve()
        if not root.is_dir():
            raise ValueError('Input is not a directory: ' + str(root))
        if root.name.casefold() == 'shared':
            shared.append(str(root))
            continue
        if (root / 'outlines.json').is_file():
            candidates = [root]
        else:
            container = root / 'modules' if (root / 'modules').is_dir() else root
            if linked(container):
                raise ValueError('Module collection cannot be a link/junction: ' + str(container))
            candidates = []
            for child in sorted(container.iterdir()):
                if child.name.casefold() == 'shared':
                    shared.append(str(child))
                elif child.is_dir() and child.name.casefold() not in SKIP:
                    if linked(child):
                        raise ValueError('Module cannot be a link/junction: ' + str(child))
                    if (child / 'outlines.json').is_file():
                        candidates.append(child)
        for candidate in candidates:
            if candidate not in modules:
                modules.append(candidate)
    if not modules:
        raise ValueError('No course outlines.json found; Shared is not a course')
    return modules, sorted(set(shared))


def source_paths(root, directories, excluded_shared=None, excluded_files=None, *, preserve_shared=False):
    """Collect regular files with logical paths, never following links/junctions."""
    root = Path(root).resolve()
    files = {}
    for directory in map(Path, directories):
        if directory.name.casefold() == 'shared' and not preserve_shared:
            if excluded_shared is not None:
                excluded_shared.append(str(directory))
            continue
        if linked(directory) or not directory.resolve().is_relative_to(root):
            raise ValueError('Source must stay inside the selected root: ' + str(directory))
        for current, dirs, names in os.walk(directory, followlinks=False):
            base = Path(current)
            for name in dirs:
                if name.casefold() == 'shared' and excluded_shared is not None:
                    excluded_shared.append(str(base / name))
            dirs[:] = sorted(d for d in dirs if d.casefold() not in SKIP | (set() if preserve_shared else {'shared'}))
            for name in [*dirs, *names]:
                if linked(base / name):
                    raise ValueError('Source cannot contain links/junctions: ' + str(base / name))
            for name in sorted(names):
                path = base / name
                if path.suffix.lower() in {'.zip', '.skzip'}:
                    continue
                if not stat.S_ISREG(path.stat().st_mode):
                    raise ValueError('Source must contain regular files: ' + str(path))
                with path.open('rb') as stream:
                    reason = blocked_reason(path.relative_to(root).as_posix(), stream.read(512))
                if reason:
                    if excluded_files is not None:
                        excluded_files.append({'path': path.relative_to(root).as_posix(), 'reason': reason})
                    continue
                files[path.relative_to(root).as_posix()] = path
    return files


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', nargs='+', type=Path, help='Module, collection, project root, or several directories')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        modules, shared = discover_modules(args.directories)
        print(json.dumps({'status': 'passed', 'modules': list(map(str, modules)),
                          'excludedShared': shared}, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({'status': 'error', 'error': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
