/**
 * Regole di gioco: le anime da raccogliere, la speranza che si consuma nel
 * buio, i battenti da aprire. Nessuna dipendenza dal DOM o da WebGL: il modulo
 * è coperto dai test headless.
 */
import * as THREE from 'three';

export const STATES = {
  menu: 'menu',
  playing: 'playing',
  paused: 'paused',
  dead: 'dead',
  ending: 'ending',
  done: 'done',
};

export const RULES = {
  hopeMax: 100,
  hopeStart: 100,
  hopeOnSigil: 21,
  hopeRespawn: 62,
  drainInDark: 1.05,
  gainNearFire: 3.6,
  // `heat` è la somma grezza delle luci calde (watt / m²): 300 ≈ la soglia.
  warmthFull: 300,
  burnDamage: 9.5,
  poiRadius: 2.6,
  gateRadius: 2.8,
  openDuration: 3.4,
};

export function distance2(a, b) {
  const dx = a.x - b.x;
  const dy = (a.y ?? 0) - (b.y ?? 0);
  const dz = a.z - b.z;
  return dx * dx + dy * dy + dz * dz;
}

function asVector3(value) {
  if (value instanceof THREE.Vector3) return value.clone();
  if (Array.isArray(value)) return new THREE.Vector3(...value);
  return new THREE.Vector3(value?.x ?? 0, value?.y ?? 0, value?.z ?? 0);
}

export class GameState {
  constructor({ points = [], gate, spawn, rules = RULES } = {}) {
    this.rules = { ...RULES, ...rules };
    // scene.json porta le posizioni come array: qui diventano vettori.
    this.points = points.map((p) => ({ ...p, position: asVector3(p.position), taken: false }));
    this.gate = gate ? { ...gate, position: asVector3(gate.position) } : null;
    this.spawn = spawn;
    this.state = STATES.menu;
    this.hope = this.rules.hopeStart;
    this.time = 0;
    this.distance = 0;
    this.deaths = 0;
    this.doorsOpen = 0; // 0 = chiusi, 1 = spalancati
    this.doorPhase = 0;
    this.burning = 0;
    this.lastVerse = null;
  }

  get collected() { return this.points.filter((p) => p.taken).length; }
  get total() { return this.points.length; }
  get allCollected() { return this.collected === this.total && this.total > 0; }

  start() { this.state = STATES.playing; }
  pause() { if (this.state === STATES.playing) this.state = STATES.paused; }
  resume() { if (this.state === STATES.paused) this.state = STATES.playing; }

  reset(keepProgress = true) {
    this.hope = keepProgress ? this.rules.hopeRespawn : this.rules.hopeStart;
    this.burning = 0;
    this.doorsOpen = 0;
    this.doorPhase = 0;
    this.state = STATES.playing;
    if (!keepProgress) {
      this.points.forEach((p) => { p.taken = false; });
      this.time = 0;
      this.distance = 0;
      this.deaths = 0;
    }
  }

  /** Anima più vicina non ancora raccolta, o null. */
  nearestPoint(position, radius = this.rules.poiRadius) {
    let best = null;
    let bestD = radius * radius;
    for (const p of this.points) {
      if (p.taken) continue;
      const d = distance2(position, p.position);
      if (d < bestD) { bestD = d; best = p; }
    }
    return best;
  }

  /** Distanza orizzontale dalla soglia. */
  gateDistance(position) {
    if (!this.gate) return Infinity;
    return Math.hypot(position.x - this.gate.position.x, position.z - this.gate.position.z);
  }

  /** Cosa può fare il giocatore qui, adesso. */
  interactionAt(position) {
    const poi = this.nearestPoint(position);
    if (poi) return { kind: 'sigil', poi };
    if (this.gate && this.gateDistance(position) < this.rules.gateRadius + 1.6) {
      if (!this.allCollected) return { kind: 'gate-locked' };
      if (this.doorsOpen < 0.98) return { kind: 'gate-open' };
    }
    return null;
  }

  /** Raccoglie un'anima: restituisce il verso, se c'è. */
  collect(poi) {
    if (!poi || poi.taken) return null;
    poi.taken = true;
    this.hope = Math.min(this.rules.hopeMax, this.hope + this.rules.hopeOnSigil);
    this.lastVerse = poi.verse || null;
    return poi;
  }

  /** Un passo di simulazione delle regole. */
  update(dt, ctx = {}) {
    if (this.state !== STATES.playing && this.state !== STATES.ending) {
      return { events: [] };
    }
    const events = [];
    const { heat = 0, inFire = false } = ctx;
    this.time += dt;

    if (this.state === STATES.ending) {
      this.doorPhase = Math.min(1, this.doorPhase + dt / this.rules.openDuration);
      this.doorsOpen = this.doorPhase;
      if (this.doorPhase >= 1) {
        this.state = STATES.done;
        events.push({ type: 'ending' });
      }
      return { events };
    }

    // Speranza: il buio la consuma, il calore la restituisce.
    const warmth = Math.min(1, Math.max(0, heat / this.rules.warmthFull));
    const drain = this.rules.drainInDark * (1 - warmth) - this.rules.gainNearFire * warmth;
    this.hope = Math.min(this.rules.hopeMax, this.hope - drain * dt);

    // Fuoco, lava e braci sono attraversabili: se ci cammini dentro, bruci.
    this.burning = inFire ? Math.min(1, this.burning + dt * 2.4)
      : Math.max(0, this.burning - dt * 1.6);
    if (this.burning > 0.05) {
      this.hope -= this.rules.burnDamage * this.burning * dt;
      if (!events.some((e) => e.type === 'burn')) events.push({ type: 'burn', amount: this.burning });
    }

    if (this.hope <= 0) {
      this.hope = 0;
      this.deaths += 1;
      this.state = STATES.dead;
      events.push({ type: 'dead' });
    }
    return { events };
  }

  /** Apre i battenti: possibile solo con tutte le anime. */
  beginOpening() {
    if (!this.allCollected || this.state !== STATES.playing) return false;
    this.state = STATES.ending;
    this.doorPhase = 0;
    return true;
  }

  stats() {
    return {
      time: this.time,
      distance: this.distance,
      collected: this.collected,
      total: this.total,
      deaths: this.deaths,
    };
  }
}

/** Versi di riserva, se scene.json non ne porta. */
export const FALLBACK_VERSES = [
  ['Nel mezzo del cammin di nostra vita\nmi ritrovai per una selva oscura.', 'Inferno I, 1-2'],
  ['Per me si va ne la città dolente.', 'Inferno III, 1'],
  ['Lasciate ogne speranza, voi ch\'intrate.', 'Inferno III, 9'],
];
