/**
 * Test di integrazione sugli asset realmente esportati dal .blend:
 * geometria, BVH, fisica del giocatore, cardini, zone di fuoco.
 *
 *   node --test --import ./tests/register.js "tests/*.test.js"
 */
import test, { before } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { mergeToGeometry, collectHazards, isHazardMaterial } from '../src/world.js';
import {
  DOOR_BARRIER, Capsule, applyDoorBarrier, buildBVH, groundHeightAt, stepCapsule,
} from '../src/physics.js';

const ctx = {};

async function parseGLB(file) {
  const buffer = await readFile(new URL(`../public/${file}`, import.meta.url));
  const data = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  return new Promise((resolve, reject) => {
    loader.parse(data, '', (gltf) => resolve(gltf), reject);
  });
}

before(async () => {
  ctx.scene = JSON.parse(await readFile(new URL('../public/scene.json', import.meta.url), 'utf8'));
  ctx.collision = await parseGLB('collision.glb');
  ctx.map = await parseGLB('map.glb');
  ctx.geometry = mergeToGeometry(ctx.collision.scene);
  assert.ok(ctx.geometry, 'la mesh di collisione è vuota');
  ctx.bvh = buildBVH(ctx.geometry);
});

test('scene.json descrive la scena esportata', () => {
  const { scene } = ctx;
  assert.equal(scene.source, 'porta_dell_inferno.blend');
  assert.ok(scene.lights.length >= 24, `luci: ${scene.lights.length}`);
  assert.equal(scene.points_of_interest.length, 7, 'le sette anime della scena');
  assert.equal(scene.hinges.length, 2);
  assert.match(scene.inscription.text, /LASCIATE OGNI SPERANZA/);
  assert.ok(scene.spawn.eye_height > 1.4);
  assert.ok(scene.gate.radius > 1);
  for (const poi of scene.points_of_interest) {
    assert.equal(poi.position.length, 3);
    assert.ok(poi.verse.length > 10, `verso mancante per ${poi.id}`);
    assert.match(poi.canto, /Inferno/);
  }
});

test('le coordinate sono già nello spazio di gioco (Y in alto)', () => {
  // Il monumento sta a z ≈ 0 e il pellegrino a sud: in Blender era y = -29,5.
  const pilgrim = ctx.scene.points_of_interest.find((p) => p.id.startsWith('pellegrino'));
  assert.ok(pilgrim.position[2] > 20, `il pellegrino è a sud della porta (z=${pilgrim.position[2]})`);
  assert.ok(Math.abs(ctx.scene.gate.position[2]) < 6, 'la soglia sta vicino all’origine');
  assert.ok(ctx.scene.bounds.max[1] > 25, `il monumento supera i 25 m (top=${ctx.scene.bounds.max[1]})`);
});

test('la geometria esportata non è schiacciata dalla quantizzazione', () => {
  // Regressione: quantizzando le posizioni a pochi bit il mondo diventa un
  // piano e la fisica sembra funzionare lo stesso. Le tre dimensioni devono
  // essere tutte da decine di metri.
  const box = ctx.geometry.boundingBox;
  const size = box.getSize(new THREE.Vector3());
  assert.ok(size.y > 20, `il mondo è alto solo ${size.y.toFixed(2)} m: posizioni quantizzate male`);
  assert.ok(size.x > 100, `il mondo è largo solo ${size.x.toFixed(2)} m`);
  assert.ok(size.z > 100, `il mondo è profondo solo ${size.z.toFixed(2)} m`);
  assert.ok(size.y < 200 && size.x < 800 && size.z < 800, `dimensioni assurde: ${size.toArray()}`);
  assert.ok(box.max.y > 25, `la cima del monumento è a ${box.max.y.toFixed(1)} m`);
});

test('il terreno è un rilievo, non un piano', () => {
  // Campiona il suolo lungo la valle: le quote devono variare di parecchi metri.
  const samples = [];
  for (let z = -60; z <= 60; z += 10) {
    for (const x of [-80, -30, 0, 30, 80]) {
      const h = groundHeightAt(ctx.bvh, x, z);
      if (h !== null) samples.push(h);
    }
  }
  assert.ok(samples.length > 30, `pochi campioni di terreno: ${samples.length}`);
  const min = Math.min(...samples);
  const max = Math.max(...samples);
  assert.ok(max - min > 3, `il terreno è piatto: quote da ${min.toFixed(2)} a ${max.toFixed(2)}`);
  assert.ok(min > -20 && max < 80, `quote fuori scala: ${min.toFixed(1)} … ${max.toFixed(1)}`);
});

test('la mesh di collisione è solida e ha un BVH', () => {
  const triangles = ctx.geometry.index.count / 3;
  assert.ok(triangles > 20000, `troppi pochi triangoli: ${triangles}`);
  assert.ok(triangles < 500000, `troppi triangoli: ${triangles}`);
  assert.ok(ctx.geometry.attributes.position.count > 1000);
  assert.ok(ctx.bvh, 'BVH non costruito');
  assert.ok(Number.isFinite(ctx.geometry.boundingBox.min.y));
});

