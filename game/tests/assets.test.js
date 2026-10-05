/**
 * Controlli sul pacchetto web: ogni file richiesto dalla pagina esiste, i
 * moduli sono coerenti col ruolo dichiarato e la pagina non chiede nulla alla
 * rete esterna. Serve a intercettare refusi e file finiti nel posto sbagliato.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const GAME = fileURLToPath(new URL('../', import.meta.url));
const read = (p) => readFile(new URL(`../${p}`, import.meta.url), 'utf8');

const ASSETS = [
  'index.html', 'style.css', 'server.js', 'package.json',
  'src/main.js', 'src/world.js', 'src/physics.js', 'src/player.js',
  'src/particles.js', 'src/audio.js', 'src/objectives.js', 'src/hud.js',
  'src/heightfield.js',
  'vendor/three/three.module.js', 'vendor/three/three.core.js',
  'vendor/three-addons/loaders/GLTFLoader.js',
  'vendor/three-addons/libs/meshopt_decoder.module.js',
  'vendor/three-mesh-bvh/core/MeshBVH.js',
  'vendor/versions.json',
  'public/scene.json', 'public/map.glb', 'public/collision.glb',
  'public/heightmap.png',
  'tools/export_map.py', 'tools/export_map.sh', 'tools/vendor.sh',
];

test('tutti i file del gioco esistono e non sono vuoti', async () => {
  for (const file of ASSETS) {
    const info = await stat(new URL(`../${file}`, import.meta.url));
    assert.ok(info.size > 0, `${file} è vuoto`);
  }
});

test('style.css è davvero un foglio di stile', async () => {
  const css = await read('style.css');
  assert.match(css, /^\s*:root\s*\{/m, 'manca il blocco :root: il file è stato sovrascritto');
  for (const selector of ['#hud', '#minimap', '.screen', '#load-bar', '#stick']) {
    assert.ok(css.includes(selector), `selettore mancante: ${selector}`);
  }
  assert.ok(css.split('{').length > 30, 'il foglio di stile è sospettosamente corto');
  assert.ok(!css.includes('export class') && !css.includes('import '),
    'il CSS contiene codice JavaScript');
  // Il joystick su touch deve poter ricevere gli eventi, l'HUD no.
  assert.match(css, /#hud\s*\{[^}]*pointer-events:\s*none/, 'l’HUD intercetterebbe i click');
  assert.match(css, /#stick\s*\{[^}]*pointer-events:\s*auto/, 'il joystick touch non riceve eventi');
});

test('ogni modulo JS ha il ruolo che il nome promette', async () => {
  const expected = {
    'src/world.js': /export function mergeToGeometry|export async function fetchJSON/,
    'src/physics.js': /export class Capsule/,
    'src/player.js': /export class Player/,
    'src/particles.js': /export class Particles/,
    'src/audio.js': /export class Ambience/,
    'src/objectives.js': /export class GameState/,
    'src/hud.js': /export class Hud/,
    'src/heightfield.js': /export function createHeightField/,
    'src/main.js': /async function boot/,
    'server.js': /createServer/,
  };
  for (const [file, pattern] of Object.entries(expected)) {
    const source = await read(file);
    assert.match(source, pattern, `${file} non contiene ciò che ci si aspetta`);
    assert.ok(source.length > 2000, `${file} è troppo corto (${source.length} B)`);
  }
  // Nessun modulo deve essere una copia di un altro.
  const bodies = {};
  for (const file of Object.keys(expected)) bodies[file] = await read(file);
  const seen = new Map();
  for (const [file, body] of Object.entries(bodies)) {
    assert.equal(seen.has(body), false,
      `${file} è identico a ${seen.get(body)}`);
    seen.set(body, file);
  }
});

test('la pagina non dipende da CDN o risorse esterne', async () => {
  const html = await read('index.html');
  const urls = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((m) => m[1]);
  for (const url of urls) {
    assert.equal(/^https?:/.test(url), false, `risorsa esterna: ${url}`);
    assert.ok(url.startsWith('./') || url.startsWith('#'), `percorso sospetto: ${url}`);
  }
  assert.match(html, /<script type="importmap">/, 'manca l’import map');
  assert.match(html, /"three":\s*"\.\/vendor\/three\/three\.module\.js"/);
  assert.match(html, /"three\/addons\/":\s*"\.\/vendor\/three-addons\/"/);
  assert.match(html, /"three-mesh-bvh\/":\s*"\.\/vendor\/three-mesh-bvh\/"/);
  assert.match(html, /src="\.\/src\/main\.js"/, 'manca l’entry point');
});

test('l’import map copre ogni import nudo usato dai moduli', async () => {
  const html = await read('index.html');
  const map = JSON.parse(html.match(/<script type="importmap">([\s\S]*?)<\/script>/)[1]).imports;
  const files = ['src/main.js', 'src/world.js', 'src/physics.js', 'src/player.js',
    'src/particles.js', 'src/audio.js', 'src/objectives.js', 'src/hud.js', 'src/heightfield.js'];
  for (const file of files) {
    const source = await read(file);
    for (const [, spec] of source.matchAll(/from\s+'([^'.][^']*)'/g)) {
      const covered = Object.keys(map).some((k) => (k.endsWith('/')
        ? spec.startsWith(k) : spec === k));
      assert.ok(covered, `${file}: import '${spec}' non risolto dall’import map`);
    }
  }
});

test('gli ID usati dal JavaScript esistono nell’HTML', async () => {
  const html = await read('index.html');
  const ids = new Set([...html.matchAll(/id="([^"]+)"/g)].map((m) => m[1]));
  const sources = ['src/main.js', 'src/hud.js', 'src/heightfield.js', 'src/player.js'];
  for (const file of sources) {
    const source = await read(file);
    for (const [, id] of source.matchAll(/getElementById\('([^']+)'\)/g)) {
      assert.ok(ids.has(id), `${file}: #${id} non esiste in index.html`);
    }
  }
});

test('i file public/ sono quelli prodotti dall’esportatore', async () => {
  const scene = JSON.parse(await read('public/scene.json'));
  assert.equal(scene.source, 'porta_dell_inferno.blend');
  assert.equal(scene.generator, 'game/tools/export_map.py');
  assert.equal(scene.heightmap.file, 'heightmap.png');
  const total = (await stat(new URL('../public/map.glb', import.meta.url))).size
    + (await stat(new URL('../public/collision.glb', import.meta.url))).size;
  assert.ok(total < 12_000_000, `gli asset pesano troppo: ${(total / 1e6).toFixed(1)} MB`);
  assert.ok(GAME.includes('game'), 'i test girano fuori da game/');
});
