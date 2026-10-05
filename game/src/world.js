/**
 * Mondo di gioco: carica gli asset esportati dal .blend, ricostruisce le luci
 * della scena Blender, il cielo e la foschia di cenere.
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

export const ASSETS = {
  scene: './public/scene.json',
  map: './public/map.glb',
  collision: './public/collision.glb',
  heightmap: './public/heightmap.png',
};

export async function fetchJSON(url) {
  const res = await fetch(url, { cache: 'no-cache' });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

function makeLoader() {
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  return loader;
}

/** Carica un GLB (anche compresso con EXT_meshopt_compression). */
export function loadGLB(url, onProgress) {
  return new Promise((resolve, reject) => {
    makeLoader().load(url, (gltf) => resolve(gltf), onProgress, reject);
  });
}

/**
 * gltfpack comprime con KHR_mesh_quantization: le posizioni restano interi a 16
 * bit e la scala sta nella matrice del nodo. `applyMatrix4` su un attributo
 * Uint16 trancherebbe i valori, quindi si ricostruisce la geometria in float.
 */
function dequantize(geometry, matrix) {
  const src = geometry.attributes.position;
  const out = new THREE.BufferGeometry();
  const positions = new Float32Array(src.count * 3);
  const v = new THREE.Vector3();
  for (let i = 0; i < src.count; i += 1) {
    v.fromBufferAttribute(src, i).applyMatrix4(matrix);
    positions[i * 3] = v.x;
    positions[i * 3 + 1] = v.y;
    positions[i * 3 + 2] = v.z;
  }
  out.setAttribute('position', new THREE.BufferAttribute(positions, 3));

  const normals = geometry.attributes.normal;
  if (normals) {
    const normalMatrix = new THREE.Matrix3().getNormalMatrix(matrix);
    const data = new Float32Array(normals.count * 3);
    const n = new THREE.Vector3();
    for (let i = 0; i < normals.count; i += 1) {
      n.fromBufferAttribute(normals, i).applyMatrix3(normalMatrix).normalize();
      data[i * 3] = n.x;
      data[i * 3 + 1] = n.y;
      data[i * 3 + 2] = n.z;
    }
    out.setAttribute('normal', new THREE.BufferAttribute(data, 3));
  }
  if (geometry.index) out.setIndex(geometry.index.clone());
  return out;
}

/** Unisce tutte le mesh di un GLB in una sola geometria: serve per l'BVH. */
export function mergeToGeometry(root, filter = null) {
  root.updateMatrixWorld(true);
  const parts = [];
  root.traverse((obj) => {
    if (!obj.isMesh) return;
    if (filter && !filter(obj)) return;
    if (!obj.geometry.index) return;
    parts.push(dequantize(obj.geometry, obj.matrixWorld));
  });
  if (!parts.length) return null;
  const merged = mergeGeometries(parts, false);
  parts.forEach((g) => g.dispose());
  if (!merged) return null;
  merged.computeBoundingSphere();
  merged.computeBoundingBox();
  return merged;
}

/**
 * L'exporter di Blender può scrivere il colore per vertice su COLOR_1 (three lo
 * chiama `color1`): lo si riporta su `color`, che è ciò che illumina il diffuse.
 */
export function adoptVertexColors(root) {
  let aliased = 0;
  root.traverse((obj) => {
    if (!obj.isMesh) return;
    const geo = obj.geometry;
    const secondary = geo.attributes.color1 || geo.attributes.COLOR_1 || geo.attributes.COLOR1;
    if (!geo.attributes.color && secondary) {
      geo.setAttribute('color', secondary);
      aliased += 1;
    }
    if (geo.attributes.color) {
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      mats.forEach((m) => { if (m) m.vertexColors = true; });
    }
  });
  return aliased;
}

/** Materiali che nel gioco sono fuoco: si attraversano, ma bruciano. */
export const HAZARD_PREFIXES = ['Lava', 'Magma', 'Fiamma', 'Brace', 'Braci', 'Spaccature'];

export function isHazardMaterial(name = '') {
  return HAZARD_PREFIXES.some((p) => name.startsWith(p));
}

