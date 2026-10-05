/**
 * Partita simulata: percorre davvero la valle con la fisica del gioco, senza
 * WebGL. Serve a garantire che la mappa sia percorribile e che la speranza
 * non si azzeri prima di arrivare alla soglia.
 */
import test, { before } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { mergeToGeometry } from '../src/world.js';
import {
  DOOR_BARRIER, Capsule, applyDoorBarrier, buildBVH, groundHeightAt, stepCapsule,
} from '../src/physics.js';
import { GameState, RULES } from '../src/objectives.js';

const ctx = {};

async function parseGLB(file) {
  const buffer = await readFile(new URL(`../public/${file}`, import.meta.url));
  const data = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  return new Promise((res, rej) => loader.parse(data, '', res, rej));
}

before(async () => {
  ctx.data = JSON.parse(await readFile(new URL('../public/scene.json', import.meta.url), 'utf8'));
  const gltf = await parseGLB('collision.glb');
  ctx.bvh = buildBVH(mergeToGeometry(gltf.scene));
});

/**
 * Cammina verso un obiettivo: restituisce il percorso e la speranza finale.
 * `walkTo` è deliberatamente semplice (vai dritto, scavalca i piccoli ostacoli)
 * — se un punto fosse irraggiungibile, il test lo direbbe.
 */
function playthrough({ route, maxSeconds = 420, speed = 3.6 }) {
  const data = ctx.data;
  const spawn = data.spawn.position;
  const ground = groundHeightAt(ctx.bvh, spawn[0], spawn[2]);
  const capsule = new Capsule({ position: [spawn[0], (ground ?? spawn[1]) + 0.1, spawn[2]] });
  const game = new GameState({
    points: data.points_of_interest,
    gate: data.gate,
    spawn: data.spawn,
  });
  game.start();

  // Le stesse luci calde usate dal gioco per il calore.
  const warm = data.lights
    .filter((l) => l.color[0] - l.color[2] > 0.25)
    .map((l) => ({ position: new THREE.Vector3(...l.position), power: l.power_watt }));
  const heatAt = (p) => {
    let heat = 0;
    for (const l of warm) heat += l.power / (l.position.distanceToSquared(p) + 4);
    return heat;
  };

  const dt = 1 / 60;
  const steps = Math.round(maxSeconds / dt);
  const wish = new THREE.Vector3();
  const log = [];
  let targetIndex = 0;
  // Raggio di arrivo di ogni tappa: le anime si raccolgono a 1,6 m, la soglia
  // basta raggiungerla entro il raggio d'azione del gioco.
  const reach = route.map((r) => (r.gate ? RULES.gateRadius : 1.6));
  let seconds = 0;
  let stuckFor = 0;
  let stuckTotal = 0;
  let minHope = game.hope;

  for (let i = 0; i < steps; i += 1) {
    const target = route[targetIndex];
    const targetVec = new THREE.Vector3(...(target.position ?? target));
    const flat = new THREE.Vector3(targetVec.x - capsule.position.x, 0, targetVec.z - capsule.position.z);
    const distance = flat.length();
    if (distance < reach[targetIndex]) {
      log.push({ reached: targetIndex, seconds: +seconds.toFixed(1), hope: +game.hope.toFixed(1) });
      targetIndex += 1;
      if (targetIndex >= route.length) break;
      continue;
    }
    flat.normalize();
    wish.copy(flat);
    const before = capsule.position.clone();
    stepCapsule(ctx.bvh, capsule, dt, { move: wish, jump: false }, { maxSpeed: speed });
    applyDoorBarrier(capsule, game.doorsOpen);
    const moved = capsule.position.distanceTo(before);
    stuckFor = moved < 0.004 ? stuckFor + dt : 0;
    // Se resta incastrato, salta (come farebbe chi gioca) per scavalcare.
    if (stuckFor > 0.5 && capsule.grounded) {
      stepCapsule(ctx.bvh, capsule, dt, { move: wish, jump: true }, { maxSpeed: speed });
      applyDoorBarrier(capsule, game.doorsOpen);
      stuckFor = 0;
      stuckTotal += 1;
    }
    seconds += dt;
    // Il giocatore raccoglie l'anima quando ci passa vicino (tasto E).
    const near = game.nearestPoint(capsule.position);
    if (near) game.collect(near);
    game.update(dt, { heat: heatAt(capsule.position), inFire: false });
    minHope = Math.min(minHope, game.hope);
    if (game.state !== 'playing') break;
  }

  return {
    game,
    seconds,
    log,
    minHope,
    stuckTotal,
    reached: targetIndex,
    total: route.length,
    position: capsule.position.clone(),
  };
}

