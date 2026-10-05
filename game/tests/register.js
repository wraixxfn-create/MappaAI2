/**
 * Registrato con `node --import` prima dei test: risolve gli import nudi
 * ('three', 'three/addons/', 'three-mesh-bvh/') verso game/vendor/, così i
 * test headless usano esattamente gli stessi file del browser, e offre un
 * minimo shim DOM per i moduli che ascoltano tastiera e mouse.
 */
import { register } from 'node:module';

globalThis.self ??= globalThis;

if (typeof globalThis.window === 'undefined') {
  const listeners = new Map();
  const noop = () => {};
  globalThis.window = globalThis;
  globalThis.window.innerWidth = 1280;
  globalThis.window.innerHeight = 720;
  globalThis.window.devicePixelRatio = 1;
  globalThis.window.addEventListener = noop;
  globalThis.window.removeEventListener = noop;
  globalThis.window.matchMedia = () => ({ matches: false, addEventListener: noop });
  globalThis.window.AudioContext = undefined;
  globalThis.window.webkitAudioContext = undefined;
  globalThis.document = {
    addEventListener: noop,
    removeEventListener: noop,
    pointerLockElement: null,
    exitPointerLock: noop,
    getElementById: () => null,
    createElement: () => ({ width: 0, height: 0, getContext: () => null }),
  };
  globalThis.navigator ??= { userAgent: 'node' };
  globalThis.listeners = listeners;
}

register('./hooks.mjs', import.meta.url);
