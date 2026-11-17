#!/usr/bin/env python3
"""Prepare media and references in staging, then check and deliver an ordinary ZIP.

Automatically runs available Python/Node/build/browser checks in isolated snapshots.
Missing dependencies use saved one-time installation consent. Never uploads.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import tempfile
import zipfile
import os
import shutil
from contextlib import contextmanager

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / 'common')]
from skzip import digest
from module.source_inputs import default_output
from module.source_checks import inspect_collection
from module.source_prepare import prepare_images
from module.source_media import prepare_media
from module.source_archive import write_source_archive
from module.source_report import start_report, record_stage, finish_report
from module.local_validation import capabilities, dependency_gate, node_references, local_checks
from common.local_context import context_metadata
from media.prepare_videos import EXTENSIONS as VIDEO_EXTENSIONS
from media.prepare_audio import EXTENSIONS as AUDIO_EXTENSIONS
from common.image_policy import IMAGE_SUFFIXES
SKILL_ROOT = Path(__file__).resolve().parents[2]


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', nargs='+', type=Path,
                        help='Module, modules directory, project root, or several directories; output is placed beside the modules')
    parser.add_argument('--ffmpeg', default='ffmpeg', help='FFmpeg executable name or path; only needed for audio/video')
    parser.add_argument('--ffprobe', default='ffprobe', help='ffprobe executable name or path; only needed for audio/video')
    parser.add_argument('--checks', choices=['auto','basic'], default=os.environ.get('CREATOR_SKILL_CHECK_MODE','auto'), help='auto: run every available check; basic only at explicit user request')
    parser.add_argument('--context', type=Path, help='This window absolute target-root.json; never changes the global binding')
    parser.add_argument('--shuku-root', type=Path, help='Optional local Shuku runtime/build checkout')
    parser.add_argument('--actions', type=Path, help='Authorized course-specific browser actions JSON; otherwise check default states')
    return parser


@contextmanager
def reserve_output(directories):
    while True:
        output = default_output(directories)
        lock = output.with_suffix('.lock')
        try:
            with lock.open('x', encoding='utf-8') as stream:
                stream.write(str(os.getpid()))
            break
        except FileExistsError:
            continue
    try:
        yield output
    finally:
        lock.unlink(missing_ok=True)


def export_source(directories, *, ffmpeg='ffmpeg', ffprobe='ffprobe', checks=None, context=None, shuku=None, actions=None):
    """Reserve unique outputs so simultaneous windows never overwrite each other's reports."""
    bound = context or os.environ.get('CREATOR_SKILL_TARGET_CONFIG')
    if bound and (context or (Path(bound).parent/'context.json').is_file()):
        metadata = context_metadata(bound)
        directories = [Path(p) if Path(p).is_absolute() else Path(metadata['targetRoot'])/p for p in directories]
        root=Path(metadata['targetRoot'])
        allowed=root
        if metadata.get('module'):
            from _common import resolve_module
            allowed=resolve_module(metadata['module'],root)[0]
        if any(not Path(p).resolve().is_relative_to(root) or metadata.get('module') and Path(p).resolve()!=allowed for p in directories):
            started=time.monotonic();report=start_report(directories,None)
            report['issues']['serious'].append({'code':'CONTEXT_SCOPE','message':'输入不属于本窗口绑定的工程或课件，未写入其他目录。'})
            return finish_report(report,started,'error')
    with reserve_output(directories) as output:
        return _export_source(directories, output, ffmpeg=ffmpeg, ffprobe=ffprobe,
                              checks=checks or os.environ.get('CREATOR_SKILL_CHECK_MODE','auto'), context=context, shuku=shuku, actions=actions)


