/** Campionamento della heightmap e proiezione sulla minimappa. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createHeightField, regionToGame, worldToMap } from '../src/heightfield.js';

/** Campo sintetico 4x2: altezza crescente lungo x, calore su una cella. */
function synthetic() {
  const width = 4;
  const height = 2;
  const meta = { width, height, region: [-10, -20, 10, 20], zRange: [0, 10] };
  const rgba = new Uint8Array(width * height * 4);
  for (let i = 0; i < width * height; i += 1) {
    const x = i % width;
    const q = Math.round((x / 3) * 65535 * 0.5); // da 0 a 5 m
    rgba[i * 4] = (q >> 8) & 0xff;
    rgba[i * 4 + 1] = q & 0xff;
    rgba[i * 4 + 2] = i === width * height - 1 ? 255 : 0;
    rgba[i * 4 + 3] = 255;
  }
  return createHeightField(meta, rgba);
}

test('la regione Blender diventa regione di gioco con z invertita', () => {
  const meta = { width: 2, height: 2, region: [-150, -62, 150, 95], zRange: [-4, 58] };
  const game = regionToGame(meta);
  assert.deepEqual(game.region, [-150, -95, 150, 62]);
});

test('altezza e calore si campionano nel punto giusto', () => {
  const field = synthetic();
  assert.ok(Math.abs(field.heightAt(-10, 0) - 0) < 0.2, 'a ovest il terreno è basso');
  assert.ok(Math.abs(field.heightAt(10, 0) - 5) < 0.2, 'a est il terreno è alto');
  assert.equal(field.heatAt(10, 20), 1, 'cella calda');
  assert.equal(field.heatAt(-10, -20), 0, 'cella fredda');
});

test('fuori dalla regione si ottiene il valore di riserva', () => {
  const field = synthetic();
  assert.equal(field.heightAt(999, 999), 0);
  assert.equal(field.has(999, 999), false);
  assert.equal(field.has(0, 0), true);
});

test('la proiezione sulla mappa rispetta i bordi', () => {
  const field = synthetic();
  const [x0, z0] = worldToMap(field, 400, 200, -10, -20);
  const [x1, z1] = worldToMap(field, 400, 200, 10, 20);
  assert.deepEqual([x0, z0], [0, 0]);
  assert.deepEqual([x1, z1], [400, 200]);
  const [xc, zc] = worldToMap(field, 400, 200, 0, 0);
  assert.deepEqual([xc, zc], [200, 100]);
});
