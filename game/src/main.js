/**
 * La Porta dell'Inferno — esplorazione in prima persona della mappa
 * porta_dell_inferno.blend. Questo file collega asset, fisica, regole e HUD.
 */
import * as THREE from 'three';
import {
  ASSETS, LightRig, adoptVertexColors, collectHazards, createSky, fetchJSON, loadGLB,
  makeSpriteTexture, mergeToGeometry, openDirection, tuneMaterials,
} from './world.js';
import { DOOR_BARRIER, Capsule, applyDoorBarrier, buildBVH, groundHeightAt } from './physics.js';
import { Player } from './player.js';
import { Particles } from './particles.js';
import { Ambience } from './audio.js';
import { GameState, STATES } from './objectives.js';
import { Hud, Screens } from './hud.js';
import { loadHeightField, renderMapCanvas } from './heightfield.js';

const canvas = document.getElementById('scene');
const screens = new Screens();
const hud = new Hud();

const settings = {
  exposure: 1.0,
  fov: 72,
  sensitivity: 1,
  audio: true,
  particles: true,
};

const world = {
  renderer: null,
  scene: null,
  camera: null,
  data: null,
  lights: null,
  particles: null,
  hinges: [],
  hazardBVH: null,
  mapCanvas: null,
  heightField: null,
};

let player = null;
let game = null;
let audio = null;
let lantern = null;
let rafId = 0;
let lastTime = 0;
let bigMapOpen = false;
let endingStart = null;
const tmpVec = new THREE.Vector3();
const tmpRay = new THREE.Ray(new THREE.Vector3(), new THREE.Vector3(0, -1, 0));

/* ------------------------------------------------------------------ */
/* Avvio                                                                */
/* ------------------------------------------------------------------ */

async function boot() {
  screens.show('loading');
  try {
    screens.progress(0.05, 'Lettura della scena…');
    const data = await fetchJSON(ASSETS.scene);
    world.data = data;

    screens.progress(0.15, 'Caricamento della geometria…');
    const [mapGltf, collisionGltf] = await Promise.all([
      loadGLB(ASSETS.map, (e) => {
        if (e.total) screens.progress(0.15 + 0.5 * (e.loaded / e.total), 'Caricamento della geometria…');
      }),
      loadGLB(ASSETS.collision),
    ]);

    screens.progress(0.68, 'Costruzione delle collisioni…');
    const collisionGeometry = mergeToGeometry(collisionGltf.scene);
    if (!collisionGeometry) throw new Error('collision.glb non contiene mesh');
    const bvh = buildBVH(collisionGeometry);

    screens.progress(0.78, 'Terreno e minimappa…');
    const heightField = await loadHeightField(ASSETS.heightmap, data.heightmap);
    world.heightField = heightField;
    world.mapCanvas = renderMapCanvas(heightField, 512);

    screens.progress(0.86, 'Luci della scena…');
    setupRenderer();
    world.scene.add(mapGltf.scene);
    world.mapRoot = mapGltf.scene;
    adoptVertexColors(mapGltf.scene);
    tuneMaterials(mapGltf.scene, data);

    const hazardGeometry = collectHazards(mapGltf.scene);
    world.hazardBVH = hazardGeometry ? buildBVH(hazardGeometry) : null;

    world.lights = new LightRig(world.scene, data, { budget: 9 });
    world.scene.add(createSky());

    const sprite = makeSpriteTexture(64);
    world.particles = new Particles(world.scene, data, sprite);
    world.particles.setEnabled(settings.particles);

    setupHinges(mapGltf.scene, data);
    setupLantern();

    screens.progress(0.94, 'Preparazione del pellegrino…');
    game = new GameState({
      points: data.points_of_interest,
      gate: data.gate,
      spawn: data.spawn,
      rules: { gateRadius: data.gate.radius },
    });
    audio = new Ambience();
    world.bvh = bvh;
    player = new Player({ camera: world.camera, capsule: makeCapsule(bvh), dom: canvas, audio });
    player.setLook(yawFromForward(data.spawn.forward), 0.06);
    aimCamera();
    wireUI();

    screens.progress(1, 'Pronto');
    hud.setSigils(0);
    hud.setHope(game.hope);
    updateObjective();
    resize();
    renderOnce();
    screens.show('menu');
    loop(performance.now());
  } catch (err) {
    console.error(err);
    screens.error(`${err.message || err} — servono i file in game/public/ (vedi game/tools/export_map.sh).`);
  }
}

