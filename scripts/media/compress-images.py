"""Convert every raster image in place, migrate references, then remove originals.
SVG and valid WebP are retained. Unsupported input blocks completion.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.image_policy import IMAGE_SUFFIXES
from module.source_media import prepare_media
from module.source_inputs import source_paths
from common._common import project_path

MAX_WIDTH, MAX_HEIGHT, QUALITY = 1600, 900, 80

def fit_size(width, height):
    scale = min(1, MAX_WIDTH/width, MAX_HEIGHT/height)
    return max(1, round(width*scale)), max(1, round(height*scale))

def convert(path, dry_run=False, backup=None, delivery=True):
    path = Path(path)
    if dry_run:
        return {'source':str(path), 'status':'eligible', 'after_size':None}
    name = 'modules/course/assets/'+path.parent.name+'/'+path.name
    _, report, _ = prepare_media({name:path}, path.parent, in_place=True)
    if report['status'] != 'passed':
        raise ValueError(json.dumps(report['issues'], ensure_ascii=False))
    rows = report['conversions']
    return {'source':str(path), 'status':'converted' if rows else 'preserved',
            'target':str(path.with_suffix('.webp')) if rows else str(path),
            'quality':QUALITY}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--delivery', action='store_true', help='Compatibility option; all raster images are always converted')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--backup-dir', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = project_path(args.directory).resolve()
    if not root.is_dir():
        parser.error('An existing directory is required')
    # Include source text for reference migration, but do not process audio/video.
    from media.prepare_videos import EXTENSIONS as videos
    from media.prepare_audio import EXTENSIONS as audio
    prefix = 'modules/course/assets/' if root.name == 'assets' else 'modules/course/'
    files = {prefix+name:path for name,path in source_paths(root,[root]).items()
             if path.suffix.lower() not in (videos|audio)-{'.ts'} or path.suffix.lower() in IMAGE_SUFFIXES}
    if args.dry_run:
        print(json.dumps({'status':'dry-run','images':[n for n,p in files.items() if p.suffix.lower() in IMAGE_SUFFIXES]}))
        return 0
    import shutil
    from module.local_validation import node_references
    node = shutil.which('node')
    runner = (lambda f,c,d:node_references(f,c,d,{'node':node})) if node else None
    _, report, _ = prepare_media(files, root, in_place=True, reference_runner=runner)
    if args.report:
        project_path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status']=='passed' else 1

if __name__ == '__main__':
    raise SystemExit(main())
