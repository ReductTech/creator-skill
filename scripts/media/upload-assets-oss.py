#!/usr/bin/env python3
"""Upload immutable SHA-256 objects and return a logical-path manifest. Dry-run has no network IO."""
from __future__ import annotations
import argparse
import hashlib
import json
import mimetypes
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from _common import get_target_root, emit_result, report_error, project_path
from module_assets import asset_roots, object_relatives

ROOT = None
DEFAULT_ASSETS_DIR = None
OSS_PREFIX = 'assets/sha256/'


def object_key(assets_dir, path, private_records=False):
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return OSS_PREFIX + digest[:2] + '/' + digest


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets-dir', type=Path)
    parser.add_argument('--module', help='Only this canonical module UUID')
    parser.add_argument('--config', type=Path, help='Shared Shuku JSON; required for a real upload')
    parser.add_argument('--overwrite', action='store_true', help='Rejected: SHA-256 objects are immutable')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--private-records', action='store_true', help='Restrict inputs to JSON; all CAS objects remain private')
    return parser


def visualization_files(assets_dir):
    directory = Path(assets_dir).resolve()
    candidates = directory.rglob('*')
    if DEFAULT_ASSETS_DIR is not None and directory == DEFAULT_ASSETS_DIR.resolve():
        candidates = {p for base in asset_roots(ROOT).values() for p in (ROOT / base).rglob('*')}
    return sorted(p for p in candidates if p.is_file() and not p.is_symlink()
                  and p.resolve().is_relative_to(directory) and '_scratchpad' not in p.parts)


def upload_one(bucket, assets_dir, path, overwrite=False, private_records=False, expected_key=None):
    if overwrite:
        raise ValueError('Content-addressed objects cannot be overwritten')
    if private_records and path.suffix.lower() != '.json':
        raise ValueError('Private playback records must be JSON')
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    key = OSS_PREFIX + digest[:2] + '/' + digest
    if expected_key is not None and key != expected_key:
        raise ValueError('Asset changed after manifest creation; retry from a fixed source version')
    def verify():
        head = bucket.head_object(key)
        if head.content_length != len(data):
            raise ValueError('Existing SHA-256 object has incorrect size')
        if head.headers.get('x-oss-meta-sha256') != key.rsplit('/', 1)[-1]:
            if bucket.get_object(key).read() != data:
                raise ValueError('Existing SHA-256 object is corrupt')
    if bucket.object_exists(key):
        verify()
        return 'skipped', key
    try:
        bucket.put_object(key, data, headers={'Content-Type': 'application/octet-stream',
            'x-oss-object-acl': 'private', 'x-oss-forbid-overwrite': 'true',
            'x-oss-meta-sha256': key.rsplit('/', 1)[-1]})
    except Exception as error:
        if getattr(error, 'status', None) != 409 or getattr(error, 'code', None) != 'FileAlreadyExists':
            raise
        verify()
        return 'skipped', key
    return 'uploaded', key


def upload_assets(args):
    global ROOT, DEFAULT_ASSETS_DIR
    ROOT = get_target_root()
    DEFAULT_ASSETS_DIR = ROOT / 'modules'
    if args.overwrite:
        raise ValueError('Content-addressed objects cannot be overwritten')
    directory = project_path(args.assets_dir, external=True) if args.assets_dir else DEFAULT_ASSETS_DIR
    if not directory.is_dir():
        raise ValueError('Assets directory does not exist')
    files = visualization_files(directory)
    if args.module:
        parsed = uuid.UUID(args.module)
        if str(parsed) != args.module or parsed.version != 4:
            raise ValueError('Module must be a canonical UUID v4')
        owned = ROOT / 'modules' / args.module / 'assets'
        files = [p for p in files if p.is_relative_to(owned)]
    if args.private_records and any(p.suffix.lower() != '.json' for p in files):
        raise ValueError('Private playback records must be JSON')
    if not files:
        raise ValueError('No asset files found')
    records, unique = [], {}
    for file in files:
        data = file.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        key = OSS_PREFIX + digest[:2] + '/' + digest
        unique.setdefault(key, file)
        aliases = object_relatives(ROOT, file) if directory == DEFAULT_ASSETS_DIR else [file.relative_to(directory).as_posix()]
        for alias in aliases:
            records.append({'path': alias, 'object_key': key, 'size': len(data),
                'sha256': key.rsplit('/', 1)[-1], 'mime': mimetypes.guess_type(file.name)[0] or 'application/octet-stream'})
    manifest = {'schema': 2, 'kind': 'asset-manifest', 'storage': 'sha256-v1', 'files': sorted(records, key=lambda r: r['path'])}
    settings = None
    if getattr(args, 'config', None):
        settings = json.loads(project_path(args.config, external=True).read_text(encoding='utf-8-sig')).get('storage', {}).get('oss', {})
    if args.dry_run:
        return {'status': 'dry-run', 'objects': sorted(unique), 'files': len(files), 'unique_objects': len(unique), 'manifest': manifest}
    if not settings or not all(settings.get(k) for k in ('endpoint', 'bucket', 'region', 'access_key_id', 'access_key_secret')):
        raise ValueError('Pass --config pointing to the shared Shuku JSON with storage.oss settings')
    import oss2
    bucket = oss2.Bucket(oss2.AuthV4(settings['access_key_id'], settings['access_key_secret']),
                         settings['endpoint'], settings['bucket'], region=settings['region'])
    # Versioned buckets ignore forbid-overwrite; do not silently create duplicate object versions.
    if bucket.get_bucket_versioning().status not in (None, '', 'Disabled'):
        raise ValueError('CAS requires an unversioned bucket; no bucket settings were changed')
    uploaded = skipped = 0
    for key, file in unique.items():
        status, _ = upload_one(bucket, directory, file, False, args.private_records, expected_key=key)
        uploaded += status == 'uploaded'
        skipped += status == 'skipped'
    return {'status': 'ok', 'uploaded': uploaded, 'skipped': skipped, 'manifest': manifest,
            'publicUrlPrefix': None, 'access': 'resolve logical paths through the version manifest'}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = upload_assets(args)
        emit_result(result)
        return 0
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        return report_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