/** Raccoglie la geometria di fuoco/lava dal modello visivo. */
export function collectHazards(root) {
  return mergeToGeometry(root, (obj) => {
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    return mats.some((m) => m && isHazardMaterial(m.name));
  });
}

/* ------------------------------------------------------------------ */
/* Cielo e atmosfera                                                    */
/* ------------------------------------------------------------------ */

/** Volta con gradiente cotto nei colori per vertice: nessuno shader custom. */
export function createSky() {
  const geo = new THREE.SphereGeometry(420, 32, 20);
  const pos = geo.attributes.position;
  const colors = new Float32Array(pos.count * 3);
  const zenith = new THREE.Color('#070810');
  const horizon = new THREE.Color('#2a0f08');
  const ember = new THREE.Color('#5c1c07');
  const tmp = new THREE.Color();
  for (let i = 0; i < pos.count; i += 1) {
    const h = pos.getY(i) / 420;
    if (h >= 0) tmp.copy(horizon).lerp(zenith, Math.pow(h, 0.45));
    else tmp.copy(horizon).lerp(ember, Math.min(1, -h * 2.6));
    colors[i * 3] = tmp.r;
    colors[i * 3 + 1] = tmp.g;
    colors[i * 3 + 2] = tmp.b;
  }
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  const mat = new THREE.MeshBasicMaterial({
    vertexColors: true, side: THREE.BackSide, fog: false, depthWrite: false, toneMapped: true,
  });
  const sky = new THREE.Mesh(geo, mat);
  sky.name = 'Cielo';
  sky.frustumCulled = false;
  sky.renderOrder = -1;
  return sky;
}

/* ------------------------------------------------------------------ */
/* Luci                                                                 */
/* ------------------------------------------------------------------ */

const WARM_BIAS = 0.4;

function lightDistance(lamp) {
  return THREE.MathUtils.clamp(Math.sqrt(lamp.power_watt) * 0.62, 7, 55);
}

function isWarm(lamp) {
  return lamp.color[0] - lamp.color[2] > WARM_BIAS * 0.6;
}

/**
 * La scena Blender ha 32 luci: troppe per un solo shader. Se ne tiene un
 * budget mobile, scegliendo le più vicine al giocatore.
 */
export class LightRig {
  constructor(scene, sceneData, { budget = 9 } = {}) {
    this.scene = scene;
    this.lamps = sceneData.lights.map((lamp) => ({
      ...lamp,
      position: new THREE.Vector3(...lamp.position),
      warm: isWarm(lamp),
      distance: lightDistance(lamp),
    }));
    this.budget = budget;
    this.lights = [];
    for (let i = 0; i < budget; i += 1) {
      const light = new THREE.PointLight(0xffffff, 0, 10, 2);
      light.visible = false;
      scene.add(light);
      this.lights.push(light);
    }
    // Luce d'ambiente: un sussurro, come nella scena originale.
    this.ambient = new THREE.HemisphereLight(0x2b3a55, 0x120806, 0.16);
    scene.add(this.ambient);

    this.flickerSeeds = this.lights.map(() => Math.random() * 10);
    this.elapsed = 0;
    this.assigned = [];
    this.target = new THREE.Vector3();
  }

  setAmbient(v) { this.ambient.intensity = v; }

  /** Assegna le luci del budget: le più vicine, con precedenza al calore. */
  update(target, dt = 0) {
    this.elapsed += dt;
    this.target.copy(target);
    const scored = this.lamps.map((lamp, index) => {
      const d = lamp.position.distanceTo(this.target);
      const score = d - (lamp.warm ? 9 : 0) + (lamp.kind === 'area' ? 4 : 0);
      return { index, lamp, d, score };
    }).sort((a, b) => a.score - b.score).slice(0, this.budget);

    this.assigned = scored;
    scored.forEach((entry, i) => {
      const light = this.lights[i];
      const { lamp, d } = entry;
      light.visible = d < lamp.distance * 1.15;
      light.position.copy(lamp.position);
      light.color.setRGB(lamp.color[0], lamp.color[1], lamp.color[2], THREE.LinearSRGBColorSpace);
      light.distance = lamp.distance;
      light.decay = 2;
      let intensity = lamp.intensity;
      if (lamp.warm) {
        // Il fuoco respira: sfarfallio lento e irregolare.
        const seed = this.flickerSeeds[i];
        const t = this.elapsed;
        const f = 0.86
          + 0.09 * Math.sin(t * 3.1 + seed)
          + 0.05 * Math.sin(t * 7.7 + seed * 2.3)
          + 0.04 * Math.sin(t * 13.3 + seed * 4.1);
        intensity *= f;
      }
      light.intensity = intensity;
    });
    for (let i = scored.length; i < this.lights.length; i += 1) this.lights[i].visible = false;
  }