test('sotto lo spawn c’è terreno', () => {
  const [x, y, z] = ctx.scene.spawn.position;
  const ground = groundHeightAt(ctx.bvh, x, z);
  assert.notEqual(ground, null, 'nessun terreno sotto il punto di nascita');
  assert.ok(Math.abs(ground - y) < 6, `spawn a ${y}, terreno a ${ground}`);
});

test('il giocatore cade, atterra e resta in piedi', () => {
  const [x, y, z] = ctx.scene.spawn.position;
  const ground = groundHeightAt(ctx.bvh, x, z);
  const capsule = new Capsule({ position: [x, ground + 2.5, z] });
  for (let i = 0; i < 180; i += 1) {
    stepCapsule(ctx.bvh, capsule, 1 / 60, { move: new THREE.Vector3() });
  }
  assert.equal(capsule.grounded, true, 'dopo la caduta il giocatore è a terra');
  assert.ok(Math.abs(capsule.position.y - ground) < 0.45,
    `piedi a ${capsule.position.y.toFixed(2)}, terreno a ${ground.toFixed(2)}`);
  assert.ok(Math.abs(capsule.velocity.y) < 0.01, 'la velocità verticale si è annullata');
});

test('si cammina verso la porta senza attraversare il mondo', () => {
  const [x, y, z] = ctx.scene.spawn.position;
  const ground = groundHeightAt(ctx.bvh, x, z);
  const capsule = new Capsule({ position: [x, ground + 0.4, z] });
  const startZ = capsule.position.z;
  let walked = 0;
  const forward = new THREE.Vector3(0, 0, -1);
  for (let i = 0; i < 60 * 8; i += 1) {
    const r = stepCapsule(ctx.bvh, capsule, 1 / 60, { move: forward });
    walked += r.horizontal;
    assert.ok(capsule.position.y > -5, `il giocatore è caduto nel vuoto a y=${capsule.position.y}`);
  }
  assert.ok(capsule.position.z < startZ - 8,
    `avanzando di 8 s verso la porta ci si sposta di ${(startZ - capsule.position.z).toFixed(1)} m`);
  assert.ok(walked > 12, `percorso ${walked.toFixed(1)} m`);

  // Camminando verso la porta si sale sulla scalinata cerimoniale: i piedi
  // possono stare più in alto del terreno, ma non sotto né sospesi nel vuoto.
  const underFeet = groundHeightAt(ctx.bvh, capsule.position.x, capsule.position.z, capsule.position.y + 3, 12);
  assert.notEqual(underFeet, null, 'sotto i piedi non c’è più terreno');
  assert.equal(capsule.grounded, true, 'il giocatore non è appoggiato: sta cadendo');
  assert.ok(capsule.position.y > underFeet - 0.4,
    `il giocatore è affondato nel terreno (${capsule.position.y} vs ${underFeet})`);
  assert.ok(capsule.position.y < underFeet + 2.5,
    `il giocatore è sospeso a ${(capsule.position.y - underFeet).toFixed(2)} m dal suolo`);
});

test('davanti alla soglia ci sono il pavimento e i battenti', () => {
  // La soglia è il punto in cui il giocatore si ferma a spingere: deve avere
  // il suolo sotto i piedi e i battenti davanti.
  const gate = ctx.scene.gate.position;
  // Sotto la soglia passa l'arco: un raggio dall'alto incontrerebbe prima la
  // volta. Il suolo calpestabile si trova lasciando cadere una capsula.
  const probe = new Capsule({ position: [gate[0], gate[1] + 3, gate[2]] });
  for (let i = 0; i < 300 && !probe.grounded; i += 1) {
    stepCapsule(ctx.bvh, probe, 1 / 60, { move: new THREE.Vector3() });
  }
  assert.equal(probe.grounded, true, 'alla soglia non c’è un piano di calpestio');
  const ground = probe.position.y;
  assert.ok(Math.abs(ground - gate[1]) < 3,
    `la soglia dichiara y=${gate[1]} ma il suolo è a ${ground}`);

  // Spingendo in avanti non si deve oltrepassare i battenti: la mesh, ridotta
  // per la fisica, lascia fessure, quindi il varco è presidiato dalla sbarra
  // che il gioco applica a ogni passo.
  const push = new THREE.Vector3(0, 0, -1);
  for (let i = 0; i < 60 * 6; i += 1) {
    stepCapsule(ctx.bvh, probe, 1 / 60, { move: push, jump: i % 40 === 0 }, { maxSpeed: 4.2 });
    applyDoorBarrier(probe, 0);
  }
  assert.ok(probe.position.z > DOOR_BARRIER.z,
    `il giocatore ha oltrepassato i battenti: z=${probe.position.z.toFixed(2)}`);
});

