/**
 * Hook di risoluzione per i test headless: 'three' e le sue addon puntano a
 * game/vendor/, gli stessi file serviti al browser dall'import map.
 */
const VENDOR = new URL('../vendor/', import.meta.url);

export function resolve(specifier, context, next) {
  if (specifier === 'three') {
    return { url: new URL('three/three.module.js', VENDOR).href, shortCircuit: true };
  }
  if (specifier.startsWith('three/addons/')) {
    return {
      url: new URL(specifier.replace('three/addons/', 'three-addons/'), VENDOR).href,
      shortCircuit: true,
    };
  }
  if (specifier.startsWith('three-mesh-bvh/')) {
    return {
      url: new URL(specifier.replace('three-mesh-bvh/', 'three-mesh-bvh/'), VENDOR).href,
      shortCircuit: true,
    };
  }
  return next(specifier, context);
}
