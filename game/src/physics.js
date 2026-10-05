/**
 * Fisica del giocatore: capsula contro la mesh di collisione esportata dal
 * .blend, risolta con l'BVH di three-mesh-bvh.
 *
 * Nessuna dipendenza dal DOM: questo modulo è usato anche dai test headless.
 */
import { Box3, DoubleSide, Line3, Ray, Sphere, Vector3 } from 'three';
import { MeshBVH } from 'three-mesh-bvh/core/MeshBVH.js';
import { NOT_INTERSECTED } from 'three-mesh-bvh/core/Constants.js';

export const GRAVITY = 23.0;

// Margine con cui si solleva la capsula oltre l'altezza del gradino.
const STEP_CLEARANCE = 0.06;

export function buildBVH(geometry, options = {}) {
  geometry.boundsTree = new MeshBVH(geometry, { maxLeafTris: 8, ...options });
  return geometry.boundsTree;
}

/** Un giocatore-capsula: `position` sono i piedi, in metri, coordinate di gioco. */
export class Capsule {
  constructor({ radius = 0.34, height = 1.78, position = [0, 0, 0] } = {}) {
    this.radius = radius;
    this.height = height;
    this.position = new Vector3(...position);
    this.velocity = new Vector3();
    this.grounded = false;
    this.headBumped = false;
    this.lastImpact = 0;
  }

  segment(target = new Line3()) {
    target.start.set(this.position.x, this.position.y + this.radius, this.position.z);
    target.end.set(this.position.x, this.position.y + this.height - this.radius, this.position.z);
    return target;
  }
}

const _box = new Box3();
const _sphere = new Sphere();
const _segment = new Line3();
const _triPoint = new Vector3();
const _capsulePoint = new Vector3();
const _delta = new Vector3();
const _ray = new Ray();
const _wish = new Vector3();
const _offset = new Vector3();

/**
 * Spinge la capsula fuori dalla geometria lungo il vettore di minima
 * traslazione. Restituisce lo spostamento totale applicato.
 */
export function resolvePenetration(bvh, capsule, out = new Vector3()) {
  const startX = capsule.position.x;
  const startY = capsule.position.y;
  const startZ = capsule.position.z;

  for (let pass = 0; pass < 4; pass += 1) {
    let moved = false;
    capsule.segment(_segment);
    _box.makeEmpty();
    _box.expandByPoint(_segment.start);
    _box.expandByPoint(_segment.end);
    _box.expandByScalar(capsule.radius + 0.02);
    _sphere.center.copy(_segment.start).lerp(_segment.end, 0.5);
    _sphere.radius = _segment.distance() * 0.5 + capsule.radius;

    bvh.shapecast({
      intersectsBounds: (box) => (box.intersectsBox(_box) ? 1 : NOT_INTERSECTED),
      intersectsTriangle: (tri) => {
        tri.closestPointToSegment(_segment, _triPoint, _capsulePoint);
        const distance = _triPoint.distanceTo(_capsulePoint);
        if (distance >= capsule.radius) return false;
        const depth = capsule.radius - distance;
        if (distance > 1e-6) _delta.subVectors(_capsulePoint, _triPoint).normalize();
        else _delta.set(0, 1, 0);
        _segment.start.addScaledVector(_delta, depth);
        _segment.end.addScaledVector(_delta, depth);
        moved = true;
        return false;
      },
    });

    if (!moved) break;
  }

  capsule.position.set(_segment.start.x, _segment.start.y - capsule.radius, _segment.start.z);
  return out.set(
    capsule.position.x - startX,
    capsule.position.y - startY,
    capsule.position.z - startZ,
  );
}

/** Distanza verticale dal primo suolo sotto i piedi, o null se non c'è. */
export function groundDistance(bvh, capsule, reach = 0.8) {
  _ray.origin.set(capsule.position.x, capsule.position.y + 0.25, capsule.position.z);
  _ray.direction.set(0, -1, 0);
  const hit = bvh.raycastFirst(_ray, DoubleSide, 0, reach + 0.25);
  if (!hit) return null;
  return _ray.origin.y - hit.point.y - 0.25;
}

/** Altezza del suolo in (x, z): per spawn, respawn e appoggio degli oggetti. */
export function groundHeightAt(bvh, x, z, fromY = 60, reach = 140) {
  _ray.origin.set(x, fromY, z);
  _ray.direction.set(0, -1, 0);
  const hit = bvh.raycastFirst(_ray, DoubleSide, 0, reach);
  return hit ? hit.point.y : null;
}


/**
 * Sbarra del varco. La geometria dei battenti, semplificata per la fisica, può
 * lasciare fessure: il varco è quindi presidiato anche da questo vincolo, che
 * si apre solo quando i battenti sono spalancati.
 *
 * Il piano è ricavato dalla posizione dei battenti chiusi nel modello.
 */
export const DOOR_BARRIER = {
  z: 0.83,      // fronte dei battenti chiusi
  halfWidth: 4.7,
  top: 14,      // sopra i 14 m c'è l'arco, non serve sbarra
  openAt: 0.55, // oltre questa apertura si passa
};

/**
 * Impedisce al giocatore di oltrepassare i battenti chiusi.
 * @returns {boolean} true se è stato respinto
 */
