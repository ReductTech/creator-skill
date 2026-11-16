"""SKZIP source envelope. The public workflow key is a convention, not authentication.

Reads a bounded ZIP without extracting or executing its contents. No network.
"""
import hashlib
import hmac
import json
from pathlib import PurePosixPath
import stat
import struct
import zipfile
from common.submission_policy import high_risk_reason, blocked_reason

MANIFEST = 'skzip-manifest.json'
PUBLIC_KEY = b'shuku-skzip-public-workflow-v1'
POLICY = 'source'  # Legacy import name; never used as an acceptance gate.
SERVER_PENDING = ('classification', 'security', 'admission', 'build', 'rendering')
CHECKS = ('images', 'references', 'editIds', 'resources', 'admission', 'build', 'mediaReferences', 'rendering')
HARD_CHECKS = ('resources', 'admission', 'build')
MAX_FILES, MAX_BYTES, MAX_FILE_BYTES = 10000, 1024 ** 3, 128 * 1024 ** 2
MAX_MANIFEST = 4 * 1024 ** 2


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_name(name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or any(ord(c) < 32 for c in name) or PurePosixPath(name).is_absolute()
            or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('Invalid SKZIP path: ' + str(name))
    return name


def seal(document):
    document = dict(document)
    document.pop('workflowTag', None)
    document['workflowTag'] = hmac.new(PUBLIC_KEY, canonical(document), hashlib.sha256).hexdigest()
    return document


def envelope(files, checks, review, producer):
    """Legacy call shape retained; client check labels are metadata, not admission."""
    rows = [{'path': safe_name(name), 'size': len(files[name]), 'sha256': digest(files[name])}
            for name in sorted(files)]
    return seal({'format': 'shuku-skzip', 'packageKind': 'source',
                 'producer': producer, 'checks': checks, 'resourceReview': review, 'files': rows})


def source_envelope(rows, report, producer):
    """Write a content-described source package without client version labels."""
    checks = {'source': {'status': 'passed'}, 'paths': {'status': 'passed'},
              'images': {'status': report['images']['status']},
              **{name: {'status': 'server-pending'} for name in SERVER_PENDING}}
    risks = [{'path': row['path'], 'riskLevel': 'high', 'reason': high_risk_reason(row['path'])}
             for row in sorted(rows, key=lambda row: row['path']) if high_risk_reason(row['path'])]
    document = seal({'format': 'shuku-skzip', 'packageKind': 'source',
                     'sharedPolicy': 'server-provided', 'producer': producer,
                     'highRiskFiles': risks, 'riskLevel': 'high' if risks else 'unassessed',
                     'imageConversions': report['images'].get('conversions', []),
                     'checks': checks, 'serverPending': list(SERVER_PENDING),
                     'report': report, 'files': rows})
    validate_manifest(document)
    return document


def validate_manifest(document):
    """Validate actual inventory and integrity, ignoring historical version labels."""
    if not isinstance(document, dict) or document.get('format') != 'shuku-skzip':
        raise ValueError('Invalid SKZIP manifest')
    tag = document.get('workflowTag')
    if not isinstance(tag, str) or not hmac.compare_digest(tag, seal(document)['workflowTag']):
        raise ValueError('Invalid SKZIP workflow tag; re-run course.pack')
    rows = document.get('files')
    if not isinstance(rows, list) or not 1 <= len(rows) < MAX_FILES:
        raise ValueError('Invalid SKZIP file inventory')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid SKZIP file record')
        name = safe_name(row.get('path'))
        if name == MANIFEST or name.casefold() in seen:
            raise ValueError('Duplicate/reserved SKZIP path')
        seen.add(name.casefold())
        if (type(row.get('size')) is not int or not 0 <= row['size'] <= MAX_FILE_BYTES
                or not isinstance(row.get('sha256'), str) or len(row['sha256']) != 64
                or any(c not in '0123456789abcdef' for c in row['sha256'])):
            raise ValueError('Invalid SKZIP file record: ' + name)
    if sum(row['size'] for row in rows) > MAX_BYTES:
        raise ValueError('SKZIP expanded size limit exceeded')
    if not isinstance(document.get('imageConversions', []), list):
        raise ValueError('Invalid image conversion inventory')
    if 'highRiskFiles' in document:
        expected = [{'path': row['path'], 'riskLevel': 'high', 'reason': high_risk_reason(row['path'])}
                    for row in sorted(rows, key=lambda row: row['path']) if high_risk_reason(row['path'])]
        if document['highRiskFiles'] != expected:
            raise ValueError('Missing or incorrect high-risk file declaration')
    return rows


def check_directory(path):
    """Bound central-directory parsing before zipfile allocates entry objects."""
    with path.open('rb') as stream:
        size = path.stat().st_size
        stream.seek(max(0, size - 65557))
        tail = stream.read(65557)
    for at in range(len(tail) - 22, -1, -1):
        if tail[at:at+4] != b'PK\x05\x06':
            continue
        _, disk, owner, count_disk, count, length, offset, comment = struct.unpack_from('<4s4H2IH', tail, at)
        if at + 22 + comment != len(tail):
            continue
        if disk or owner or count_disk != count or not 1 < count <= MAX_FILES or length > MAX_MANIFEST or offset + length != size - len(tail) + at:
            raise ValueError('Unsupported SKZIP central directory')
        return
    raise ValueError('Missing SKZIP central directory')


def verify_archive(path, *, require_extension=True):
    """Recompute the actual inventory; never trust a successful check label alone."""
    if (require_extension and path.suffix.lower() != '.skzip') or path.stat().st_size > MAX_BYTES:
        raise ValueError('Select a bounded .skzip created by course.pack')
    check_directory(path)
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if not 1 < len(entries) <= MAX_FILES:
            raise ValueError('SKZIP file count limit exceeded')
        seen = set()
        for item in entries:
            safe_name(item.filename)
            mode = item.external_attr >> 16
            if (item.filename.casefold() in seen or item.is_dir() or stat.S_ISLNK(mode)
                    or item.flag_bits & 1 or item.compress_type not in (0, 8)
                    or item.file_size > MAX_FILE_BYTES):
                raise ValueError('Unsupported/duplicate SKZIP entry: ' + item.filename)
            seen.add(item.filename.casefold())
        if sum(i.file_size for i in entries) > MAX_BYTES or MANIFEST not in archive.namelist():
            raise ValueError('Missing SKZIP manifest or expanded size exceeded')
        if archive.getinfo(MANIFEST).file_size > MAX_MANIFEST:
            raise ValueError('SKZIP manifest too large')
        document = json.loads(archive.read(MANIFEST))
        rows = validate_manifest(document)
        if set(archive.namelist()) != {MANIFEST, *(row['path'] for row in rows)}:
            raise ValueError('SKZIP contains missing or unlisted files')
        for row in rows:
            info = archive.getinfo(row['path'])
            if info.file_size != row['size']:
                raise ValueError('SKZIP size differs: ' + row['path'])
            calculated = hashlib.sha256()
            with archive.open(info) as stream:
                header = stream.read(512)
                if blocked_reason(row['path'], header):
                    raise ValueError('Forbidden SKZIP payload: ' + row['path'])
                calculated.update(header)
                while block := stream.read(1024 * 1024):
                    calculated.update(block)
            if calculated.hexdigest() != row['sha256']:
                raise ValueError('SKZIP hash differs: ' + row['path'])
    return document
