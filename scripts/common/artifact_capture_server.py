"""Loopback-only capture server for completed, manifest-listed course artifacts."""
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json,re,threading,hashlib
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,urlencode,unquote
from _common import get_target_root

@contextmanager
def artifact_server(output_root=None):
    root=Path(output_root or get_target_root() / 'dist').resolve()
    if not root.is_dir():raise ValueError('Build the course first; set --build-output to the completed Shuku output directory')
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_HEAD(self):
            self._head_only=True
            try:return self.do_GET()
            finally:self._head_only=False
        def copyfile(self,source,outputfile):
            if not getattr(self,'_head_only',False):return super().copyfile(source,outputfile)
        def do_GET(self):
            parsed=urlsplit(self.path)
            decoded=unquote(parsed.path)
            if '\\' in decoded or any(p in ('.','..') for p in decoded.split('/')):self.send_error(404);return
            is_guide=parsed.path.rstrip('/').startswith('/modules/')
            if parsed.path.rstrip('/')=='/scenedeck' or is_guide:
                query=parse_qs(parsed.query);mid=parsed.path.rstrip('/').rsplit('/',1)[-1] if is_guide else query.get('deck',[''])[0]
                if not re.fullmatch(r'[a-f0-9-]{36}',mid):self.send_error(400,'Select a course UUID');return
                versions=[]
                for manifest in (root/mid).glob('*/artifact-manifest.json'):
                    try:
                        info=json.loads(manifest.read_text(encoding='utf-8'))
                        if info.get('module_id')==mid and info.get('revision')==manifest.parent.name:
                            versions.append((manifest.stat().st_mtime,manifest.parent))
                    except (ValueError,OSError):continue
                if versions:
                    base=mid+'/'+max(versions)[1].name+'/'
                else:
                    # Flat IDL builds also have per-course artifact manifests.
                    folder=root/mid
                    try:
                        info=json.loads((folder/'artifact-manifest.json').read_text(encoding='utf-8'))
                        if info.get('module_id')!=mid:raise ValueError('Wrong module')
                    except (OSError,ValueError):self.send_error(404,'Build the selected course first');return
                    base=mid+'/'
                values={'mode':'guide' if is_guide else 'ppt','scenedeckCapture':'1','slide':query.get('slide',[''])[0]}
                self.send_response(302);self.send_header('Location','/'+base+'index.html?'+urlencode(values));self.end_headers();return
            parts=Path(decoded.lstrip('/')).parts
            if len(parts)<2 or any(part.startswith('.') or part=='..' for part in parts):self.send_error(404);return
            versioned=len(parts)>2 and bool(re.fullmatch(r'[a-f0-9]{64}',parts[1]))
            offset=2 if versioned else 1
            folder=root.joinpath(*parts[:offset]).resolve()
            if not folder.is_relative_to(root):self.send_error(404);return
            try:
                manifest=json.loads((folder/'artifact-manifest.json').read_text(encoding='utf-8'))
                allowed={record['path']:record for record in manifest['files']}
            except (ValueError,OSError,KeyError):self.send_error(404);return
            logical='/'.join(parts[offset:])
            target=(folder/logical).resolve()
            if logical not in allowed or not target.is_relative_to(folder) or target.is_symlink() or target.suffix in {'.tsx','.ts','.py','.map'}:self.send_error(404);return
            record=allowed[logical]
            if not target.is_file():self.send_error(404);return
            if target.stat().st_size!=record['size']:self.send_error(409,'Artifact size changed');return
            digest=hashlib.sha256()
            with target.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            if digest.hexdigest()!=record['sha256']:self.send_error(409,'Artifact checksum changed');return
            return super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(root)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield 'http://127.0.0.1:'+str(server.server_port)
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
