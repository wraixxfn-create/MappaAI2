/**
 * Server di file statici per il gioco (senza dipendenze).
 *
 *   node server.js            # porta 8080
 *   PORT=3000 node server.js
 *
 * Serve MIME corretti, supporta le Range request (il GLB è grosso) e accetta
 * qualsiasi host, così funziona anche dietro un proxy di anteprima.
 */
import { createServer } from 'node:http';
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(fileURLToPath(new URL('.', import.meta.url)));
const PORT = Number(process.env.PORT || 8080);
const HOST = process.env.HOST || '0.0.0.0';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.glb': 'model/gltf-binary',
  '.gltf': 'model/gltf+json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.wasm': 'application/wasm',
  '.map': 'application/json; charset=utf-8',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
};

function safePath(urlPath) {
  const clean = decodeURIComponent(urlPath.split('?')[0].split('#')[0]);
  const relative = normalize(clean).replace(/^(\.\.[/\\])+/, '');
  const full = resolve(join(ROOT, relative));
  if (full !== ROOT && !full.startsWith(ROOT + sep)) return null;
  return full;
}

function parseRange(header, size) {
  if (!header || !header.startsWith('bytes=')) return null;
  const [rawStart, rawEnd] = header.slice(6).split(',')[0].split('-');
  const start = rawStart ? Number(rawStart) : Math.max(0, size - Number(rawEnd));
  const end = rawStart && rawEnd ? Number(rawEnd) : size - 1;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start > end || start >= size) return null;
  return { start, end: Math.min(end, size - 1) };
}

const server = createServer(async (req, res) => {
  const urlPath = req.url === '/' ? '/index.html' : req.url;
  const full = safePath(urlPath);
  if (!full) {
    res.writeHead(403).end('percorso non consentito');
    return;
  }
  let info;
  try {
    info = await stat(full);
  } catch {
    res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' }).end('404 — file non trovato');
    return;
  }
  if (info.isDirectory()) {
    res.writeHead(302, { location: `${urlPath.replace(/\/$/, '')}/index.html` }).end();
    return;
  }
  const type = MIME[extname(full).toLowerCase()] || 'application/octet-stream';
  const headers = {
    'content-type': type,
    'accept-ranges': 'bytes',
    'cache-control': 'no-cache',
    'cross-origin-opener-policy': 'same-origin',
  };
  const range = parseRange(req.headers.range, info.size);
  if (range) {
    res.writeHead(206, {
      ...headers,
      'content-range': `bytes ${range.start}-${range.end}/${info.size}`,
      'content-length': range.end - range.start + 1,
    });
    if (req.method === 'HEAD') { res.end(); return; }
    createReadStream(full, { start: range.start, end: range.end }).pipe(res);
    return;
  }
  res.writeHead(200, { ...headers, 'content-length': info.size });
  if (req.method === 'HEAD') { res.end(); return; }
  createReadStream(full).pipe(res);
});

server.listen(PORT, HOST, () => {
  console.log(`La Porta dell'Inferno — http://${HOST}:${PORT}/ (root ${ROOT})`);
});
