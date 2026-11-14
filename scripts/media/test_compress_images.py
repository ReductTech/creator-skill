import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('compress_images', Path(__file__).with_name('compress-images.py'))
compress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compress)


@pytest.mark.parametrize('size,expected', [
    ((2500, 1000), (900, 360)), ((1000, 2500), (360, 900)),
    ((1600, 900), (900, 506)), ((900, 900), (900, 900)),
    ((640, 480), (640, 480)), ((2000, 1), (900, 1)),
])
def test_long_edge_limit_preserves_aspect_ratio(size, expected):
    assert compress.fit_size(*size) == expected


@pytest.mark.parametrize('suffix', ['png', 'jpg', 'webp'])
@pytest.mark.parametrize('size', [(800, 600), (900, 400), (400, 900)])
def test_small_and_boundary_images_are_byte_identical(tmp_path, suffix, size):
    source = tmp_path / ('small.' + suffix)
    Image.new('RGB', size, 'red').save(source)
    original = source.read_bytes()
    assert compress.convert(source)['reason'] == 'within-bounds'
    assert source.read_bytes() == original
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize('suffix', ['png', 'jpg', 'jpeg'])
def test_large_images_become_webp_q80_and_retain_source(tmp_path, suffix):
    source = tmp_path / ('photo.' + suffix)
    Image.effect_noise((1600, 900), 64).convert('RGB').save(source)
    original = source.read_bytes()
    result = compress.convert(source)
    assert result['status'] == 'converted' and result['quality'] == 80
    with Image.open(source.with_suffix('.webp')) as image:
        assert image.format == 'WEBP' and image.size == (900, 506)
    assert source.read_bytes() == original
    assert compress.convert(source)['reason'] == 'webp-already-exists'


def test_transparent_png_keeps_alpha(tmp_path):
    source = tmp_path / 'alpha.png'
    Image.new('RGBA', (1000, 500), (255, 0, 0, 128)).save(source)
    assert compress.convert(source)['status'] == 'converted'
    with Image.open(source.with_suffix('.webp')) as image:
        assert image.size == (900, 450)
        assert image.getchannel('A').getextrema() == (128, 128)


def test_palette_transparency_is_preserved(tmp_path):
    source = tmp_path / 'palette.png'
    Image.new('P', (1000, 500)).save(source, transparency=0)
    assert compress.convert(source)['status'] == 'converted'
    with Image.open(source.with_suffix('.webp')) as image:
        assert image.getchannel('A').getextrema() == (0, 0)


def test_existing_large_webp_is_backed_up_once(tmp_path):
    source, backup = tmp_path / 'large.webp', tmp_path / 'backup/large.webp'
    Image.new('RGB', (1200, 1800), 'red').save(source)
    original = source.read_bytes()
    assert compress.convert(source, backup=backup)['status'] == 'converted'
    assert backup.read_bytes() == original
    with Image.open(source) as image:
        assert image.format == 'WEBP' and image.size == (600, 900)
    once = source.read_bytes()
    assert compress.convert(source, backup=backup)['reason'] == 'within-bounds'
    assert backup.read_bytes() == original and source.read_bytes() == once


def test_dry_run_does_not_write_and_reports_dimensions(tmp_path):
    source = tmp_path / 'photo.png'
    Image.new('RGB', (1000, 2000), 'red').save(source)
    original = source.read_bytes()
    result = compress.convert(source, dry_run=True)
    assert result['status'] == 'eligible' and result['after_size'] == [450, 900]
    assert list(tmp_path.iterdir()) == [source] and source.read_bytes() == original


@pytest.mark.parametrize('folder', ['scenedeck-thumbnails', 'course-thumbnails', 'course-covers'])
def test_thumbnail_and_cover_profiles_override_ordinary_limit(tmp_path, folder):
    directory = tmp_path / folder
    directory.mkdir()
    source = directory / 'page.png'
    Image.new('RGB', (320, 180), 'navy').save(source)
    result = compress.convert(source)
    assert result['quality'] == 20 and result['status'] == 'converted'
    with Image.open(source.with_suffix('.webp')) as image:
        assert image.format == 'WEBP' and image.size == (1600, 900)


@pytest.mark.parametrize('suffix', ['png', 'webp'])
def test_animation_is_untouched(tmp_path, suffix):
    source = tmp_path / ('animation.' + suffix)
    Image.new('RGB', (1000, 500), 'red').save(source, save_all=True,
        append_images=[Image.new('RGB', (1000, 500), 'blue')], duration=100, loop=0)
    original = source.read_bytes()
    assert compress.convert(source)['reason'] == 'animated'
    assert source.read_bytes() == original


def test_high_bit_depth_png_is_untouched(tmp_path):
    source = tmp_path / 'scientific.png'
    Image.new('I;16', (1000, 500), 30000).save(source)
    original = source.read_bytes()
    assert compress.convert(source)['reason'] == 'unsupported-bit-depth-or-mode'
    assert source.read_bytes() == original


def test_exif_orientation_is_applied_before_fitting(tmp_path):
    source = tmp_path / 'rotated.jpg'
    exif = Image.Exif()
    exif[274] = 6
    Image.new('RGB', (2500, 1000), 'red').save(source, exif=exif)
    result = compress.convert(source)
    assert result['before_size'] == [1000, 2500]
    with Image.open(source.with_suffix('.webp')) as image:
        assert image.size == (360, 900) and image.getexif().get(274, 1) == 1


def test_cli_dry_run_writes_neither_report_nor_images(tmp_path):
    directory = tmp_path / 'assets'
    directory.mkdir()
    source = directory / 'large.png'
    Image.new('RGB', (1000, 500), 'red').save(source)
    config = tmp_path / 'target-root.json'
    config.write_text(json.dumps({'targetRoot': str(tmp_path)}))
    result = subprocess.run([sys.executable, str(SCRIPTS / 'tools.py'), 'assets.compress',
        'assets', '--dry-run', '--report', 'report.json'], capture_output=True, text=True,
        env={**os.environ, 'CREATOR_SKILL_TARGET_CONFIG': str(config)}, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['images'][0]['after_size'] == [900, 450]
    assert list(directory.iterdir()) == [source]
    assert not (tmp_path / 'report.json').exists()
