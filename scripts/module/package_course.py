#!/usr/bin/env python3
"""Export a source ZIP only after round-trip Shuku admission and real builds.

Reads: Configured course repository and explicitly selected Shuku checkout.
Writes: A new ZIP and verified builds beside it. Never uploads or publishes.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from _common import emit_result, report_error, require_target_root, resolve_module, modules_directory

SKIP = {'.git', 'node_modules', 'dist', '__pycache__', '_scratchpad', '.pytest_cache', 'creator-skill'}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', action='append', required=True, help='Course UUID or alias; repeat for a collection')
    parser.add_argument('--shuku-root', type=Path, required=True, help='Absolute path to the Shuku checkout used by the destination platform')
    parser.add_argument('--output', type=Path, required=True, help='New absolute .zip path; existing files are never overwritten')
    parser.add_argument('--timeout', type=int, default=300, help='Maximum seconds per admission/build command')
    return parser


def source_paths(root, directories):
    """Collect only requested source roots, preserving their actual logical paths."""
    files = {}
    for directory in directories:
        directory = Path(directory)
        if directory.is_symlink() or not directory.resolve().is_relative_to(root):
            raise ValueError('Source dependency must stay inside targetRoot: '+str(directory))
        if not directory.is_dir():
            raise ValueError('Missing source dependency: '+str(directory))
        for current, dirs, names in os.walk(directory, followlinks=False):
            base = Path(current)
            dirs[:] = [name for name in dirs if name not in SKIP]
            if any((base/name).is_symlink() for name in [*dirs, *names]):
                raise ValueError('Source ZIP cannot contain symlinks: '+str(base))
            for name in names:
                path = base/name
                if path.suffix.lower() in {'.zip', '.pyc'} or name == '.env' or name.startswith('.env.'):
                    continue
                files[path.relative_to(root).as_posix()] = path
    return files


def export_course(root, requested, shuku, output, timeout=300):
    root, shuku, output = Path(root).resolve(), Path(shuku), Path(output)
    if not shuku.is_absolute() or not output.is_absolute() or output.suffix.lower() != '.zip':
        raise ValueError('--shuku-root and .zip --output must be absolute paths')
    shuku, output = shuku.resolve(), output.resolve()
    if output.exists():
        raise ValueError('Output already exists; choose a new ZIP path')
    if output.is_relative_to(root) or output.is_relative_to(shuku):
        raise ValueError('Place delivery outputs outside the course and Shuku repositories')
    if timeout < 1:
        raise ValueError('Timeout must be positive')
    worker_build = shuku/'tooling/course-build/scripts/worker-build.mjs'
    if not worker_build.is_file() or not (shuku/'shared/courses/course_format.json').is_file():
        raise ValueError('Selected directory is not a current Shuku checkout')
    node = shutil.which('node')
    if not node:
        raise ValueError('Node.js 24 and the Shuku course builder dependencies are required')
    # Load only after argument/help processing; Shuku owns ZIP limits, dependency
    # discovery, style completion, admission and the compiler. No duplicate format.
    sys.path.insert(0, str(shuku))
    from shared.courses.source_files import SourceFiles
    from shared.courses.course_repository import discover_shuku_courses, course_input_paths
    from shared.courses.styles import supply_default_style, DEFAULT_STYLE_ID
    from worker.shuku_worker.engine import unpack_zip, MAX_FILES, MAX_BYTES, MAX_FILE_BYTES
    from worker.shuku_worker.course_validation import validate_zip_course, check_authoring

    selected_ids = {resolve_module(name, root)[1]['id'] for name in requested}
    directories = [modules_directory(root)]
    registry = root/'course-styles.json'
    if registry.is_file():
        catalog = json.loads(registry.read_text(encoding='utf-8-sig'))
        directories.extend(root/item['path'] for item in catalog['styles']
                           if (root/item['path']).exists() or item['id'] != DEFAULT_STYLE_ID)
    raw = source_paths(root, directories)
    if registry.is_file():
        raw['course-styles.json'] = registry
    files = supply_default_style(SourceFiles(raw))
    candidates = discover_shuku_courses(files)
    selected = [item for item in candidates if item['module_id'] in selected_ids]
    if len(selected) != len(selected_ids) or any(not item['ready'] for item in selected):
        raise ValueError('Select implemented UUID courses; outline-only drafts cannot be delivered')
    inputs = course_input_paths(files, candidates, selected={item['path'] for item in selected})
    included = set().union(*inputs.values())
    packaged = [item for item in candidates if item['path']+'/outlines.json' in included]
    if any(not item['ready'] for item in packaged):
        raise ValueError('A dependency or computed import includes an outline-only draft; make the import explicit or move reusable code into shared')
    if len(included) > MAX_FILES or sum(files.size(name) for name in included) > MAX_BYTES:
        raise ValueError('Source ZIP exceeds the selected platform expanded size/file-count limits')
    if any(files.size(name) > MAX_FILE_BYTES for name in included):
        raise ValueError('Source ZIP exceeds the platform per-file size limit')

    output.parent.mkdir(parents=True, exist_ok=True)
    builds = output.parent/(output.stem+'-verified-'+uuid4().hex[:8])
    env = {key:value for key,value in os.environ.items()
           if key not in {'SHUKU_ASSET_PYTHON','SHUKU_SOURCE_PYTHON','SHUKU_ASSET_CONFIG','SHUKU_COURSE_COMMIT'}}
    with tempfile.TemporaryDirectory(prefix='creator-pack-', dir=output.parent) as temporary:
        scratch = Path(temporary)
        archive = scratch/'course.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as stream:
            for name in sorted(included):
                stream.writestr(name, files[name])
        if archive.stat().st_size > MAX_BYTES:
            raise ValueError('ZIP exceeds the platform upload size limit')
        # Validate the archive's actual bytes, rather than its source directories.
        normalized = unpack_zip(archive, scratch/'payload')
        extracted = scratch/'source'
        def check(checked):
            for name in checked:
                target = extracted/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(checked[name])
            check_authoring(extracted, timeout)
        _, admitted = validate_zip_course(normalized, check)
        for course in admitted:
            run = subprocess.run([node, str(worker_build), course['module_id']], cwd=shuku,
                env={**env, 'SHUKU_COURSE_SOURCE':str(extracted), 'SHUKU_COURSE_OUTPUT':str(scratch/'builds')},
                capture_output=True, text=True, encoding='utf-8', timeout=timeout)
            if run.stdout:
                print(run.stdout, file=sys.stderr, end='')
            if run.returncode:
                raise ValueError('Shuku build failed: '+(run.stderr or run.stdout)[-2500:])
        (scratch/'builds').rename(builds)
        try:
            # Atomic, fails if another process created the destination meanwhile.
            os.link(archive, output)
        except OSError:
            # Builds remain available for diagnosis; an unverified ZIP is never delivered.
            raise ValueError('Could not create new ZIP; verified builds retained at '+str(builds)) from None
    return {'output':str(output), 'buildOutput':str(builds), 'courses':[c['module_id'] for c in admitted],
            'requested':sorted(selected_ids), 'files':len(included), 'zipBytes':output.stat().st_size,
            'coverage':{'zipRoundTrip':True,'platformAdmission':True,'realBuild':True,'rendering':False,'productionUpload':False},
            'unverified':['Inspect affected pages/interactions in these builds before upload', 'Destination deployment and live compute services']}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = export_course(require_target_root(), args.module, args.shuku_root, args.output, args.timeout)
        emit_result(result, status='passed')
        return 0
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.TimeoutExpired) as error:
        return report_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
