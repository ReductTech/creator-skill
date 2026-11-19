import {useEffect, useRef, useState} from 'react';
import {CloudUpload} from 'lucide-react';
import './publish.css';

const channel = 'shuku-creator-zip-v1';

export function PublishButton({course, origin}: {course: string; origin: string}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const attempt = useRef<AbortController>(null);
  const [message, setMessage] = useState('');
  const [report, setReport] = useState('');
  const [download, setDownload] = useState<{url: string; name: string}>();
  const [busy, setBusy] = useState(false);

  useEffect(() => () => attempt.current?.abort(), []);
  useEffect(() => () => {
    if (download) URL.revokeObjectURL(download.url);
  }, [download]);

  function publish() {
    attempt.current?.abort();
    const controller = new AbortController();
    attempt.current = controller;
    const nonce = crypto.randomUUID();
    const destination = new URL('/workspace', origin);
    destination.searchParams.set('creatorPublish', nonce);
    destination.searchParams.set('creatorOrigin', location.origin);
    const receiver = window.open(destination, '_blank');
    dialog.current?.showModal();
    setReport('');
    setDownload(undefined);
    if (!receiver) {
      setMessage('浏览器拦截了术库页面。允许弹出窗口后再试。');
      return;
    }
    setBusy(true);
    setMessage('正在检查并打包当前课件…');
    let file: File | undefined;
    let ready = false;

    function send() {
      if (!file || !ready || !receiver || receiver.closed) return;
      receiver.postMessage({channel, type: 'file', nonce, file}, origin);
    }

    window.addEventListener('message', event => {
      if (event.source !== receiver || event.origin !== origin ||
          event.data?.channel !== channel || event.data.nonce !== nonce) return;
      if (event.data.type === 'ready') {
        ready = true;
        send();
      } else if (event.data.type === 'received') {
        setMessage('课件包已送到术库，请在术库页面确认上传。');
        controller.abort();
      } else if (event.data.type === 'rejected') {
        setMessage('术库未接收此文件。请在术库页面查看提示。');
      }
    }, {signal: controller.signal});

    void fetch('/__creator/publish-package?course=' + encodeURIComponent(course), {
      method: 'POST', signal: controller.signal,
    }).then(async response => {
      if (!response.ok) {
        const failure = await response.json();
        setReport(failure.report || '');
        throw new Error(failure.error || '本地打包失败。');
      }
      const blob = await response.blob();
      const name = course + '.zip';
      file = new File([blob], name, {type: 'application/zip'});
      setDownload({url: URL.createObjectURL(file), name});
      setMessage('课件包已就绪，正在等待术库接收。也可以下载 ZIP 手动上传。');
      send();
    }).catch(error => {
      if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : '准备课件包失败。');
    }).finally(() => {
      if (attempt.current === controller) setBusy(false);
    });
  }

  return <>
    <button className="creator-publish-button" type="button" onClick={publish} disabled={busy}>
      <CloudUpload aria-hidden="true" />发布到术库
    </button>
    <dialog className="creator-publish-dialog" ref={dialog} aria-label="发布到术库">
      <h2>发布到术库</h2>
      <p role="status" aria-live="polite">{message}</p>
      {report && <p className="creator-publish-report">检查报告 <code>{report}</code></p>}
      <div className="creator-publish-dialog-actions">
        {download && <a href={download.url} download={download.name}>下载 ZIP</a>}
        <button type="button" onClick={() => dialog.current?.close()}>关闭</button>
      </div>
    </dialog>
  </>;
}
