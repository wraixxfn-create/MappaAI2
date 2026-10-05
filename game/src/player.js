/**
 * Controlli in prima persona: pointer lock, sguardo, andatura, lanterna.
 * La fisica sta in physics.js; qui c'è solo input e camera.
 */
import * as THREE from 'three';
import { stepCapsule } from './physics.js';

const EYE = 1.62;

export class Player {
  constructor({ camera, capsule, dom, audio, sensitivity = 1 }) {
    this.camera = camera;
    this.capsule = capsule;
    this.dom = dom;
    this.audio = audio;
    this.sensitivity = sensitivity;

    this.yaw = 0;
    this.pitch = 0;
    this.keys = new Set();
    this.locked = false;
    this.bobPhase = 0;
    this.bobAmount = 0;
    this.stepAccumulator = 0;
    this.moving = false;
    this.running = false;
    this.wantJump = false;
    this.touchMove = new THREE.Vector2();
    this.eyeHeight = EYE;
    this.onStep = null;

    this.forward = new THREE.Vector3();
    this.right = new THREE.Vector3();
    this.wish = new THREE.Vector3();

    this.bind();
  }

  bind() {
    this.onKeyDown = (e) => {
      const code = e.code;
      if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Tab'].includes(code)) e.preventDefault();
      this.keys.add(code);
      if (code === 'Space') this.wantJump = true;
    };
    this.onKeyUp = (e) => this.keys.delete(e.code);
    this.onBlur = () => this.keys.clear();
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
    window.addEventListener('blur', this.onBlur);

    this.onMouseMove = (e) => {
      if (!this.locked) return;
      const s = 0.0022 * this.sensitivity;
      this.yaw -= e.movementX * s;
      this.pitch -= e.movementY * s;
      this.pitch = Math.max(-1.45, Math.min(1.45, this.pitch));
    };
    document.addEventListener('mousemove', this.onMouseMove);

    this.onLockChange = () => {
      this.locked = document.pointerLockElement === this.dom;
      if (this.onLock) this.onLock(this.locked);
    };
    document.addEventListener('pointerlockchange', this.onLockChange);

    this.onTouchLook = (e) => {
      const t = e.changedTouches[0];
      if (!t || t.clientX < window.innerWidth * 0.45) return;
      if (this.lastTouch) {
        const s = 0.005 * this.sensitivity;
        this.yaw -= (t.clientX - this.lastTouch.x) * s;
        this.pitch -= (t.clientY - this.lastTouch.y) * s;
        this.pitch = Math.max(-1.45, Math.min(1.45, this.pitch));
      }
      this.lastTouch = { x: t.clientX, y: t.clientY };
    };
    document.addEventListener('touchmove', this.onTouchLook, { passive: true });
    document.addEventListener('touchend', () => { this.lastTouch = null; }, { passive: true });
  }

  requestLock() {
    if (!this.dom.requestPointerLock) return;
    // Dopo un'uscita da pointer lock il browser impone una breve pausa: la
    // richiesta può essere rifiutata, e allora si riprova al click successivo.
    try {
      const result = this.dom.requestPointerLock();
      if (result && typeof result.catch === 'function') result.catch(() => {});
    } catch {
      /* ritentato al prossimo click sulla scena */
    }
  }

  setLook(yaw, pitch = 0) { this.yaw = yaw; this.pitch = pitch; }

  setTouchMove(x, y) { this.touchMove.set(x, y); }

  /** Direzione di movimento desiderata, già orientata con lo sguardo. */
  readWish(target = this.wish) {
    target.set(0, 0, 0);
    const k = this.keys;
    const fwd = (k.has('KeyW') || k.has('ArrowUp') ? 1 : 0) - (k.has('KeyS') || k.has('ArrowDown') ? 1 : 0);
    const strafe = (k.has('KeyD') || k.has('ArrowRight') ? 1 : 0) - (k.has('KeyA') || k.has('ArrowLeft') ? 1 : 0);
    this.forward.set(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
    this.right.set(Math.cos(this.yaw), 0, -Math.sin(this.yaw));
    target.addScaledVector(this.forward, fwd).addScaledVector(this.right, strafe);
    target.x += this.forward.x * -this.touchMove.y + this.right.x * this.touchMove.x;
    target.z += this.forward.z * -this.touchMove.y + this.right.z * this.touchMove.x;
    if (target.lengthSq() > 1) target.normalize();
    return target;
  }

  update(dt, bvh, options = {}) {
    const wish = this.readWish();
    this.running = (this.keys.has('ShiftLeft') || this.keys.has('ShiftRight')) && wish.lengthSq() > 0.01;
    const speed = options.runSpeed ?? 7.2;
    const walkSpeed = options.walkSpeed ?? 3.4;

    const result = stepCapsule(bvh, this.capsule, dt, {
      move: wish,
      jump: this.wantJump,
    }, { maxSpeed: this.running ? speed : walkSpeed });
    this.wantJump = false;
    this.moving = result.horizontal > 0.002;

    // Andatura: il sobbalzo della camera e i passi sulla cenere.
    const speedNow = result.horizontal / Math.max(1e-4, dt);
    const bobTarget = this.capsule.grounded && this.moving ? Math.min(1, speedNow / 4) : 0;
    this.bobAmount += (bobTarget - this.bobAmount) * Math.min(1, dt * 8);
    this.bobPhase += dt * (5.4 + speedNow * 1.5) * (this.running ? 1.25 : 1);

    const bobY = Math.sin(this.bobPhase * 2) * 0.035 * this.bobAmount;
    const bobX = Math.cos(this.bobPhase) * 0.028 * this.bobAmount;
    const roll = Math.cos(this.bobPhase) * 0.0075 * this.bobAmount;

    const crouch = this.keys.has('KeyC') || this.keys.has('ControlLeft') ? 0.42 : 0;
    this.eyeHeight += (EYE - crouch - this.eyeHeight) * Math.min(1, dt * 9);

    this.camera.position.set(
      this.capsule.position.x + bobX * Math.cos(this.yaw),
      this.capsule.position.y + this.eyeHeight + bobY,
      this.capsule.position.z - bobX * Math.sin(this.yaw),
    );
    this.camera.rotation.set(this.pitch, this.yaw, roll, 'YXZ');

    if (this.capsule.grounded && this.moving) {
      this.stepAccumulator += dt * (this.running ? 2.1 : 1.5);
      if (this.stepAccumulator >= 1) {
        this.stepAccumulator = 0;
        if (this.onStep) this.onStep(this.running);
      }
    } else {
      this.stepAccumulator = Math.min(this.stepAccumulator, 0.75);
    }

    return result;
  }

  dispose() {
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
    window.removeEventListener('blur', this.onBlur);
    document.removeEventListener('mousemove', this.onMouseMove);
    document.removeEventListener('pointerlockchange', this.onLockChange);
    document.removeEventListener('touchmove', this.onTouchLook);
  }
}
