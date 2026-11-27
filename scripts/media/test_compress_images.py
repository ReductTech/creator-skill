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


def test_delivery_preserves_svg_without_creating_webp(tmp_path):
    source = tmp_path / 'diagram.svg'
    raw = b'<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="1600"/>'
    source.write_bytes(raw)
    result = compress.convert(source, delivery=True)
    assert result['status'] == 'preserved'
    assert source.read_bytes() == raw
    assert not source.with_suffix('.webp').exists()


@pytest.mark.parametrize('size,expected', [
    ((2500, 1000), (1600, 640)), ((1000, 2500), (360, 900)),
    ((2000, 1000), (1600, 800)), ((1000, 2000), (450, 900)),
    ((2000, 1500), (1200, 900)), ((1500, 2000), (675, 900)),
    ((1200, 1200), (900, 900)), ((1600, 1000), (1440, 900)),
    ((1601, 900), (1600, 899)), ((900, 1601), (506, 900)),
    ((1600, 901), (1598, 900)), ((901, 1600), (507, 900)),
    ((1600, 900), (1600, 900)), ((900, 900), (900, 900)),
    ((640, 480), (640, 480)), ((2000, 1), (1600, 1)),
])
def test_fixed_width_and_height_limits_preserve_aspect_ratio(size, expected):
    assert compress.fit_size(*size) == expected


@pytest.mark.parametrize('suffix', ['png','jpg','jpeg','bmp','tiff','gif','ico'])
@pytest.mark.parametrize('size', [(64,64),(2000,1000)])
def test_all_sizes_convert_and_remove_original(tmp_path, suffix, size):
    source=tmp_path/('image.'+suffix)
    Image.new('RGB',size,'red').save(source)
    result=compress.convert(source)
    assert result['status']=='converted'
    assert not source.exists()
    with Image.open(source.with_suffix('.webp')) as image:
        assert image.format=='WEBP'

def test_valid_webp_retained(tmp_path):
    source=tmp_path/'image.webp'
    Image.new('RGB',(40,40),'blue').save(source)
    raw=source.read_bytes()
    assert compress.convert(source)['status']=='preserved'
    assert source.read_bytes()==raw

def test_animation_is_converted_with_frames(tmp_path):
    source=tmp_path/'animation.gif'
    frames=[Image.new('RGB',(40,40),c) for c in ['red','blue']]
    frames[0].save(source,save_all=True,append_images=frames[1:],duration=[100,200],loop=2)
    compress.convert(source)
    assert not source.exists()
    with Image.open(source.with_suffix('.webp')) as image:
        assert image.n_frames==2 and image.info['loop']==2

def test_collision_blocks_without_removing_original(tmp_path):
    source=tmp_path/'image.png'; target=source.with_suffix('.webp')
    Image.new('RGB',(40,40),'red').save(source)
    Image.new('RGB',(40,40),'blue').save(target)
    raw=target.read_bytes()
    with pytest.raises(ValueError):compress.convert(source)
    assert source.exists() and target.read_bytes()==raw

def test_high_bit_depth_fails_explicitly(tmp_path):
    source=tmp_path/'depth.png'
    Image.new('I;16',(40,40),30000).save(source)
    with pytest.raises(ValueError):compress.convert(source)
    assert source.exists()


def test_cli_updates_source_references_in_place(tmp_path):
    assets=tmp_path/'assets';assets.mkdir()
    Image.new('RGBA',(64,64),(255,0,0,128)).save(assets/'a.png')
    code=tmp_path/'page.tsx'
    code.write_text('const url="assets/a.png";',encoding='utf-8')
    result=subprocess.run([sys.executable,str(SCRIPTS/'media/compress-images.py'),str(tmp_path)],
                          capture_output=True,text=True,encoding='utf-8',
                          env={**os.environ,'CREATOR_SKILL_PROJECT_ROOT':str(tmp_path)})
    assert result.returncode==0,result.stdout+result.stderr
    assert code.read_text()=='const url="assets/a.webp";'
    assert not (assets/'a.png').exists()
    assert sorted(p.name for p in tmp_path.iterdir())==['assets','page.tsx']
    with Image.open(assets/'a.webp') as image:
        assert image.getchannel('A').getextrema()==(128,128)


def test_thumbnail_profile_and_transparency(tmp_path):
    folder=tmp_path/'course-thumbnails';folder.mkdir()
    source=folder/'page.png'
    Image.new('RGBA',(320,180),(255,0,0,128)).save(source)
    compress.convert(source)
    assert not source.exists()
    with Image.open(source.with_suffix('.webp')) as image:
        assert image.size==(1600,900)

def test_exif_orientation_before_resize(tmp_path):
    source=tmp_path/'photo.jpg'
    exif=Image.Exif();exif[274]=6
    Image.new('RGB',(2500,1000),'red').save(source,exif=exif)
    compress.convert(source)
    with Image.open(source.with_suffix('.webp')) as image:
        assert image.size==(360,900)