  /** Calore percepito in un punto: alimenta speranza, minimappa e riverberi. */
  heatAt(position) {
    let heat = 0;
    for (const lamp of this.lamps) {
      if (!lamp.warm) continue;
      const d2 = lamp.position.distanceToSquared(position) + 4;
      heat += lamp.power_watt / d2;
    }
    return heat;
  }

  nearestWarm(position) {
    let best = { distance: Infinity, lamp: null };
    for (const lamp of this.lamps) {
      if (!lamp.warm) continue;
      const d = lamp.position.distanceTo(position);
      if (d < best.distance) best = { distance: d, lamp };
    }
    return best;
  }
}

/* ------------------------------------------------------------------ */
/* Materiali                                                            */
/* ------------------------------------------------------------------ */

/**
 * Ritocchi ai materiali esportati: l'iscrizione deve leggersi, il fuoco deve
 * ardere anche senza bloom, e la doppia faccia va tenuta dove serve.
 */
export function tuneMaterials(root, sceneData) {
  const inscriptionNode = sceneData.inscription?.node;
  const tuned = { standard: 0, emissive: 0 };
  root.traverse((obj) => {
    if (!obj.isMesh) return;
    obj.matrixAutoUpdate = false;
    obj.castShadow = false;
    obj.receiveShadow = false;
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    mats.forEach((mat) => {
      if (!mat || !mat.isMeshStandardMaterial) return;
      tuned.standard += 1;
      mat.envMapIntensity = 0.35;
      if (mat.emissive && (mat.emissive.r + mat.emissive.g + mat.emissive.b) > 0.02) {
        tuned.emissive += 1;
        mat.emissiveIntensity = Math.max(1.0, mat.emissiveIntensity || 1);
        mat.toneMapped = true;
      }
      if (obj.name === inscriptionNode) {
        mat.emissive = new THREE.Color('#ff7a30');
        mat.emissiveIntensity = 0.55;
        mat.color.multiplyScalar(1.25);
      }
      mat.needsUpdate = true;
    });
  });
  return tuned;
}

/**
 * Direzione di apertura dei battenti: si prova entrambi i versi e si tiene
 * quello che porta l'anta dentro il portale (lontano dal piazzale).
 */
export function openDirection(hingeNode, probe = 0.15) {
  const before = hingeNode.rotation.y;
  const boxA = new THREE.Box3();
  const boxB = new THREE.Box3();
  hingeNode.rotation.y = before + probe;
  hingeNode.updateMatrixWorld(true);
  boxA.setFromObject(hingeNode);
  hingeNode.rotation.y = before - probe;
  hingeNode.updateMatrixWorld(true);
  boxB.setFromObject(hingeNode);
  hingeNode.rotation.y = before;
  hingeNode.updateMatrixWorld(true);
  const centerA = boxA.getCenter(new THREE.Vector3());
  const centerB = boxB.getCenter(new THREE.Vector3());
  // -Z è la direzione della porta; si sceglie il verso che ci entra.
  return centerA.z < centerB.z ? 1 : -1;
}

export function makeSpriteTexture(size = 64, inner = 'rgba(255,240,210,1)', outer = 'rgba(255,120,30,0)') {
  const canvas = typeof document !== 'undefined' ? document.createElement('canvas') : null;
  if (!canvas) return null;
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, inner);
  g.addColorStop(0.35, 'rgba(255,170,80,0.75)');
  g.addColorStop(1, outer);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
