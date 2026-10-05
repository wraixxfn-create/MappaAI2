/**
 * Heightmap esportata dal .blend: altezza del terreno (16 bit) + calore delle
 * braci. Serve per la minimappa e come riserva per l'altezza del suolo.
 *
 * La parte di campionamento è pura (nessun DOM): la usano anche i test.
 */

/**
 * @param {{width:number,height:number,region:number[],zRange:number[]}} meta
 *   region è [xMin, zMin, xMax, zMax] in coordinate di gioco.
 * @param {Uint8Array|Uint8ClampedArray} rgba pixel RGBA, riga per riga.
 */
export function createHeightField(meta, rgba) {
  const { width, height, region, zRange } = meta;
  const [xMin, zMin, xMax, zMax] = region;
  const heights = new Float32Array(width * height);
  const heat = new Float32Array(width * height);
  const valid = new Uint8Array(width * height);
  const span = zRange[1] - zRange[0];
  for (let i = 0; i < width * height; i += 1) {
    const o = i * 4;
    if (rgba[o + 3] === 0) { heights[i] = zRange[0]; continue; }
    const q = (rgba[o] << 8) | rgba[o + 1];
    heights[i] = zRange[0] + (q / 65535) * span;
    heat[i] = rgba[o + 2] / 255;
    valid[i] = 1;
  }
  return {
    meta,
    width,
    height,
    region,
    zRange,
    heights,
    heat,
    valid,
    heightAt(x, z) { return sample(heights, width, height, xMin, zMin, xMax, zMax, x, z, zRange[0]); },
    heatAt(x, z) { return sample(heat, width, height, xMin, zMin, xMax, zMax, x, z, 0); },
    has(x, z) {
      const [ix, iz] = indices(width, height, xMin, zMin, xMax, zMax, x, z);
      return ix !== null && valid[iz * width + ix] === 1;
    },
  };
}

function indices(width, height, xMin, zMin, xMax, zMax, x, z) {
  if (x < xMin || x > xMax || z < zMin || z > zMax) return [null, null];
  const ix = Math.min(width - 1, Math.max(0, Math.round(((x - xMin) / (xMax - xMin)) * (width - 1))));
  const iz = Math.min(height - 1, Math.max(0, Math.round(((z - zMin) / (zMax - zMin)) * (height - 1))));
  return [ix, iz];
}

function sample(grid, width, height, xMin, zMin, xMax, zMax, x, z, fallback) {
  const [ix, iz] = indices(width, height, xMin, zMin, xMax, zMax, x, z);
  if (ix === null) return fallback;
  return grid[iz * width + ix];
}

/**
 * Converte la regione della heightmap (esportata in coordinate Blender) nella
 * regione di gioco: Blender (x, y, z) -> gioco (x, z, -y).
 */
export function regionToGame(meta) {
  const [x0, y0, x1, y1] = meta.region;
  return { ...meta, region: [Math.min(x0, x1), -Math.max(y0, y1), Math.max(x0, x1), -Math.min(y0, y1)] };
}

/** Legge il PNG della heightmap nel browser. */
export async function loadHeightField(url, meta) {
  const image = await loadImage(url);
  const canvas = document.createElement('canvas');
  canvas.width = image.width;
  canvas.height = image.height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(image, 0, 0);
  const { data } = ctx.getImageData(0, 0, image.width, image.height);
  if (image.width !== meta.width || image.height !== meta.height) {
    throw new Error(`heightmap: attesi ${meta.width}x${meta.height}, trovati ${image.width}x${image.height}`);
  }
  return createHeightField(regionToGame(meta), data);
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`impossibile leggere ${url}`));
    img.src = url;
  });
}

/* ------------------------------------------------------------------ */
/* Disegno della mappa                                                  */
/* ------------------------------------------------------------------ */

/**
 * Rilievo ombreggiato + calore: una volta sola, su una canvas offscreen.
 * @returns {HTMLCanvasElement}
 */
export function renderMapCanvas(field, size = 512) {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = Math.max(1, Math.round(size * (field.height / field.width)));
  const ctx = canvas.getContext('2d');
  const img = ctx.createImageData(canvas.width, canvas.height);
  const light = normalize([-0.55, -0.7, 0.45]);
  const scaleX = (field.region[2] - field.region[0]) / field.width;
  const scaleZ = (field.region[3] - field.region[1]) / field.height;
  for (let z = 0; z < canvas.height; z += 1) {
    for (let x = 0; x < canvas.width; x += 1) {
      const i = z * canvas.width + x;
      const h = field.heights[i];
      const dx = (field.heights[i + 1] ?? h) - (field.heights[i - 1] ?? h);
      const dz = (field.heights[i + field.width] ?? h) - (field.heights[i - field.width] ?? h);
      const nx = -dz / (2 * scaleZ);
      const nz = -dx / (2 * scaleX);
      const ny = 1;
      const len = Math.hypot(nx, ny, nz);
      const lambert = Math.max(0, (nx * light[0] + ny * light[1] + nz * light[2]) / len);
      const shade = 0.22 + 0.78 * lambert;
      const t = (h - field.zRange[0]) / (field.zRange[1] - field.zRange[0]);
      const heat = field.heat[i];
      const base = 12 + t * 46;
      const o = i * 4;
      img.data[o] = Math.min(255, base * shade + heat * 190);
      img.data[o + 1] = Math.min(255, base * shade * 0.92 + heat * 74);
      img.data[o + 2] = Math.min(255, base * shade * 0.95 + heat * 22);
      img.data[o + 3] = field.valid[i] ? 255 : 0;
    }
  }
  ctx.putImageData(img, 0, 0);
  return canvas;
}

function normalize(v) {
  const l = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / l, v[1] / l, v[2] / l];
}

/** Proietta un punto del mondo nella canvas della mappa. */
export function worldToMap(field, width, height, x, z) {
  const [xMin, zMin, xMax, zMax] = field.region;
  return [((x - xMin) / (xMax - xMin)) * width, ((z - zMin) / (zMax - zMin)) * height];
}