export function applyDoorBarrier(capsule, doorsOpen = 0, barrier = DOOR_BARRIER) {
  if (doorsOpen >= barrier.openAt) return false;
  const { x, y, z } = capsule.position;
  if (Math.abs(x) > barrier.halfWidth || y > barrier.top) return false;
  const limit = barrier.z + capsule.radius;
  if (z >= limit) return false;
  capsule.position.z = limit;
  if (capsule.velocity.z < 0) capsule.velocity.z = 0;
  return true;
}

export function clamp(v, min, max) {
  return v < min ? min : (v > max ? max : v);
}

/**
 * Un passo di simulazione. `input.move` è il desiderio di movimento orizzontale
 * normalizzato (già orientato secondo lo sguardo), `input.jump` il salto.
 */
/**
 * Prova uno spostamento orizzontale a una data altezza e dice quanto è
 * effettivamente avanzato. Usata per i gradini: si riprova più in alto.
 */
function tryMove(bvh, capsule, offset, lift, vertical, start) {
  capsule.position.copy(start);
  capsule.position.y += lift + vertical;
  capsule.position.x += offset.x;
  capsule.position.z += offset.z;
  resolvePenetration(bvh, capsule);
  return {
    horizontal: Math.hypot(capsule.position.x - start.x, capsule.position.z - start.z),
    lifted: lift,
    position: capsule.position.clone(),
  };
}

export function stepCapsule(bvh, capsule, dt, input, options = {}) {
  const {
    accel = 70, airAccel = 18, friction = 12, maxSpeed = 4.4,
    // La scalinata cerimoniale ha alzate di ~1,3 m: si sale saltando
    // (il salto copre ~1,5 m), non camminando.
    jumpSpeed = 8.4, stepHeight = 0.8,
  } = options;

  const before = capsule.position.clone();
  const wish = input.move || _wish.set(0, 0, 0);
  const moving = wish.lengthSq() > 1e-6;
  const wasGrounded = capsule.grounded;
  capsule.headBumped = false;

  if (moving) {
    const control = wasGrounded ? accel : airAccel;
    const dx = clamp(wish.x * maxSpeed - capsule.velocity.x, -control * dt, control * dt);
    const dz = clamp(wish.z * maxSpeed - capsule.velocity.z, -control * dt, control * dt);
    capsule.velocity.x += dx;
    capsule.velocity.z += dz;
  } else if (wasGrounded) {
    const speed = Math.hypot(capsule.velocity.x, capsule.velocity.z);
    if (speed > 1e-4) {
      const scale = Math.max(0, 1 - (friction * dt));
      capsule.velocity.x *= scale;
      capsule.velocity.z *= scale;
    }
  }

  if (input.jump && wasGrounded) {
    capsule.velocity.y = jumpSpeed;
    capsule.grounded = false;
  }

  capsule.velocity.y -= GRAVITY * dt;
  if (capsule.velocity.y < -55) capsule.velocity.y = -55;

  // Spostamento di questo passo: orizzontale dalla velocità, verticale dalla
  // gravità. Entrambi vanno applicati, altrimenti si resta sospesi in aria.
  _offset.set(capsule.velocity.x * dt, 0, capsule.velocity.z * dt);
  const wanted = _offset.length();
  const vertical = capsule.velocity.y * dt;
  const start = capsule.position.clone();
  let push;
  if (wanted > 1e-9) {
    let attempt = tryMove(bvh, capsule, _offset, 0, vertical, start);
    // Se qualcosa ci blocca e siamo a terra, riproviamo più in alto: è un
    // gradino. La scalinata cerimoniale ha alzate di ~0,8 m.
    if (wasGrounded && stepHeight > 0 && attempt.horizontal < wanted * 0.72) {
      // Il sollevamento supera il gradino di un margine: senza margine la
      // capsula resterebbe qualche millimetro sotto il bordo e verrebbe
      // respinta indietro invece di salire.
      const lift = stepHeight + STEP_CLEARANCE;
      const lifted = tryMove(bvh, capsule, _offset, lift, vertical, start);
      if (lifted.horizontal > attempt.horizontal + 1e-4) {
        attempt = lifted;
        // Riscende e lascia che la risoluzione delle compenetrazioni lo appoggi
        // sulla superficie che ha sotto: il gradino, se è sopra il gradino.
        capsule.position.y -= lift;
        resolvePenetration(bvh, capsule);
      } else {
        capsule.position.copy(attempt.position);
      }
    }
    push = attempt.position.clone().sub(start);
  } else {
    capsule.position.y += vertical;
    push = resolvePenetration(bvh, capsule);
  }

  const below = groundDistance(bvh, capsule, 0.55);
  const standing = below !== null && below <= 0.14 && capsule.velocity.y <= 0.001;
  const pushedUp = push.y > 1e-4 && capsule.velocity.y <= 0.001;
  capsule.grounded = standing || pushedUp;

  if (capsule.grounded && capsule.velocity.y < 0) capsule.velocity.y = 0;
  if (!capsule.grounded && push.y < -1e-4 && capsule.velocity.y > 0) {
    capsule.velocity.y = 0;
    capsule.headBumped = true;
  }

  const fallSpeed = -push.y;
  if (push.y < -0.35) capsule.lastImpact = Math.max(capsule.lastImpact, fallSpeed);

  return {
    delta: capsule.position.clone().sub(before),
    horizontal: Math.hypot(capsule.position.x - before.x, capsule.position.z - before.z),
    grounded: capsule.grounded,
    headBumped: capsule.headBumped,
    groundDistance: below,
  };
}
