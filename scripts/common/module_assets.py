"""Resolve module-owned files while retaining stable OSS UUID namespaces."""
import json
from pathlib import Path
try:
    from .course_paths import modules_directory
except ImportError:
    from course_paths import modules_directory


def asset_roots(root):
    root = Path(root)
    from course_metadata import RULES
    for name in RULES['retired_resource_manifests']:
        if (root / name).exists():
            raise ValueError(f'{name}: resource indexes and filename mappings are unsupported; use course-local assets with their actual filenames')
    roots = {}
    for outline in modules_directory(root).glob('*/outlines.json'):
        doc = json.loads(outline.read_text(encoding='utf-8-sig'))
        if not isinstance(doc, dict):
            raise ValueError(f'{outline}: outline must be an object')
        identity = doc.get('moduleIdentity')
        uid = identity.get('id') if isinstance(identity, dict) else None
        if isinstance(uid, str) and uid:
            roots[uid] = (outline.parent / 'assets').relative_to(root).as_posix()
    return roots


def asset_directory(root, uid):
    root = Path(root).resolve()
    relative = asset_roots(root).get(uid)
    if not relative:raise ValueError('Unknown course UUID: '+str(uid))
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError('Asset directory leaves repository')
    return target


def object_relative(root, file):
    root, file = Path(root).resolve(), Path(file).resolve()
    # Resolve the registered course ownership directly.
    for uid, relative in asset_roots(root).items():
        directory = (root / relative).resolve()
        if file.is_relative_to(directory):
            return uid + '/' + file.relative_to(directory).as_posix()
    raise ValueError('File is not in a registered module assets directory: ' + str(file))


def object_relatives(root, file):
    root, file = Path(root).resolve(), Path(file).resolve()
    return [uid+'/'+file.relative_to((root/relative).resolve()).as_posix()
            for uid,relative in asset_roots(root).items()
            if file.is_relative_to((root/relative).resolve())]


def asset_relative(root, uid, name):
    from pathlib import PurePosixPath
    path=PurePosixPath(name)
    if path.is_absolute() or any(part in ('', '.', '..') for part in name.split('/')) or any(char in name for char in ':?#') or '\\' in name:
        raise ValueError('Use a relative resource path')
    return name
