/**
 * Braci, cenere e fumo: sostituiscono le mesh volumetriche della scena Blender
 * (che in tempo reale sarebbero solo geometria immobile) con sciami animati.
 */
import * as THREE from 'three';

function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function pointCloud(count, material) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  const points = new THREE.Points(geo, material);
  points.frustumCulled = false;
  return points;
}

/** Le sorgenti di fumo si deducono dai nomi delle luci della scena Blender. */
export function smokeSources(sceneData) {
  const out = [];
  for (const lamp of sceneData.lights) {
    const n = lamp.name.toLowerCase();
    if (n.includes('fumo') || n.includes('braciere') || n.includes('torre spezzata')) {
      out.push(new THREE.Vector3(...lamp.position));
    }
  }
  if (!out.length) out.push(new THREE.Vector3(0, 6, -2));
  return out;
}

export class Particles {
  constructor(scene, sceneData, texture, { embers = 1500, ash = 2400, smoke = 320 } = {}) {
    this.scene = scene;
    this.rand = mulberry32(20260127);
    this.enabled = true;
    this.time = 0;

    const gate = new THREE.Vector3(...(sceneData.gate?.position ?? [0, 1.6, -1.2]));
    this.gate = gate;

    // ---- braci ------------------------------------------------------
    this.emberMaterial = new THREE.PointsMaterial({
      size: 0.16, map: texture, vertexColors: true, transparent: true,
      blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true,
      fog: true,
    });
    this.embers = pointCloud(embers, this.emberMaterial);
    this.emberData = [];
    const warmLamps = sceneData.lights
      .filter((l) => l.color[0] - l.color[2] > 0.25)
      .map((l) => new THREE.Vector3(...l.position));
    for (let i = 0; i < embers; i += 1) {
      const nearGate = this.rand() < 0.45 || !warmLamps.length;
      const base = nearGate ? gate : warmLamps[(this.rand() * warmLamps.length) | 0];
      const spread = nearGate ? 11 : 5.5;
      const p = {
        base: base.clone(),
        spread,
        x: base.x + (this.rand() - 0.5) * spread * 2,
        y: base.y * 0.25 + this.rand() * (nearGate ? 13 : 7),
        z: base.z + (this.rand() - 0.5) * spread * 2,
        rise: 0.25 + this.rand() * 1.05,
        swirl: this.rand() * Math.PI * 2,
        swirlSpeed: 0.4 + this.rand() * 1.5,
        top: 9 + this.rand() * 16,
        heat: 0.35 + this.rand() * 0.65,
      };
      this.emberData.push(p);
      const c = new THREE.Color().setHSL(0.045 + this.rand() * 0.03, 0.95, 0.35 + p.heat * 0.4);
      this.embers.geometry.attributes.color.setXYZ(i, c.r, c.g, c.b);
    }
    scene.add(this.embers);

    // ---- cenere -----------------------------------------------------
    this.ashMaterial = new THREE.PointsMaterial({
      size: 0.075, map: texture, vertexColors: true, transparent: true, opacity: 0.5,
      depthWrite: false, sizeAttenuation: true, fog: true, blending: THREE.NormalBlending,
    });
    this.ash = pointCloud(ash, this.ashMaterial);
    this.ashData = [];
    this.ashBox = new THREE.Vector3(70, 34, 70);
    for (let i = 0; i < ash; i += 1) {
      const p = {
        x: (this.rand() - 0.5) * this.ashBox.x,
        y: this.rand() * this.ashBox.y,
        z: (this.rand() - 0.5) * this.ashBox.z,
        fall: 0.18 + this.rand() * 0.6,
        drift: 0.2 + this.rand() * 0.7,
        phase: this.rand() * Math.PI * 2,
      };
      this.ashData.push(p);
      const g = 0.22 + this.rand() * 0.3;
      this.ash.geometry.attributes.color.setXYZ(i, g, g * 0.95, g * 0.9);
    }
    scene.add(this.ash);

    // ---- fumo -------------------------------------------------------
    this.smokeMaterial = new THREE.PointsMaterial({
      size: 9.5, map: texture, vertexColors: true, transparent: true, opacity: 0.16,
      depthWrite: false, sizeAttenuation: true, fog: true, blending: THREE.NormalBlending,
    });
    this.smoke = pointCloud(smoke, this.smokeMaterial);
    this.smokeData = [];
    const sources = smokeSources(sceneData);
    for (let i = 0; i < smoke; i += 1) {
      const src = sources[i % sources.length];
      this.smokeData.push({
        src,
        y: this.rand() * 22,
        rise: 0.5 + this.rand() * 1.1,
        radius: 1 + this.rand() * 6,
        phase: this.rand() * Math.PI * 2,
      });
      const g = 0.05 + this.rand() * 0.07;
      this.smoke.geometry.attributes.color.setXYZ(i, g * 1.5, g * 0.8, g * 0.7);
    }
    scene.add(this.smoke);

    this.setEnabled(true);
  }

