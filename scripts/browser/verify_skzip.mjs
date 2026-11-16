/** Official SKZIP v1 local browser gate. Reads a File/Blob, never executes archive
 * code and never uploads. The PUBLIC_KEY is a workflow convention, not a secret.
 * Import verifySkzip(file, {onProgress}) from an HTTPS/localhost application.
 */
const MANIFEST = 'skzip-manifest.json', POLICY = 'creator-delivery-v2';
const PUBLIC_KEY = 'shuku-skzip-public-workflow-v1';
const CHECKS = ['images','references','editIds','resources','admission','build','mediaReferences','rendering'];
const HARD_CHECKS = ['resources','admission','build'];
const MAX_FILES = 10000, MAX_BYTES = 1024 ** 3, MAX_FILE = 128 * 1024 ** 2, MAX_MANIFEST = 4 * 1024 ** 2;
export const SKZIP_MAX_BYTES = MAX_BYTES;
const utf8 = new TextDecoder('utf-8', {fatal:true}), encoder = new TextEncoder();
const hex = raw => [...new Uint8Array(raw)].map(n=>n.toString(16).padStart(2,'0')).join('');
const sha = async bytes => hex(await crypto.subtle.digest('SHA-256',bytes));
export const canonical = value => JSON.stringify(value, (_, v) => v && typeof v === 'object' && !Array.isArray(v)
  ? Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])) : v);
export class SkzipValidationError extends Error {
  constructor(code) { super(code); this.name='SkzipValidationError'; this.code=code; }
}
function requireThat(ok, message, code='SKZIP_INVALID') { if (!ok) throw new SkzipValidationError(code); }
function safeName(name) {
  requireThat(typeof name === 'string' && name && !/[\\:\u0000-\u001f]/.test(name)
    && !name.startsWith('/') && !name.split('/').some(p=>!p || p==='.' || p==='..'), 'Invalid SKZIP path');
  return name;
}

export async function validateManifest(document) {
  requireThat(document && document.format==='shuku-skzip' && document.schema===1 && ['creator-delivery-v1',POLICY].includes(document.policy),
    '请选择官方打包程序生成的 SKZIP；格式或版本不受支持。','SKZIP_FORMAT');
  const {workflowTag,...unsigned} = document;
  const key = await crypto.subtle.importKey('raw',encoder.encode(PUBLIC_KEY),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  const expected = hex(await crypto.subtle.sign('HMAC',key,encoder.encode(canonical(unsigned))));
  requireThat(workflowTag===expected, 'SKZIP 流程标记不正确，请重新打包。','SKZIP_INTEGRITY');
  requireThat(document.checks && HARD_CHECKS.every(k=>document.checks[k]?.status==='passed'),
    '必要的交付检查未通过。','SKZIP_CHECKS');
  requireThat(document.resourceReview?.confirmed===true, '作者尚未完成资源取舍。','SKZIP_REVIEW');
  requireThat(Array.isArray(document.files) && document.files.length>0 && document.files.length<MAX_FILES,
    'Invalid SKZIP inventory');
  const seen = new Set(); let bytes = 0;
  for (const row of document.files) {
    safeName(row.path); const folded = row.path.toLowerCase();
    requireThat(row.path!==MANIFEST && !seen.has(folded), 'Duplicate/reserved SKZIP path'); seen.add(folded);
    requireThat(Number.isSafeInteger(row.size) && row.size>=0 && row.size<=MAX_FILE && /^[a-f0-9]{64}$/.test(row.sha256),
      'Invalid SKZIP file record'); bytes+=row.size;
  }
  requireThat(bytes<=MAX_BYTES, 'SKZIP 展开大小超过限制。');
  return document.files;
}

async function read(blob, start, length) {
  requireThat(Number.isSafeInteger(start) && Number.isSafeInteger(length) && start>=0 && length>=0 && start+length<=blob.size,
    'Truncated SKZIP');
  return new Uint8Array(await blob.slice(start,start+length).arrayBuffer());
}
function view(bytes) { return new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength); }

