"""Compress course assets to WebP without enlarging ordinary images.

Ordinary PNG/JPEG/WebP images with a long edge above 900 become WebP q=80,
proportionally resized to a 900-pixel long edge. Smaller images stay byte-identical.
Thumbnails and covers instead use 1600x900 WebP q=20. Animation and high-bit-depth
images are skipped. Sources are retained; in-place WebP writes require a backup.
References must be updated explicitly to the reported real WebP filenames.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from _common import project_path

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp'}
THUMBNAIL_DIRS = {'scenedeck-thumbnails', 'course-thumbnails', 'course-covers'}
MAX_SIDE = 900
QUALITY = 80


def fit_size(width, height):
    scale = min(1.0, MAX_SIDE / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale))


def is_link(path):
    # Windows junction support without requiring Python 3.12 Path.is_junction.
    return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400)


def convert(path, dry_run=False, backup=None):
    from PIL import Image, ImageOps
    from media.thumbnail_profiles import THUMBNAIL_SIZE, THUMBNAIL_QUALITY, thumbnail_image

    path = Path(path)
    result = {'source': str(path), 'status': 'skipped'}
    if is_link(path) or path.suffix.lower() not in IMAGE_SUFFIXES:
        return {**result, 'reason': 'unsupported-format-or-link'}
    target = path.with_suffix('.webp')
    thumbnail = bool(THUMBNAIL_DIRS.intersection(path.parts))
    quality = THUMBNAIL_QUALITY if thumbnail else QUALITY
    with Image.open(path) as original:
        if original.format not in {'PNG', 'JPEG', 'WEBP'}:
            return {**result, 'reason': 'format-mismatch'}
        if getattr(original, 'n_frames', 1) != 1 or getattr(original, 'is_animated', False):
            return {**result, 'reason': 'animated'}
        if original.mode not in {'RGB', 'RGBA', 'L', 'LA', 'P', 'CMYK'}:
            return {**result, 'reason': 'unsupported-bit-depth-or-mode'}
        image = ImageOps.exif_transpose(original)
        before_size = image.size
        after_size = THUMBNAIL_SIZE if thumbnail else fit_size(*before_size)
        result.update(target=str(target), before_size=list(before_size),
                      after_size=list(after_size), before=path.stat().st_size,
                      quality=quality, profile='thumbnail' if thumbnail else 'ordinary')
        if not thumbnail and after_size == before_size:
            return {**result, 'reason': 'within-bounds'}
        if target != path and target.exists():
            return {**result, 'reason': 'webp-already-exists'}
        if dry_run:
            return {**result, 'status': 'eligible'}
        if target == path:
            if backup is None:
                raise ValueError('In-place WebP conversion requires an original backup')
            backup = Path(backup)
            if backup.resolve() == path.resolve():
                raise ValueError('Backup must not overwrite source: ' + str(path))
        if thumbnail:
            image = thumbnail_image(image)
        else:
            alpha = image.mode in {'RGBA', 'LA'} or 'transparency' in image.info
            image = image.convert('RGBA' if alpha else 'RGB')
            image = image.resize(after_size, Image.Resampling.LANCZOS)
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.webp', delete=False) as stream:
            temporary = Path(stream.name)
        try:
            image.save(temporary, format='WEBP', quality=quality, method=6,
                       icc_profile=original.info.get('icc_profile', b''))
            with Image.open(temporary) as check:
                check.load()
                if check.format != 'WEBP' or check.size != after_size:
                    raise ValueError('WebP verification failed: ' + str(path))
            if target == path:
                backup.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with backup.open('xb') as output, path.open('rb') as source:
                        shutil.copyfileobj(source, output)
                except FileExistsError:
                    pass
                original.close()
                os.replace(temporary, target)
            else:
                with target.open('xb') as output:
                    output.write(temporary.read_bytes())
            return {**result, 'status': 'converted', 'after': target.stat().st_size,
                    **({'backup': str(backup)} if target == path else {})}
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--backup-dir', type=Path,
                        help='Defaults to a sibling <directory>-image-originals directory')
    args = parser.parse_args()
    directory = project_path(args.directory)
    if not directory.is_dir():
        parser.error('An existing image directory is required')
    backup = project_path(args.backup_dir or directory.with_name(directory.name + '-image-originals'))
    if backup == directory or backup.is_relative_to(directory):
        parser.error('Backup directory must be outside the input directory')
    report = project_path(args.report) if args.report else None
    rows = []
    for current, dirs, names in os.walk(directory, followlinks=False):
        base = Path(current)
        dirs[:] = sorted(name for name in dirs if not is_link(base / name) and name != '_scratchpad')
        for name in sorted(names):
            path = base / name
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                rows.append(convert(path, args.dry_run, backup / path.relative_to(directory)))
    if report and not args.dry_run:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    counts = {}
    for row in rows:
        key = row.get('reason', row['status'])
        counts[key] = counts.get(key, 0) + 1
    print(json.dumps({'counts': counts, 'images': rows}, ensure_ascii=False))


if __name__ == '__main__':
    main()
