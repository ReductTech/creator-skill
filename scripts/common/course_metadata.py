"""Metadata contract mirrored from Shuku; release packaging verifies against the selected live platform."""
import json
from pathlib import Path
import re

RULES = json.loads(Path(__file__).with_name('course_format.json').read_text(encoding='utf-8'))


def page_errors(doc, label, *, complete=False):
    errors = []
    if 'pageAliases' in doc:
        errors.append('Page aliases are unsupported; use page UUIDs: ' + label)
    pages = doc.get('pages')
    if not isinstance(pages, list) or len(pages) > RULES['max_pages']:
        return errors + ['Course pages require stable page IDs: ' + label]
    if complete and not pages and (doc.get('entry') or (doc.get('ppt') or {}).get('entry')):
        errors.append(label + ': pages must be a nonempty array')
    seen = set()
    for number, page in enumerate(pages, 1):
        if not isinstance(page, dict):
            errors.append(f'{label}: page {number} must be an object')
            continue
        uid = page.get('id')
        if not isinstance(uid, str) or not re.fullmatch(RULES['page_uuid_pattern'], uid):
            errors.append('Page id must be a canonical UUID: ' + label)
        elif uid in seen:
            errors.append('Duplicate page IDs: ' + label)
        else:
            seen.add(uid)
        obsolete = sorted(set(page) & set(RULES['retired_page_fields']))
        if obsolete:
            errors.append(label + ': obsolete outline fields are unsupported: ' + ', '.join(obsolete))
        if complete:
            for field in RULES['required_page_fields']:
                if not isinstance(page.get(field), str) or not page[field].strip():
                    errors.append(f'{label}: page {number} has no {field}')
    return errors


def module_errors(doc, identity, *, complete=False, exists=None):
    if not isinstance(doc, dict):
        return [identity + ': outline must be an object']
    errors = []
    asset = doc.get('moduleIdentity')
    ppt = doc.get('ppt', {})
    if not isinstance(asset, dict) or not isinstance(ppt, dict):
        return ['Invalid module identity or presentation metadata: ' + identity]
    if set(asset) != set(RULES['identity_fields']) or type(asset.get('version')) not in (int, float) or asset['version'] != RULES['identity_version']:
        errors.append('moduleIdentity requires only id and version: ' + identity)
    if not re.fullmatch(RULES['module_uuid_pattern'], identity) or doc.get('id') != identity or asset.get('id') != identity:
        errors.append('Module directory, id and moduleIdentity.id must match: ' + identity)
    if complete:
        for field in RULES['required_course_fields']:
            if not isinstance(doc.get(field), str) or not doc[field].strip():
                errors.append(identity + ': missing nonempty ' + field)
        if doc.get('path') != '/modules/' + identity:
            errors.append(identity + ': path must match /modules/' + identity)
    for entry in (doc.get('entry'), ppt.get('entry')):
        if not entry:
            continue
        valid = isinstance(entry, str) and '\\' not in entry and ':' not in entry and all(p not in ('', '.', '..') for p in entry.split('/'))
        if not valid or complete and not entry.endswith(RULES['entry_extension']) or exists and not exists(entry):
            errors.append('Missing course entry: ' + identity + '/' + str(entry))
    return errors + page_errors(doc, identity, complete=complete)
