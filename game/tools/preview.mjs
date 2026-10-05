/**
 * Anteprima CPU della mappa: costruisce la stessa scena del gioco e la rende
 * con ray casting (senza WebGL). Serve a controllare inquadratura, proporzioni
 * e illuminazione quando non si ha una GPU a disposizione.
 *
 *   node game/tools/preview.mjs --width 320 --out /tmp/preview.png
 *
 * Opzioni: --width, --height, --camera (spawn|gate|wide), --from, --to.
 */
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { deflateSync } from 'node:zlib';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { MeshBVH } from 'three-mesh-bvh/core/MeshBVH.js';

const GAME = fileURLToPath(new URL('../', import.meta.url));

function parseArgs(argv) {
  const out = {
    width: 320, height: 200, camera: 'spawn',
    out: '/tmp/preview.png', samples: 1,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--width') out.width = Number(value);
    else if (key === '--height') out.height = Number(value);
    else if (key === '--camera') out.camera = value;
    else if (key === '--out') out.out = value;
    else if (key === '--samples') out.samples = Number(value);
  }
  return out;
}

const opts = parseArgs(process.argv.slice(2));

/* ----------------------------- PNG out ----------------------------- */
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body) >>> 0);
  return Buffer.concat([len, body, crc]);
}
let CRC_TABLE = null;
function crc32(buf) {
  if (!CRC_TABLE) {
    CRC_TABLE = new Int32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      CRC_TABLE[n] = c;
    }
  }
  let c = -1;
  for (let i = 0; i < buf.length; i += 1) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return c ^ -1;
}
function writePNG(path, width, height, rgba) {
  const raw = Buffer.alloc(height * (width * 4 + 1));
  for (let y = 0; y < height; y += 1) {
    raw[y * (width * 4 + 1)] = 0;
    rgba.copy(raw, y * (width * 4 + 1) + 1, y * width * 4, (y + 1) * width * 4);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; ihdr[9] = 6;
  const png = Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
  return writeFile(path, png);
}

/* ----------------------------- Caricamento ----------------------------- */
async function loadGLB(path) {
  const buffer = await readFile(new URL(`../public/${path}`, import.meta.url));
  const data = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  return new Promise((resolve, reject) => loader.parse(data, '', resolve, reject));
}

/** Ricostruisce la geometria in float: gltfpack quantizza a 16 bit. */
function dequantize(geometry, matrix) {
  const src = geometry.attributes.position;
  const out = new THREE.BufferGeometry();
  const positions = new Float32Array(src.count * 3);
  const v = new THREE.Vector3();
  for (let i = 0; i < src.count; i += 1) {
    v.fromBufferAttribute(src, i).applyMatrix4(matrix);
    positions[i * 3] = v.x; positions[i * 3 + 1] = v.y; positions[i * 3 + 2] = v.z;
  }
  out.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const nrm = geometry.attributes.normal;
  if (nrm) {
    const nm = new THREE.Matrix3().getNormalMatrix(matrix);
    const data = new Float32Array(nrm.count * 3);
    const n = new THREE.Vector3();
    for (let i = 0; i < nrm.count; i += 1) {
      n.fromBufferAttribute(nrm, i).applyMatrix3(nm).normalize();
      data[i * 3] = n.x; data[i * 3 + 1] = n.y; data[i * 3 + 2] = n.z;
    }
    out.setAttribute('normal', new THREE.BufferAttribute(data, 3));
  }
  const color = geometry.attributes.color || geometry.attributes.color1;
  if (color) {
    // Il colore per vertice cuoce AO, cenere e riflesso del fuoco.
    const data = new Float32Array(color.count * 3);
    for (let i = 0; i < color.count; i += 1) {
      data[i * 3] = color.getX(i); data[i * 3 + 1] = color.getY(i); data[i * 3 + 2] = color.getZ(i);
    }
    out.setAttribute('color', new THREE.BufferAttribute(data, 3));
  }
  if (geometry.index) out.setIndex(geometry.index.clone());
  return out;
}

console.log('caricamento map.glb…');
const gltf = await loadGLB('map.glb');
gltf.scene.updateMatrixWorld(true);

const parts = [];
gltf.scene.traverse((o) => { if (o.isMesh && o.geometry.index) parts.push(dequantize(o.geometry, o.matrixWorld)); });
const geometry = mergeGeometries(parts, false);
geometry.computeBoundingBox();
console.log(`geometria: ${geometry.index.count / 3} triangoli`);
const bvh = new MeshBVH(geometry, { maxLeafTris: 8 });

const sceneData = JSON.parse(await readFile(new URL('../public/scene.json', import.meta.url), 'utf8'));

/* ----------------------------- Camera ----------------------------- */
const gate = new THREE.Vector3(...sceneData.gate.position);
const spawn = new THREE.Vector3(...sceneData.spawn.position);
spawn.y += sceneData.spawn.eye_height ?? 1.68;

const views = {
  spawn: { position: spawn.clone(), target: new THREE.Vector3(gate.x, 12, gate.z), fov: 72 },
  gate: { position: new THREE.Vector3(gate.x, 1.68, gate.z + 26), target: new THREE.Vector3(gate.x, 9, gate.z), fov: 70 },
  wide: { position: new THREE.Vector3(26, 14, 46), target: new THREE.Vector3(gate.x, 12, gate.z), fov: 72 },
  low: { position: new THREE.Vector3(gate.x + 2, 1.68, gate.z + 9), target: new THREE.Vector3(gate.x, 6, gate.z), fov: 75 },
};
const view = views[opts.camera] || views.spawn;

const camera = new THREE.PerspectiveCamera(view.fov, opts.width / opts.height, 0.1, 900);
camera.position.copy(view.position);
camera.lookAt(view.target);
camera.updateMatrixWorld(true);
camera.updateProjectionMatrix();

/* ----------------------------- Illuminazione ----------------------------- */
// Le stesse luci della scena Blender, in candele come nel gioco.
const lamps = sceneData.lights.map((l) => ({
  position: new THREE.Vector3(...l.position),
  color: l.color,
  power: l.power_watt * 0.02,
  warm: l.color[0] - l.color[2] > 0.25,
}));
const ambient = new THREE.Color(0.05, 0.06, 0.09);

const hit = { point: new THREE.Vector3(), normal: new THREE.Vector3(), distance: 0, faceIndex: -1 };
const ray = new THREE.Ray();
const n = new THREE.Vector3();
const toLight = new THREE.Vector3();
const shade = [0, 0, 0];

function shadeHit(point, normal, color) {
  shade[0] = 0; shade[1] = 0; shade[2] = 0;
  n.copy(normal);
  if (n.lengthSq() < 1e-6) n.set(0, 1, 0); else n.normalize();
  for (const lamp of lamps) {
    toLight.subVectors(lamp.position, point);
    const dist2 = toLight.lengthSq() + 1;
    const dist = Math.sqrt(dist2);
    toLight.divideScalar(dist);
    const lambert = Math.max(0, n.dot(toLight));
    if (lambert <= 0) continue;
    // Occlusione: se un muro è in mezzo, la luce non arriva.
    ray.origin.copy(point).addScaledVector(n, 0.03);
    ray.direction.copy(toLight);
    const blocked = bvh.raycastFirst(ray, THREE.DoubleSide, 0, dist - 0.1);
    if (blocked) continue;
    const falloff = lamp.power / dist2;
    shade[0] += lamp.color[0] * lambert * falloff;
    shade[1] += lamp.color[1] * lambert * falloff;
    shade[2] += lamp.color[2] * lambert * falloff;
  }
  return [
    color[0] * (ambient.r + shade[0]),
    color[1] * (ambient.g + shade[1]),
    color[2] * (ambient.b + shade[2]),
  ];
}

const colors = geometry.attributes.color;
const index = geometry.index;
const positions = geometry.attributes.position;
const normals = geometry.attributes.normal;
const vColor = [1, 1, 1];

function vertexColorAt(faceIndex) {
  vColor[0] = 1; vColor[1] = 1; vColor[2] = 1;
  if (!colors) return vColor;
  const i0 = index.getX(faceIndex * 3);
  vColor[0] = colors.getX(i0); vColor[1] = colors.getY(i0); vColor[2] = colors.getZ(i0);
  return vColor;
}

/* ----------------------------- Rendering ----------------------------- */
const rgba = Buffer.alloc(opts.width * opts.height * 4);
const aspect = opts.width / opts.height;
const tanHalf = Math.tan((camera.fov * Math.PI) / 360);
console.log(`rendering ${opts.width}x${opts.height}…`);

let hits = 0;
let maxDepth = 0;
for (let y = 0; y < opts.height; y += 1) {
  const py = 1 - (2 * (y + 0.5)) / opts.height;
  for (let x = 0; x < opts.width; x += 1) {
    const px = ((2 * (x + 0.5)) / opts.width - 1) * aspect * tanHalf;
    const dir = new THREE.Vector3(px, py * tanHalf, -1).applyQuaternion(camera.quaternion).normalize();
    ray.origin.copy(camera.position);
    ray.direction.copy(dir);
    const result = bvh.raycastFirst(ray, THREE.DoubleSide, 0, 900);
    let rgb;
    if (result) {
      hits += 1;
      maxDepth = Math.max(maxDepth, result.distance);
      const face = result.faceIndex;
      const faceNormal = result.face
        ? result.face.normal
        : new THREE.Vector3().fromBufferAttribute(normals, index.getX(face * 3));
      rgb = shadeHit(result.point, faceNormal, vertexColorAt(face));
    } else {
      // Cielo: gradiente come nel gioco.
      const h = Math.max(0, dir.y);
      rgb = [0.02 + 0.10 * (1 - h) * (1 - h), 0.012 + 0.03 * (1 - h), 0.02 + 0.012 * (1 - h)];
    }
    const o = (y * opts.width + x) * 4;
    // Tone mapping (ACES approssimato) + gamma.
    for (let c = 0; c < 3; c += 1) {
      let v = rgb[c];
      v = (v * (2.51 * v + 0.03)) / (v * (2.43 * v + 0.59) + 0.14);
      v = Math.max(0, Math.min(1, Math.pow(v, 1 / 2.2)));
      rgba[o + c] = Math.round(v * 255);
    }
    rgba[o + 3] = 255;
  }
  if (y % 40 === 0) process.stdout.write(`  riga ${y}/${opts.height}\r`);
}

await writePNG(opts.out, opts.width, opts.height, rgba);
const coverage = ((hits / (opts.width * opts.height)) * 100).toFixed(1);
console.log(`\nfatto: ${opts.out}`);
console.log(`geometria a schermo: ${coverage}% · profondità max ${maxDepth.toFixed(1)} m`);
console.log(`camera ${view.position.toArray().map((v) => v.toFixed(1))} -> ${view.target.toArray().map((v) => v.toFixed(1))}`);
