from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4


def state_root():
    override = os.environ.get('CREATOR_SKILL_LOCAL_STATE')
    if override:
        return Path(override).expanduser().resolve()
    base = os.environ.get('LOCALAPPDATA') if os.name=='nt' else os.environ.get('XDG_CONFIG_HOME')
    return (Path(base) if base else Path.home()/'.config')/'creator-skill'


@contextmanager
def state_lock():
    root = state_root()
    root.mkdir(parents=True, exist_ok=True)
    lock = root/'preferences.lock'
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise ValueError('本机依赖偏好正在由另一窗口写入，请重试读取；不要重复询问用户。') from error
    try:
        yield root
    finally:
        lock.rmdir()


def _read(root):
    file = root/'dependency-preferences.json'
    if not file.exists():
        return {'installation': 'unknown'}
    document = json.loads(file.read_text(encoding='utf-8'))
    if document.get('installation') not in {'unknown', 'pending', 'allowed', 'declined'}:
        raise ValueError('依赖偏好文件损坏；请核对，不自动覆盖或重新提问。')
    return document


def _write(root, document):
    temporary = root/('preferences-'+str(uuid4())+'.tmp')
    try:
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        os.replace(temporary, root/'dependency-preferences.json')
    finally:
        temporary.unlink(missing_ok=True)


def install_policy(*, missing=(), owner=None, decision=None, request_id=None):
    """Only the first concurrent caller owns the one-time question; no expiry/re-asking."""
    with state_lock() as root:
        document = _read(root)
        if decision is not None:
            if decision not in {'allowed', 'declined', 'unknown'}:
                raise ValueError('Decision must be allowed, declined or unknown')
            if document['installation'] == 'pending' and decision != 'unknown' and request_id != document.get('requestId'):
                raise ValueError('使用本次 requestId 保存回答，避免其他窗口覆盖尚未回答的问题。')
            document = {'installation': decision, 'updatedAt': datetime.now(timezone.utc).isoformat()}
            _write(root, document)
        ask = False
        if missing and document['installation'] == 'unknown':
            document = {'installation': 'pending', 'requestId': str(uuid4()), 'owner': owner,
                        'missingAtQuestion': list(missing), 'updatedAt': datetime.now(timezone.utc).isoformat()}
            _write(root, document)
            ask = True
        return {**document, 'askUser': ask, 'path': str(root/'dependency-preferences.json'),
                'question': '是否允许为本 Skill 按任务需要安装本地依赖（Node、Python包、浏览器及FFmpeg）？本机只询问一次，可随时主动更改偏好。' if ask else None}
