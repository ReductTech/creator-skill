import json
from PIL import Image
from media.migrate_thumbnail_webp import migrate


def test_migration_preserves_new_webp_capture_and_original_files(tmp_path):
    shared = tmp_path / 'modules/shared/react'
    shared.mkdir(parents=True)
    assets = tmp_path / 'modules/Example/assets'
    thumbs = assets / 'scenedeck-thumbnails'
    thumbs.mkdir(parents=True)
    Image.new('RGB', (8, 8), 'red').save(thumbs / 'one.png')
    Image.new('RGB', (1600, 900), 'blue').save(thumbs / 'one.webp', quality=20)
    fresh = (thumbs / 'one.webp').read_bytes()
    Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(thumbs / 'two.png')
    Image.new('RGB', (8, 8), 'green').save(assets / 'lesson.png')
    (assets.parent / 'outlines.json').write_text(json.dumps({'moduleIdentity': {'id': 'uuid'}}))
    (shared.parent / 'asset-index.json').write_text(json.dumps({
        'roots': {'legacy': 'modules/Example/assets'}, 'formats': {}}))
    result = migrate(tmp_path)
    assert result == {'thumbnailCount': 2, 'converted': 1, 'removedOldFiles': 0}
    assert (thumbs / 'one.webp').read_bytes() == fresh
    assert (assets / 'lesson.png').is_file()
    assert len(list(thumbs.glob('*.png'))) == 2
    with Image.open(thumbs / 'two.webp') as image:
        assert image.format == 'WEBP' and image.size == (1600, 900)
        assert min(image.getpixel((0, 0))) >= 250
    assert sorted(p.name for p in shared.glob('*.json')) == []
    assert migrate(tmp_path)['converted'] == 0
