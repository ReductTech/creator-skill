"""Mandatory delivery steps on an isolated course copy, never the author's files."""
from collections import defaultdict
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from skzip import canonical, digest

SCRIPTS = Path(__file__).resolve().parents[1]


def tool(root, config, name, arguments, timeout, *, advisory=False):
    env = {**os.environ, 'CREATOR_SKILL_TARGET_CONFIG': str(config)}
    process = subprocess.run([sys.executable, str(SCRIPTS/'tools.py'), name, *map(str, arguments)],
                             cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=timeout)
    try:
        result = json.loads(process.stdout)
    except ValueError:
        raise ValueError(name + ' did not return a check result: ' + process.stderr[-1500:]) from None
    if process.returncode or result.get('status') in ('error', 'failed'):
        if advisory:
            return {**result, 'status':'warning'}
        raise ValueError(name + ' failed: ' + json.dumps(result, ensure_ascii=False))
    return result


def compressor():
    spec = importlib.util.spec_from_file_location('delivery_compressor', SCRIPTS/'media/compress-images.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(root, courses, workspace, timeout):
    """Compress -> rewrite -> repeat check -> add/check IDs -> metadata/import checks."""
    config = workspace/'target-root.json'
    config.write_bytes(canonical({'targetRoot': str(root)}))
    results = []
    convert = compressor().convert
    originals = set()
    for course in courses:
        directory = root/course['path']
        assets = directory/'assets'
        assets.mkdir(exist_ok=True)
        changes, images = {}, []
        # Freeze the list: conversions may create new WebP siblings.
        for file in sorted(assets.rglob('*')):
            if not file.is_file():
                continue
            if file.suffix.lower() in ('.gif', '.svg', '.avif', '.bmp', '.tif', '.tiff', '.ico'):
                images.append({'path':file.relative_to(root).as_posix(), 'status':'skipped',
                               'reason':'format-outside-automatic-source-conversion', 'before':file.stat().st_size})
                continue
            if file.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
                continue
            backup = workspace/'originals'/file.relative_to(root)
            try:
                row = convert(file, backup=backup, delivery=True)
            except (ValueError, OSError) as error:
                row = {'status':'warning', 'reason':str(error)[:1000]}
            images.append({'path':file.relative_to(root).as_posix(),
                           **{k: v for k, v in row.items() if k not in ('source', 'target', 'backup')}})
            if row.get('status') == 'converted' and file.suffix.lower() != '.webp':
                changes[file.relative_to(assets).as_posix()] = Path(row['target']).relative_to(assets).as_posix()
                originals.add(file.relative_to(root).as_posix())
        change_file = workspace/(course['module_id']+'-changes.json')
        change_file.write_bytes(canonical(changes))
        arguments = ['--module', course['module_id'], '--changes', change_file]
        for apply in (False, True, False):
            plan = tool(root, config, 'assets.rewrite', [*arguments, *(['--apply'] if apply else [])], timeout, advisory=True)
        applied = tool(root, config, 'module.edit-ids', [directory, '--apply', '--backup-dir', workspace/'id-backups'], timeout, advisory=True)
        checked = tool(root, config, 'module.edit-ids', [directory, '--check'], timeout, advisory=True)
        results.append({'module': course['module_id'], 'images': images, 'migratedPaths': changes,
                        'idsAdded': applied.get('idsWritten', 0), 'idsKept': checked.get('existingIdsKept', 0),
                        'skippedComponents': checked.get('skipped', []),
                        'references':plan, 'editIds':checked})
    return results, originals, config


def resource_review(root, courses, originals, snapshot):
    """Suspected-unused is advisory only. Never infer permission to drop a file."""
    records, groups = [], defaultdict(list)
    for course in courses:
        directory = root/course['path']
        source = '\n'.join(p.read_text(encoding='utf-8', errors='replace') for p in directory.rglob('*')
                           if p.is_file() and 'assets' not in p.relative_to(directory).parts
                           and '_scratchpad' not in p.parts and p.suffix in ('.tsx', '.ts', '.js', '.jsx', '.css', '.json', '.html'))
        for file in sorted((directory/'assets').rglob('*')):
            if not file.is_file():
                continue
            name = file.relative_to(root).as_posix()
            raw = file.read_bytes()
            row = {'path': name, 'size': len(raw), 'sha256': digest(raw), 'decision': 'pending', 'reasons': []}
            if name in originals:
                row['reasons'].append('converted-original')
            if file.name not in source:
                row['reasons'].append('suspected-unused-not-proof')
            records.append(row)
            groups[row['sha256']].append(name)
    for row in records:
        if len(groups[row['sha256']]) > 1:
            row['reasons'].append('identical-bytes')
            row['duplicates'] = groups[row['sha256']]
    return {'schema': 1, 'sourceSnapshot': snapshot, 'resources': records,
            'totalBytes': sum(r['size'] for r in records),
            'instructions': 'Author chooses keep/exclude for every resource, or explicitly chooses --resources keep-all. Exclusion affects only the delivery copy; suspected unused is not proof. Shared dependencies remain intact.'}


def choose_resources(review, decisions=None, policy=None):
    if policy == 'keep-all':
        choices = {r['path']: 'keep' for r in review['resources']}
    elif decisions is not None:
        if not isinstance(decisions, dict) or decisions.get('schema') != 1 or decisions.get('sourceSnapshot') != review['sourceSnapshot']:
            raise ValueError('Resource review is stale; run course.pack again')
        rows = decisions.get('resources')
        if not isinstance(rows, list) or len(rows) != len(review['resources']) or any(not isinstance(row, dict) for row in rows):
            raise ValueError('Resource decisions must cover the full current inventory')
        supplied = {r.get('path'): r for r in rows}
        if len(supplied) != len(rows) or set(supplied) != {r['path'] for r in review['resources']}:
            raise ValueError('Resource decisions contain duplicate, missing or foreign paths')
        choices = {}
        for row in review['resources']:
            selected = supplied[row['path']]
            if any(selected.get(k) != row[k] for k in ('size', 'sha256')) or selected.get('decision') not in ('keep', 'exclude'):
                raise ValueError('Unconfirmed or changed resource: ' + row['path'])
            choices[row['path']] = selected['decision']
    elif review['resources']:
        return None
    else:
        choices = {}
    return {'confirmed': True, 'policy': policy or ('author-decisions' if choices else 'empty-inventory'),
            'sourceSnapshot': review['sourceSnapshot'],
            'decisions': [{**{k: row[k] for k in ('path', 'size', 'sha256')}, 'decision': choices[row['path']]}
                          for row in review['resources']],
            'excludedBytes': sum(r['size'] for r in review['resources'] if choices[r['path']] == 'exclude')}
