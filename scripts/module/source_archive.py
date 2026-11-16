"""Stream an inspected inventory into a source SKZIP and verify its integrity.

Python standard library only. Does not inspect JS, alter images, build, or render.
The caller supplies the inventory and report; this component does not rediscover it.
"""
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from skzip import (MANIFEST, MAX_BYTES, MAX_FILE_BYTES, MAX_FILES, MAX_MANIFEST,
                   canonical, safe_name, source_envelope, verify_archive)
from module.source_inputs import linked

TEXT = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css', '.html', '.json',
        '.md', '.txt', '.csv', '.tsv', '.svg', '.xml', '.yaml', '.yml', '.py'}


def write_source_archive(files, report, output, producer):
    """Hash bytes while writing once; re-read the resulting archive for integrity."""
    output = Path(output).expanduser().absolute()
    if output.suffix.lower() != '.skzip':
        raise ValueError('Output must have the .skzip extension')
    if output.exists() or output.is_symlink():
        raise ValueError('Output already exists; choose a new .skzip path')
    output = output.resolve()
    roots = [path.parent for name, path in files.items() if name.count('/') == 2 and name.endswith('/outlines.json')]
    if any(output.is_relative_to(root) for root in roots):
        raise ValueError('Output must be outside the selected module directories')
    seen, total, snapshots = set(), 0, {}
    for name, path in files.items():
        safe_name(name)
        if name.casefold() in seen:
            raise ValueError('Duplicate or excluded Shared archive path: ' + name)
        seen.add(name.casefold())
        info = path.stat()
        if linked(path) or info.st_size > MAX_FILE_BYTES:
            raise ValueError('Linked source or file exceeds 128 MiB: ' + name)
        total += info.st_size
        snapshots[name] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    if not files or len(files) >= MAX_FILES or total > MAX_BYTES - MAX_MANIFEST:
        raise ValueError('Source exceeds SKZIP file-count or 1 GiB expanded-size limit')
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.source-pack-', suffix='.skzip', dir=output.parent)
    os.close(descriptor)
    temporary = Path(temporary)
    rows = []
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for name, path in sorted(files.items()):
                if linked(path):
                    raise ValueError('Source changed to a link while packing: ' + name)
                calculated, size = hashlib.sha256(), 0
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_DEFLATED if path.suffix.lower() in TEXT else zipfile.ZIP_STORED
                info._compresslevel = 1
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                with path.open('rb') as source, archive.open(info, 'w') as destination:
                    before = os.fstat(source.fileno())
                    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != snapshots[name]:
                        raise ValueError('Source changed while packing: ' + name)
                    while block := source.read(1024 * 1024):
                        size += len(block)
                        if size > before.st_size:
                            raise ValueError('Source grew while packing: ' + name)
                        calculated.update(block)
                        destination.write(block)
                    after = os.fstat(source.fileno())
                    if size != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
                        raise ValueError('Source changed while packing: ' + name)
                rows.append({'path': name, 'size': size, 'sha256': calculated.hexdigest()})
            document = source_envelope(rows, report, producer)
            manifest = canonical(document)
            if len(manifest) > MAX_MANIFEST:
                raise ValueError('SKZIP manifest exceeds 4 MiB')
            archive.writestr(MANIFEST, manifest)
        verify_archive(temporary)
        os.link(temporary, output)  # Atomic and exclusive on Windows and POSIX.
    finally:
        temporary.unlink(missing_ok=True)
    return {'output': str(output), 'policy': document['policy'], 'files': len(rows),
            'sourceBytes': total, 'zipBytes': output.stat().st_size,
            'serverPending': document['serverPending'], 'skzipIntegrity': True}