  setEnabled(on) {
    this.enabled = on;
    this.embers.visible = on;
    this.ash.visible = on;
    this.smoke.visible = on;
  }

  update(dt, cameraPosition) {
    if (!this.enabled) return;
    this.time += dt;
    const t = this.time;

    const ePos = this.embers.geometry.attributes.position;
    for (let i = 0; i < this.emberData.length; i += 1) {
      const p = this.emberData[i];
      p.y += p.rise * dt;
      p.swirl += p.swirlSpeed * dt;
      if (p.y > p.top) {
        p.y = p.base.y * 0.2 + this.rand() * 1.5;
        p.x = p.base.x + (this.rand() - 0.5) * p.spread * 2;
        p.z = p.base.z + (this.rand() - 0.5) * p.spread * 2;
      }
      ePos.setXYZ(i,
        p.x + Math.sin(p.swirl) * 0.5,
        p.y,
        p.z + Math.cos(p.swirl * 0.8) * 0.5);
    }
    ePos.needsUpdate = true;

    const aPos = this.ash.geometry.attributes.position;
    const half = this.ashBox;
    for (let i = 0; i < this.ashData.length; i += 1) {
      const p = this.ashData[i];
      p.y -= p.fall * dt;
      p.phase += dt * 0.7;
      if (p.y < 0) p.y += half.y;
      let x = cameraPosition.x + p.x + Math.sin(p.phase) * 1.2;
      let z = cameraPosition.z + p.z + Math.cos(p.phase * 0.8) * 1.2 + p.drift * dt * 6;
      if (x > cameraPosition.x + half.x / 2) x -= half.x;
      if (x < cameraPosition.x - half.x / 2) x += half.x;
      if (z > cameraPosition.z + half.z / 2) z -= half.z;
      if (z < cameraPosition.z - half.z / 2) z += half.z;
      p.z = z - cameraPosition.z;
      p.x = x - cameraPosition.x;
      aPos.setXYZ(i, x, cameraPosition.y - half.y * 0.35 + p.y, z);
    }
    aPos.needsUpdate = true;

    const sPos = this.smoke.geometry.attributes.position;
    for (let i = 0; i < this.smokeData.length; i += 1) {
      const p = this.smokeData[i];
      p.y += p.rise * dt;
      if (p.y > 30) p.y = 0;
      p.phase += dt * 0.25;
      const grow = 1 + p.y * 0.09;
      sPos.setXYZ(i,
        p.src.x + Math.sin(p.phase) * p.radius * grow,
        p.src.y + p.y,
        p.src.z + Math.cos(p.phase * 1.3) * p.radius * grow);
    }
    sPos.needsUpdate = true;
  }

  /** Il fuoco vicino alla soglia pulsa: si vede anche dal materiale. */
  pulse(amount) {
    this.emberMaterial.size = 0.16 * (1 + amount * 0.25);
  }
}
