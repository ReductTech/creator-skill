"""Real local transcoding checks; no server, browser or course assets are modified."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from media import prepare_videos as tool


@pytest.fixture
def binaries():
    ffmpeg = os.environ.get('CREATOR_TEST_FFMPEG') or shutil.which('ffmpeg')
    ffprobe = os.environ.get('CREATOR_TEST_FFPROBE') or shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        pytest.skip('Real FFmpeg and ffprobe required')
    return ffmpeg, ffprobe


def make_video(binaries, path, size='1920x1080', fps=60, audio=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [binaries[0], '-v', 'error', '-f', 'lavfi', '-i', f'testsrc2=size={size}:rate={fps}']
    if audio:
        command += ['-f', 'lavfi', '-i', 'sine=frequency=440']
    command += ['-t', '0.6', '-c:v', 'libx264', '-preset', 'ultrafast']
    if audio:
        command += ['-c:a', 'aac']
    subprocess.run([*command, str(path)], check=True)
    return path


def options(binaries, source, *extra):
    return tool.build_parser().parse_args([str(source), '--ffmpeg', binaries[0], '--ffprobe', binaries[1], *extra])


@pytest.mark.parametrize('size,fps,audio,expected', [
    ('1920x1080', 60, True, (1280, 720, 30)),
    ('640x360', 24, False, (640, 360, 24)),
    ('720x1280', 30, True, (404, 720, 30)),
])
def test_real_conversion_and_exclusive_output(tmp_path, binaries, size, fps, audio, expected):
    source = make_video(binaries, tmp_path / '中文 路径' / '演示.mov', size, fps, audio)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    result = tool.run_task(options(binaries, source, '--apply'))
    assert result['status'] == 'ok', result
    item = result['items'][0]
    output = Path(item['output'])
    document = tool.probe(binaries[1], output)
    stream = tool.video_stream(document)
    assert (stream['width'], stream['height'], tool.rate(stream['avg_frame_rate'])) == expected
    assert any(s['codec_type'] == 'audio' for s in document['streams']) == audio
    assert stream['codec_name'] == 'h264' and stream['pix_fmt'] == 'yuv420p'
    before = output.read_bytes()
    repeated = tool.run_task(options(binaries, source, '--apply'))
    assert repeated['status'] == 'error'
    assert output.read_bytes() == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert not list(output.parent.glob('.video-*'))


def test_inspection_does_not_write_and_launcher_needs_no_config(tmp_path, binaries):
    source = make_video(binaries, tmp_path / 'source.mp4', '320x180', 24, False)
    env = {**os.environ, 'CREATOR_SKILL_TARGET_CONFIG': str(tmp_path / 'absent.json')}
    launcher = Path(__file__).resolve().parents[1] / 'tools.py'
    result = subprocess.run([sys.executable, str(launcher), 'course.videos',
                             source.name, '--ffprobe', binaries[1]],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'dry-run'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['source.mp4']


def test_mixed_batch_rejects_corruption_and_excludes_shared(tmp_path, binaries):
    make_video(binaries, tmp_path / 'good.mov', '320x180', 24, False)
    (tmp_path / 'bad.mp4').write_bytes(b'not a video')
    (tmp_path / 'Shared').mkdir()
    (tmp_path / 'Shared' / 'untouched.mp4').write_bytes(b'read only')
    result = tool.run_task(options(binaries, tmp_path, '--apply'))
    assert result['status'] == 'error'
    assert len(result['items']) == 2
    assert {i['status'] for i in result['items']} == {'error', 'created'}
    assert (tmp_path / 'bad.mp4').read_bytes() == b'not a video'
    assert not list(tmp_path.rglob('.video-*'))


def test_rotation_uses_display_dimensions(tmp_path, binaries):
    base = make_video(binaries, tmp_path / 'base.mp4', '640x360', 24, False)
    source = tmp_path / 'rotated.mp4'
    subprocess.run([binaries[0], '-v', 'error', '-display_rotation:v:0', '90',
                    '-i', str(base), '-c', 'copy', str(source)], check=True)
    result = tool.run_task(options(binaries, source, '--apply'))
    assert result['status'] == 'ok', result
    document = tool.probe(binaries[1], Path(result['items'][0]['output']))
    assert tool.dimensions(tool.video_stream(document)) == (360, 640)


def test_hdr_and_alpha_are_not_silently_flattened():
    for metadata in [{'color_transfer': 'smpte2084'}, {'pix_fmt': 'yuva420p'}]:
        with pytest.raises(ValueError):
            tool.dimensions({'width': 1280, 'height': 720, **metadata})


def test_invalid_paths_fail_without_writing(tmp_path, binaries):
    source = make_video(binaries, tmp_path / 'input' / 'a.mp4', '320x180', 24, False)
    for output in [source.parent, tmp_path / 'Shared' / 'output']:
        with pytest.raises(ValueError):
            tool.run_task(options(binaries, source, '--apply', '--output', str(output)))
    assert not (tmp_path / 'Shared').exists()


def test_symlink_output_is_rejected(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    link = tmp_path / 'linked'
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Symlink privilege unavailable')
    with pytest.raises(ValueError, match='Linked paths'):
        tool.safe_path(link / 'output')
    assert list(outside.iterdir()) == []