test('si può camminare dallo spawn fino alla soglia senza morire', () => {
  const data = ctx.data;
  const gate = data.gate.position;
  const pilgrim = data.points_of_interest.find((p) => p.id.startsWith('pellegrino')).position;
  const result = playthrough({
    route: [
      pilgrim,
      { position: [gate[0], gate[1], gate[2] + 6] },
      { position: [gate[0], gate[1], gate[2]], gate: true },
    ],
  });

  assert.equal(result.reached, result.total,
    `fermato alla tappa ${result.reached}/${result.total} dopo ${result.seconds.toFixed(0)}s ` +
    `in ${result.position.toArray().map((v) => v.toFixed(1))}`);
  assert.ok(result.game.hope > 0,
    `la speranza si è azzerata al secondo ${result.seconds.toFixed(0)} (minima ${result.minHope.toFixed(1)})`);
  assert.ok(result.seconds < 300, `il percorso dura troppo: ${result.seconds.toFixed(0)}s`);
  // Deve restare una sfida: la speranza deve comunque calare un po'.
  assert.ok(result.minHope < RULES.hopeStart,
    'la speranza non scende mai: il buio non pesa');
});

test('si può visitare tutte e sette le anime e aprire i battenti', () => {
  const data = ctx.data;
  const gate = data.gate.position;
  // Ordine: dalla più lontana (il pellegrino) fino ai gradini, poi la soglia.
  const order = ['pellegrino', 'anima-in-cammino-1', 'anima-in-cammino-2', 'anima-in-cammino-3',
    'dannato-che-arranca-sul-selciato', 'dannato-curvo-sul-gradino',
    'dannato-inginocchiato-sui-gradini'];
  const route = order.map((prefix) => {
    const poi = data.points_of_interest.find((p) => p.id.startsWith(prefix));
    assert.ok(poi, `anima mancante: ${prefix}`);
    return poi.position;
  });
  route.push({ position: [gate[0], gate[1], gate[2]], gate: true });

  const result = playthrough({ route, maxSeconds: 900, speed: 4.2 });
  const { game } = result;

  assert.equal(result.reached, result.total,
    `arrivato solo a ${result.reached}/${result.total} tappe in ${result.seconds.toFixed(0)}s`);
  assert.ok(game.hope > 0, `la speranza è finita (minima ${result.minHope.toFixed(1)})`);

  assert.equal(game.collected, game.total,
    `raccolte solo ${game.collected} anime su ${game.total} lungo il percorso`);
  assert.equal(game.allCollected, true, 'manca qualche anima: i battenti restano chiusi');
  assert.equal(game.beginOpening(), true, 'i battenti non si aprono');
  assert.ok(game.gateDistance(result.position) < RULES.gateRadius + 2,
    `non si arriva alla soglia: ${game.gateDistance(result.position).toFixed(1)} m`);
});

test('ogni anima è raggiungibile a piedi dal suo vicino', () => {
  const data = ctx.data;
  const points = data.points_of_interest;
  const spawn = data.spawn.position;
  // Ordina per distanza dal punto di partenza: un giro plausibile.
  const remaining = points.map((p) => ({ p, position: new THREE.Vector3(...p.position) }));
  const route = [];
  let from = new THREE.Vector3(spawn[0], spawn[1], spawn[2]);
  while (remaining.length) {
    let best = 0;
    let bestD = Infinity;
    remaining.forEach((item, i) => {
      const d = from.distanceTo(item.position);
      if (d < bestD) { bestD = d; best = i; }
    });
    const [next] = remaining.splice(best, 1);
    route.push(next.p.position);
    from = next.position;
  }
  route.push({ position: [data.gate.position[0], data.gate.position[1], data.gate.position[2]], gate: true });
  const result = playthrough({ route, maxSeconds: 900, speed: 4.2 });
  assert.equal(result.reached, result.total,
    `raggiunte solo ${result.reached}/${result.total} anime ` +
    `(ultima posizione ${result.position.toArray().map((v) => v.toFixed(1))})`);
  assert.ok(result.game.hope > 0, `morto di buio dopo ${result.seconds.toFixed(0)}s`);
});

