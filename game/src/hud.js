/**
 * Interfaccia: HUD, minimappa, bussola, sottotitoli dei versi.
 */
import { worldToMap } from './heightfield.js';

const $ = (id) => document.getElementById(id);

export class Hud {
  constructor() {
    this.el = {
      hud: $('hud'),
      sigilli: $('sigilli-count'),
      hopeFill: $('hope-fill'),
      objective: $('objective'),
      subtitle: $('subtitle'),
      prompt: $('prompt'),
      promptText: $('prompt-text'),
      toast: $('toast'),
      compass: $('compass-strip'),
      heatFlash: $('heat-flash'),
      minimap: $('minimap'),
      minimapLabel: $('minimap-label'),
      bigmap: $('bigmap'),
      hint: $('controls-hint'),
    };
    this.minimapCtx = this.el.minimap.getContext('2d');
    this.bigmapCtx = this.el.bigmap.getContext('2d');
    this.subtitleTimer = 0;
    this.toastTimer = 0;
    this.hintTimer = 0;
    this.buildCompass();
  }

  buildCompass() {
    const marks = [];
    for (let deg = 0; deg < 720; deg += 15) {
      const d = deg % 360;
      const label = d === 0 ? '<b>N</b>' : d === 90 ? '<b>E</b>' : d === 180 ? '<b>S</b>'
        : d === 270 ? '<b>O</b>' : d % 45 === 0 ? '·' : '';
      marks.push(`<span style="display:inline-block;width:26px;text-align:center">${label}</span>`);
    }
    this.el.compass.innerHTML = marks.join('');
    this.compassWidth = 26 * 24; // 360° = 24 tacche
  }

  show() { this.el.hud.classList.remove('hidden'); this.el.hud.setAttribute('aria-hidden', 'false'); }
  hide() { this.el.hud.classList.add('hidden'); this.el.hud.setAttribute('aria-hidden', 'true'); }

  setHope(v) {
    const pct = Math.max(0, Math.min(100, v));
    this.el.hopeFill.style.width = `${pct}%`;
    this.el.hopeFill.style.filter = pct < 25 ? 'saturate(1.6) brightness(1.25)' : 'none';
  }

  setSigils(n) { this.el.sigilli.textContent = String(n); }

  setObjective(text) { this.el.objective.textContent = text; }

  setPrompt(text) {
    if (!text) { this.el.prompt.classList.remove('show'); return; }
    this.el.promptText.textContent = text;
    this.el.prompt.classList.add('show');
  }

  showSubtitle(text, canto, seconds = 7) {
    this.el.subtitle.innerHTML = `${text}${canto ? `<em>${canto}</em>` : ''}`;
    this.el.subtitle.classList.add('show');
    this.subtitleTimer = seconds;
  }

  toast(text, seconds = 2.6) {
    this.el.toast.textContent = text;
    this.el.toast.classList.add('show');
    this.toastTimer = seconds;
  }

  setCompass(yaw, gateBearing) {
    // yaw: 0 = verso -Z (nord della valle). La bussola scorre in pixel.
    const deg = ((yaw * 180) / Math.PI) % 360;
    const offset = -((deg / 15) * 26) + this.el.compass.parentElement.clientWidth / 2 - 13;
    this.el.compass.style.transform = `translateX(${offset}px)`;
    this.gateBearing = gateBearing;
  }

  heatFlash(amount) {
    this.el.heatFlash.style.opacity = String(Math.max(0, Math.min(0.85, amount)));
  }

  fadeControls(after = 14) { this.hintTimer = after; }

  update(dt) {
    if (this.subtitleTimer > 0) {
      this.subtitleTimer -= dt;
      if (this.subtitleTimer <= 0) this.el.subtitle.classList.remove('show');
    }
    if (this.toastTimer > 0) {
      this.toastTimer -= dt;
      if (this.toastTimer <= 0) this.el.toast.classList.remove('show');
    }
    if (this.hintTimer > 0) {
      this.hintTimer -= dt;
      if (this.hintTimer <= 0) this.el.hint.classList.add('faded');
    }
  }

