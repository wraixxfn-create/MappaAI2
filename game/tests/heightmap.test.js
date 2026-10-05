/**
 * Decodifica della heightmap PNG prodotta da game/tools/export_map.py.
 * Il PNG è scritto a mano dallo script (zlib + chunk), quindi il test
 * verifica sia il formato sia i valori che il gioco userà per la minimappa.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { inflateSync } from 'node:zlib';
import { createHeightField, regionToGame } from '../src/heightfield.js';

const PNG = new URL('../public/heightmap.png', import.meta.url);

function decodePNG(buffer) {
  assert.deepEqual([...buffer.subarray(0, 8)], [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a],
    'firma PNG mancante');
  let offset = 8;
  let header = null;
  const idat = [];
  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.toString('ascii', offset + 4, offset + 8);
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      header = {
        width: data.readUInt32BE(0),
        height: data.readUInt32BE(4),
        bitDepth: data[8],
        colorType: data[9],
        interlace: data[12],
      };
    } else if (type === 'IDAT') {
      idat.push(data);
    } else if (type === 'IEND') {
      break;
    }
    offset += 12 + length;
  }
  assert.ok(header, 'chunk IHDR mancante');
  assert.equal(header.bitDepth, 8);
  assert.equal(header.colorType, 6, 'atteso RGBA');
  assert.equal(header.interlace, 0, 'niente interlacciamento');

  const raw = inflateSync(Buffer.concat(idat));
  const { width, height } = header;
  const stride = width * 4;
  const out = new Uint8Array(width * height * 4);
  const prev = new Uint8Array(stride);
  const line = new Uint8Array(stride);
  for (let y = 0; y < height; y += 1) {
    const filter = raw[y * (stride + 1)];
    const row = raw.subarray(y * (stride + 1) + 1, y * (stride + 1) + 1 + stride);
    for (let x = 0; x < stride; x += 1) {
      const a = x >= 4 ? line[x - 4] : 0;
      const b = prev[x];
      const c = x >= 4 ? prev[x - 4] : 0;
      let v = row[x];
      if (filter === 1) v += a;
      else if (filter === 2) v += b;
      else if (filter === 3) v += (a + b) >> 1;
      else if (filter === 4) {
        const p = a + b - c;
        const pa = Math.abs(p - a);
        const pb = Math.abs(p - b);
        const pc = Math.abs(p - c);
        v += pa <= pb && pa <= pc ? a : (pb <= pc ? b : c);
      }
      line[x] = v & 0xff;
    }
    out.set(line, y * stride);
    prev.set(line);
  }
  return { width, height, data: out };
}

test('heightmap.png è un PNG RGBA valido e delle dimensioni dichiarate', async () => {
  const scene = JSON.parse(await readFile(new URL('../public/scene.json', import.meta.url), 'utf8'));
  const png = decodePNG(await readFile(PNG));
  assert.equal(png.width, scene.heightmap.width);
  assert.equal(png.height, scene.heightmap.height);
  assert.equal(png.data.length, png.width * png.height * 4);
});

test('le altezze della heightmap seguono il terreno della valle', async () => {
  const scene = JSON.parse(await readFile(new URL('../public/scene.json', import.meta.url), 'utf8'));
  const png = decodePNG(await readFile(PNG));
  const field = createHeightField(regionToGame(scene.heightmap), png.data);

  const spawn = scene.spawn.position;
  const atSpawn = field.heightAt(spawn[0], spawn[2]);
  assert.ok(Number.isFinite(atSpawn), 'nessuna altezza allo spawn');
  assert.ok(atSpawn > -4 && atSpawn < 20, `altezza allo spawn improbabile: ${atSpawn}`);
  assert.equal(field.has(spawn[0], spawn[2]), true, 'lo spawn è fuori dalla mappa');

  // La valle sale verso i bordi: il terreno lontano è più alto della soglia.
  const atGate = field.heightAt(scene.gate.position[0], scene.gate.position[2]);
  const atEdge = field.heightAt(-140, -90);
  assert.equal(field.has(-140, -90), true, 'il bordo sud-ovest è fuori mappa');
  assert.ok(atEdge > atGate + 1, `bordo (${atEdge}) non più alto della soglia (${atGate})`);

  // Il terreno copre una buona parte della regione esportata.
  let covered = 0;
  for (let i = 0; i < field.valid.length; i += 1) covered += field.valid[i];
  assert.ok(covered / field.valid.length > 0.3,
    `copertura del terreno troppo bassa: ${(covered / field.valid.length * 100).toFixed(1)}%`);

  // Il calore è concentrato dove il modello mette lava e bracieri.
  const heatGate = field.heatAt(0, 0);
  const heatFar = field.heatAt(140, -90);
  assert.ok(heatGate > heatFar, `calore alla porta (${heatGate}) non maggiore che altrove (${heatFar})`);
});
