"""End-to-end staged preparation: real media bytes, path migration and agent reports."""
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from PIL import Image
import pytest

from module.package_course import export_source
from module.source_report import agent_summary
from test_delivery import course, snapshot


def image_course(tmp_path, code):
    root = course(tmp_path/'source')
    (root/'assets/images').mkdir(parents=True)
    Image.new('RGBA', (2000, 1000), (255, 0, 0, 100)).save(root/'assets/images/a.png')
    (root/'Guide.tsx').write_text(code, encoding='utf-8')
    return root


def test_real_conversion_updates_literals_data_css_and_bom_without_node(tmp_path):
    root = image_course(tmp_path, '\ufeffconst paths=["images/a.png"];\r\nexport function Guide(){return <img src={moduleAssetUrl("images/a.png?raw#x")}/>;}\r\n')
    (root/'data.json').write_text('{ "image": "images/a.png" }', encoding='utf-8')
    (root/'page.css').write_text('/* keep */ .hero{background:url("./assets/images/a.png#one")}', encoding='utf-8')
    before = snapshot(root)
    execution = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'module/package_course.py'), str(root)],
        env={**os.environ, 'PATH': ''}, capture_output=True, text=True, encoding='utf-8', check=True)
    compact = json.loads(execution.stdout)
    report = json.loads(Path(compact['reportPath']).read_text(encoding='utf-8'))
    assert report['status'] == 'passed', report['issues']
    assert not (root/'assets/images/a.png').exists()
    assert (root/'assets/images/a.webp').is_file()
    assert b'images/a.webp' in (root/'Guide.tsx').read_bytes()
    assert compact['references']['replacements'] == 4
    assert compact['media']['counts']['imageConverted'] == 1
    with zipfile.ZipFile(compact['output']) as archive:
        prefix = 'modules/'+root.name+'/'
        assert prefix+'assets/images/a.png' not in archive.namelist()
        raw = archive.read(prefix+'Guide.tsx')
        assert raw.startswith(b'\xef\xbb\xbf') and b'\r\n' in raw
        assert b'images/a.webp?raw#x' in raw
        assert json.loads(archive.read(prefix+'data.json'))['image']=='images/a.webp'
        assert b'./assets/images/a.webp#one' in archive.read(prefix+'page.css')
        from io import BytesIO
        with Image.open(BytesIO(archive.read(prefix+'assets/images/a.webp'))) as image:
            assert image.size == (1600, 800) and image.mode == 'RGBA'


@pytest.mark.parametrize('code', [
    'const x=moduleAssetUrl(`images/${id}.png`);',
    'const x=moduleAssetUrl("images/"+id+".png");',
    'const x=moduleAssetUrl(data.path);',
    'const x="images/"+id+".png";',
])
def test_uncertain_conversion_blocks_and_points_to_original_source(tmp_path, code):
    root = image_course(tmp_path, code)
    before = snapshot(root)
    report = export_source([root])
    assert report['status'] == 'failed' and not report['outputCreated']
    assert snapshot(root) == before
    problem = next(i for i in report['issues']['serious'] if i['code'].startswith('REFERENCE_'))
    assert problem['path'].endswith('/Guide.tsx') and problem['line']==1
    assert report['media']['conversions'][0]['target'].endswith('/a.webp')
    assert report['agentNextAction']=='repair-and-repack'


def test_collision_is_not_overwritten_or_silently_associated(tmp_path):
    root = image_course(tmp_path, 'const x="images/a.png";')
    Image.new('RGB', (30, 20), 'blue').save(root/'assets/images/a.webp')
    before = snapshot(root)
    result = export_source([root])
    assert result['status']=='failed' and not result['outputCreated']
    assert snapshot(root)==before
    assert any('冲突' in i['message'] for i in result['issues']['serious'])


def test_animation_duration_loop_and_frames_survive(tmp_path):
    root = course(tmp_path/'source')
    (root/'assets').mkdir()
    frames = [Image.new('RGB',(60,40),color) for color in ['red','blue']]
    frames[0].save(root/'assets/animation.gif', save_all=True, append_images=frames[1:], duration=[100,200], loop=2)
    result=export_source([root])
    assert result['status']=='passed',result['issues']
    with zipfile.ZipFile(result['output']) as archive:
        from io import BytesIO
        with Image.open(BytesIO(archive.read('modules/'+root.name+'/assets/animation.webp'))) as image:
            assert image.n_frames==2 and image.info['loop']==2
            durations=[]
            for n in range(2):
                image.seek(n); image.load(); durations.append(image.info['duration'])
            assert durations==[100,200]


def test_missing_ffmpeg_reports_each_media_without_partial_zip(tmp_path, monkeypatch):
    root=course(tmp_path/'source'); (root/'assets').mkdir()
    (root/'assets/clip.mov').write_bytes(b'video')
    (root/'assets/voice.wav').write_bytes(b'audio')
    monkeypatch.setattr('module.source_media.shutil.which',lambda name:None)
    before=snapshot(root); result=export_source([root])
    assert result['status']=='failed' and result['seriousErrorCount']==2
    assert snapshot(root)==before
    assert all('FFmpeg' in i['message'] for i in result['issues']['serious'])