  /* ------------------------------ mappe ------------------------------ */

  /** Minimappa circolare, nord in alto, centrata sul giocatore. */
  drawMinimap(field, mapCanvas, view) {
    const ctx = this.minimapCtx;
    const size = this.el.minimap.width;
    const c = size / 2;
    const radiusMetres = view.radius ?? 55;
    ctx.clearRect(0, 0, size, size);
    ctx.save();
    ctx.beginPath();
    ctx.arc(c, c, c - 1, 0, Math.PI * 2);
    ctx.clip();
    ctx.fillStyle = '#07060a';
    ctx.fillRect(0, 0, size, size);

    const scale = size / (radiusMetres * 2);
    const [px, pz] = worldToMap(field, mapCanvas.width, mapCanvas.height, view.position.x, view.position.z);
    const sw = radiusMetres * 2 * (mapCanvas.width / (field.region[2] - field.region[0]));
    const sh = radiusMetres * 2 * (mapCanvas.height / (field.region[3] - field.region[1]));
    ctx.drawImage(mapCanvas, px - sw / 2, pz - sh / 2, sw, sh, 0, 0, size, size);

    const toScreen = (x, z) => [c + (x - view.position.x) * scale, c + (z - view.position.z) * scale];

    // calore della soglia
    if (view.gate) {
      const [gx, gz] = toScreen(view.gate.position.x, view.gate.position.z);
      const g = ctx.createRadialGradient(gx, gz, 0, gx, gz, 26);
      g.addColorStop(0, 'rgba(255,120,40,0.55)');
      g.addColorStop(1, 'rgba(255,80,20,0)');
      ctx.fillStyle = g;
      ctx.fillRect(gx - 26, gz - 26, 52, 52);
      ctx.strokeStyle = 'rgba(255,170,110,0.9)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(gx - 7, gz); ctx.lineTo(gx + 7, gz);
      ctx.moveTo(gx, gz - 7); ctx.lineTo(gx, gz + 7);
      ctx.stroke();
    }

    for (const p of view.points) {
      const [sx, sz] = toScreen(p.position.x, p.position.z);
      if (sx < -6 || sx > size + 6 || sz < -6 || sz > size + 6) continue;
      ctx.beginPath();
      ctx.arc(sx, sz, p.taken ? 2.4 : 4.2, 0, Math.PI * 2);
      ctx.fillStyle = p.taken ? 'rgba(180,160,150,0.5)' : 'rgba(255,206,140,0.95)';
      ctx.fill();
      if (!p.taken) {
        ctx.strokeStyle = 'rgba(255,120,40,0.6)';
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }

    // il giocatore: freccia orientata
    ctx.translate(c, c);
    ctx.rotate(view.yaw);
    ctx.beginPath();
    ctx.moveTo(0, -8);
    ctx.lineTo(5.5, 6);
    ctx.lineTo(0, 3);
    ctx.lineTo(-5.5, 6);
    ctx.closePath();
    ctx.fillStyle = '#ffe0bf';
    ctx.fill();
    ctx.restore();

    ctx.strokeStyle = 'rgba(255,150,90,0.35)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(c, c, c - 1, 0, Math.PI * 2);
    ctx.stroke();
  }

  /** Mappa grande (tasto M). */
  drawBigMap(field, mapCanvas, view) {
    const ctx = this.bigmapCtx;
    const { width, height } = this.el.bigmap;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = '#06050a';
    ctx.fillRect(0, 0, width, height);
    const scale = Math.min(width / mapCanvas.width, height / mapCanvas.height);
    const w = mapCanvas.width * scale;
    const h = mapCanvas.height * scale;
    const ox = (width - w) / 2;
    const oy = (height - h) / 2;
    ctx.drawImage(mapCanvas, ox, oy, w, h);

    const project = (x, z) => {
      const [mx, mz] = worldToMap(field, mapCanvas.width, mapCanvas.height, x, z);
      return [ox + mx * scale, oy + mz * scale];
    };

    ctx.font = '12px Georgia, serif';
    if (view.gate) {
      const [gx, gz] = project(view.gate.position.x, view.gate.position.z);
      ctx.strokeStyle = 'rgba(255,140,70,0.95)';
      ctx.lineWidth = 2;
      ctx.strokeRect(gx - 10, gz - 10, 20, 20);
      ctx.fillStyle = 'rgba(255,190,140,0.9)';
      ctx.fillText('la Porta', gx + 15, gz + 4);
    }
    view.points.forEach((p, i) => {
      const [sx, sz] = project(p.position.x, p.position.z);
      ctx.beginPath();
      ctx.arc(sx, sz, p.taken ? 3 : 6, 0, Math.PI * 2);
      ctx.fillStyle = p.taken ? 'rgba(170,150,140,0.6)' : 'rgba(255,206,140,0.95)';
      ctx.fill();
      ctx.fillStyle = 'rgba(230,210,195,0.75)';
      ctx.fillText(p.taken ? '' : String(i + 1), sx + 9, sz + 4);
    });
    const [px, pz] = project(view.position.x, view.position.z);
    ctx.save();
    ctx.translate(px, pz);
    ctx.rotate(view.yaw);
    ctx.beginPath();
    ctx.moveTo(0, -11); ctx.lineTo(7, 8); ctx.lineTo(0, 4); ctx.lineTo(-7, 8);
    ctx.closePath();
    ctx.fillStyle = '#fff0dd';
    ctx.fill();
    ctx.restore();
  }
}

/** Schermate di stato. */
export class Screens {
  constructor() {
    this.overlay = $('overlay');
    this.screens = {
      loading: $('screen-loading'),
      menu: $('screen-menu'),
      pause: $('screen-pause'),
      map: $('screen-map'),
      dead: $('screen-dead'),
      end: $('screen-end'),
      error: $('screen-error'),
    };
  }

