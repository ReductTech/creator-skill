"""Verify audio conversion using real FFmpeg/ffprobe, isolated from course assets."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from media import prepare_audio as tool


@pytest.fixture
def binaries():
    ffmpeg = os.environ.get('CREATOR_TEST_FFMPEG') or shutil.which('ffmpeg')
    ffprobe = os.environ.get('CREATOR_TEST_FFPROBE') or shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        pytest.skip('Real FFmpeg and ffprobe required')
    return ffmpeg, ffprobe


def make_audio(binaries, path, channels=1, sample_rate=44100):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([binaries[0], '-v', 'error', '-f', 'lavfi', '-i',
                    f'sine=frequency=440:sample_rate={sample_rate}', '-t', '1.2',
                    '-ac', str(channels), str(path)], check=True)
    return path


def options(binaries, path, *extra):
    return tool.build_parser().parse_args([str(path), '--ffmpeg', binaries[0], '--ffprobe', binaries[1], *extra])


@pytest.mark.parametrize('suffix,channels,source_rate,target_rate', [
    ('.wav', 1, 44100, 44100), ('.flac', 2, 96000, 48000),
    ('.mp3', 1, 22050, 22050), ('.opus', 2, 48000, 48000),
])
def test_conversion_preserves_audio_contract(tmp_path, binaries, suffix, channels, source_rate, target_rate):
    source = make_audio(binaries, tmp_path / '中文 目录' / ('讲解' + suffix), channels, source_rate)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    result = tool.run_task(options(binaries, source, '--apply'))
    assert result['status'] == 'ok', result
    item = result['items'][0]
    assert item['output_exists'] and item['temporary_output']
    assert item['source_relative'] == source.name
    assert item['reference_status'] == 'pending-promotion-and-reference-check'
    output = Path(item['output'])
    document = tool.probe(binaries[1], output)
    stream = tool.audio_stream(document)
    assert stream['codec_name'] == 'aac' and stream['profile'] == 'LC'
    assert stream['channels'] == channels
    assert int(stream['sample_rate']) == target_rate
    assert abs(tool.duration(document) - 1.2) < 0.15
    before = output.read_bytes()
    repeated = tool.run_task(options(binaries, source, '--apply'))
    assert repeated['status'] == 'error' and output.read_bytes() == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert not list(output.parent.glob('.audio-*'))


def test_dry_run_launcher_without_target_config_writes_nothing(tmp_path, binaries):
    source = make_audio(binaries, tmp_path / 'source.wav')
    launcher = Path(__file__).resolve().parents[1] / 'tools.py'
    result = subprocess.run([sys.executable, str(launcher), 'course.audio', source.name,
                             '--ffprobe', binaries[1]], cwd=tmp_path, capture_output=True,
                            text=True, env={**os.environ, 'CREATOR_SKILL_TARGET_CONFIG': str(tmp_path / 'missing.json')})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'dry-run'
    assert [p.name for p in tmp_path.iterdir()] == ['source.wav']


def test_corrupt_batch_and_shared_protection(tmp_path, binaries):
    make_audio(binaries, tmp_path / 'good.wav')
    (tmp_path / 'bad.mp3').write_bytes(b'broken audio')
    (tmp_path / 'Shared').mkdir()
    (tmp_path / 'Shared' / 'keep.wav').write_bytes(b'read only')
    result = tool.run_task(options(binaries, tmp_path, '--apply'))
    assert result['status'] == 'error'
    assert len(result['items']) == 2
    assert {i['status'] for i in result['items']} == {'error', 'created'}
    assert (tmp_path / 'bad.mp3').read_bytes() == b'broken audio'
    assert not list(tmp_path.rglob('.audio-*'))
    with pytest.raises(ValueError, match='Shared'):
        tool.run_task(options(binaries, tmp_path / 'Shared', '--apply'))


def test_surround_downmix_and_custom_bitrate(tmp_path, binaries):
    source = make_audio(binaries, tmp_path / 'surround.wav', 6, 48000)
    result = tool.run_task(options(binaries, source, '--apply', '--bitrate', '128'))
    assert result['status'] == 'ok', result
    item = result['items'][0]
    assert item['channels'] == 2 and item['bitrate_kbps'] == 128
    assert 'warning_channels' in item


def test_failed_verification_never_publishes(tmp_path, binaries, monkeypatch):
    source = make_audio(binaries, tmp_path / 'source.wav')
    real_probe = tool.probe
    def bad_output(executable, path):
        result = real_probe(executable, path)
        if path.name == 'output.m4a':
            result['streams'][0]['duration'] = '999'
        return result
    monkeypatch.setattr(tool, 'probe', bad_output)
    result = tool.run_task(options(binaries, source, '--apply'))
    assert result['status'] == 'error'
    assert not Path(result['items'][0]['output']).exists()
    assert not list(tmp_path.rglob('.audio-*'))


def test_video_is_not_silently_stripped():
    with pytest.raises(ValueError, match='video'):
        tool.settings({'streams': [{'codec_type': 'video'}, {'codec_type': 'audio', 'channels': 2, 'sample_rate': '48000'}]})


def test_output_boundaries(tmp_path, binaries):
    source = make_audio(binaries, tmp_path / 'input' / 'a.wav')
    for output in [source.parent, tmp_path / 'Shared' / 'output']:
        with pytest.raises(ValueError):
            tool.run_task(options(binaries, source, '--apply', '--output', str(output)))
    assert not (tmp_path / 'Shared').exists()


@pytest.mark.parametrize('kind', ['audio', 'video'])
def test_nested_same_names_and_relative_output_paths(tmp_path, binaries, monkeypatch, kind):
    """Returned paths must identify each real file, even with Chinese and basename collisions."""
    from media import prepare_videos
    selected = tool if kind == 'audio' else prepare_videos
    root = tmp_path / '输入 素材'
    names = ['章节一/演示.wav', '章节二/演示.wav', '章节一/演示.flac'] if kind == 'audio' else [
        '章节一/演示.mov', '章节二/演示.mov', '章节一/演示.mp4']
    originals = {}
    for name in names:
        path = root / name
        if kind == 'audio':
            make_audio(binaries, path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([binaries[0], '-v', 'error', '-f', 'lavfi', '-i',
                            'testsrc2=size=160x90:rate=24', '-t', '0.3', '-c:v',
                            'libx264', '-preset', 'ultrafast', str(path)], check=True)
        originals[path] = path.read_bytes()
    monkeypatch.chdir(tmp_path)
    args = selected.build_parser().parse_args([
        root.name, '--output', '输出 成品', '--apply',
        '--ffmpeg', binaries[0], '--ffprobe', binaries[1]])
    result = selected.run_task(args)
    assert result['status'] == 'ok', result
    outputs = set()
    for item in result['items']:
        target = Path(item['output'])
        assert target.is_absolute() and target.is_file()
        assert item['output_exists'] and not item['temporary_output']
        assert item['source_relative'] in names
        assert target == tmp_path / '输出 成品' / item['output_relative']
        assert target.parent.name == Path(item['source_relative']).parent.name
        assert '\\' not in item['output_relative']
        outputs.add(target)
    assert len(outputs) == len(names)
    assert all(path.read_bytes() == content for path, content in originals.items())


def test_output_mapping_rejects_missing_file_and_escape(tmp_path):
    from media.prepare_videos import output_paths
    root, output = tmp_path / 'input', tmp_path / 'output'
    root.mkdir()
    source = root / 'source.wav'
    source.write_bytes(b'input')
    with pytest.raises(ValueError, match='missing or empty'):
        output_paths(source, output / 'missing.m4a', root, output, created=True)
    with pytest.raises(ValueError, match='leaves'):
        output_paths(source, tmp_path / 'escaped.m4a', root, output, created=False)
