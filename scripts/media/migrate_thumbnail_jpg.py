#!/usr/bin/env python3
"""Normalize course thumbnail directories to 320x180 JPEG, using real filenames without legacy URL aliases.

Existing JPGs take precedence, so freshly captured pages are never replaced by
stale PNGs. Ordinary course images and scratch screenshots are left untouched.
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from _common import get_target_root, modules_directory
from PIL import Image
try:
    from media.thumbnail_profiles import THUMBNAIL_SIZE, save_thumbnail
except ModuleNotFoundError:
    from thumbnail_profiles import THUMBNAIL_SIZE, save_thumbnail

THUMBNAIL_DIRS = {'scenedeck-thumbnails', 'course-thumbnails'}


def migrate(root=None):
    root = Path(root) if root is not None else get_target_root()
    modules = modules_directory(root)
    files = sorted({p.resolve() for p in modules.rglob('*')
                    if p.is_file() and 'assets' in p.parts and '_scratchpad' not in p.parts
                    and THUMBNAIL_DIRS.intersection(p.parts)
                    and p.suffix.lower() in {'.png', '.jpeg', '.webp', '.jpg'}})
    converted = removed = 0
    # Write and validate every replacement before deleting any original.
    for source in files:
        target = source.with_suffix('.jpg')
        if not target.exists():
            with Image.open(source) as image:
                save_thumbnail(image, target)
            converted += 1
        with Image.open(target) as image:
            resized = image.copy() if image.size != THUMBNAIL_SIZE else None
        if resized is not None:
            save_thumbnail(resized, target)
        with Image.open(target) as image:
            assert image.format == 'JPEG', target
            image.verify()
    for source in files:
        if source.suffix.lower() != '.jpg':
            assert source.is_relative_to(modules.resolve())
            source.unlink()
            removed += 1
    return {'thumbnailCount': len({p.with_suffix('.jpg') for p in files}),
            'converted': converted, 'removedOldFiles': removed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(migrate(), ensure_ascii=False))
