#!/usr/bin/env python3
"""Prepare local SDR course videos as MP4/H.264, <=1280x720 and <=30 fps.

Reads explicit paths relative to cwd; no target-root.json is required.
Default is read-only inspection. --apply writes new files to --output or
<input folder>/_scratchpad/video-720p. Originals and references are never changed.
Requires FFmpeg with libx264 and ffprobe. No automatic installation or download.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from _common import emit_result, report_error

EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v', '.mpeg',
              '.mpg', '.mts', '.m2ts', '.wmv', '.flv', '.3gp', '.ts'}
EXCLUDED = {'shared', '.git', 'node_modules', '_scratchpad'}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Video file or recursive folder, relative to cwd')
    parser.add_argument('--output', type=Path, help='New output folder; default <input folder>/_scratchpad/video-720p')
    parser.add_argument('--apply', action='store_true', help='Encode and verify; default only inspects inputs')
    parser.add_argument('--crf', type=int, choices=range(18, 31), default=24, metavar='18..30', help='Higher is smaller; default 24')
    parser.add_argument('--ffmpeg', default='ffmpeg', help='Executable name or path (libx264 required)')
    parser.add_argument('--ffprobe', default='ffprobe', help='Executable name or path')
    return parser


def linked(path: Path) -> bool:
    """Include Windows junction/reparse points, not just symbolic links."""
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def safe_path(path: Path) -> Path:
    """Reject existing linked path components before resolving a supplied path."""
    path = Path(os.path.abspath(path.expanduser()))
    for part in [path, *path.parents]:
        if os.path.lexists(part) and linked(part):
            raise ValueError(f'Linked paths/junctions are not supported: {part}')
    return path.resolve()


def output_paths(source: Path, target: Path, root: Path, output: Path,
                 *, created: bool) -> dict:
    """Confirm the concrete mapping and distinguish temporary files from course references."""
    source, target = safe_path(source), safe_path(target)
    root, output = safe_path(root), safe_path(output)
    if not source.is_relative_to(root) or not target.is_relative_to(output) or target == source:
        raise ValueError('Media output mapping leaves its selected roots or aliases the source')
    exists = target.is_file()
    if created and (not exists or target.stat().st_size == 0):
        raise ValueError(f'Converted output is missing or empty: {target}')
    return {'source_relative': source.relative_to(root).as_posix(),
            'output_relative': target.relative_to(output).as_posix(),
            'output_exists': exists,
            'temporary_output': any(p.lower() == '_scratchpad' for p in target.parts),
            'reference_status': 'pending-promotion-and-reference-check'}


def execute(command: list[str], *, capture: bool = False) -> str:
    """Keep encoder diagnostics on disk, returning a bounded tail on failure."""
    with tempfile.TemporaryFile() as diagnostics:
        result = subprocess.run(command, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                                stderr=diagnostics)
        if result.returncode:
            diagnostics.seek(0, os.SEEK_END)
            diagnostics.seek(max(0, diagnostics.tell() - 8000))
            raise RuntimeError(diagnostics.read().decode('utf-8', errors='replace'))
        return result.stdout.decode('utf-8') if capture else ''


def probe(executable: str, path: Path) -> dict:
    return json.loads(execute([executable, '-v', 'error', '-show_streams',
                              '-show_format', '-of', 'json', str(path)], capture=True))


def rate(value: str | None) -> float:
    try:
        return float(Fraction(value or '0'))
    except (ValueError, ZeroDivisionError):
        return 0


def video_stream(document: dict) -> dict:
    return next((s for s in document['streams'] if s.get('codec_type') == 'video'
                 and not s.get('disposition', {}).get('attached_pic')), {})


def dimensions(stream: dict) -> tuple[int, int]:
    """Fit display geometry, including SAR and phone rotation, without stretching."""
    width, height = stream.get('width', 0), stream.get('height', 0)
    if width < 2 or height < 2:
        raise ValueError('No usable video dimensions')
    if stream.get('color_transfer') in {'smpte2084', 'arib-std-b67'}:
        raise ValueError('HDR requires separate tone mapping; this tool only handles SDR')
    pixel_format = stream.get('pix_fmt', '')
    if pixel_format.startswith(('yuva', 'gbrap')) or pixel_format in {'rgba', 'bgra', 'argb', 'abgr'} or str(stream.get('tags', {}).get('alpha_mode', '0')) == '1':
        raise ValueError('Transparent video cannot retain alpha in H.264; handle separately')
    sar = rate(str(stream.get('sample_aspect_ratio', '1:1')).replace(':', '/')) or 1
    width = width * sar
    rotation = float(stream.get('tags', {}).get('rotate', 0))
    for side in stream.get('side_data_list', []):
        if 'rotation' in side:
            rotation = float(side['rotation'])
    if not math.isclose(rotation / 90, round(rotation / 90), abs_tol=0.001):
        raise ValueError('Non-right-angle rotation requires separate handling')
    if round(rotation / 90) % 2:
        width, height = height, width
    ratio = min(1, 1280 / width, 720 / height)
    return max(2, int(width * ratio) // 2 * 2), max(2, int(height * ratio) // 2 * 2)


def duration(document: dict) -> float:
    return float(video_stream(document).get('duration') or document.get('format', {}).get('duration') or 0)


def verify(document: dict, original: dict, expected: tuple[int, int]) -> None:
    """Validate the actual output contract, including duration and audio preservation."""
    stream = video_stream(document)
    fps = rate(stream.get('r_frame_rate'))
    if (stream.get('codec_name') != 'h264' or stream.get('pix_fmt') != 'yuv420p'
            or (stream.get('width'), stream.get('height')) != expected
            or fps <= 0 or fps > 30.001 or rate(stream.get('avg_frame_rate')) > 30.001):
        raise ValueError('Encoded video does not meet H.264 / dimensions / 30fps contract')
    audio = [s for s in document['streams'] if s.get('codec_type') == 'audio']
    had_audio = any(s.get('codec_type') == 'audio' for s in original['streams'])
    if len(audio) != int(had_audio) or any(s.get('codec_name') != 'aac' or s.get('channels') != 2 for s in audio):
        raise ValueError('Encoded audio does not meet AAC stereo contract')
    before, after = duration(original), duration(document)
    if after <= 0 or (before > 0 and abs(after - before) > max(0.25, before * 0.01)):
        raise ValueError('Encoded duration is missing or changed unexpectedly')


def encode(ffmpeg: str, ffprobe: str, source: Path, target: Path,
           original: dict, size: tuple[int, int], crf: int) -> dict:
    """Validate a temporary result before publishing it with exclusive creation."""
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_path(target.parent)
    with tempfile.TemporaryDirectory(prefix='.video-', dir=target.parent) as folder:
        partial = Path(folder) / 'output.mp4'
        execute([ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
                 '-filter_threads', '2', '-xerror', '-err_detect', 'explode',
                 '-i', str(source), '-map', '0:V:0',
                 '-map', '0:a:0?', '-sn', '-dn', '-vf', f'scale={size[0]}:{size[1]},setsar=1',
                 '-fpsmax:v', '30', '-c:v', 'libx264', '-preset', 'slow',
                 '-crf', str(crf), '-threads', '2', '-pix_fmt', 'yuv420p',
                 '-tag:v', 'avc1', '-c:a', 'aac', '-b:a', '96k', '-ac', '2',
                 '-map_metadata', '-1', '-map_chapters', '-1',
                 '-movflags', '+faststart', str(partial)])
        document = probe(ffprobe, partial)
        verify(document, original, size)
        execute([ffmpeg, '-v', 'error', '-nostdin', '-xerror', '-err_detect', 'explode',
                 '-i', str(partial), '-map', '0:v:0', '-map', '0:a:0?', '-f', 'null', '-'])
        # Same-filesystem hard link is atomic and fails if a destination already exists.
        # TemporaryDirectory then removes only the temporary name, retaining the result.
        os.link(partial, target)
    return document


def discover(source: Path, output: Path, extensions: set[str] = EXTENSIONS) -> tuple[list[Path], list[str]]:
    files, skipped = [], []
    if source.is_file():
        if source.suffix.lower() not in extensions:
            raise ValueError(f'Unsupported media extension: {source.suffix}')
        return [source], skipped
    for folder, dirs, names in os.walk(source, followlinks=False):
        parent = Path(folder)
        for name in dirs[:]:
            path = parent / name
            if name.lower() in EXCLUDED or linked(path) or path.resolve() == output:
                dirs.remove(name)
                skipped.append(str(path))
        for name in sorted(names):
            path = parent / name
            if path.suffix.lower() not in extensions:
                continue
            if linked(path):
                skipped.append(str(path))
            else:
                files.append(path)
    return sorted(files), skipped


def run_task(args: argparse.Namespace) -> dict:
    source = safe_path(args.input)
    if not source.exists():
        raise ValueError(f'Input does not exist: {source}')
    root = source if source.is_dir() else source.parent
    if any(p.lower() == 'shared' for p in root.parts):
        raise ValueError('Shared is read-only; select course-specific assets')
    output = safe_path(args.output or root / '_scratchpad' / 'video-720p')
    if output == root or root.is_relative_to(output):
        raise ValueError('Output must not equal or contain the input folder')
    if any(p.lower() == 'shared' for p in output.parts):
        raise ValueError('Output must not be inside Shared')
    if output.exists() and not output.is_dir():
        raise ValueError('Output must be a directory')
    files, skipped = discover(source, output)
    if not files:
        raise ValueError('No matching videos found')
    ffprobe = shutil.which(args.ffprobe)
    ffmpeg = shutil.which(args.ffmpeg)
    if not ffprobe or (args.apply and not ffmpeg):
        raise RuntimeError('Install FFmpeg and ffprobe, or supply --ffmpeg / --ffprobe paths; nothing was written')
    items = []
    for index, path in enumerate(files, 1):
        relative = path.relative_to(root)
        target = output / relative.parent / (relative.name + '.720p.mp4')
        item = {'source': str(path), 'output': str(target)}
        print(f'[{index}/{len(files)}] {relative}', file=sys.stderr, flush=True)
        try:
            safe_path(path)
            safe_path(target)
            if os.path.lexists(target):
                raise ValueError('Output already exists; never overwritten or assumed valid. Choose a new --output')
            document = probe(ffprobe, path)
            stream = video_stream(document)
            size = dimensions(stream)
            item.update(width=size[0], height=size[1], source_bytes=path.stat().st_size)
            if args.apply:
                result = encode(ffmpeg, ffprobe, path, target, document, size, args.crf)
                item.update(status='created', output_bytes=target.stat().st_size,
                            fps=rate(video_stream(result).get('avg_frame_rate')))
                if item['output_bytes'] >= item['source_bytes']:
                    item['warning'] = 'Output is not smaller; compare with the original before promoting'
            else:
                item['status'] = 'would-create'
            item.update(output_paths(path, target, root, output, created=args.apply))
            if len([s for s in document['streams'] if s.get('codec_type') == 'audio']) > 1:
                item['warning_tracks'] = 'Only the first audio track is retained'
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            item.update(status='error', error=str(exc))
        items.append(item)
    return {'status': 'error' if any(i['status'] == 'error' for i in items) else 'ok' if args.apply else 'dry-run',
            'items': items, 'skipped_directories_or_links': skipped,
            'references_changed': False,
            'note': 'Review output visually; promote selected files to course assets and update literal references before packaging. Packing never runs this tool.'}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_task(args)
        emit_result(result)
        return 2 if result['status'] == 'error' else 0
    except (OSError, ValueError, RuntimeError) as exc:
        return report_error(exc)
    except KeyboardInterrupt:
        return report_error(RuntimeError('Cancelled; original files are unchanged'))


if __name__ == '__main__':
    raise SystemExit(main())
