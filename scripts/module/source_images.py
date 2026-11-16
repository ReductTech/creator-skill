#!/usr/bin/env python3
"""Inspect original image signatures and PNG dimensions; never decode or convert.

Reads up to 1 KiB per file, reports format counts and header inconsistencies.
Can be called independently or with an already collected pipeline inventory.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from module.source_inputs import source_paths

EXTENSIONS = {'.png': 'png', '.jpg': 'jpeg', '.jpeg': 'jpeg', '.webp': 'webp',
              '.gif': 'gif', '.svg': 'svg', '.avif': 'avif', '.bmp': 'bmp', '.ico': 'ico'}


def image_type(header):
    if header.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
    if header.startswith(b'\xff\xd8\xff'): return 'jpeg'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP': return 'webp'
    if header.startswith((b'GIF87a', b'GIF89a')): return 'gif'
    if header.startswith(b'BM'): return 'bmp'
    if header.startswith(b'\x00\x00\x01\x00'): return 'ico'
    if header[4:8] == b'ftyp' and header[8:12] in (b'avif', b'avis'): return 'avif'
    if b'<svg' in header.lstrip(b'\xef\xbb\xbf \r\n\t'): return 'svg'
    return None


def inspect_images(files):
    """Check original headers; decoding correctness and policy remain server work."""
    counts, issues = Counter(), []
    for name, path in sorted(files.items()):
        expected = EXTENSIONS.get(path.suffix.lower())
        if expected is None:
            continue
        with path.open('rb') as stream:
            header = stream.read(1024)
        detected = image_type(header)
        counts[detected or 'unrecognized'] += 1
        if detected != expected:
            issues.append({'path': name, 'expected': expected, 'detected': detected})
        if detected == 'png' and (len(header) < 33 or header[12:16] != b'IHDR'
                or not all(struct.unpack('>II', header[16:24]))):
            issues.append({'path': name, 'message': 'Invalid PNG IHDR/dimensions'})
    return {'status': 'warning' if issues else 'passed', 'counts': dict(counts),
            'issueCount': len(issues), 'issues': issues, 'converted': 0,
            'coverage': 'File signatures and PNG dimensions only; no image decoding or recompression'}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Directory to inspect; Shared and development artifacts excluded')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        root = args.directory.expanduser().absolute()
        result = inspect_images(source_paths(root, [root]))
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['status'] == 'passed' else 1
    except (ValueError, OSError) as error:
        print(json.dumps({'status': 'error', 'error': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
