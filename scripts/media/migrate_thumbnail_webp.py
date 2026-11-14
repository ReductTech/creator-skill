#!/usr/bin/env python3
"""Normalize course thumbnails and covers to 1600x900 WebP q=20.

Existing correctly sized WebPs take precedence over older source formats.
Original files, ordinary course images and scratch screenshots are retained.
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

THUMBNAIL_DIRS = {'scenedeck-thumbnails', 'course-thumbnails', 'course-covers'}


def migrate(root=None):
    root = Path(root) if root is not None else get_target_root()
    modules = modules_directory(root)
    files = sorted({p.resolve() for p in modules.rglob('*')
                    if p.is_file() and 'assets' in p.parts and '_scratchpad' not in p.parts
                    and THUMBNAIL_DIRS.intersection(p.parts)
                    and p.suffix.lower() in {'.png', '.jpeg', '.webp', '.jpg'}})
    converted = 0
    # Prefer existing WebP, then the old JPEG capture over older PNG copies.
    priority = {'.webp': 0, '.jpg': 1, '.jpeg': 2, '.png': 3}
    files.sort(key=lambda p: (str(p.with_suffix('')), priority[p.suffix.lower()]))
    for source in files:
        target = source.with_suffix('.webp')
        if not target.exists():
            with Image.open(source) as image:
                save_thumbnail(image, target)
            converted += 1
        with Image.open(target) as image:
            resized = image.copy() if image.size != THUMBNAIL_SIZE else None
        if resized is not None:
            assets = next(parent for parent in target.parents if parent.name == 'assets')
            backup = assets.with_name(assets.name + '-image-originals') / target.relative_to(assets)
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                backup.write_bytes(target.read_bytes())
            save_thumbnail(resized, target)
        with Image.open(target) as image:
            assert image.format == 'WEBP' and image.size == THUMBNAIL_SIZE, target
            image.verify()
    return {'thumbnailCount': len({p.with_suffix('.webp') for p in files}),
            'converted': converted, 'removedOldFiles': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(migrate(), ensure_ascii=False))
