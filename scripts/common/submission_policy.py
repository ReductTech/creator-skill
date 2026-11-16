"""SKZIP file rules, mirrored by Shuku; no source execution or third-party deps."""
from pathlib import PurePosixPath
import re

POLICY_REVISION = 'submission-files-v2'
OUTSIDE_ASSETS_LIMIT = 100 * 1024
SOURCE_EXTENSIONS = frozenset({'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css'})
BLOCKED_EXTENSIONS = frozenset({
    '.pyc', '.pyo', '.pyw', '.ps1', '.psm1', '.psd1', '.sh', '.bash',
    '.zsh', '.ksh', '.fish', '.bat', '.cmd', '.exe', '.com', '.scr', '.msi',
    '.dll', '.so', '.dylib', '.run', '.appimage', '.deb', '.rpm',
    '.apk', '.jar', '.class', '.elf', '.o', '.a', '.desktop', '.service',
    '.vbs', '.vbe', '.wsf', '.wsh', '.pl', '.pm', '.rb', '.php',
})


def blocked_reason(name, header=b''):
    """Denylist takes precedence over location and source-extension allowlist."""
    parts = PurePosixPath(name).parts
    lower = parts[-1].casefold().rstrip(' .')
    if any(p.casefold() == '.env' or p.casefold().startswith('.env.') for p in parts):
        return 'environment-file'
    if lower in {'.envrc', '.bashrc', '.bash_profile', '.profile', '.zshrc', '.zprofile'}:
        return 'shell-startup-file'
    if PurePosixPath(lower).suffix in BLOCKED_EXTENSIONS or re.search(r'\.so\..+$', lower):
        return 'blocked-extension'
    if header.startswith((b'\x7fELF', b'MZ', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
                          b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe',
                          b'\xbe\xba\xfe\xca', b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca')):
        return 'executable-content'
    first = header.split(b'\n', 1)[0].lower()
    if first.startswith(b'#!') and re.search(rb'\b(?:python[\d.]*|(?:ba|da|z|k|fi|c|tc)?sh|perl|ruby|php|pwsh|powershell)\b', first):
        if (PurePosixPath(lower).suffix == '.py'
                and re.match(rb'^#!\s*(?:/[^\s]*/python[\d.]*|/usr/bin/env\s+(?:-S\s+)?python[\d.]*)(?:\s|$)', first)):
            return None
        return 'script-interpreter'
    return None


def high_risk_reason(name):
    """Allowed payloads still require independent server security review."""
    return {'.py': 'python-source', '.bin': 'binary-data'}.get(PurePosixPath(name).suffix.casefold())


def outside_assets_violation(name, size):
    """name is course-relative; metadata exceptions are exact root paths."""
    path = PurePosixPath(name)
    return (size > OUTSIDE_ASSETS_LIMIT and path.parts[0] != 'assets'
            and path.suffix.casefold() not in SOURCE_EXTENSIONS
            and name not in {'outlines.json', 'style.json'})


def issue(code, path, message, impact, repair, **details):
    return {'code': code, 'path': path, 'message': message, 'impact': impact,
            'repair': repair, 'recheck': '重新运行 course.pack，确认本项消失；服务器仍独立校验。', **details}
