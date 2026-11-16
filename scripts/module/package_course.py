#!/usr/bin/env python3
"""Python/Pillow SKZIP pipeline: inspect, optimize images, inventory and archive.

Never installs/runs Node, rewrites source, builds, captures, deletes or uploads.
The server verifies image mappings and migrates references before compilation.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import tempfile
import zipfile

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / 'common')]
from skzip import digest
from module.source_inputs import default_output
from module.source_checks import inspect_collection
from module.source_prepare import prepare_images
from module.source_archive import write_source_archive
from module.source_report import start_report, record_stage, finish_report


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', nargs='+', type=Path,
                        help='Module, modules directory, project root, or several directories; output is placed beside the modules')
    return parser


def export_source(directories):
    """Pass one inventory through the pipeline; severe errors block the whole request."""
    started = time.monotonic()
    output = default_output(directories)
    report = start_report(directories, output)
    stage, stage_started = 'source-checks', time.monotonic()
    try:
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
        stage, stage_started = 'image-inspection', time.monotonic()
        with tempfile.TemporaryDirectory(prefix='creator-images-') as temporary:
            if inspection.get('styleRegistry'):
                registry = Path(temporary)/'course-styles.json'
                registry.write_text(json.dumps(inspection['styleRegistry'], ensure_ascii=False), encoding='utf-8')
                files['course-styles.json'] = registry
            files, report['images'] = prepare_images(files, Path(temporary))
            report['issues']['warnings'].extend(report['images']['issues'])
            record_stage(report, stage, stage_started, report['images']['status'],
                         counts=report['images']['counts'], converted=report['images']['converted'])
            stage, stage_started = 'archive-and-integrity', time.monotonic()
            producer = {'name': 'creator-skill/course.pack', 'revision': digest(Path(__file__).read_bytes())}
            # Never embed local absolute paths in the uploaded report.
            result = write_source_archive(files, {'modules': inspection['modules'], 'images': report['images']}, output, producer)
        report.update(result)
        report['outputCreated'] = True
        report['coverage']['skzipIntegrity'] = True
        record_stage(report, stage, stage_started, 'passed', files=result['files'], zipBytes=result['zipBytes'])
        return finish_report(report, started, 'passed')
    except (ValueError, OSError, UnicodeError, zipfile.BadZipFile) as error:
        record_stage(report, stage, stage_started, 'failed', message=str(error))
        report['issues']['serious'].append({'stage': stage, 'reason': str(error)})
        return finish_report(report, started, 'error')


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = export_source(args.directories)
    except (ValueError, OSError) as error:
        started = time.monotonic()
        result = start_report(args.directories, None)
        result['issues']['serious'].append({'stage': 'output-location', 'reason': str(error)})
        record_stage(result, 'output-location', started, 'failed', message=str(error))
        result = finish_report(result, started, 'error')
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result['status'] == 'passed' else 1 if result['status'] == 'failed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