test('i battenti chiusi sbarrano il passaggio', () => {
  // Con i battenti chiusi il giocatore non deve riuscire a entrare nel varco,
  // nemmeno spingendo e saltando contro la porta.
  const capsule = new Capsule({ position: [0, 1.5, 8] });
  const dir = new THREE.Vector3(0, 0, -1);
  for (let i = 0; i < 60 * 25; i += 1) {
    stepCapsule(ctx.bvh, capsule, 1 / 60, { move: dir, jump: i % 40 === 0 }, { maxSpeed: 4.4 });
    applyDoorBarrier(capsule, 0);
  }
  assert.ok(capsule.position.z > DOOR_BARRIER.z,
    `il giocatore è passato oltre i battenti: z=${capsule.position.z.toFixed(2)}`);
  assert.ok(Math.abs(capsule.position.x) < 12, 'il giocatore è scivolato fuori dal portale');
});

test('con i battenti spalancati il varco è libero', () => {
  const capsule = new Capsule({ position: [0, 1.5, 8] });
  const dir = new THREE.Vector3(0, 0, -1);
  let blocked = 0;
  for (let i = 0; i < 60 * 25; i += 1) {
    stepCapsule(ctx.bvh, capsule, 1 / 60, { move: dir, jump: i % 40 === 0 }, { maxSpeed: 4.4 });
    if (applyDoorBarrier(capsule, 1)) blocked += 1;
  }
  assert.equal(blocked, 0, 'la sbarra continua a respingere anche a porte aperte');
  assert.ok(capsule.position.z < DOOR_BARRIER.z,
    `a porte aperte non si passa: z=${capsule.position.z.toFixed(2)}`);
});

test('dalla soglia si può interagire con i battenti', () => {
  // Il giocatore fermo davanti ai battenti chiusi deve essere nel raggio
  // d'azione previsto dalle regole, altrimenti "spingi i battenti" è inutile.
  const data = ctx.data;
  const game = new GameState({ points: data.points_of_interest, gate: data.gate, spawn: data.spawn });
  game.start();
  game.points.forEach((p) => { p.taken = true; });
  const capsule = new Capsule({ position: [0, 1.5, 8] });
  const dir = new THREE.Vector3(0, 0, -1);
  let stuck = 0;
  for (let i = 0; i < 60 * 25; i += 1) {
    const before = capsule.position.clone();
    stepCapsule(ctx.bvh, capsule, 1 / 60, { move: dir, jump: false }, { maxSpeed: 4.0 });
    applyDoorBarrier(capsule, game.doorsOpen);
    stuck = capsule.position.distanceTo(before) < 0.004 ? stuck + 1 / 60 : 0;
    // La scalinata si sale saltando, come farebbe chi gioca.
    if (stuck > 0.5 && capsule.grounded) {
      stepCapsule(ctx.bvh, capsule, 1 / 60, { move: dir, jump: true }, { maxSpeed: 4.0 });
      applyDoorBarrier(capsule, game.doorsOpen);
      stuck = 0;
    }
  }
  const action = game.interactionAt(capsule.position);
  assert.ok(action, `nessuna interazione disponibile a ${capsule.position.toArray().map((v) => v.toFixed(1))}`);
  assert.equal(action.kind, 'gate-open', `interazione inattesa: ${action.kind}`);
});

test('le anime sono distribuite nella valle, non ammassate', () => {
  const points = ctx.data.points_of_interest.map((p) => new THREE.Vector3(...p.position));
  let minDistance = Infinity;
  for (let i = 0; i < points.length; i += 1) {
    for (let j = i + 1; j < points.length; j += 1) {
      minDistance = Math.min(minDistance, points[i].distanceTo(points[j]));
    }
  }
  assert.ok(minDistance > RULES.poiRadius * 1.5,
    `due anime sono troppo vicine: ${minDistance.toFixed(2)} m`);
  const spread = Math.max(...points.map((p) => p.z)) - Math.min(...points.map((p) => p.z));
  assert.ok(spread > 15, `le anime occupano solo ${spread.toFixed(1)} m di profondità`);
});
