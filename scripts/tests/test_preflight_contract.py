"""Preserved static metadata compatibility cases; no platform execution or builds."""
import json
import pytest
from checks.validate_module import validate_modules
MID = '11111111-1111-4111-8111-111111111111'


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

