#!/usr/bin/env python3
"""Inspect course source metadata, UTF-8 and literal local imports using Python.

No compilation, source execution, dependency installation or security certification.
Independently callable; returns valid modules, rejected inputs and warnings.
"""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / 'common')]
from course_metadata import module_errors
from module.source_inputs import discover_modules, source_paths

CODE = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css'}
IMPORT = re.compile(r'''(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s*)['"](\.[^'"\r\n]+)['"]''')


def inspect_module(module, files):
    """Use the existing Python metadata contract; missing runtime code is not built."""
    doc = json.loads((module / 'outlines.json').read_text(encoding='utf-8-sig'))
    def exists(entry):
        return isinstance(entry, str) and entry in files
    errors = module_errors(doc, module.name, complete=True, exists=exists)
    if errors:
        raise ValueError('; '.join(errors))
    warnings = []
    if not doc.get('entry') and not (doc.get('ppt') or {}).get('entry'):
        warnings.append({'kind': 'outline-only', 'module': module.name,
                         'message': 'Source draft; server determines import eligibility'})
    missing = sum('assets/shuku-thumbnails/' + page['id'] + '.webp' not in files for page in doc['pages'])
    if missing:
        warnings.append({'kind': 'missing-thumbnails', 'module': module.name, 'count': missing,
                         'message': 'Existing thumbnails retained; no capture required for source packaging'})
    for name, path in files.items():
        if path.suffix.lower() not in CODE:
            continue
        text = path.read_text(encoding='utf-8-sig')
        if '\x00' in text:
            raise ValueError('Source contains a NUL byte: ' + name)
        for reference in IMPORT.findall(text):
            if any(p.casefold() == 'shared' for p in reference.replace('\\', '/').split('/')):
                continue
            target = (path.parent / reference).resolve()
            candidates = [target, *(Path(str(target) + ext) for ext in CODE | {'.json'}),
                          *(target / ('index' + ext) for ext in CODE)]
            if not target.is_relative_to(module) or not any(p.is_file() for p in candidates):
                warnings.append({'kind': 'unverified-import', 'module': module.name,
                                 'path': name, 'reference': reference})
    return {'id': doc['id'], 'title': doc.get('title') or '未命名标题',
            'pages': len(doc['pages']), 'files': len(files), 'missingThumbnails': missing}, warnings


def inspect_collection(directories):
    """Discover and check once; return the collected inventory for the next stage."""
    modules, shared = discover_modules(directories)
    files, accepted, rejected, warnings, identities = {}, [], [], [], set()
    for module in modules:
        try:
            local = source_paths(module, [module], shared)
            record, notes = inspect_module(module, local)
            if record['id'] in identities:
                raise ValueError('Duplicate module identity from multiple directories')
            identities.add(record['id'])
            accepted.append(record)
            warnings.extend(notes)
            files.update({'modules/' + module.name + '/' + name: path for name, path in local.items()})
        except (ValueError, OSError, UnicodeError, TypeError, KeyError) as error:
            rejected.append({'directory': str(module), 'reason': str(error)})
    return files, {'status': 'passed' if accepted and not rejected else 'failed', 'modules': accepted,
                   'moduleCount': len(accepted), 'rejectedModuleCount': len(rejected),
                   'rejectedModules': rejected, 'excludedShared': sorted(set(shared)),
                   'warningCount': len(warnings), 'warnings': warnings,
                   'coverage': 'Metadata, declared local entries, UTF-8 and literal import hints; no JS parsing, build or security review'}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', nargs='+', type=Path, help='Module, collection, project root, or several directories')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        _, report = inspect_collection(args.directories)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report['status'] == 'passed' else 1
    except (ValueError, OSError) as error:
        print(json.dumps({'status': 'error', 'error': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