def test_video_audio_share_reference_migration_and_report(tmp_path, monkeypatch):
    # Encoding/validation have independent real-media tests. This checks orchestration,
    # complete mapping and original preservation across two independent converters.
    from module import source_media
    root=course(tmp_path/'source'); (root/'assets').mkdir()
    (root/'assets/clip.mov').write_bytes(b'video original')
    (root/'assets/voice.wav').write_bytes(b'audio original')
    (root/'Guide.tsx').write_text('const a="clip.mov", b="voice.wav";')
    monkeypatch.setattr(source_media.shutil,'which',lambda name:name)
    monkeypatch.setattr(source_media.video,'probe',lambda *a:{'streams':[]})
    monkeypatch.setattr(source_media.video,'dimensions',lambda *a:(1280,720))
    monkeypatch.setattr(source_media.audio,'settings',lambda *a:(1,24000))
    def encode(*args):
        target=args[3]; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(b'encoded')
    monkeypatch.setattr(source_media.video,'encode',encode)
    monkeypatch.setattr(source_media.audio,'encode',encode)
    before=snapshot(root); result=export_source([root])
    assert result['status']=='passed',result['issues']
    assert result['media']['counts']['videoConverted']==result['media']['counts']['audioConverted']==1
    assert snapshot(root)==before
    with zipfile.ZipFile(result['output']) as archive:
        code=archive.read('modules/'+root.name+'/Guide.tsx')
        assert b'clip.mov.720p.mp4' in code and b'voice.wav.compressed.m4a' in code


def test_compact_output_bounds_issues_and_retains_full_report(tmp_path):
    root=course(tmp_path/'source')
    for n in range(30): (root/f'file{n}.sh').write_text('echo x')
    result=export_source([root]); compact=agent_summary(result)
    assert len(compact['issues'])==20 and compact['remainingIssues']==10
    assert compact['warningCount']==30
    full=json.loads(Path(compact['reportPath']).read_text(encoding='utf-8'))
    assert len(full['issues']['warnings'])==30


def test_comments_are_untouched_but_alias_dynamic_call_is_reported(tmp_path):
    root=image_course(tmp_path, '// images/a.png\nconst text="ordinary\\ntext"; const x="images/a.png";')
    result=export_source([root])
    assert result['status']=='passed',result['issues']
    with zipfile.ZipFile(result['output']) as archive:
        code=archive.read('modules/'+root.name+'/Guide.tsx')
        assert b'// images/a.png' in code and b'"images/a.webp"' in code
    Image.new('RGB', (40,40), 'red').save(root/'assets/images/a.png')
    (root/'assets/images/a.webp').unlink()
    (root/'Guide.tsx').write_text("import {moduleAssetUrl as asset} from '@shuku/course-runtime/react/assets'; const x=asset(data.path);")
    result=export_source([root])
    assert result['status']=='failed'
    assert any(i['code']=='REFERENCE_DYNAMIC' for i in result['issues']['serious'])


def test_unhandled_srcset_blocks_even_when_another_attribute_is_migrated(tmp_path):
    root=image_course(tmp_path, 'const x="images/a.png";')
    (root/'preview.html').write_text('<img src="assets/images/a.png" srcset="assets/images/a.png 1x">')
    result=export_source([root])
    assert result['status']=='failed'
    assert any(i['code']=='REFERENCE_REVIEW' and i['path'].endswith('preview.html') for i in result['issues']['serious'])


def test_glob_and_other_courses_do_not_escape_migration_scope(tmp_path):
    root=image_course(tmp_path, 'const x=import.meta.glob("./assets/**/*.png");')
    other=course(root.parent)
    (other/'Guide.tsx').write_text('const url=moduleAssetUrl(external.path);')
    result=export_source([root,other])
    assert result['status']=='failed'
    assert any(i['code']=='REFERENCE_GLOB' for i in result['issues']['serious'])
    assert not any(i['path'].startswith('modules/'+other.name+'/') for i in result['issues']['serious'])


def test_pack_dependency_diagnostic_does_not_require_node_or_target_config(tmp_path):
    script=Path(__file__).resolve().parents[1]/'tools.py'
    execution=subprocess.run([sys.executable,str(script),'environment.doctor','--tool','course.pack'],
        env={**os.environ,'PATH':'','CREATOR_SKILL_TARGET_CONFIG':str(tmp_path/'missing.json')},
        text=True,capture_output=True,encoding='utf-8',check=True)
    result=json.loads(execution.stdout)
    assert result['status']=='passed'
    assert not any(item['name']=='Node' for item in result['checks'])
    assert all(item.get('optional') for item in result['checks'] if item['name'] in {'ffmpeg','ffprobe'})


def test_lossless_in_place_keeps_exact_teaching_pixels(tmp_path):
    from module.source_media import prepare_media
    root=course(tmp_path/'source');(root/'assets').mkdir()
    source=root/'assets/sample.png'
    from PIL import Image
    image=Image.new('RGBA',(32,32),(200,50,10,0))
    image.putpixel((1,1),(10,20,30,128));image.save(source)
    prefix='modules/'+root.name
    files={prefix+'/assets/sample.png':source}
    _,report,_=prepare_media(files,tmp_path,in_place=True,lossless=True)
    assert report['status']=='passed',report
    with Image.open(source.with_suffix('.webp')) as encoded:
        assert encoded.convert('RGBA').tobytes()==image.tobytes()
    assert not source.exists()
