#!/usr/bin/env python3
"""The official SKZIP delivery entry: prepare, review resources, verify, then seal.

Reads: Configured course repository and explicitly selected Shuku checkout.
Writes: A resource review, or a new .skzip and verified builds. Never uploads or publishes.
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
from _common import emit_result, report_error, require_target_root, modules_directory
from skzip import canonical, digest, envelope, verify_archive, MANIFEST, CHECKS
from module.delivery_prepare import prepare, resource_review, choose_resources, tool

SKIP = {'.git', 'node_modules', 'dist', '__pycache__', '_scratchpad', '.pytest_cache', 'creator-skill'}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', action='append', required=True, help='Course UUID or alias; repeat for a collection')
    parser.add_argument('--shuku-root', type=Path, required=True, help='Absolute path to the Shuku checkout used by the destination platform')
    parser.add_argument('--output', type=Path, required=True, help='New absolute .skzip path; existing outputs are never overwritten')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--resources', choices=['keep-all'], help='Author explicitly chooses to retain every inventoried resource')
    group.add_argument('--resource-decisions', type=Path, help='Author-reviewed JSON from the previous run, with keep/exclude per resource')
    parser.add_argument('--plan', action='store_true', help='Prepare and write a resource review only; never produce a SKZIP')
    parser.add_argument('--timeout', type=int, default=300, help='Maximum seconds per admission/build command')
    return parser


def source_paths(root, directories):
    """Collect only requested source roots, preserving their actual logical paths."""
    files = {}
    def linked(path):
        return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400)
    for directory in directories:
        directory = Path(directory)
        if linked(directory) or not directory.resolve().is_relative_to(root):
            raise ValueError('Source dependency must stay inside targetRoot: '+str(directory))
        if not directory.is_dir():
            raise ValueError('Missing source dependency: '+str(directory))
        for current, dirs, names in os.walk(directory, followlinks=False):
            base = Path(current)
            dirs[:] = [name for name in dirs if name not in SKIP]
            if any(linked(base/name) for name in [*dirs, *names]):
                raise ValueError('Source ZIP cannot contain symlinks: '+str(base))
            for name in names:
                path = base/name
                if path.suffix.lower() in {'.zip', '.skzip', '.pyc'} or name == '.env' or name.startswith('.env.'):
                    continue
                files[path.relative_to(root).as_posix()] = path
    return files


def export_course(root, requested, shuku, output, timeout=300, *, resources=None, resource_decisions=None, plan_only=False):
    root, shuku, output = Path(root).resolve(), Path(shuku), Path(output)
    if not shuku.is_absolute() or not output.is_absolute() or output.suffix.lower() != '.skzip':
        raise ValueError('--shuku-root and .skzip --output must be absolute paths; ordinary ZIP delivery is no longer supported')
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
    from shared.courses.source.source_files import SourceFiles
    from shared.courses.source.course_repository import discover_shuku_courses, course_input_paths, normalize_course_files
    from shared.courses.styles import supply_default_style, DEFAULT_STYLE_ID
    from shared.courses.source.zip_input import unpack_zip
    from shared.courses.source.source_limits import MAX_FILES, MAX_BYTES, MAX_FILE_BYTES
    from worker.shuku_worker.build.course_validation import validate_zip_course, check_authoring, CourseValidationError

    directories = [modules_directory(root)]
    registry = root/'course-styles.json'
    if registry.is_file():
        catalog = json.loads(registry.read_text(encoding='utf-8-sig'))
        directories.extend(root/item['path'] for item in catalog['styles']
                           if (root/item['path']).exists() or item['id'] != DEFAULT_STYLE_ID)
    raw = source_paths(root, directories)
    if registry.is_file():
        raw['course-styles.json'] = registry
    files = supply_default_style(normalize_course_files(SourceFiles(raw)))
    candidates = discover_shuku_courses(files, partial=True)
    selected = []
    for name in requested:
        matches = [item for item in candidates if any(isinstance(value, str) and name.casefold() == value.casefold()
                   for value in (item['module_id'], item['path'], item['outline'].get('alias')))]
        if len(matches) != 1:
            raise ValueError('Unknown or ambiguous course: '+name)
        if matches[0] not in selected:
            selected.append(matches[0])
    selected_ids = {item['module_id'] for item in selected}
    inputs = course_input_paths(files, candidates, selected={item['path'] for item in selected})
    included = set().union(*inputs.values())
    packaged = [item for item in candidates if item['path']+'/outlines.json' in included]
    if len(included) > MAX_FILES or sum(files.size(name) for name in included) > MAX_BYTES:
        raise ValueError('Source ZIP exceeds the selected platform expanded size/file-count limits')
    if any(files.size(name) > MAX_FILE_BYTES for name in included):
        raise ValueError('Source ZIP exceeds the platform per-file size limit')

    output.parent.mkdir(parents=True, exist_ok=True)
    builds = output.parent/(output.stem+'-verified-'+uuid4().hex[:8])
    scripts = Path(__file__).resolve().parents[1]
    producer_files = sorted((p for p in scripts.rglob('*') if p.is_file()
                             and p.suffix in ('.py', '.js', '.mjs', '.cjs')
                             and p.relative_to(scripts).parts[0] not in ('tests', 'templates')),
                            key=lambda p:p.relative_to(scripts).as_posix())
    producer_hash = digest(canonical([[p.relative_to(scripts).as_posix(),digest(p.read_bytes())] for p in producer_files]))
    env = {key:value for key,value in os.environ.items()
           if key not in {'SHUKU_ASSET_PYTHON','SHUKU_SOURCE_PYTHON','SHUKU_ASSET_CONFIG','SHUKU_COURSE_COMMIT'}}
    with tempfile.TemporaryDirectory(prefix='creator-pack-', dir=output.parent) as temporary:
        scratch = Path(temporary)
        prepared = scratch/'prepared'
        original_records = []
        for name in sorted(included):
            raw = files[name]
            target = prepared/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            original_records.append({'path':name, 'sha256':digest(raw), 'size':len(raw)})
        # Bind author decisions to both the exact source bytes and preparation rules.
        snapshot = digest(canonical({'files':original_records, 'tool':producer_hash}))
        preparation, originals, config = prepare(prepared, packaged, scratch, timeout)
        review = resource_review(prepared, packaged, originals, snapshot)
        decisions = json.loads(Path(resource_decisions).read_text(encoding='utf-8-sig')) if resource_decisions else None
        choice = choose_resources(review, decisions, resources)
        if plan_only or choice is None:
            review_path = output.parent/(output.stem+'-resource-review-'+uuid4().hex[:8]+'.json')
            review_path.write_bytes(canonical(review))
            return {'status':'needs-resource-review', 'review':str(review_path), 'sourceSnapshot':snapshot,
                    'resourceCount':len(review['resources']), 'resourceBytes':review['totalBytes'],
                    'preparation':preparation, 'outputCreated':False,
                    'nextAction':'Show the inventory to the author. Use their reviewed --resource-decisions file or their explicit --resources keep-all choice. Never choose on their behalf.'}
        for row in choice['decisions']:
            if row['decision'] == 'exclude':
                # Exact inventoried file in the disposable tree only; never recursive.
                target = prepared/row['path']
                if not target.resolve().is_relative_to(prepared.resolve()) or digest(target.read_bytes()) != row['sha256']:
                    raise ValueError('Resource changed before exclusion')
                target.unlink()
        payload = source_paths(prepared, [prepared])
        archive = scratch/'payload.zip'
        def write_payload():
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as stream:
                for name in sorted(payload):
                    stream.writestr(name, payload[name].read_bytes())
        write_payload()
        if archive.stat().st_size > MAX_BYTES:
            raise ValueError('SKZIP exceeds the platform upload size limit')
        normalized = unpack_zip(archive, scratch/'payload')
        extracted = scratch/'source'
        extracted.mkdir()
        def check(checked):
            directory = Path(tempfile.mkdtemp(prefix='admission-', dir=scratch))
            for name in checked:
                target = directory/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(checked[name])
            try:
                check_authoring(directory, timeout)
            finally:
                shutil.rmtree(directory)
        normalized, admitted = validate_zip_course(normalized, check, partial=True)
        inputs = course_input_paths(normalized, admitted, conservative_dynamic=False)
        verified = []
        rejected = [{'module_id':course['module_id'], 'issues':course.get('validation', {}).get('issues',
                    [{'path':course['path'], 'message':'Course has no buildable entry'}])}
                    for course in admitted if not course['ready']]
        accepted = []
        delivery_warnings = []
        from shared.courses.delivery.delivery_validation import validate_local_delivery
        for course in admitted:
            if not course['ready']:
                continue
            shutil.rmtree(extracted)
            extracted.mkdir()
            for name in inputs[course['path']]:
                target = extracted/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(normalized[name])
            try:
                run = subprocess.run([node, str(worker_build), course['module_id']], cwd=shuku,
                    env={**env, 'SHUKU_COURSE_SOURCE':str(extracted), 'SHUKU_COURSE_OUTPUT':str(scratch/'builds')},
                    capture_output=True, text=True, encoding='utf-8', timeout=timeout)
            except subprocess.TimeoutExpired:
                rejected.append({'module_id':course['module_id'], 'issues':[{'path':course['path'],
                    'message':'Shuku build exceeded the per-course timeout'}]})
                continue
            if run.stdout:
                print(run.stdout, file=sys.stderr, end='')
            if run.returncode:
                rejected.append({'module_id':course['module_id'], 'issues':[{'path':course['path'],
                    'message':'Shuku build failed: '+(run.stderr or run.stdout)[-2500:]}]})
                continue
            manifests = list((scratch/'builds'/course['module_id']).glob('*/artifact-manifest.json'))
            if len(manifests) != 1:
                rejected.append({'module_id':course['module_id'], 'issues':[{'path':course['path'],
                    'message':'Expected one completed Shuku build'}]})
                continue
            accepted.append(course['module_id'])
            try:
                checked = validate_local_delivery(manifests[0].parent, timeout_ms=min(30000,timeout*1000))
                verified.append({'module_id':course['module_id'], **checked})
            except (ValueError, RuntimeError, OSError, ImportError, subprocess.TimeoutExpired) as error:
                delivery_warnings.append({'module_id':course['module_id'], 'message':str(error)[:2500]})
        if not accepted:
            raise ValueError('No course passed admission and build: '+json.dumps(rejected, ensure_ascii=False))
        checks = {name:{'status':'passed'} for name in CHECKS}
        for name in ('admission', 'build'):
            checks[name].update(scope='accepted-courses', accepted=accepted, rejected=rejected)
        checks['images']['status'] = 'warning' if any(image.get('status') not in ('converted', 'unchanged')
            or image.get('reason') not in (None, 'within-bounds') for row in preparation for image in row['images']) else 'passed'
        if any(row['decision'] == 'keep' and row['path'] in originals for row in choice['decisions']):
            checks['images'].update(status='warning', retainedOriginals=True)
        checks['references']['status'] = 'warning' if any(row['references'].get('status') == 'warning'
            or any(row['references'].get(key) for key in ('unresolved','unverified','changedFiles','referenceCount'))
            for row in preparation) else 'passed'
        checks['editIds']['status'] = 'warning' if any(row['editIds'].get('status') == 'warning'
            or row['skippedComponents'] for row in preparation) else 'passed'
        checks['images']['courses'] = preparation
        checks['editIds']['coverage'] = 'Eligible authored JSX nodes were checked; per-course reports record failures and skipped components. Shared is immutable. A warning is not a coverage guarantee.'
        checks['resources']['retainedBytes'] = review['totalBytes'] - choice['excludedBytes']
        checks['rendering']['courses'] = verified
        if delivery_warnings:
            for name in ('rendering', 'mediaReferences'):
                checks[name].update(status='warning', warnings=delivery_warnings)
        package_files = SourceFiles(payload)
        document = envelope(package_files, checks, choice,
                            {'name':'creator-skill/course.pack', 'revision':producer_hash})
        sealed = scratch/'course.skzip'
        with zipfile.ZipFile(sealed, 'w', zipfile.ZIP_DEFLATED) as stream:
            for name in sorted(payload):
                stream.write(payload[name], name)
            stream.writestr(MANIFEST, canonical(document))
        verify_archive(sealed)
        # Hash verification includes all entries and the manifest. An ordinary ZIP,
        # partial check or changed source cannot be silently delivered as SKZIP.
        (scratch/'builds').rename(builds)
        try:
            # Atomic, fails if another process created the destination meanwhile.
            os.link(sealed, output)
        except OSError:
            # Builds remain available for diagnosis; an unverified ZIP is never delivered.
            raise ValueError('Could not create new ZIP; verified builds retained at '+str(builds)) from None
    return {'status':'passed', 'output':str(output), 'buildOutput':str(builds), 'courses':accepted, 'rejectedCourses':rejected,
            'requested':sorted(selected_ids), 'files':len(payload), 'zipBytes':output.stat().st_size,
            'coverage':{**{name:record['status'] == 'passed' for name,record in checks.items()},
                        'skzipIntegrity':True, 'zipRoundTrip':True, 'resourceReview':True,
                        'platformAdmission':True, 'realBuild':True, 'productionUpload':False},
            'warnings':delivery_warnings, 'preparation':preparation,
            'verifiedDeliveries':verified,
            'unverified':['Interaction states beyond the initial capture', 'Destination deployment and live compute services']}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = export_course(require_target_root(), args.module, args.shuku_root, args.output, args.timeout,
                               resources=args.resources, resource_decisions=args.resource_decisions, plan_only=args.plan)
        emit_result(result)
        return 0 if result['status'] == 'passed' else 1
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.TimeoutExpired) as error:
        return report_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
