/**
 * Audio interamente procedurale (WebAudio): nessun file esterno. Vento di
 * cenere, respiro del fuoco, passi sulla pietra, campane per le anime.
 */
export class Ambience {
  constructor() {
    this.ctx = null;
    this.enabled = true;
    this.ready = false;
    this.heat = 0;
    this.nextCrackle = 0;
    this.stepPhase = 0;
  }

  init() {
    if (this.ctx) return this.ctx;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    try {
      this.ctx = new Ctx();
    } catch (err) {
      console.warn('audio non disponibile:', err);
      return null;
    }
    const ctx = this.ctx;

    this.master = ctx.createGain();
    this.master.gain.value = this.enabled ? 0.9 : 0;
    this.master.connect(ctx.destination);

    // Vento: rumore bruno filtrato, con un LFO lento sull'apertura.
    const noiseBuffer = this.noiseBuffer(4);
    this.windSource = ctx.createBufferSource();
    this.windSource.buffer = noiseBuffer;
    this.windSource.loop = true;
    this.windFilter = ctx.createBiquadFilter();
    this.windFilter.type = 'lowpass';
    this.windFilter.frequency.value = 320;
    this.windFilter.Q.value = 0.6;
    this.windGain = ctx.createGain();
    this.windGain.gain.value = 0.09;
    this.windSource.connect(this.windFilter).connect(this.windGain).connect(this.master);
    this.windSource.start();

    this.lfo = ctx.createOscillator();
    this.lfo.frequency.value = 0.06;
    this.lfoGain = ctx.createGain();
    this.lfoGain.gain.value = 130;
    this.lfo.connect(this.lfoGain).connect(this.windFilter.frequency);
    this.lfo.start();

    // Bordone basso: la valle che rimbomba.
    this.droneGain = ctx.createGain();
    this.droneGain.gain.value = 0.05;
    this.droneGain.connect(this.master);
    this.drones = [41.2, 61.7, 82.4].map((freq, i) => {
      const osc = ctx.createOscillator();
      osc.type = i === 2 ? 'triangle' : 'sine';
      osc.frequency.value = freq;
      const g = ctx.createGain();
      g.gain.value = i === 0 ? 0.5 : 0.22;
      osc.connect(g).connect(this.droneGain);
      osc.start();
      const wob = ctx.createOscillator();
      wob.frequency.value = 0.03 + i * 0.017;
      const wobGain = ctx.createGain();
      wobGain.gain.value = 0.6 + i * 0.3;
      wob.connect(wobGain).connect(osc.frequency);
      wob.start();
      return osc;
    });

    // Crackling del fuoco: raffiche di rumore su un banda stretta.
    this.crackleFilter = ctx.createBiquadFilter();
    this.crackleFilter.type = 'bandpass';
    this.crackleFilter.frequency.value = 1400;
    this.crackleFilter.Q.value = 1.1;
    this.crackleGain = ctx.createGain();
    this.crackleGain.gain.value = 0;
    this.crackleFilter.connect(this.crackleGain).connect(this.master);
    this.noise = noiseBuffer;

    this.ready = true;
    return ctx;
  }

  noiseBuffer(seconds) {
    const ctx = this.ctx;
    const length = Math.floor(ctx.sampleRate * seconds);
    const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    let last = 0;
    for (let i = 0; i < length; i += 1) {
      const white = Math.random() * 2 - 1;
      last = (last + 0.02 * white) / 1.02;
      data[i] = last * 3.2 + white * 0.28;
    }
    return buffer;
  }

  setEnabled(on) {
    this.enabled = on;
    if (this.master) {
      this.master.gain.setTargetAtTime(on ? 0.9 : 0, this.ctx.currentTime, 0.1);
    }
    if (on && this.ctx?.state === 'suspended') this.ctx.resume();
  }

  resume() { if (this.ctx?.state === 'suspended') this.ctx.resume(); }

  /** 0 = buio freddo, 1 = dentro il fuoco. */
  setHeat(v) {
    this.heat = Math.max(0, Math.min(1, v));
    if (!this.ready || !this.enabled) return;
    const t = this.ctx.currentTime;
    this.crackleGain.gain.setTargetAtTime(this.heat * 0.16, t, 0.4);
    this.windGain.gain.setTargetAtTime(0.09 - this.heat * 0.03, t, 0.6);
    this.droneGain.gain.setTargetAtTime(0.05 + this.heat * 0.05, t, 0.8);
  }

  update(dt, now = performance.now() / 1000) {
    if (!this.ready || !this.enabled) return;
    if (this.heat > 0.08 && now > this.nextCrackle) {
      this.crackle();
      this.nextCrackle = now + 0.05 + Math.random() * (0.35 / Math.max(0.1, this.heat));
    }
  }

  burst(duration, volume, filterFreq = 900, type = 'lowpass') {
    if (!this.ready || !this.enabled) return;
    const ctx = this.ctx;
    const src = ctx.createBufferSource();
    src.buffer = this.noise;
    src.playbackRate.value = 0.8 + Math.random() * 0.5;
    const f = ctx.createBiquadFilter();
    f.type = type;
    f.frequency.value = filterFreq;
    const g = ctx.createGain();
    const t = ctx.currentTime;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(volume, t + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t + duration);
    src.connect(f).connect(g).connect(this.master);
    src.start(t);
    src.stop(t + duration + 0.02);
  }

  crackle() { this.burst(0.05 + Math.random() * 0.07, 0.05 + Math.random() * 0.06, 1200 + Math.random() * 2200, 'bandpass'); }

  footstep(running = false) {
    this.burst(running ? 0.11 : 0.09, running ? 0.16 : 0.1, 240 + Math.random() * 180, 'lowpass');
  }

  tone(freq, duration, volume = 0.16, type = 'sine', delay = 0) {
    if (!this.ready || !this.enabled) return;
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.value = freq;
    const g = ctx.createGain();
    const t = ctx.currentTime + delay;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(volume, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + duration);
    osc.connect(g).connect(this.master);
    osc.start(t);
    osc.stop(t + duration + 0.05);
  }

  sigil(index = 0) {
    const base = 392 * Math.pow(2, (index % 5) / 12);
    this.tone(base, 2.4, 0.13, 'sine');
    this.tone(base * 1.5, 1.8, 0.07, 'sine', 0.06);
    this.tone(base * 2.01, 1.2, 0.04, 'triangle', 0.1);
  }

  door() {
    this.burst(2.6, 0.22, 140, 'lowpass');
    this.tone(58, 3.0, 0.1, 'sawtooth');
    this.tone(29, 3.4, 0.09, 'sine', 0.2);
  }

  death() {
    this.tone(146, 1.6, 0.12, 'sine');
    this.tone(110, 2.2, 0.1, 'sine', 0.15);
    this.tone(73, 3.0, 0.09, 'triangle', 0.3);
  }

  ending() {
    [110, 164.8, 220, 293.7].forEach((f, i) => this.tone(f, 5.5, 0.08, 'sine', i * 0.6));
  }
}