test('il modello visivo ha i cardini animabili e l’iscrizione', () => {
  const root = ctx.map.scene;
  const left = root.getObjectByName('CardineBattenteSinistro');
  const right = root.getObjectByName('CardineBattenteDestro');
  const inscription = root.getObjectByName('Iscrizione');
  assert.ok(left && right, 'mancano i cardini dei battenti');
  assert.ok(inscription, 'manca l’iscrizione');
  let doorTris = 0;
  left.traverse((o) => { if (o.isMesh) doorTris += o.geometry.index.count / 3; });
  assert.ok(doorTris > 1000, `battente sinistro troppo vuoto: ${doorTris}`);
  assert.ok(Math.abs(left.position.x + right.position.x) < 0.01, 'i cardini sono simmetrici');
});

test('i battenti sono chiusi nel modello esportato', () => {
  // Nel .blend sono socchiusi: l'esportatore li chiude (varco sbarrato).
  const root = ctx.map.scene;
  root.updateMatrixWorld(true);
  const left = root.getObjectByName('CardineBattenteSinistro');
  const right = root.getObjectByName('CardineBattenteDestro');
  const boxL = new THREE.Box3().setFromObject(left);
  const boxR = new THREE.Box3().setFromObject(right);
  const gap = boxR.min.x - boxL.max.x;
  assert.ok(gap < 0.68,
    `il varco tra i battenti è di ${gap.toFixed(2)} m: il giocatore (0,68 m) passa`);
  assert.ok(gap > -0.5, `i battenti si compenetrano: ${gap.toFixed(2)} m`);
});

test('ruotando il cardine il battente si muove', () => {
  const root = ctx.map.scene;
  const left = root.getObjectByName('CardineBattenteSinistro');
  root.updateMatrixWorld(true);
  const before = new THREE.Box3().setFromObject(left).getCenter(new THREE.Vector3());
  const rest = left.rotation.y;
  left.rotation.y = rest - 0.6;
  root.updateMatrixWorld(true);
  const after = new THREE.Box3().setFromObject(left).getCenter(new THREE.Vector3());
  left.rotation.y = rest;
  root.updateMatrixWorld(true);
  assert.ok(before.distanceTo(after) > 0.5,
    `il battente non ruota col cardine (${before.distanceTo(after).toFixed(3)} m)`);
});

test('i colori per vertice (AO e cenere) sono nel modello', () => {
  let withColor = 0;
  let total = 0;
  ctx.map.scene.traverse((o) => {
    if (!o.isMesh) return;
    total += 1;
    const g = o.geometry;
    if (g.attributes.color || g.attributes.color1) withColor += 1;
  });
  assert.equal(withColor, total, `solo ${withColor}/${total} mesh hanno il colore per vertice`);
});

test('le superfici di fuoco sono individuabili e attraversabili', () => {
  assert.equal(isHazardMaterial('Lava | crosta nera, vene incandescenti e cenere'), true);
  assert.equal(isHazardMaterial('Fiamma | arancio infernale'), true);
  assert.equal(isHazardMaterial('Terreno vulcanico | cenere nera e ossidiana'), false);
  const hazards = collectHazards(ctx.map.scene);
  assert.ok(hazards, 'nessuna geometria di fuoco trovata');
  const tris = hazards.index.count / 3;
  assert.ok(tris > 20 && tris < 60000, `geometria di fuoco improbabile: ${tris} triangoli`);
  const bvh = buildBVH(hazards);
  // Dentro la colata oltre la soglia il fuoco si sente; sullo spawn no.
  const [sx, sy, sz] = ctx.scene.spawn.position;
  const raySpawn = new THREE.Ray(new THREE.Vector3(sx, sy + 2, sz), new THREE.Vector3(0, -1, 0));
  assert.equal(bvh.raycastFirst(raySpawn, THREE.DoubleSide, 0, 4), null, 'fuoco sullo spawn');
});

test('le luci della scena coprono la porta e la valle', () => {
  const lamps = ctx.scene.lights;
  const warm = lamps.filter((l) => l.color[0] - l.color[2] > 0.25);
  assert.ok(warm.length >= 15, `luci calde: ${warm.length}`);
  const nearGate = warm.filter((l) => Math.hypot(l.position[0], l.position[2]) < 25);
  assert.ok(nearGate.length >= 6, `luci calde vicino alla porta: ${nearGate.length}`);
  const strongest = lamps.reduce((a, b) => (b.power_watt > a.power_watt ? b : a));
  assert.ok(strongest.power_watt > 5000, `luce più forte: ${strongest.power_watt} W`);
  for (const l of lamps) {
    assert.ok(Number.isFinite(l.position[0]) && Number.isFinite(l.position[1]) && Number.isFinite(l.position[2]));
    assert.ok(l.intensity > 0, `intensità nulla per ${l.name}`);
  }
});