def _export_source(directories, output, *, ffmpeg, ffprobe, checks, context, shuku, actions):
    """Pass one inventory through the pipeline; severe errors block the whole request."""
    started = time.monotonic()
    report = start_report(directories, output)
    stage, stage_started = 'source-checks', time.monotonic()
    try:
        bound = context or os.environ.get('CREATOR_SKILL_TARGET_CONFIG')
        metadata = context_metadata(bound) if bound and (context or (Path(bound).parent/'context.json').is_file()) else {}
        if metadata:
            report['context'] = metadata
            root = Path(metadata['targetRoot'])
            for directory in directories:
                if not Path(directory).resolve().is_relative_to(root):
                    raise ValueError('Input leaves this window targetRoot')
            if metadata.get('module'):
                from _common import resolve_module
                selected = resolve_module(metadata['module'], root)[0]
                if any(Path(p).resolve() != selected for p in directories):
                    raise ValueError('Bound course context only packages that course; pass its explicit directory')
        files, inspection = inspect_collection(directories)
        report.update({key: value for key, value in inspection.items() if key != 'coverage'})
        report['sourceCheckCoverage'] = inspection['coverage']
        report['issues']['warnings'].extend(inspection['warnings'])
        report['issues']['serious'].extend(inspection['serious'])
        report['issues']['serious'].extend({'stage': stage, **item} for item in inspection['rejectedModules'])
        if not files and not report['issues']['serious']:
            report['issues']['serious'].append({'stage': stage, 'reason': 'No valid module source'})
        blocked = bool(report['issues']['serious'])
        record_stage(report, stage, stage_started, 'failed' if blocked else 'passed',
                     moduleCount=inspection['moduleCount'], rejectedModuleCount=inspection['rejectedModuleCount'])
        if blocked:
            return finish_report(report, started, 'failed')
        report['coverage']['sourceChecks'] = True
        original_outline = next((path for name,path in files.items() if name.endswith('/outlines.json') and name.count('/')==2),None)
        source_shared = next((p for p in [original_outline.parent.parent/'shared' if original_outline else SKILL_ROOT/'shared', SKILL_ROOT/'shared']
                              if (p/'style.json').is_file()),None)
        capability = None
        if checks == 'auto':
            has_media = any(path.suffix.lower() in VIDEO_EXTENSIONS|AUDIO_EXTENSIONS and
                            (path.suffix.lower()!='.ts' or '/assets/' in name) for name,path in files.items())
            buildable = any(json.loads(path.read_text(encoding='utf-8-sig')).get('entry') or json.loads(path.read_text(encoding='utf-8-sig')).get('ppt',{}).get('entry')
                            for name,path in files.items() if name.endswith('/outlines.json') and name.count('/')==2)
            capability = capabilities(shuku=shuku or metadata.get('shukuRoot'), media=has_media, buildable=buildable,
                                      images=any(path.suffix.lower() in IMAGE_SUFFIXES for path in files.values()))
            if has_media and shutil.which(ffmpeg) and shutil.which(ffprobe):
                capability['missing'] = [m for m in capability['missing'] if m!='ffmpeg']
            report['capabilities'] = capability
            report['dependencySetup'] = dependency_gate(capability, owner=metadata.get('sessionId'))
            if report['dependencySetup']['blockedForSetup']:
                return finish_report(report, started, 'needs-input' if report['dependencySetup']['policy']['installation']=='pending' else 'needs-setup')
        stage, stage_started = 'media-and-references', time.monotonic()
        with tempfile.TemporaryDirectory(prefix='creator-images-') as temporary:
            if inspection.get('styleRegistry'):
                registry = Path(temporary)/'course-styles.json'
                registry.write_text(json.dumps(inspection['styleRegistry'], ensure_ascii=False), encoding='utf-8')
                files['course-styles.json'] = registry
            reference_runner = (lambda f,c,d:node_references(f,c,d,capability)) if capability and capability['available']['typescript'] else None
            files, report['media'], report['images'] = prepare_media(files, Path(temporary), ffmpeg=ffmpeg, ffprobe=ffprobe, reference_runner=reference_runner)
            for item in report['media']['issues']:
                report['issues']['serious' if item.get('blocking') else 'warnings'].append(item)
            blocked = bool(report['issues']['serious'])
            record_stage(report, stage, stage_started, 'failed' if blocked else 'passed',
                         counts=report['media']['counts'], replacements=report['media']['references']['replacements'])
            if blocked:
                return finish_report(report, started, 'failed')
            files, _ = prepare_images(files, Path(temporary))
            if capability:
                stage, stage_started = 'local-checks', time.monotonic()
                files, report['localChecks'] = local_checks(files,Path(temporary),capability,output.with_suffix('.checks'),shared=source_shared,actions=actions)
                for item in report['localChecks']['issues']:
                    report['issues']['serious' if item.get('blocking') else 'warnings'].append(item)
                report['coverage'].update(localBuild=report['localChecks']['coverage']['localBuild'], rendering=report['localChecks']['coverage']['rendering'])
                blocked = bool(report['issues']['serious'])
                record_stage(report,stage,stage_started,'failed' if blocked else 'passed')
                if blocked: return finish_report(report,started,'failed')
            stage, stage_started = 'archive-and-integrity', time.monotonic()
            producer = {'name': 'creator-skill/course.pack', 'revision': digest(Path(__file__).read_bytes())}
            # Never embed local absolute paths in the uploaded report.
            result = write_source_archive(files, {'modules': inspection['modules'], 'images': report['images']}, output, producer)
        report.update(result)
        report['outputCreated'] = True
        report['coverage']['zipIntegrity'] = True
        record_stage(report, stage, stage_started, 'passed', files=result['files'], zipBytes=result['zipBytes'])
        return finish_report(report, started, 'passed')
    except (ValueError, OSError, RuntimeError, UnicodeError, zipfile.BadZipFile) as error:
        record_stage(report, stage, stage_started, 'failed', message=str(error))
        report['issues']['serious'].append({'stage': stage, 'reason': str(error)})
        return finish_report(report, started, 'error')


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = export_source(args.directories, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
                               checks=args.checks, context=args.context, shuku=args.shuku_root, actions=args.actions)
    except (ValueError, OSError) as error:
        started = time.monotonic()
        result = start_report(args.directories, None)
        result['issues']['serious'].append({'stage': 'output-location', 'reason': str(error)})
        record_stage(result, 'output-location', started, 'failed', message=str(error))
        result = finish_report(result, started, 'error')
    # One compact agent-facing document; full conversions and diagnostics are on disk.
    from module.source_report import agent_summary
    print(json.dumps(agent_summary(result), ensure_ascii=False, allow_nan=False))
    return 0 if result['status'] == 'passed' else 3 if result['status'] in {'needs-input','needs-setup'} else 1 if result['status'] == 'failed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