/** Mette la camera sugli occhi del pellegrino, guardando verso la porta. */
function aimCamera() {
  const cap = player.capsule;
  world.camera.position.set(cap.position.x, cap.position.y + player.eyeHeight, cap.position.z);
  world.camera.rotation.set(player.pitch, player.yaw, 0, 'YXZ');
  world.camera.updateMatrixWorld(true);
}

function makeCapsule(bvh) {
  const spawn = world.data.spawn.position;
  const ground = groundHeightAt(bvh, spawn[0], spawn[2]);
  const y = ground === null ? spawn[1] : ground + 0.05;
  return new Capsule({ radius: 0.34, height: 1.78, position: [spawn[0], y, spawn[2]] });
}

function yawFromForward(forward) {
  if (!forward) return 0;
  return Math.atan2(-forward[0], -forward[2]);
}

function setupRenderer() {
  const renderer = new THREE.WebGLRenderer({
    canvas, antialias: true, powerPreference: 'high-performance', stencil: false,
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  renderer.setSize(window.innerWidth, window.innerHeight, false);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = settings.exposure;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#0a0710');
  scene.fog = new THREE.FogExp2(0x180e0b, 0.0122);

  const camera = new THREE.PerspectiveCamera(settings.fov, window.innerWidth / window.innerHeight, 0.08, 900);
  scene.add(camera);

  world.renderer = renderer;
  world.scene = scene;
  world.camera = camera;
}

function setupLantern() {
  lantern = new THREE.SpotLight(0xffb27a, 16, 30, 0.62, 0.8, 2);
  lantern.position.set(0.22, -0.16, 0.05);
  const target = new THREE.Object3D();
  target.position.set(0, -0.05, -1);
  world.camera.add(lantern);
  world.camera.add(target);
  lantern.target = target;
  world.lantern = lantern;
}

function setupHinges(root, data) {
  world.hinges = (data.hinges || []).map((hinge) => {
    const node = root.getObjectByName(hinge.node);
    if (!node) return null;
    // Nel .blend i battenti sono socchiusi: il gioco li parte chiusi, così il
    // varco resta sbarrato finché tutte le anime non sono state ascoltate.
    const direction = openDirection(node);
    const closed = hinge.closed_angle ?? 0;
    node.rotation.y = closed;
    node.updateMatrixWorld(true);
    return { node, rest: closed, direction, hinge };
  }).filter(Boolean);
}

/* ------------------------------------------------------------------ */
/* Interfaccia                                                          */
/* ------------------------------------------------------------------ */

function wireUI() {
  document.getElementById('btn-start').addEventListener('click', () => startRun(false));
  document.getElementById('btn-resume').addEventListener('click', resume);
  document.getElementById('btn-restart').addEventListener('click', () => startRun(true));
  document.getElementById('btn-respawn').addEventListener('click', respawn);
  document.getElementById('btn-again').addEventListener('click', () => startRun(true));

  const exposure = document.getElementById('set-exposure');
  exposure.value = String(settings.exposure);
  exposure.addEventListener('input', () => {
    settings.exposure = Number(exposure.value);
    world.renderer.toneMappingExposure = settings.exposure;
  });
  const fov = document.getElementById('set-fov');
  fov.value = String(settings.fov);
  fov.addEventListener('input', () => {
    settings.fov = Number(fov.value);
    world.camera.fov = settings.fov;
    world.camera.updateProjectionMatrix();
  });
  const sens = document.getElementById('set-sens');
  sens.value = String(settings.sensitivity);
  sens.addEventListener('input', () => {
    settings.sensitivity = Number(sens.value);
    if (player) player.sensitivity = settings.sensitivity;
  });
  const audioToggle = document.getElementById('set-audio');
  audioToggle.addEventListener('change', () => {
    settings.audio = audioToggle.checked;
    audio?.setEnabled(settings.audio);
  });
  const particlesToggle = document.getElementById('set-particles');
  particlesToggle.addEventListener('change', () => {
    settings.particles = particlesToggle.checked;
    world.particles?.setEnabled(settings.particles);
  });

  window.addEventListener('keydown', onGlobalKey);
  window.addEventListener('resize', resize);
  canvas.addEventListener('click', () => {
    if (game.state === STATES.playing && !player.locked) player.requestLock();
  });

  player.onLock = (locked) => {
    if (!locked && game.state === STATES.playing) pause();
    else if (locked && game.state === STATES.paused) resume();
  };
  player.onStep = (running) => audio?.footstep(running);

  setupTouch();
}

function setupTouch() {
  const isTouch = window.matchMedia('(pointer: coarse)').matches;
  if (!isTouch) return;
  const touch = document.getElementById('touch');
  touch.classList.remove('hidden');
  const stick = document.getElementById('stick');
  const knob = document.getElementById('stick-knob');
  let origin = null;
  const max = 46;
  const move = (e) => {
    const t = e.changedTouches ? e.changedTouches[0] : e;
    if (!origin) return;
    let dx = t.clientX - origin.x;
    let dy = t.clientY - origin.y;
    const len = Math.hypot(dx, dy);
    if (len > max) { dx = (dx / len) * max; dy = (dy / len) * max; }
    knob.style.transform = `translate(${dx}px, ${dy}px)`;
    player.setTouchMove(dx / max, dy / max);
  };
  const end = () => {
    origin = null;
    knob.style.transform = 'translate(0px, 0px)';
    player.setTouchMove(0, 0);
  };
  stick.addEventListener('touchstart', (e) => {
    const t = e.changedTouches[0];
    const rect = stick.getBoundingClientRect();
    origin = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    move(e);
    e.preventDefault();
  }, { passive: false });
  stick.addEventListener('touchmove', (e) => { move(e); e.preventDefault(); }, { passive: false });
  stick.addEventListener('touchend', end);
  document.getElementById('btn-jump').addEventListener('touchstart', (e) => { player.wantJump = true; e.preventDefault(); }, { passive: false });
  document.getElementById('btn-use').addEventListener('touchstart', (e) => { interact(); e.preventDefault(); }, { passive: false });
  canvas.addEventListener('touchstart', () => { if (game.state === STATES.playing) player.requestLock(); }, { passive: true });
}

function onGlobalKey(event) {
  const code = event.code;
  if (code === 'KeyE') interact();
  else if (code === 'KeyF') toggleLantern();
  else if (code === 'KeyM') toggleBigMap();
  else if (code === 'Escape') {
    if (game.state === STATES.playing) pause();
    else if (bigMapOpen) toggleBigMap();
  }
}

function toggleLantern() {
  if (!lantern) return;
  lantern.userData.off = !lantern.userData.off;
  hud.toast(lantern.userData.off ? 'lanterna spenta' : 'lanterna accesa', 1.4);
}

function toggleBigMap() {
  bigMapOpen = !bigMapOpen;
  if (bigMapOpen) {
    hud.drawBigMap(world.heightField, world.mapCanvas, mapView());
    screens.show('map');
    if (game.state === STATES.playing) pause();
  } else {
    screens.hide();
  }
}

function mapView() {
  return {
    position: world.camera.position,
    yaw: player.yaw + Math.PI,
    points: game.points,
    gate: game.gate,
  };
}

function updateObjective() {
  const left = game.total - game.collected;
  if (game.allCollected) hud.setObjective('Spingi i battenti: la soglia ti aspetta');
  else if (left === 1) hud.setObjective('Resta un’anima nella cenere');
  else hud.setObjective(`Trova le anime della soglia · ${left} mancano`);
}

/* ------------------------------------------------------------------ */
/* Stati di gioco                                                       */
/* ------------------------------------------------------------------ */

function startRun(fresh) {
  audio?.init();
  audio?.resume();
  audio?.setEnabled(settings.audio);
  game.reset(!fresh);
  if (fresh) game.points.forEach((p) => { p.taken = false; });
  world.camera.position.set(...world.data.spawn.position);
  player.capsule.position.set(...makeCapsule(world.bvh).position.toArray());
  player.capsule.velocity.set(0, 0, 0);
  player.setLook(yawFromForward(world.data.spawn.forward), 0.06);
  endingStart = null;
  world.scene.fog.density = 0.0122;
  world.scene.fog.color.set('#180e0b');
  hud.setSigils(game.collected);
  hud.setHope(game.hope);
  hud.setObjective(game.allCollected ? 'Spingi i battenti' : 'Trova le anime della soglia');
  hud.fadeControls(16);
  hud.show();
  screens.hide();
  bigMapOpen = false;
  updateObjective();
  player.requestLock();
  hud.showSubtitle('La valle di cenere si apre sotto un cielo senza stelle.', null, 6);
}

function respawn() {
  game.reset(true);
  const cap = makeCapsule(world.bvh);
  player.capsule.position.copy(cap.position);
  player.capsule.velocity.set(0, 0, 0);
  hud.setHope(game.hope);
  hud.show();
  screens.hide();
  updateObjective();
  player.requestLock();
  hud.showSubtitle('Ti rialzi sui gradini. La speranza non è tutta perduta.', null, 5);
}

function pause() {
  if (game.state !== STATES.playing) return;
  game.pause();
  screens.pauseStats(game.stats());
  if (!bigMapOpen) screens.show('pause');
  if (document.pointerLockElement) document.exitPointerLock();
}

function resume() {
  if (game.state !== STATES.paused) return;
  game.resume();
  bigMapOpen = false;
  screens.hide();
  player.requestLock();
}

/* ------------------------------------------------------------------ */
/* Interazioni                                                          */
/* ------------------------------------------------------------------ */

function interact() {
  if (!game || game.state !== STATES.playing) return;
  const action = game.interactionAt(player.capsule.position);
  if (!action) return;
  if (action.kind === 'sigil') {
    const poi = game.collect(action.poi);
    hud.setSigils(game.collected);
    hud.setHope(game.hope);
    audio?.sigil(game.collected);
    hud.showSubtitle(poi.verse || '…', poi.canto, 8);
    hud.toast(`${poi.name} · ${game.collected}/${game.total}`, 3);
    updateObjective();
  } else if (action.kind === 'gate-open') {
    if (game.beginOpening()) {
      audio?.door();
      endingStart = { position: world.camera.position.clone(), time: 0 };
      hud.setPrompt(null);
      hud.showSubtitle('I battenti cedono. Il calore esce dalla pietra.', null, 5);
    }
  } else if (action.kind === 'gate-locked') {
    const left = game.total - game.collected;
    hud.toast(left === 1 ? 'Manca un’anima.' : `Mancano ${left} anime.`, 2.6);
    audio?.tone(82, 0.5, 0.07, 'triangle');
  }
}

/* ------------------------------------------------------------------ */
/* Ciclo principale                                                     */
/* ------------------------------------------------------------------ */

function inFire(position) {
  if (!world.hazardBVH) return false;
  tmpRay.origin.set(position.x, position.y + 0.35, position.z);
  tmpRay.direction.set(0, -1, 0);
  return Boolean(world.hazardBVH.raycastFirst(tmpRay, THREE.DoubleSide, 0, 0.85));
}

function updateDoors(dt) {
  const open = game.state === STATES.ending || game.state === STATES.done ? game.doorsOpen : 0;
  for (const entry of world.hinges) {
    const target = entry.rest + entry.direction * open * 1.95;
    entry.node.rotation.y += (target - entry.node.rotation.y) * Math.min(1, dt * 1.6);
    entry.node.updateMatrixWorld(true);
  }
}

function loop(now) {
  rafId = requestAnimationFrame(loop);
  const dt = Math.min(0.05, Math.max(0.0005, (now - lastTime) / 1000));
  lastTime = now;

  if (game.state === STATES.playing) {
    const result = player.update(dt, world.bvh);
    // I battenti chiusi non si oltrepassano, anche se la mesh di collisione
    // semplificata lasciasse qualche fessura.
    applyDoorBarrier(player.capsule, game.doorsOpen, DOOR_BARRIER);
    game.distance += result.horizontal;
    const heat = world.lights.heatAt(world.camera.position);
    const fire = inFire(player.capsule.position);
    const { events } = game.update(dt, { heat, inFire: fire });
    for (const ev of events) {
      if (ev.type === 'dead') {
        audio?.death();
        hud.heatFlash(0);
        screens.show('dead');
        if (document.pointerLockElement) document.exitPointerLock();
      }
    }
    hud.setHope(game.hope);
    hud.heatFlash(fire ? 0.5 + 0.3 * Math.sin(now / 120) : 0);
    hud.setCompass(player.yaw, 0);
    hud.drawMinimap(world.heightField, world.mapCanvas, { ...mapView(), radius: 58 });
    const action = game.interactionAt(player.capsule.position);
    hud.setPrompt(action ? ({
      sigil: `parla con ${action.poi.name}`,
      'gate-open': 'spingi i battenti',
      'gate-locked': 'i battenti non cedono',
    })[action.kind] : null);
  } else if (game.state === STATES.ending || game.state === STATES.done) {
    game.update(dt, { heat: 900, inFire: false });
    updateEnding(dt);
  }

  // Nel menu la camera gira lentamente sulla valle: il monumento entra
  // nell'inquadratura mentre si legge il testo.
  if (game.state === STATES.menu) {
    player.yaw += dt * 0.03;
    aimCamera();
  }

  updateDoors(dt);
  world.lights.update(world.camera.position, dt);
  world.particles.update(dt, world.camera.position);
  world.particles.pulse(0.5 + 0.5 * Math.sin(now / 900));
  if (lantern) {
    const hope = Math.max(0, Math.min(1, game.hope / 100));
    const flicker = 0.9 + 0.1 * Math.sin(now / 137) + 0.05 * Math.sin(now / 61);
    lantern.intensity = lantern.userData.off ? 0 : (5 + 20 * hope) * flicker;
    lantern.color.setRGB(1, 0.62 + 0.2 * hope, 0.36 + 0.2 * hope, THREE.LinearSRGBColorSpace);
  }
  const heat = world.lights.heatAt(world.camera.position);
  audio?.setHeat(Math.min(1, heat / 700));
  audio?.update(dt);
  hud.update(dt);

  if (bigMapOpen) hud.drawBigMap(world.heightField, world.mapCanvas, mapView());
  world.renderer.render(world.scene, world.camera);
}

function updateEnding(dt) {
  if (!endingStart) return;
  endingStart.time += dt;
  const t = Math.min(1, endingStart.time / 7.5);
  const eased = t * t * (3 - 2 * t);
  const gate = game.gate.position;
  tmpVec.set(gate.x, 1.75, gate.z - 11);
  world.camera.position.lerpVectors(endingStart.position, tmpVec, eased);
  world.camera.rotation.set(-0.05 - 0.08 * eased, 0, 0, 'YXZ');
  world.scene.fog.density = 0.0122 + eased * 0.05;
  world.scene.fog.color.setRGB(0.16 + eased * 0.5, 0.05 + eased * 0.09, 0.04 + eased * 0.05);
  if (game.state === STATES.done && !endingStart.shown) {
    endingStart.shown = true;
    audio?.ending();
    screens.end(game.stats());
    if (document.pointerLockElement) document.exitPointerLock();
  }
}

function renderOnce() {
  world.lights.update(world.camera.position, 0);
  world.renderer.render(world.scene, world.camera);
}

function resize() {
  if (!world.renderer) return;
  const w = window.innerWidth;
  const h = window.innerHeight;
  world.renderer.setSize(w, h, false);
  world.camera.aspect = w / h;
  world.camera.updateProjectionMatrix();
}

window.addEventListener('error', (e) => {
  if (!world.renderer) screens.error(String(e.message || e.error));
});

boot();
