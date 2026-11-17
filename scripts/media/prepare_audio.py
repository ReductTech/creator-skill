#!/usr/bin/env python3
"""Prepare local course audio as M4A/AAC-LC (default 96 kbps).

Reads explicit file/folder paths relative to cwd, without target-root.json.
Default only inspects; --apply writes to --output or <input folder>/_scratchpad/audio-aac.
Originals, existing outputs and course references are never overwritten.
Requires FFmpeg and ffprobe; does not install or download dependencies.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from _common import emit_result, report_error
from media.prepare_videos import safe_path, execute, probe, discover, video_stream, output_paths

EXTENSIONS = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.oga', '.opus',
              '.aiff', '.aif', '.wma', '.mka', '.amr', '.ac3', '.aifc'}
SAMPLE_RATES = (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Audio file or recursive folder; paths relative to cwd')
    parser.add_argument('--output', type=Path, help='Output folder; default <input folder>/_scratchpad/audio-aac')
    parser.add_argument('--apply', action='store_true', help='Encode and verify; default is read-only inspection')
    parser.add_argument('--bitrate', type=int, choices=[64, 96, 128, 160, 192], default=96, help='AAC kbps, default 96; music may use 128/160')
    parser.add_argument('--ffmpeg', default='ffmpeg', help='Executable name or path')
    parser.add_argument('--ffprobe', default='ffprobe', help='Executable name or path')
    return parser


def audio_stream(document: dict) -> dict:
    stream = next((s for s in document['streams'] if s.get('codec_type') == 'audio'), None)
    if not stream:
        raise ValueError('No audio stream found')
    return stream


def duration(document: dict) -> float:
    return float(audio_stream(document).get('duration') or document.get('format', {}).get('duration') or 0)


def settings(document: dict) -> tuple[int, int]:
    """Keep mono/stereo and avoid increasing the sample rate; explicitly downmix surround."""
    if video_stream(document):
        raise ValueError('Input contains video; use course.videos instead of silently dropping the picture')
    stream = audio_stream(document)
    channels = int(stream.get('channels') or 0)
    sample_rate = int(stream.get('sample_rate') or 0)
    if channels < 1 or sample_rate < min(SAMPLE_RATES):
        raise ValueError('Unsupported channel count or sample rate')
    return min(channels, 2), max(r for r in SAMPLE_RATES if r <= sample_rate)


def encode(ffmpeg: str, ffprobe: str, source: Path, target: Path,
           original: dict, channels: int, sample_rate: int, bitrate: int) -> dict:
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_path(target.parent)
    with tempfile.TemporaryDirectory(prefix='.audio-', dir=target.parent) as folder:
        partial = Path(folder) / 'output.m4a'
        execute([ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
                 '-xerror', '-err_detect', 'explode', '-i', str(source),
                 '-map', '0:a:0', '-vn', '-sn', '-dn', '-c:a', 'aac',
                 '-profile:a', 'aac_low', '-b:a', f'{bitrate}k', '-ac', str(channels),
                 '-ar', str(sample_rate), '-threads', '2', '-map_metadata', '-1',
                 '-map_chapters', '-1', '-movflags', '+faststart', str(partial)])
        result = probe(ffprobe, partial)
        stream = audio_stream(result)
        if (len(result['streams']) != 1 or stream.get('codec_name') != 'aac'
                or stream.get('profile') != 'LC' or stream.get('channels') != channels
                or int(stream.get('sample_rate', 0)) != sample_rate):
            raise ValueError('Output does not meet the AAC-LC/channel/sample-rate contract')
        before, after = duration(original), duration(result)
        if after <= 0 or (before > 0 and abs(after - before) > max(0.25, before * 0.01)):
            raise ValueError('Encoded duration is missing or changed unexpectedly')
        execute([ffmpeg, '-v', 'error', '-nostdin', '-xerror', '-err_detect', 'explode',
                 '-i', str(partial), '-map', '0:a:0', '-f', 'null', '-'])
        os.link(partial, target)
    return result


def run_task(args: argparse.Namespace) -> dict:
    source = safe_path(args.input)
    if not source.exists():
        raise ValueError(f'Input does not exist: {source}')
    root = source if source.is_dir() else source.parent
    output = safe_path(args.output or root / '_scratchpad' / 'audio-aac')
    if any(p.lower() == 'shared' for p in (*root.parts, *output.parts)):
        raise ValueError('Shared is read-only; select course-specific assets')
    if output == root or root.is_relative_to(output):
        raise ValueError('Output must not equal or contain the input folder')
    if output.exists() and not output.is_dir():
        raise ValueError('Output must be a directory')
    files, skipped = discover(source, output, EXTENSIONS)
    if not files:
        raise ValueError('No matching audio files found')
    ffprobe, ffmpeg = shutil.which(args.ffprobe), shutil.which(args.ffmpeg)
    if not ffprobe or (args.apply and not ffmpeg):
        raise RuntimeError('Install FFmpeg and ffprobe or supply executable paths; nothing was written')
    items = []
    for index, path in enumerate(files, 1):
        relative = path.relative_to(root)
        target = output / relative.parent / (relative.name + '.compressed.m4a')
        item = {'source': str(path), 'output': str(target), 'bitrate_kbps': args.bitrate}
        print(f'[{index}/{len(files)}] {relative}', file=sys.stderr, flush=True)
        try:
            safe_path(path)
            safe_path(target)
            if os.path.lexists(target):
                raise ValueError('Output already exists; choose a new --output. Existing files are never overwritten')
            document = probe(ffprobe, path)
            channels, sample_rate = settings(document)
            item.update(channels=channels, sample_rate=sample_rate, source_bytes=path.stat().st_size)
            if args.apply:
                result = encode(ffmpeg, ffprobe, path, target, document, channels, sample_rate, args.bitrate)
                item.update(status='created', output_bytes=target.stat().st_size, duration_seconds=duration(result))
                if item['output_bytes'] >= item['source_bytes']:
                    item['warning_size'] = 'Output is not smaller; compare with the original before promoting'
            else:
                item['status'] = 'would-create'
            item.update(output_paths(path, target, root, output, created=args.apply))
            if audio_stream(document)['channels'] > 2:
                item['warning_channels'] = 'Surround audio is downmixed to stereo; review the result'
            if sum(s.get('codec_type') == 'audio' for s in document['streams']) > 1:
                item['warning_tracks'] = 'Only the first audio track is retained'
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            item.update(status='error', error=str(exc))
        items.append(item)
    return {'status': 'error' if any(i['status'] == 'error' for i in items) else 'ok' if args.apply else 'dry-run',
            'items': items, 'skipped_directories_or_links': skipped, 'references_changed': False,
            'note': 'Listen before promoting selected files to course assets and updating literal references. Packing never runs this tool.'}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_task(args)
        emit_result(result)
        return 2 if result['status'] == 'error' else 0
    except (OSError, ValueError, RuntimeError) as exc:
        return report_error(exc)
    except KeyboardInterrupt:
        return report_error(RuntimeError('Cancelled; original audio files are unchanged'))


if __name__ == '__main__':
    raise SystemExit(main())
