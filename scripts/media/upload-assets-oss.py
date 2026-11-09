#!/usr/bin/env python3
"""Upload immutable SHA-256 objects and return a logical-path manifest. Dry-run has no network IO."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'common'))
from asset_protocol import PUBLIC_PREFIX, record as public_record, put_bucket, object_url
from module_assets import asset_roots, object_relatives
from _common import modules_directory, get_target_root, project_path, emit_result, report_error



ROOT = None
DEFAULT_ASSETS_DIR = None
OSS_PREFIX = PUBLIC_PREFIX+'/'


def object_key(assets_dir, path, records_only=False):
    data=Path(path).read_bytes()
    return public_record(Path(path).name,data)['object_key']


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets-dir', type=Path)
    parser.add_argument('--module', help='Only this canonical module UUID')
    parser.add_argument('--config', type=Path, help='Shared Shuku JSON; required for a real upload')
    parser.add_argument('--overwrite', action='store_true', help='Rejected: SHA-256 objects are immutable')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--records-only',dest='records_only',action='store_true',
                        help='Restrict inputs to JSON recordings; uploads still use the unified public directory')
    return parser


def visualization_files(assets_dir):
    directory = Path(assets_dir).resolve()
    candidates = directory.rglob('*')
    if DEFAULT_ASSETS_DIR is not None and directory == DEFAULT_ASSETS_DIR.resolve():
        candidates = {p for base in asset_roots(ROOT).values() for p in (ROOT / base).rglob('*')}
    return sorted(p for p in candidates if p.is_file() and not p.is_symlink()
                  and p.resolve().is_relative_to(directory) and '_scratchpad' not in p.parts)


def upload_one(bucket, assets_dir, path, overwrite=False, records_only=False, expected_key=None):
    if overwrite:
        raise ValueError('Content-addressed objects cannot be overwritten')
    if records_only and path.suffix.lower() != '.json':
        raise ValueError('Playback records must be JSON')
    data = path.read_bytes()
    item=public_record(path.name,data)
    key = item['object_key']
    if expected_key is not None and key != expected_key:
        raise ValueError('Asset changed after manifest creation; retry from a fixed source version')
    existed=bucket.object_exists(key)
    put_bucket(bucket,key,data,item['mime'])
    return ('skipped' if existed else 'uploaded'),key


def upload_assets(args):
    global ROOT, DEFAULT_ASSETS_DIR
    ROOT = get_target_root()
    DEFAULT_ASSETS_DIR = modules_directory(ROOT)
    if args.overwrite:
        raise ValueError('Content-addressed objects cannot be overwritten')
    directory=Path(args.assets_dir).expanduser() if args.assets_dir else DEFAULT_ASSETS_DIR
    directory=(directory if directory.is_absolute() else ROOT/directory).resolve()
    if not directory.is_dir():
        raise ValueError('Assets directory does not exist')
    files = visualization_files(directory)
    if args.module:
        parsed = uuid.UUID(args.module)
        if str(parsed) != args.module or parsed.version != 4:
            raise ValueError('Module must be a canonical UUID v4')
        owned = ROOT / asset_roots(ROOT).get(args.module,'modules/'+args.module+'/assets')
        files = [p for p in files if p.is_relative_to(owned)]
    if args.records_only and any(p.suffix.lower() != '.json' for p in files):
        raise ValueError('Playback records must be JSON')
    if not files:
        raise ValueError('No asset files found')
    records, unique = [], {}
    for file in files:
        data = file.read_bytes()
        item=public_record(file.name,data)
        key = item['object_key']
        unique.setdefault(key, file)
        aliases = object_relatives(ROOT, file) if directory == DEFAULT_ASSETS_DIR else [file.relative_to(directory).as_posix()]
        for alias in aliases:
            records.append({'path': alias, 'object_key': key, 'size': len(data),
                'sha256': hashlib.sha256(data).hexdigest(), 'mime': item['mime']})
    manifest = {'schema': 2, 'kind': 'asset-manifest', 'storage': 'sha256-v1', 'files': sorted(records, key=lambda r: r['path'])}
    if args.dry_run:
        return {'status': 'dry-run', 'objects': sorted(unique), 'files': len(files), 'unique_objects': len(unique), 'manifest': manifest}
    settings = None;config={}
    if getattr(args, 'config', None):
        config_path=Path(args.config).expanduser()
        config_path=config_path if config_path.is_absolute() else ROOT/config_path
        config=json.loads(config_path.read_text(encoding='utf-8-sig'))
        settings = config.get('storage', {}).get('oss', {})
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
        status, _ = upload_one(bucket, directory, file, False, args.records_only, expected_key=key)
        uploaded += status == 'uploaded'
        skipped += status == 'skipped'
    return {'status': 'ok', 'uploaded': uploaded, 'skipped': skipped, 'manifest': manifest,
            'publicUrlPrefix': object_url(config,next(iter(unique))).rsplit('/',2)[0]+'/',
            'access': 'public immutable course assets'}


def main(argv=None, *, root=None):
    args = build_parser().parse_args(argv)
    args.root=root
    try:
        result = upload_assets(args)
        emit_result(result)
        return 0
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        return report_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
