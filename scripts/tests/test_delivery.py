"""Platform parity and ZIP delivery use real input bytes and the live compiler."""
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from checks.validate_module import validate_modules
from module.package_course import source_paths

SCRIPTS = Path(__file__).resolve().parents[1]
SHUKU = os.environ.get('CREATOR_SKILL_TEST_SHUKU_ROOT')
MID = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'
DRAFT = '33333333-3333-4333-8333-333333333333'


def course(root, mid=MID, *, draft=False):
    directory = root/'modules'/mid
    directory.mkdir(parents=True)
    doc = {'id':mid,'title':'Delivery fixture','alias':'fixture-'+mid[:8], 'path':'/modules/'+mid,
           'moduleIdentity':{'version':1,'id':mid},
           'pages':[{'id':'44444444-4444-4444-8444-444444444444','title':'Opening','snippet':'Narration'}]}
    if not draft:
        doc['entry'] = 'Guide.tsx'
        (directory/'Guide.tsx').write_text('export function Guide(){return <p>Delivered</p>}',encoding='utf-8')
    (directory/'outlines.json').write_text(json.dumps(doc),encoding='utf-8')
    return directory


@pytest.mark.parametrize('change', ['valid','double-asset','double-json','signature','page-field','semantic-directory','missing-id','retired-index','old-global'])
def test_preflight_matches_current_platform_for_known_conflicts(tmp_path, change):
    directory = course(tmp_path)
    path = directory/'outlines.json'
    doc = json.loads(path.read_text())
    if change == 'signature': doc['moduleIdentity']['signature'] = 'legacy'
    if change == 'page-field': doc['pages'][0]['section'] = 'legacy'
    if change == 'missing-id': doc.pop('id')
    if change == 'semantic-directory':
        doc['id'] = 'Named-Course'
        directory.rename(directory.parent/'Named-Course')
        directory = directory.parent/'Named-Course'
        path = directory/'outlines.json'
    if change in {'double-asset','double-json'}:
        helper = 'moduleAssetUrl' if change=='double-asset' else 'moduleJson'
        (directory/'use.ts').write_text(helper+"(moduleIdentity.id, 'image.png')",encoding='utf-8')
    if change == 'retired-index': (tmp_path/'asset-index.json').write_text('{}')
    if change == 'old-global': (directory/'use.ts').write_text('const old = import.meta.env.VITE_LLM_SERVICE_URL')
    path.write_text(json.dumps(doc),encoding='utf-8')
    expected = change=='valid'
    assert (not validate_modules(tmp_path)) == expected
    if SHUKU:
        result = subprocess.run([sys.executable,str(Path(SHUKU)/'tooling/authoring/scripts/checks/validate_module.py'), '--repository', str(tmp_path)],
            cwd=SHUKU,env={**os.environ,'PYTHONPATH':SHUKU},capture_output=True,text=True,encoding='utf-8',timeout=60)
        report = json.loads(result.stdout)
        assert (report['status']=='passed') == expected, report


def test_source_selection_excludes_scratch_archives_credentials_and_skill(tmp_path):
    directory = course(tmp_path)
    for name in ('_scratchpad/draft.tsx','node_modules/cache.js','creator-skill/SKILL.md','nested.zip','.env.local'):
        p = directory/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('exclude')
    files = source_paths(tmp_path,[tmp_path/'modules'])
    assert sorted(files) == [f'modules/{MID}/Guide.tsx',f'modules/{MID}/outlines.json']


def pack(root, output, *modules):
    config = root.parent/'target-root.json'
    config.write_text(json.dumps({'targetRoot':str(root)}))
    arguments = [sys.executable,str(SCRIPTS/'tools.py'),'course.pack','--shuku-root',SHUKU,'--output',str(output)]
    for mid in modules: arguments.extend(['--module',mid])
    result = subprocess.run(arguments,env={**os.environ,'CREATOR_SKILL_TARGET_CONFIG':str(config)},
                            capture_output=True,text=True,encoding='utf-8',timeout=120)
    return result, json.loads(result.stdout)


@pytest.mark.skipif(not SHUKU, reason='Set CREATOR_SKILL_TEST_SHUKU_ROOT for real platform admission and builds')
def test_zip_roundtrip_includes_sibling_dependency_excludes_unrelated_draft_and_never_overwrites(tmp_path):
    root=tmp_path/'source';first=course(root);second=course(root,OTHER);course(root,DRAFT,draft=True)
    (second/'helper.ts').write_text('export const value="Sibling dependency"')
    (first/'Guide.tsx').write_text("import {value} from '../"+OTHER+"/helper';export function Guide(){return <p>{value}</p>}")
    (first/'_scratchpad').mkdir();(first/'_scratchpad/draft.tsx').write_text('invalid code')
    output=tmp_path/'course.zip'
    result,report=pack(root,output,MID)
    assert result.returncode==0,(report,result.stderr)
    assert set(report['courses'])=={MID,OTHER}
    assert report['coverage']['platformAdmission'] and report['coverage']['realBuild']
    assert report['coverage']['rendering'] is False
    assert len(list(Path(report['buildOutput']).rglob('artifact-manifest.json')))==2
    with zipfile.ZipFile(output) as archive:
        names=archive.namelist()
        assert any(OTHER+'/helper.ts' in name for name in names)
        assert not any(DRAFT in name or '_scratchpad' in name for name in names)
    before=output.read_bytes()
    again,error=pack(root,output,MID)
    assert again.returncode==2 and 'already exists' in error['error']
    assert output.read_bytes()==before


@pytest.mark.skipif(not SHUKU, reason='Explicit current Shuku required')
def test_no_zip_is_delivered_when_real_compile_rejects_an_import(tmp_path):
    root=tmp_path/'source';directory=course(root)
    (directory/'Guide.tsx').write_text("import {moduleAssetUrl} from '@shuku/course-style/react';export function Guide(){return <img src={moduleAssetUrl('image.png')}/>}")
    (directory/'assets').mkdir();(directory/'assets/image.png').write_bytes(b'fixture')
    output=tmp_path/'must-not-exist.zip'
    result,report=pack(root,output,MID)
    assert result.returncode==2 and 'build failed' in report['error']
    assert not output.exists()