  show(name) {
    this.overlay.classList.remove('hidden');
    Object.entries(this.screens).forEach(([key, el]) => el.classList.toggle('hidden', key !== name));
  }

  hide() {
    this.overlay.classList.add('hidden');
    Object.values(this.screens).forEach((el) => el.classList.add('hidden'));
  }

  progress(ratio, label) {
    $('load-fill').style.width = `${Math.round(Math.max(0, Math.min(1, ratio)) * 100)}%`;
    if (label) $('load-status').textContent = label;
  }

  error(message) {
    $('error-text').textContent = message;
    this.show('error');
  }

  end(stats) {
    const minutes = Math.floor(stats.time / 60);
    const seconds = Math.round(stats.time % 60);
    $('end-text').textContent = stats.deaths > 0
      ? 'I battenti hanno ceduto. Oltre la soglia non c\'è fuoco: c\'è qualcosa che ti ha guardato per tutto il tempo, e ora conosce il tuo nome.'
      : 'Nessuna esitazione, nessuna caduta: sei arrivato alla soglia con la lanterna ancora accesa. Oltre il varco, due occhi si chiudono.';
    $('end-stats').innerHTML = [
      `tempo nella valle: ${minutes}′ ${String(seconds).padStart(2, '0')}″`,
      `passi nella cenere: ${Math.round(stats.distance).toLocaleString('it-IT')} m`,
      `anime ascoltate: ${stats.collected}/${stats.total}`,
      `volte che il buio ti ha preso: ${stats.deaths}`,
    ].join('<br />');
  }

  pauseStats(stats) {
    const minutes = Math.floor(stats.time / 60);
    const seconds = Math.round(stats.time % 60);
    $('pause-stats').innerHTML =
      `${stats.collected}/${stats.total} anime · ${Math.round(stats.distance)} m percorsi · ${minutes}′ ${String(seconds).padStart(2, '0')}″`;
  }
}
