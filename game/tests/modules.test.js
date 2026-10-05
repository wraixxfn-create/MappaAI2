/**
 * Smoke test dei moduli che girano nel browser: import, costruzione e passo di
 * simulazione. Non serve WebGL — three costruisce scene e geometrie anche qui.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import * as THREE from 'three';
import { Player } from '../src/player.js';
import { Particles, smokeSources } from '../src/particles.js';
import { Ambience } from '../src/audio.js';
import { Hud, Screens } from '../src/hud.js';
import { LightRig, createSky, isHazardMaterial } from '../src/world.js';

const sceneData = JSON.parse(await readFile(new URL('../public/scene.json', import.meta.url), 'utf8'));

test('tutti i moduli del gioco si caricano', () => {
  assert.equal(typeof Player, 'function');
  assert.equal(typeof Particles, 'function');
  assert.equal(typeof Ambience, 'function');
  assert.equal(typeof Hud, 'function');
  assert.equal(typeof Screens, 'function');
  assert.equal(typeof LightRig, 'function');
});

test('il cielo è una volta chiusa con gradiente', () => {
  const sky = createSky();
  assert.ok(sky.isMesh);
  assert.equal(sky.material.side, THREE.BackSide);
  const colors = sky.geometry.attributes.color;
  assert.equal(colors.count, sky.geometry.attributes.position.count);
  let bright = 0;
  for (let i = 0; i < colors.count; i += 1) if (colors.getX(i) > 0.05) bright += 1;
  assert.ok(bright > 100, 'il gradiente del cielo è piatto');
});

test('le luci della scena vengono assegnate per vicinanza', () => {
  const scene = new THREE.Scene();
  const rig = new LightRig(scene, sceneData, { budget: 6 });
  assert.equal(rig.lights.length, 6);
  assert.ok(rig.lamps.length >= 24);

  const gate = new THREE.Vector3(...sceneData.gate.position);
  rig.update(gate, 0.016);
  const visible = rig.lights.filter((l) => l.visible);
  assert.ok(visible.length >= 3, `solo ${visible.length} luci visibili alla porta`);
  assert.ok(visible.every((l) => l.intensity > 0), 'una luce visibile ha intensità nulla');

  const heatGate = rig.heatAt(gate);
  const heatFar = rig.heatAt(new THREE.Vector3(120, 2, 40));
  assert.ok(heatGate > heatFar * 5,
    `la soglia (${heatGate.toFixed(1)}) non è molto più calda del bordo (${heatFar.toFixed(1)})`);
  assert.ok(rig.nearestWarm(gate).distance < 30);
});

test('lo sfarfallio del fuoco cambia le intensità nel tempo', () => {
  const scene = new THREE.Scene();
  const rig = new LightRig(scene, sceneData, { budget: 4 });
  const gate = new THREE.Vector3(...sceneData.gate.position);
  rig.update(gate, 0.016);
  const first = rig.lights.map((l) => l.intensity);
  for (let i = 0; i < 40; i += 1) rig.update(gate, 0.05);
  const later = rig.lights.map((l) => l.intensity);
  assert.ok(first.some((v, i) => Math.abs(v - later[i]) > 1e-4), 'il fuoco non sfarfalla');
});

test('braci, cenere e fumo si muovono e restano finiti', () => {
  const scene = new THREE.Scene();
  const particles = new Particles(scene, sceneData, null, { embers: 300, ash: 400, smoke: 60 });
  const camera = new THREE.Vector3(9.2, 1.7, 44);
  const before = particles.embers.geometry.attributes.position.array.slice(0, 30);
  for (let i = 0; i < 90; i += 1) particles.update(1 / 60, camera);
  const after = particles.embers.geometry.attributes.position.array;
  let moved = 0;
  for (let i = 0; i < before.length; i += 1) if (Math.abs(before[i] - after[i]) > 1e-4) moved += 1;
  assert.ok(moved > 10, `solo ${moved} coordinate di brace si sono mosse`);
  for (const key of ['embers', 'ash', 'smoke']) {
    const arr = particles[key].geometry.attributes.position.array;
    for (let i = 0; i < arr.length; i += 1) {
      assert.ok(Number.isFinite(arr[i]), `${key}: coordinate non finita in ${i}`);
    }
  }
  particles.setEnabled(false);
  assert.equal(particles.embers.visible, false);
});

test('le sorgenti di fumo vengono dalle luci della scena', () => {
  const sources = smokeSources(sceneData);
  assert.ok(sources.length >= 2, `sorgenti di fumo: ${sources.length}`);
  assert.ok(sources.every((s) => s.isVector3 && Number.isFinite(s.y)));
});

test('il giocatore legge i tasti e produce una direzione', () => {
  const camera = new THREE.PerspectiveCamera(70, 1.5, 0.1, 100);
  const capsule = { position: new THREE.Vector3(), velocity: new THREE.Vector3(), radius: 0.34, height: 1.78 };
  const player = new Player({ camera, capsule, dom: {}, audio: null });
  player.setLook(0, 0); // guarda verso -Z
  player.keys.add('KeyW');
  const wish = player.readWish(new THREE.Vector3());
  assert.ok(wish.z < -0.9, `avanti con yaw 0 deve andare verso -Z, invece ${wish.z}`);
  player.keys.clear();
  player.keys.add('KeyD');
  const right = player.readWish(new THREE.Vector3());
  assert.ok(right.x > 0.9, `la destra con yaw 0 deve essere +X, invece ${right.x}`);
  player.setLook(Math.PI / 2, 0); // guarda verso -X
  player.keys.clear();
  player.keys.add('KeyW');
  const turned = player.readWish(new THREE.Vector3());
  assert.ok(turned.x < -0.9, `ruotando di 90° avanti deve andare verso -X, invece ${turned.x}`);
  player.dispose();
});

test('l’audio si costruisce anche senza contesto e non esplode', () => {
  const audio = new Ambience();
  assert.equal(audio.init(), null, 'senza AudioContext non deve creare nulla');
  audio.setEnabled(false);
  audio.setHeat(0.8);
  audio.update(0.016);
  audio.footstep(true);
  audio.sigil(1);
  audio.door();
  audio.death();
  audio.ending();
});

test('i materiali di fuoco sono riconosciuti', () => {
  assert.equal(isHazardMaterial('Magma | vena incandescente tra i conci'), true);
  assert.equal(isHazardMaterial('Bronzo annerito | patina, ossidi e colature'), false);
});
