"""One location and upload protocol for immutable public course objects."""
import hashlib
import mimetypes
from pathlib import PurePosixPath
from urllib.parse import quote, urlsplit

import json,re
from pathlib import Path
PUBLIC_LAYOUT = json.loads(Path(__file__).with_name('public_objects.json').read_text(encoding='utf-8'))
PUBLIC_PREFIX = PUBLIC_LAYOUT['prefix']

def public_blob_key(digest, path):
    if not re.fullmatch(r'[a-f0-9]{64}', digest):raise ValueError('Invalid SHA-256 digest')
    extension=PUBLIC_LAYOUT['extensions'].get(PurePosixPath(path).suffix.lower(),PurePosixPath(path).suffix.lower())
    if not re.fullmatch(r'\.[a-z0-9]{1,16}',extension):extension='.bin'
    return f'{PUBLIC_PREFIX}/{digest[:2]}/{digest}{extension}'

def is_public_key(key):
    return isinstance(key,str) and key.startswith(PUBLIC_PREFIX+'/')

def validate_blob_record(item):
    key=item['object_key'];digest=item['sha256']
    if key != public_blob_key(digest,key) or type(item['size']) is not int or item['size']<0:
        raise ValueError('Object key does not match SHA-256 or invalid size')
    return key


PRIVATE_CODE_SUFFIXES = {'.html', '.htm', '.js', '.mjs'}


def object_url(config,key):
    if not is_public_key(key):raise ValueError('Not a public course object')
    settings=config.get('course_build',{}).get('public_assets',{})
    if settings.get('prefix',PUBLIC_PREFIX).strip('/') != PUBLIC_PREFIX:
        raise ValueError('Course objects use the unified prefix '+PUBLIC_PREFIX)
    oss=config.get('storage',{}).get('oss',{})
    base=settings.get('base_url') or oss.get('public_url')
    if not base and oss.get('bucket') and oss.get('endpoint'):
        base='https://'+oss['bucket']+'.'+str(urlsplit(oss['endpoint']).hostname)
    address=urlsplit(base or '')
    if address.scheme!='https' or not address.hostname or address.query or address.fragment:
        raise ValueError('Configure an HTTPS OSS public asset base URL')
    return base.rstrip('/')+'/'+quote(key,safe='/')


def record(path,raw,*,course_uuid=None,build_id=None):
    digest=hashlib.sha256(raw).hexdigest()
    stored_path=path.rsplit('.',1)[0]+'.jpg' if raw.startswith(b'\xff\xd8') else path
    extension = PurePosixPath(stored_path).suffix.lower()
    private = extension in PRIVATE_CODE_SUFFIXES
    directory_file = private or extension == '.css' or (extension == '.json' and not path.startswith('assets/'))
    if directory_file and (course_uuid or build_id or private or extension=='.css'):
        if not course_uuid or not build_id:
            raise ValueError('Compiled code requires course_uuid and build_id')
        raise ValueError('Publish compiled code through the Shuku course build pipeline')
    key=public_blob_key(digest,stored_path)
    return {'path':path,'object_key':key,'sha256':digest,'size':len(raw),
            'mime':'application/javascript' if extension in ('.js','.mjs') else mimetypes.guess_type(stored_path)[0] or 'application/octet-stream'}


def put_bucket(bucket,key,raw,mime=None):
    if not is_public_key(key):raise ValueError('Public course uploads require the unified object prefix')
    digest=hashlib.sha256(raw).hexdigest()
    validate_blob_record({'object_key':key,'sha256':digest,'size':len(raw)})
    def verify_existing():
        if hasattr(bucket,'head_object'):
            head=bucket.head_object(key)
            if head.headers.get('x-oss-meta-sha256'):
                if head.content_length!=len(raw) or head.headers['x-oss-meta-sha256']!=digest:
                    raise ValueError('Existing public object has an invalid hash or size')
                return
        if bucket.get_object(key).read()!=raw:raise ValueError('Existing public object has an invalid hash')
    if bucket.object_exists(key):
        verify_existing()
    else:
        try:
            bucket.put_object(key,raw,headers={'Content-Type':mime or mimetypes.guess_type(key)[0] or 'application/octet-stream',
                'Cache-Control':'public, max-age=31536000, immutable','x-oss-object-acl':'public-read',
                'x-oss-meta-sha256':digest,'x-oss-forbid-overwrite':'true'})
        except Exception as error:
            if getattr(error,'status',None)!=409:raise
            verify_existing()
    return {'object_key':key,'sha256':digest,'size':len(raw)}