async function directory(file) {
  const tailStart = Math.max(0,file.size-65557), tail = await read(file,tailStart,file.size-tailStart), v = view(tail);
  let end = -1;
  for(let i=tail.length-22;i>=0;i--) if(v.getUint32(i,true)===0x06054b50 && i+22+v.getUint16(i+20,true)===tail.length) { end=i;break; }
  requireThat(end>=0,'Invalid SKZIP ZIP directory');
  const count=v.getUint16(end+10,true), size=v.getUint32(end+12,true), offset=v.getUint32(end+16,true);
  requireThat(v.getUint16(end+4,true)===0 && v.getUint16(end+6,true)===0 && v.getUint16(end+8,true)===count
    && count>1 && count<=MAX_FILES && size<=MAX_MANIFEST && offset+size===tailStart+end,
    'Unsupported SKZIP directory/ZIP64/multi-volume archive');
  const raw=await read(file,offset,size), d=view(raw), entries=new Map(), offsets=new Set(); let at=0,total=0;
  for(let i=0;i<count;i++) {
    requireThat(at+46<=raw.length && d.getUint32(at,true)===0x02014b50,'Invalid ZIP entry');
    const flags=d.getUint16(at+8,true), method=d.getUint16(at+10,true), compressed=d.getUint32(at+20,true),
      length=d.getUint32(at+24,true), n=d.getUint16(at+28,true), extra=d.getUint16(at+30,true), comment=d.getUint16(at+32,true),
      mode=d.getUint32(at+38,true)>>>16, local=d.getUint32(at+42,true);
    requireThat(at+46+n+extra+comment<=raw.length && d.getUint16(at+34,true)===0,'Invalid ZIP entry bounds');
    const name=safeName(utf8.decode(raw.subarray(at+46,at+46+n))), folded=name.toLowerCase();
    requireThat(!entries.has(folded) && !offsets.has(local) && !(flags&1) && [0,8].includes(method)
      && (mode&0xf000)!==0xa000 && length<=MAX_FILE && compressed<=MAX_BYTES && local<offset,
      'Unsupported/duplicate SKZIP entry');
    entries.set(folded,{name,flags,method,compressed,length,local}); offsets.add(local); total+=length;
    at+=46+n+extra+comment;
  }
  requireThat(at===raw.length && total<=MAX_BYTES,'Invalid SKZIP expanded size');
  const spans=[...entries.values()].sort((a,b)=>a.local-b.local);
  for(let i=0;i<spans.length;i++) spans[i].limit=i+1<spans.length?spans[i+1].local:offset;
  return entries;
}

async function contents(file, entry) {
  const h=view(await read(file,entry.local,30));
  requireThat(h.getUint32(0,true)===0x04034b50 && h.getUint16(6,true)===entry.flags && h.getUint16(8,true)===entry.method,
    'ZIP local header differs');
  const n=h.getUint16(26,true), extra=h.getUint16(28,true), start=entry.local+30+n+extra;
  requireThat(utf8.decode(await read(file,entry.local+30,n))===entry.name && start+entry.compressed<=entry.limit,'ZIP entry overlaps/differs');
  let stream=file.slice(start,start+entry.compressed).stream();
  if(entry.method===8) stream=stream.pipeThrough(new DecompressionStream('deflate-raw'));
  const reader=stream.getReader(), chunks=[];let size=0;
  try {
    for(;;) {
      const {done,value}=await reader.read();if(done)break;
      size+=value.length;requireThat(size<=entry.length && size<=MAX_FILE,'SKZIP decompression limit exceeded');chunks.push(value);
    }
  } catch(error) { await reader.cancel().catch(()=>{});throw error; }
  requireThat(size===entry.length,'SKZIP file size differs');
  const result=new Uint8Array(size);let at=0;for(const c of chunks){result.set(c,at);at+=c.length;}return result;
}

export async function verifySkzip(file, {onProgress=()=>{}}={}) {
  requireThat(globalThis.crypto?.subtle && typeof globalThis.DecompressionStream==='function',
    'Browser does not support local SKZIP verification','SKZIP_BROWSER');
  requireThat(file && /\.skzip$/i.test(file.name||'') && file.size>0 && file.size<=MAX_BYTES,
    '请选择不超过 1 GiB 的 .skzip 文件；普通 ZIP 不可上传。','SKZIP_FORMAT');
  const entries=await directory(file), manifest=entries.get(MANIFEST);
  requireThat(manifest?.name===MANIFEST && manifest.length<=MAX_MANIFEST,'缺少 SKZIP 交付清单。','SKZIP_FORMAT');
  const document=JSON.parse(utf8.decode(await contents(file,manifest))), rows=await validateManifest(document);
  requireThat(entries.size===rows.length+1,'SKZIP 存在未登记或缺失文件。');
  let completed=0;
  for(const row of rows) {
    const entry=entries.get(row.path.toLowerCase());
    requireThat(entry?.name===row.path && entry.length===row.size,'SKZIP 文件清单不一致：'+row.path,'SKZIP_INTEGRITY');
    requireThat(await sha(await contents(file,entry))===row.sha256,'SKZIP 内容已变化，请重新打包：'+row.path,'SKZIP_INTEGRITY');
    onProgress({completed:++completed,total:rows.length,path:row.path});
  }
  return {status:'passed',format:document.format,policy:document.policy,files:rows.length,
    bytes:rows.reduce((n,r)=>n+r.size,0),manifest:document,
    warnings:CHECKS.filter(k=>!HARD_CHECKS.includes(k) && document.checks?.[k]?.status!=='passed')};
}
