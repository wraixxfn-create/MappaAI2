(() => {
  'use strict';

  const WORLD = { width: 2800, height: 1850 };
  const MAP_SCALE = 0.54;
  const SAVE_KEY = 'mappa-inferno-esplorazione-v1';
  const SPAWN = { x: 330, y: 1530 };
  const BRIDGE = { x: 1365, y: 1055 };
  const RIVER_POINTS = [
    [1500, 115], [1450, 300], [1520, 475], [1465, 620], [1425, 770],
    [1370, 900], [1330, 1030], [1360, 1100], [1425, 1230], [1400, 1380], [1500, 1580], [1610, 1835]
  ];
  const ROUTE_POINTS = [
    [300, 1550], [465, 1510], [600, 1430], [760, 1350], [920, 1245], [1075, 1230],
    [1195, 1270], [1290, 1180], [1365, 1070], [1430, 980], [1570, 920], [1730, 880],
    [1880, 820], [2060, 775], [2250, 690], [2375, 655]
  ];

  const landmarks = [
    {
      id: 'selva', x: 620, y: 1235, radius: 155, title: 'La selva dei sussurri',
      kicker: 'LUOGO DIMENTICATO', location: 'LIMBO · SELVA OCCIDENTALE', icon: 'tree',
      text: 'Gli alberi bevono la cenere e tendono rami come dita. Fra le radici, una voce ripete il tuo nome — ma non è la tua.'
    },
    {
      id: 'acheronte', x: 1370, y: 1050, radius: 125, title: 'Il ponte di Caronte',
      kicker: 'RIVA DELL’ACHERONTE', location: 'LIMBO · PASSAGGIO SUL FIUME', icon: 'bridge',
      text: 'L’Acheronte taglia la via. Il nocchiero non si mostra; sulla riva resta un obolo bruciato, caldo come una moneta appena coniata.'
    },
    {
      id: 'ignavi', x: 1850, y: 1120, radius: 150, title: 'L’altare degli ignavi',
      kicker: 'VOCI SENZA NOME', location: 'LIMBO · PIANURA DELLE OMBRE', icon: 'altar',
      text: 'Anime che vissero senza scegliere corrono in cerchio, inseguendo un vessillo vuoto. Il vento non porta le loro grida: le trattiene.'
    },
    {
      id: 'porta', x: 2370, y: 655, radius: 190, title: 'La Porta dell’Inferno',
      kicker: 'SOGLIA DEL PRIMO CERCHIO', location: 'LIMBO · LA SOGLIA', icon: 'gate', art: true,
      text: '«Lasciate ogni speranza, voi ch’entrate». Tre sigilli spezzati pulsano nella pietra. Riuniscili: solo allora il varco saprà il tuo nome.'
    }
  ];

  const shards = [
    { id: 'sigillo-oblio', x: 790, y: 1320, name: 'Scheggia dell’oblio', mark: 'I' },
    { id: 'sigillo-cenere', x: 1390, y: 1035, name: 'Sigillo di cenere', mark: 'II' },
    { id: 'sigillo-soglia', x: 1905, y: 800, name: 'Occhio della soglia', mark: 'III' }
  ];

  const regions = [
    { name: 'LA SELVA DEL LIMBO', x: 520, y: 1170, radius: 760 },
    { name: 'RIVA DELL’ACHERONTE', x: 1370, y: 980, radius: 540 },
    { name: 'PIANURA DEGLI IGNAVI', x: 1900, y: 1130, radius: 610 },
    { name: 'LA PORTA DELL’INFERNO', x: 2360, y: 670, radius: 500 }
  ];

  const canvas = document.getElementById('gameCanvas');
  const ctx = canvas.getContext('2d', { alpha: false });
  const mapLayer = document.createElement('canvas');
  const fogLayer = document.createElement('canvas');
  mapLayer.width = fogLayer.width = Math.ceil(WORLD.width * MAP_SCALE);
  mapLayer.height = fogLayer.height = Math.ceil(WORLD.height * MAP_SCALE);
  const mapCtx = mapLayer.getContext('2d');
  const fogCtx = fogLayer.getContext('2d');
  mapCtx.setTransform(MAP_SCALE, 0, 0, MAP_SCALE, 0, 0);
  fogCtx.setTransform(MAP_SCALE, 0, 0, MAP_SCALE, 0, 0);

  const miniMap = document.getElementById('miniMap');
  const fullMap = document.getElementById('fullMap');
  const stage = document.getElementById('gameStage');
  const keys = new Set();
  let viewWidth = 1;
  let viewHeight = 1;
  let dpr = 1;
  let zoom = 1;
  let time = 0;
  let lastFrame = 0;
  let lastMapDraw = 0;
  let lastSave = 0;
  let lastToastTimer = 0;
  let lastProximity = '';
  let isMapOpen = false;
  let isSoundOn = false;
  let soundContext = null;
  let masterGain = null;
  let targetPoint = null;
  let obstacles = [];
  let forestTrees = [];
  let looseRocks = [];
  let mapSeed = 713;
  let toastMessage = '';

  const saved = readSave();
  const collected = new Set(Array.isArray(saved.collected) ? saved.collected : []);
  const discovered = new Set(Array.isArray(saved.discovered) ? saved.discovered : []);
  const visited = Array.isArray(saved.visited) ? saved.visited.filter(p => p && Number.isFinite(p.x) && Number.isFinite(p.y)) : [];
  let completed = Boolean(saved.completed);
  const player = {
    x: Number.isFinite(saved.position?.x) ? clamp(saved.position.x, 80, WORLD.width - 80) : SPAWN.x,
    y: Number.isFinite(saved.position?.y) ? clamp(saved.position.y, 80, WORLD.height - 80) : SPAWN.y,
    angle: -Math.PI / 2,
    moving: false,
    bob: 0
  };
  const camera = { x: player.x, y: player.y };
  let lastVisited = visited.length ? visited[visited.length - 1] : { x: player.x, y: player.y };

  function readSave() {
    try {
      return JSON.parse(localStorage.getItem(SAVE_KEY) || '{}') || {};
    } catch (_error) {
      return {};
    }
  }

  function saveProgress() {
    try {
      localStorage.setItem(SAVE_KEY, JSON.stringify({
        position: { x: Math.round(player.x), y: Math.round(player.y) },
        collected: Array.from(collected),
        discovered: Array.from(discovered),
        visited: visited.slice(-900),
        completed
      }));
    } catch (_error) { /* La partita resta giocabile anche senza storage. */ }
  }

  function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
  function distance(x1, y1, x2, y2) { return Math.hypot(x2 - x1, y2 - y1); }
  function lerp(a, b, amount) { return a + (b - a) * amount; }

  function seededRandom(seed) {
    let value = seed >>> 0;
    return () => {
      value += 0x6D2B79F5;
      let t = value;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const random = seededRandom(mapSeed);
  const rand = (min, max) => min + random() * (max - min);

  function pointSegmentDistance(px, py, ax, ay, bx, by) {
    const dx = bx - ax;
    const dy = by - ay;
    const lengthSq = dx * dx + dy * dy;
    if (!lengthSq) return distance(px, py, ax, ay);
    const t = clamp(((px - ax) * dx + (py - ay) * dy) / lengthSq, 0, 1);
    return distance(px, py, ax + t * dx, ay + t * dy);
  }

  function distanceToLine(points, x, y) {
    let nearest = Infinity;
    for (let i = 0; i < points.length - 1; i++) {
      nearest = Math.min(nearest, pointSegmentDistance(x, y, points[i][0], points[i][1], points[i + 1][0], points[i + 1][1]));
    }
    return nearest;
  }

  function pathFromPoints(context, points) {
    context.beginPath();
    context.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length - 1; i++) {
      const midX = (points[i][0] + points[i + 1][0]) / 2;
      const midY = (points[i][1] + points[i + 1][1]) / 2;
      context.quadraticCurveTo(points[i][0], points[i][1], midX, midY);
    }
    const last = points[points.length - 1];
    context.lineTo(last[0], last[1]);
  }

  function drawGround() {
    const base = mapCtx.createLinearGradient(0, 0, WORLD.width, WORLD.height);
    base.addColorStop(0, '#1c1b20');
    base.addColorStop(.35, '#1b191b');
    base.addColorStop(.66, '#171719');
    base.addColorStop(1, '#211515');
    mapCtx.fillStyle = base;
    mapCtx.fillRect(0, 0, WORLD.width, WORLD.height);

    const warmAreas = [
      [560, 1100, 720, 620, 'rgba(47,37,32,.24)'],
      [1330, 980, 500, 730, 'rgba(23,39,42,.20)'],
      [2050, 1020, 720, 780, 'rgba(62,31,25,.19)'],
      [2300, 570, 480, 420, 'rgba(81,38,25,.15)']
    ];
    warmAreas.forEach(([x, y, rx, ry, color]) => {
      const g = mapCtx.createRadialGradient(x, y, 20, x, y, Math.max(rx, ry));
      g.addColorStop(0, color);
      g.addColorStop(1, 'rgba(0,0,0,0)');
      mapCtx.fillStyle = g;
      mapCtx.fillRect(x - rx, y - ry, rx * 2, ry * 2);
    });

    // Basalt plates and fine ash create a hand-illustrated ground texture.
    for (let i = 0; i < 2450; i++) {
      const x = rand(0, WORLD.width);
      const y = rand(0, WORLD.height);
      const w = rand(3, 34);
      const h = rand(2, 16);
      mapCtx.save();
      mapCtx.translate(x, y);
      mapCtx.rotate(rand(-.8, .8));
      mapCtx.fillStyle = random() > .49 ? 'rgba(174,153,132,.025)' : 'rgba(0,0,0,.13)';
      mapCtx.fillRect(-w / 2, -h / 2, w, h);
      mapCtx.restore();
    }
    for (let i = 0; i < 5200; i++) {
      const x = rand(0, WORLD.width);
      const y = rand(0, WORLD.height);
      const r = rand(.35, 2.0);
      mapCtx.fillStyle = random() > .58 ? 'rgba(208,179,146,.09)' : 'rgba(0,0,0,.23)';
      mapCtx.beginPath();
      mapCtx.arc(x, y, r, 0, Math.PI * 2);
      mapCtx.fill();
    }

    // Broken contour lines make the regions read like an old, scorched survey map.
    for (let i = 0; i < 48; i++) {
      const x = rand(50, WORLD.width - 50);
      const y = rand(70, WORLD.height - 70);
      const rx = rand(55, 260);
      const ry = rand(36, 170);
      mapCtx.save();
      mapCtx.translate(x, y);
      mapCtx.rotate(rand(-.45, .45));
      mapCtx.strokeStyle = random() > .5 ? 'rgba(199,166,134,.075)' : 'rgba(0,0,0,.20)';
      mapCtx.lineWidth = rand(1, 2.2);
      mapCtx.beginPath();
      mapCtx.ellipse(0, 0, rx, ry, 0, rand(0, .4), rand(4.1, 6.2));
      mapCtx.stroke();
      mapCtx.beginPath();
      mapCtx.ellipse(0, 0, rx * .72, ry * .73, 0, rand(.4, .9), rand(4.2, 6.2));
      mapCtx.stroke();
      mapCtx.restore();
    }
  }

  function drawJaggedLine(context, points, width, color, glow = 0) {
    context.save();
    context.lineCap = 'round';
    context.lineJoin = 'round';
    context.lineWidth = width;
    context.strokeStyle = color;
    if (glow) {
      context.shadowColor = color;
      context.shadowBlur = glow;
    }
    context.beginPath();
    context.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i++) {
      context.lineTo(points[i][0], points[i][1]);
    }
    context.stroke();
    context.restore();
  }

  function drawLavaPool(x, y, rx, ry, seed) {
    const r = seededRandom(seed);
    const points = [];
    const count = 24;
    for (let i = 0; i < count; i++) {
      const a = (i / count) * Math.PI * 2;
      const wobble = .75 + r() * .4;
      points.push([x + Math.cos(a) * rx * wobble, y + Math.sin(a) * ry * wobble]);
    }
    mapCtx.save();
    mapCtx.beginPath();
    mapCtx.moveTo(points[0][0], points[0][1]);
    points.slice(1).forEach(p => mapCtx.lineTo(p[0], p[1]));
    mapCtx.closePath();
    mapCtx.shadowColor = '#f05d2c';
    mapCtx.shadowBlur = 42;
    mapCtx.fillStyle = '#0d0c0e';
    mapCtx.fill();
    mapCtx.shadowBlur = 0;
    mapCtx.strokeStyle = 'rgba(239,92,43,.65)';
    mapCtx.lineWidth = 4;
    mapCtx.stroke();
    const g = mapCtx.createRadialGradient(x, y, 0, x, y, Math.max(rx, ry));
    g.addColorStop(0, 'rgba(249,130,55,.9)');
    g.addColorStop(.2, 'rgba(220,63,32,.74)');
    g.addColorStop(.52, 'rgba(104,32,26,.58)');
    g.addColorStop(1, 'rgba(10,10,12,.95)');
    mapCtx.fillStyle = g;
    mapCtx.fill();
    mapCtx.restore();

    for (let i = 0; i < 7; i++) {
      const a = rand(0, Math.PI * 2);
      const rr = rand(.15, .8);
      const sx = x + Math.cos(a) * rx * rr;
      const sy = y + Math.sin(a) * ry * rr;
      const ex = sx + rand(-45, 45);
      const ey = sy + rand(-35, 35);
      drawJaggedLine(mapCtx, [[sx, sy], [(sx + ex) / 2 + rand(-15, 15), (sy + ey) / 2 + rand(-12, 12)], [ex, ey]], rand(1, 3), 'rgba(255,177,83,.76)', 8);
    }
  }

  function drawRiver() {
    mapCtx.save();
    pathFromPoints(mapCtx, RIVER_POINTS);
    mapCtx.lineCap = 'round';
    mapCtx.lineJoin = 'round';
    mapCtx.strokeStyle = 'rgba(208,77,40,.18)';
    mapCtx.lineWidth = 112;
    mapCtx.shadowColor = '#df5833';
    mapCtx.shadowBlur = 44;
    mapCtx.stroke();
    mapCtx.shadowBlur = 0;
    mapCtx.strokeStyle = '#101216';
    mapCtx.lineWidth = 83;
    mapCtx.stroke();
    mapCtx.strokeStyle = '#1e2023';
    mapCtx.lineWidth = 66;
    mapCtx.stroke();
    mapCtx.strokeStyle = 'rgba(65,91,94,.42)';
    mapCtx.lineWidth = 31;
    mapCtx.stroke();
    mapCtx.setLineDash([28, 37]);
    mapCtx.lineWidth = 3;
    mapCtx.strokeStyle = 'rgba(217,117,67,.5)';
    mapCtx.stroke();
    mapCtx.setLineDash([]);
    mapCtx.restore();

    // Thin drifting currents in the black water.
    for (let i = 0; i < 38; i++) {
      const y = 160 + i * 43;
      const x = 1450 + Math.sin(i * .77) * 62;
      mapCtx.beginPath();
      mapCtx.moveTo(x - 24, y);
      mapCtx.quadraticCurveTo(x, y + rand(-7, 7), x + 25, y + rand(-5, 5));
      mapCtx.strokeStyle = i % 3 === 0 ? 'rgba(230,125,76,.24)' : 'rgba(152,172,165,.12)';
      mapCtx.lineWidth = rand(1, 2.5);
      mapCtx.stroke();
    }
  }

  function drawFissures() {
    const fissures = [
      [[230, 405], [340, 455], [410, 530], [520, 558], [590, 640]],
      [[320, 900], [430, 855], [485, 785], [590, 750], [670, 680]],
      [[720, 335], [780, 400], [840, 430], [870, 520], [980, 565]],
      [[1780, 190], [1740, 300], [1800, 380], [1760, 455], [1820, 510]],
      [[2130, 280], [2075, 375], [2115, 453], [2040, 530], [2055, 600]],
      [[2440, 900], [2510, 955], [2490, 1040], [2580, 1090], [2600, 1180]],
      [[2290, 1270], [2180, 1325], [2130, 1405], [2010, 1450], [1970, 1550]],
      [[740, 1665], [850, 1605], [910, 1540], [1025, 1515]],
      [[1710, 1510], [1810, 1555], [1860, 1640], [1980, 1690]],
      [[1190, 300], [1090, 370], [1070, 455], [990, 500]]
    ];
    fissures.forEach((line, i) => {
      drawJaggedLine(mapCtx, line, i % 3 === 0 ? 5 : 3.2, 'rgba(9,9,11,.96)');
      drawJaggedLine(mapCtx, line, i % 3 === 0 ? 1.8 : 1.2, 'rgba(242,91,43,.78)', 12);
      line.forEach((p, j) => {
        if ((j + i) % 2 === 0) {
          mapCtx.beginPath();
          mapCtx.arc(p[0], p[1], rand(2, 4), 0, Math.PI * 2);
          mapCtx.fillStyle = '#f69b4d';
          mapCtx.shadowColor = '#f05d2c';
          mapCtx.shadowBlur = 12;
          mapCtx.fill();
          mapCtx.shadowBlur = 0;
        }
      });
    });
  }

  function makeTreeField() {
    const result = [];
    const safeSpots = [SPAWN, ...landmarks, ...shards, { x: 840, y: 790 }, { x: 970, y: 700 }];
    let attempts = 0;
    while (result.length < 82 && attempts < 2400) {
      attempts++;
      const x = rand(210, 1150);
      const y = rand(390, 1500);
      if (distanceToLine(ROUTE_POINTS, x, y) < 116) continue;
      if (distanceToLine(RIVER_POINTS, x, y) < 118) continue;
      if (safeSpots.some(p => distance(x, y, p.x, p.y) < 100)) continue;
      if (result.some(p => distance(x, y, p.x, p.y) < 38)) continue;
      result.push({ x, y, scale: rand(.55, 1.18), rotation: rand(-Math.PI, Math.PI), seed: rand(0, 1000) });
    }
    return result;
  }

  function makeRockField() {
    const result = [];
    let attempts = 0;
    while (result.length < 235 && attempts < 1400) {
      attempts++;
      const x = rand(65, WORLD.width - 65);
      const y = rand(80, WORLD.height - 65);
      const radius = rand(7, 27);
      if (distanceToLine(ROUTE_POINTS, x, y) < 69) continue;
      if (distanceToLine(RIVER_POINTS, x, y) < 78) continue;
      if (distance(x, y, SPAWN.x, SPAWN.y) < 115 || distance(x, y, 2370, 655) < 215) continue;
      if (landmarks.some(p => distance(x, y, p.x, p.y) < 90)) continue;
      if (shards.some(p => distance(x, y, p.x, p.y) < 58)) continue;
      if (result.some(p => distance(x, y, p.x, p.y) < p.radius + radius + 6)) continue;
      result.push({ x, y, radius, seed: Math.floor(rand(0, 999999)), rotation: rand(-.5, .5) });
    }
    return result;
  }

  function drawDeadTree(context, tree, withCollision = false) {
    const { x, y, scale, rotation, seed } = tree;
    const r = seededRandom(seed + 43);
    context.save();
    context.translate(x, y);
    context.rotate(rotation);
    context.scale(scale, scale);
    context.fillStyle = 'rgba(0,0,0,.38)';
    context.beginPath();
    context.ellipse(5, 11, 27, 18, 0, 0, Math.PI * 2);
    context.fill();
    context.lineCap = 'round';
    context.lineJoin = 'round';
    const branches = [
      [[0, 10], [3, -3], [-2, -17], [-7, -27]],
      [[0, -3], [11, -11], [15, -22], [24, -29]],
      [[3, -9], [-9, -15], [-16, -24], [-22, -28]],
      [[6, -14], [7, -25], [2, -33]],
      [[-7, -12], [-7, -23], [-13, -31]],
      [[12, -9], [24, -14], [30, -22]]
    ];
    branches.forEach((points, i) => {
      const wobble = r() * 2.5;
      context.beginPath();
      context.moveTo(points[0][0], points[0][1]);
      for (let j = 1; j < points.length; j++) context.lineTo(points[j][0] + wobble, points[j][1]);
      context.strokeStyle = i === 0 ? '#403432' : '#332b2b';
      context.lineWidth = Math.max(2, 7 - i * .65);
      context.stroke();
      context.beginPath();
      context.moveTo(points[1][0], points[1][1]);
      context.lineTo(points[2][0], points[2][1]);
      context.strokeStyle = 'rgba(193,137,103,.27)';
      context.lineWidth = 1;
      context.stroke();
    });
    context.beginPath();
    context.ellipse(0, 7, 9, 14, -.1, 0, Math.PI * 2);
    context.fillStyle = '#4a3935';
    context.fill();
    context.beginPath();
    context.ellipse(-2, 4, 2, 8, 0, 0, Math.PI * 2);
    context.fillStyle = 'rgba(196,133,95,.26)';
    context.fill();
    context.restore();
    if (withCollision) obstacles.push({ x, y, r: 17 * scale });
  }

  function makeRock(context, rock) {
    const randomShape = seededRandom(rock.seed);
    const points = [];
    const count = 6 + Math.floor(randomShape() * 4);
    for (let i = 0; i < count; i++) {
      const angle = i / count * Math.PI * 2 + rock.rotation;
      const radius = rock.radius * (.67 + randomShape() * .58);
      points.push([Math.cos(angle) * radius, Math.sin(angle) * radius * .74]);
    }
    context.save();
    context.translate(rock.x, rock.y);
    context.fillStyle = 'rgba(0,0,0,.34)';
    context.beginPath();
    context.ellipse(4, 7, rock.radius * 1.16, rock.radius * .71, 0, 0, Math.PI * 2);
    context.fill();
    context.beginPath();
    context.moveTo(points[0][0], points[0][1]);
    points.slice(1).forEach(p => context.lineTo(p[0], p[1]));
    context.closePath();
    const gradient = context.createLinearGradient(-rock.radius, -rock.radius, rock.radius, rock.radius);
    gradient.addColorStop(0, '#514943');
    gradient.addColorStop(.42, '#302d2e');
    gradient.addColorStop(1, '#171719');
    context.fillStyle = gradient;
    context.strokeStyle = 'rgba(186,143,111,.26)';
    context.lineWidth = 1.5;
    context.fill();
    context.stroke();
    context.beginPath();
    context.moveTo(points[0][0] * .48, points[0][1] * .48);
    context.lineTo(points[2][0] * .72, points[2][1] * .72);
    context.lineTo(points[3][0] * .36, points[3][1] * .4);
    context.strokeStyle = 'rgba(224,190,156,.13)';
    context.lineWidth = 1;
    context.stroke();
    context.restore();
  }

  function drawBone(context, x, y, length, angle) {
    context.save();
    context.translate(x, y);
    context.rotate(angle);
    context.lineCap = 'round';
    context.strokeStyle = 'rgba(194,177,153,.57)';
    context.lineWidth = 3;
    context.beginPath();
    context.moveTo(-length / 2, 0);
    context.lineTo(length / 2, 0);
    context.stroke();
    [-length / 2, length / 2].forEach(end => {
      context.beginPath();
      context.arc(end, 0, 3, 0, Math.PI * 2);
      context.fillStyle = '#c2b199';
      context.fill();
    });
    context.restore();
  }

  function drawRoad() {
    mapCtx.save();
    mapCtx.lineCap = 'round';
    mapCtx.lineJoin = 'round';
    pathFromPoints(mapCtx, ROUTE_POINTS);
    mapCtx.strokeStyle = 'rgba(0,0,0,.52)';
    mapCtx.lineWidth = 106;
    mapCtx.stroke();
    mapCtx.strokeStyle = '#282322';
    mapCtx.lineWidth = 91;
    mapCtx.stroke();
    mapCtx.strokeStyle = 'rgba(149,112,83,.34)';
    mapCtx.lineWidth = 66;
    mapCtx.stroke();
    mapCtx.strokeStyle = 'rgba(209,166,119,.17)';
    mapCtx.lineWidth = 2;
    mapCtx.setLineDash([16, 24]);
    mapCtx.stroke();
    mapCtx.setLineDash([]);
    mapCtx.restore();

    // Old paving slabs along the route.
    for (let i = 0; i < 165; i++) {
      const segment = Math.floor(rand(0, ROUTE_POINTS.length - 1));
      const a = ROUTE_POINTS[segment];
      const b = ROUTE_POINTS[segment + 1];
      const t = rand(.08, .92);
      const x = lerp(a[0], b[0], t) + rand(-31, 31);
      const y = lerp(a[1], b[1], t) + rand(-28, 28);
      mapCtx.save();
      mapCtx.translate(x, y);
      mapCtx.rotate(Math.atan2(b[1] - a[1], b[0] - a[0]) + rand(-.3, .3));
      mapCtx.fillStyle = random() > .5 ? 'rgba(174,140,111,.17)' : 'rgba(4,4,5,.26)';
      mapCtx.strokeStyle = 'rgba(210,171,133,.1)';
      mapCtx.lineWidth = 1;
      mapCtx.beginPath();
      mapCtx.moveTo(-rand(9, 22), -rand(5, 11));
      mapCtx.lineTo(rand(8, 22), -rand(4, 10));
      mapCtx.lineTo(rand(8, 18), rand(5, 10));
      mapCtx.lineTo(-rand(8, 18), rand(5, 10));
      mapCtx.closePath();
      mapCtx.fill();
      mapCtx.stroke();
      mapCtx.restore();
    }
  }

  function drawBridge() {
    const x = BRIDGE.x;
    const y = BRIDGE.y;
    mapCtx.save();
    mapCtx.translate(x, y);
    mapCtx.rotate(-.14);
    // Stone abutments and a narrow bridge span across the river.
    mapCtx.fillStyle = 'rgba(0,0,0,.55)';
    mapCtx.fillRect(-112, -39, 224, 78);
    mapCtx.fillStyle = '#56463d';
    mapCtx.fillRect(-105, -32, 210, 64);
    mapCtx.strokeStyle = '#b29370';
    mapCtx.lineWidth = 3;
    mapCtx.strokeRect(-104, -31, 208, 62);
    for (let i = 0; i < 13; i++) {
      const px = -96 + i * 16;
      mapCtx.beginPath();
      mapCtx.moveTo(px, -28);
      mapCtx.lineTo(px + rand(-4, 4), 28);
      mapCtx.strokeStyle = i % 2 ? 'rgba(13,12,13,.55)' : 'rgba(224,190,147,.3)';
      mapCtx.lineWidth = i % 3 === 0 ? 3 : 1.5;
      mapCtx.stroke();
    }
    [-93, 93].forEach(px => {
      mapCtx.fillStyle = '#81705b';
      mapCtx.fillRect(px - 10, -36, 20, 72);
      mapCtx.strokeStyle = 'rgba(229,183,135,.45)';
      mapCtx.strokeRect(px - 10, -36, 20, 72);
      mapCtx.fillStyle = '#a17c59';
      mapCtx.fillRect(px - 13, -39, 26, 7);
      mapCtx.fillRect(px - 13, 32, 26, 7);
    });
    mapCtx.restore();
  }

  function drawGate() {
    const x = 2370;
    const y = 655;
    mapCtx.save();
    mapCtx.translate(x, y);
    mapCtx.shadowColor = 'rgba(243,90,44,.62)';
    mapCtx.shadowBlur = 70;
    const halo = mapCtx.createRadialGradient(0, 4, 15, 0, 4, 225);
    halo.addColorStop(0, 'rgba(235,92,46,.35)');
    halo.addColorStop(1, 'rgba(235,92,46,0)');
    mapCtx.fillStyle = halo;
    mapCtx.fillRect(-250, -230, 500, 460);
    mapCtx.shadowBlur = 0;

    // Broad, broken curtain wall.
    mapCtx.fillStyle = '#292628';
    mapCtx.strokeStyle = '#78604d';
    mapCtx.lineWidth = 4;
    mapCtx.beginPath();
    mapCtx.moveTo(-170, -89); mapCtx.lineTo(-147, -121); mapCtx.lineTo(148, -121); mapCtx.lineTo(177, -83);
    mapCtx.lineTo(164, 91); mapCtx.lineTo(95, 91); mapCtx.lineTo(69, 46); mapCtx.lineTo(-68, 46);
    mapCtx.lineTo(-99, 91); mapCtx.lineTo(-171, 91); mapCtx.closePath();
    mapCtx.fill(); mapCtx.stroke();
    for (let row = 0; row < 5; row++) {
      const yy = -95 + row * 31;
      mapCtx.beginPath(); mapCtx.moveTo(-155 + (row % 2) * 19, yy); mapCtx.lineTo(157, yy + rand(-2, 2));
      mapCtx.strokeStyle = 'rgba(5,5,6,.45)'; mapCtx.lineWidth = 2; mapCtx.stroke();
      for (let col = 0; col < 7; col++) {
        const xx = -130 + col * 42 + (row % 2) * 17;
        if (Math.abs(xx) < 75 && yy > -8) continue;
        mapCtx.beginPath(); mapCtx.moveTo(xx, yy - 13); mapCtx.lineTo(xx + 24, yy - 13);
        mapCtx.strokeStyle = 'rgba(188,143,104,.17)'; mapCtx.lineWidth = 1; mapCtx.stroke();
      }
    }
    // Three dark, angular towers.
    [[-151, -116, 37, 59], [0, -144, 53, 80], [150, -113, 42, 68]].forEach(([tx, ty, tw, th], i) => {
      mapCtx.fillStyle = i === 1 ? '#3b3030' : '#332d2e';
      mapCtx.fillRect(tx - tw / 2, ty - th / 2, tw, th);
      mapCtx.strokeStyle = 'rgba(196,155,112,.45)'; mapCtx.lineWidth = 2;
      mapCtx.strokeRect(tx - tw / 2, ty - th / 2, tw, th);
      mapCtx.beginPath(); mapCtx.moveTo(tx - tw / 2 - 5, ty - th / 2); mapCtx.lineTo(tx, ty - th / 2 - 19); mapCtx.lineTo(tx + tw / 2 + 5, ty - th / 2);
      mapCtx.closePath(); mapCtx.fillStyle = '#4a3732'; mapCtx.fill(); mapCtx.stroke();
    });
    // Arched, ember-lit threshold.
    mapCtx.beginPath(); mapCtx.moveTo(-67, 92); mapCtx.lineTo(-62, -1); mapCtx.quadraticCurveTo(0, -94, 62, -1); mapCtx.lineTo(68, 92); mapCtx.closePath();
    mapCtx.fillStyle = '#0b0b0e'; mapCtx.fill();
    const threshold = mapCtx.createLinearGradient(0, -35, 0, 100);
    threshold.addColorStop(0, 'rgba(255,153,70,.85)');
    threshold.addColorStop(.58, 'rgba(219,64,37,.7)');
    threshold.addColorStop(1, 'rgba(117,32,24,.18)');
    mapCtx.fillStyle = threshold;
    mapCtx.beginPath(); mapCtx.moveTo(-6, 83); mapCtx.lineTo(-4, 0); mapCtx.quadraticCurveTo(0, -10, 4, 0); mapCtx.lineTo(7, 83); mapCtx.closePath(); mapCtx.fill();
    mapCtx.strokeStyle = 'rgba(255,157,78,.7)'; mapCtx.lineWidth = 2;
    mapCtx.beginPath(); mapCtx.moveTo(-77, 81); mapCtx.quadraticCurveTo(-72, -12, 0, -74); mapCtx.quadraticCurveTo(69, -12, 76, 81); mapCtx.stroke();
    // Fallen stones in front of the entrance.
    for (let i = 0; i < 12; i++) {
      const sx = rand(-160, 160), sy = rand(100, 143), size = rand(5, 13);
      mapCtx.fillStyle = '#4b403a'; mapCtx.fillRect(sx, sy, size * 1.4, size * .7);
    }
    mapCtx.restore();
  }

  function drawRuin(x, y, scale = 1, variant = 0) {
    mapCtx.save();
    mapCtx.translate(x, y);
    mapCtx.scale(scale, scale);
    mapCtx.rotate(variant * .09);
    mapCtx.fillStyle = 'rgba(0,0,0,.45)';
    mapCtx.fillRect(-92, -13, 184, 95);
    mapCtx.fillStyle = '#28292a';
    mapCtx.strokeStyle = 'rgba(182,148,120,.47)';
    mapCtx.lineWidth = 2;
    mapCtx.fillRect(-87, -28, 174, 72); mapCtx.strokeRect(-87, -28, 174, 72);
    for (let i = 0; i < 6; i++) {
      const bx = -77 + i * 31;
      mapCtx.fillStyle = i === variant % 6 ? '#171719' : '#3c3634';
      mapCtx.fillRect(bx, -41, 23, 26);
      mapCtx.strokeStyle = 'rgba(198,159,126,.33)'; mapCtx.strokeRect(bx, -41, 23, 26);
      mapCtx.fillStyle = '#51443c'; mapCtx.fillRect(bx - 3, -47, 29, 7);
    }
    mapCtx.fillStyle = '#19191b';
    mapCtx.fillRect(-36, -8, 72, 51);
    mapCtx.strokeStyle = 'rgba(209,159,117,.3)'; mapCtx.strokeRect(-36, -8, 72, 51);
    mapCtx.beginPath(); mapCtx.moveTo(-38, -8); mapCtx.lineTo(-22, -31); mapCtx.lineTo(0, -43); mapCtx.lineTo(25, -30); mapCtx.lineTo(38, -8);
    mapCtx.strokeStyle = '#82664f'; mapCtx.lineWidth = 3; mapCtx.stroke();
    mapCtx.restore();
  }

  function drawShrine(x, y) {
    mapCtx.save();
    mapCtx.translate(x, y);
    mapCtx.fillStyle = 'rgba(0,0,0,.48)';
    mapCtx.beginPath(); mapCtx.ellipse(0, 13, 71, 41, 0, 0, Math.PI * 2); mapCtx.fill();
    mapCtx.fillStyle = '#443933'; mapCtx.strokeStyle = 'rgba(210,166,123,.51)'; mapCtx.lineWidth = 2;
    mapCtx.beginPath(); mapCtx.moveTo(-52, 1); mapCtx.lineTo(-41, -46); mapCtx.lineTo(39, -46); mapCtx.lineTo(54, 1); mapCtx.closePath(); mapCtx.fill(); mapCtx.stroke();
    mapCtx.fillStyle = '#171618'; mapCtx.beginPath(); mapCtx.arc(0, -13, 21, 0, Math.PI * 2); mapCtx.fill();
    mapCtx.strokeStyle = 'rgba(225,145,90,.48)'; mapCtx.lineWidth = 2; mapCtx.beginPath(); mapCtx.arc(0, -13, 14, 0, Math.PI * 2); mapCtx.stroke();
    mapCtx.fillStyle = 'rgba(230,111,59,.68)'; mapCtx.beginPath(); mapCtx.arc(0, -13, 4, 0, Math.PI * 2); mapCtx.fill();
    for (let i = -1; i <= 1; i++) {
      mapCtx.fillStyle = '#76604b'; mapCtx.fillRect(i * 39 - 7, 1, 14, 25);
      mapCtx.fillStyle = '#9b7958'; mapCtx.fillRect(i * 39 - 10, -2, 20, 5);
    }
    mapCtx.fillStyle = '#6e5949'; mapCtx.fillRect(-58, 25, 116, 10);
    mapCtx.restore();
  }

  function drawCharonBoat(x, y) {
    mapCtx.save();
    mapCtx.translate(x, y);
    mapCtx.rotate(-.32);
    mapCtx.shadowColor = 'rgba(237,110,56,.5)'; mapCtx.shadowBlur = 20;
    mapCtx.fillStyle = '#211d1d'; mapCtx.strokeStyle = 'rgba(207,154,112,.54)'; mapCtx.lineWidth = 2;
    mapCtx.beginPath(); mapCtx.moveTo(-55, -16); mapCtx.lineTo(42, -16); mapCtx.lineTo(67, 0); mapCtx.lineTo(32, 23); mapCtx.lineTo(-38, 20); mapCtx.lineTo(-62, 0); mapCtx.closePath(); mapCtx.fill(); mapCtx.stroke();
    mapCtx.shadowBlur = 0;
    for (let i = -2; i <= 2; i++) {
      mapCtx.beginPath(); mapCtx.moveTo(i * 17, -11); mapCtx.lineTo(i * 15, 15); mapCtx.strokeStyle = 'rgba(191,145,105,.29)'; mapCtx.lineWidth = 2; mapCtx.stroke();
    }
    mapCtx.beginPath(); mapCtx.moveTo(-32, -19); mapCtx.lineTo(-17, -51); mapCtx.lineTo(4, -18); mapCtx.fillStyle = '#423633'; mapCtx.fill();
    mapCtx.strokeStyle = 'rgba(225,149,91,.4)'; mapCtx.stroke();
    mapCtx.restore();
  }

  function drawForestEdge() {
    // Ash and scrub between tree roots; small amber fungi are sparse and dim.
    for (let i = 0; i < 86; i++) {
      const x = rand(265, 1170);
      const y = rand(480, 1480);
      if (distanceToLine(ROUTE_POINTS, x, y) < 95) continue;
      if (distanceToLine(RIVER_POINTS, x, y) < 95) continue;
      mapCtx.beginPath(); mapCtx.ellipse(x, y, rand(5, 15), rand(3, 8), rand(0, Math.PI), 0, Math.PI * 2);
      mapCtx.fillStyle = random() > .5 ? 'rgba(101,79,66,.24)' : 'rgba(9,9,11,.5)'; mapCtx.fill();
      if (i % 11 === 0) {
        mapCtx.beginPath(); mapCtx.arc(x, y, 2.3, 0, Math.PI * 2); mapCtx.fillStyle = 'rgba(242,140,73,.8)'; mapCtx.shadowColor = '#f07a42'; mapCtx.shadowBlur = 10; mapCtx.fill(); mapCtx.shadowBlur = 0;
      }
    }
  }

  function drawBridgeApproach() {
    // A pair of watchstones at the crossing, marking the safe way over.
    [-1, 1].forEach(side => {
      const x = BRIDGE.x + side * 128;
      const y = BRIDGE.y + side * 4;
      mapCtx.fillStyle = '#403732'; mapCtx.strokeStyle = 'rgba(218,169,123,.47)'; mapCtx.lineWidth = 2;
      mapCtx.beginPath(); mapCtx.moveTo(x - 17, y + 22); mapCtx.lineTo(x - 13, y - 24); mapCtx.lineTo(x, y - 39); mapCtx.lineTo(x + 15, y - 23); mapCtx.lineTo(x + 18, y + 22); mapCtx.closePath(); mapCtx.fill(); mapCtx.stroke();
      mapCtx.fillStyle = 'rgba(232,125,68,.58)'; mapCtx.beginPath(); mapCtx.arc(x, y - 6, 4, 0, Math.PI * 2); mapCtx.shadowColor = '#f38244'; mapCtx.shadowBlur = 12; mapCtx.fill(); mapCtx.shadowBlur = 0;
    });
  }

  function drawMapLabels() {
    const labels = [
      { text: 'SELVA DEI SOSPIRI', x: 500, y: 755, size: 19 },
      { text: 'LE RIVE DELL’ACHERONTE', x: 1200, y: 520, size: 17 },
      { text: 'PIANURA DEGLI IGNAVI', x: 1945, y: 1370, size: 17 },
      { text: 'LA SOGLIA', x: 2220, y: 390, size: 16 }
    ];
    labels.forEach(label => {
      mapCtx.save(); mapCtx.textAlign = 'center'; mapCtx.font = `500 ${label.size}px Georgia, serif`;
      mapCtx.letterSpacing = '3px';
      mapCtx.fillStyle = 'rgba(203,178,151,.40)';
      mapCtx.shadowColor = 'rgba(0,0,0,.9)'; mapCtx.shadowBlur = 8;
      mapCtx.fillText(label.text, label.x, label.y);
      mapCtx.restore();
    });
    mapCtx.save();
    mapCtx.translate(2670, 180);
    mapCtx.strokeStyle = 'rgba(213,177,144,.48)'; mapCtx.lineWidth = 1;
    mapCtx.beginPath(); mapCtx.moveTo(0, 31); mapCtx.lineTo(0, -31); mapCtx.moveTo(-21, 0); mapCtx.lineTo(21, 0); mapCtx.stroke();
    mapCtx.beginPath(); mapCtx.moveTo(0, -31); mapCtx.lineTo(-6, -15); mapCtx.lineTo(0, -19); mapCtx.lineTo(6, -15); mapCtx.closePath(); mapCtx.fillStyle = '#d98d5e'; mapCtx.fill();
    mapCtx.fillStyle = '#d4b798'; mapCtx.textAlign = 'center'; mapCtx.font = '600 12px Georgia'; mapCtx.fillText('N', 0, -43);
    mapCtx.restore();
  }

  function drawWorldMap() {
    drawGround();
    drawLavaPool(1920, 260, 155, 98, 98);
    drawLavaPool(2495, 1475, 235, 155, 51);
    drawLavaPool(265, 300, 135, 83, 29);
    drawFissures();
    drawRiver();
    drawForestEdge();

    forestTrees = makeTreeField();
    forestTrees.forEach(tree => drawDeadTree(mapCtx, tree, true));
    looseRocks = makeRockField();
    looseRocks.forEach(rock => {
      makeRock(mapCtx, rock);
      obstacles.push({ x: rock.x, y: rock.y, r: rock.radius * .68 });
    });

    // Ruined watchposts, broken stones and the drowned altar.
    drawRuin(890, 705, 1.05, 1);
    drawRuin(1720, 1295, .89, 3);
    drawRuin(1110, 470, .66, 2);
    drawShrine(1850, 1120);
    drawCharonBoat(1270, 890);
    drawRoad();
    drawBridge();
    drawBridgeApproach();
    drawGate();

    // Bone trails, scattered well away from the pilgrim's road.
    for (let i = 0; i < 46; i++) {
      const x = rand(170, WORLD.width - 150);
      const y = rand(170, WORLD.height - 140);
      if (distanceToLine(ROUTE_POINTS, x, y) < 115 || distanceToLine(RIVER_POINTS, x, y) < 75) continue;
      drawBone(mapCtx, x, y, rand(7, 19), rand(-Math.PI, Math.PI));
    }
    drawMapLabels();

    // A fine, weathered border around the edges of the surveyed land.
    mapCtx.strokeStyle = 'rgba(219,178,137,.16)'; mapCtx.lineWidth = 3;
    mapCtx.strokeRect(25, 25, WORLD.width - 50, WORLD.height - 50);
    mapCtx.strokeStyle = 'rgba(0,0,0,.52)'; mapCtx.lineWidth = 19;
    mapCtx.strokeRect(7, 7, WORLD.width - 14, WORLD.height - 14);
  }

  function revealAt(x, y, radius = 205) {
    fogCtx.save();
    fogCtx.setTransform(MAP_SCALE, 0, 0, MAP_SCALE, 0, 0);
    fogCtx.globalCompositeOperation = 'destination-out';
    const gradient = fogCtx.createRadialGradient(x, y, radius * .1, x, y, radius);
    gradient.addColorStop(0, 'rgba(0,0,0,1)');
    gradient.addColorStop(.62, 'rgba(0,0,0,.93)');
    gradient.addColorStop(1, 'rgba(0,0,0,0)');
    fogCtx.fillStyle = gradient;
    fogCtx.beginPath();
    fogCtx.arc(x, y, radius, 0, Math.PI * 2);
    fogCtx.fill();
    fogCtx.restore();
  }

  function initializeFog() {
    fogCtx.setTransform(MAP_SCALE, 0, 0, MAP_SCALE, 0, 0);
    fogCtx.globalCompositeOperation = 'source-over';
    fogCtx.fillStyle = 'rgba(5,5,8,.96)';
    fogCtx.fillRect(0, 0, WORLD.width, WORLD.height);
    visited.forEach(p => revealAt(p.x, p.y, 205));
    revealAt(player.x, player.y, 235);
  }

  function drawTorch(context, x, y, scale, t) {
    const flicker = .7 + Math.sin(t * 8 + x) * .16 + Math.sin(t * 13 + y) * .1;
    context.save();
    context.globalCompositeOperation = 'lighter';
    const glow = context.createRadialGradient(x, y - 2, 1, x, y - 2, 60 * scale);
    glow.addColorStop(0, `rgba(255,156,79,${.47 * flicker})`);
    glow.addColorStop(.26, `rgba(214,73,39,${.21 * flicker})`);
    glow.addColorStop(1, 'rgba(255,92,38,0)');
    context.fillStyle = glow; context.beginPath(); context.arc(x, y - 2, 60 * scale, 0, Math.PI * 2); context.fill();
    context.fillStyle = '#e68a4a'; context.shadowColor = '#ff8643'; context.shadowBlur = 14 * scale;
    context.beginPath(); context.moveTo(x, y + 5 * scale); context.quadraticCurveTo(x - 9 * scale, y - 8 * flicker * scale, x, y - 19 * flicker * scale); context.quadraticCurveTo(x + 9 * scale, y - 7 * scale, x, y + 5 * scale); context.fill();
    context.fillStyle = '#ffd29a'; context.shadowBlur = 5 * scale;
    context.beginPath(); context.ellipse(x, y - 4 * scale, 2.1 * scale, 5 * scale, 0, 0, Math.PI * 2); context.fill();
    context.restore();
  }

  const torches = [
    { x: 1042, y: 1220, s: .8 }, { x: 1515, y: 915, s: .86 }, { x: 1574, y: 896, s: .72 },
    { x: 2236, y: 686, s: 1.05 }, { x: 2505, y: 690, s: .94 }, { x: 1802, y: 1122, s: .65 }
  ];
  const emberRandom = seededRandom(5704);
  const embers = Array.from({ length: 165 }, () => ({
    x: emberRandom() * WORLD.width,
    y: emberRandom() * WORLD.height,
    size: .7 + emberRandom() * 2.1,
    speed: 7 + emberRandom() * 20,
    drift: (emberRandom() - .5) * 11,
    phase: emberRandom() * Math.PI * 2,
    hot: emberRandom()
  }));

  function drawDynamicWorld(context, dt) {
    context.save();
    // A few low, wavering torches make the ancient road legible through the ash.
    torches.forEach(torch => drawTorch(context, torch.x, torch.y, torch.s, time));
    context.globalCompositeOperation = 'lighter';
    embers.forEach(p => {
      p.y -= p.speed * dt;
      p.x += (p.drift + Math.sin(time * 1.8 + p.phase) * 4) * dt;
      if (p.y < 0) p.y = WORLD.height;
      if (p.x < 0) p.x = WORLD.width;
      if (p.x > WORLD.width) p.x = 0;
      const alpha = .2 + (Math.sin(time * 3 + p.phase) + 1) * .23;
      context.fillStyle = p.hot > .86 ? `rgba(255,191,110,${alpha})` : `rgba(240,104,54,${alpha})`;
      context.shadowColor = '#f06a3c'; context.shadowBlur = p.size * 5;
      context.beginPath(); context.ellipse(p.x, p.y, p.size * .6, p.size * 1.45, -.3, 0, Math.PI * 2); context.fill();
    });
    context.shadowBlur = 0;
    context.restore();

    landmarks.forEach(place => drawLandmarkMarker(context, place, time));
    shards.forEach(shard => { if (!collected.has(shard.id)) drawShard(context, shard, time); });
  }

  function drawLandmarkMarker(context, place, t) {
    const known = discovered.has(place.id);
    const pulse = .5 + .5 * Math.sin(t * 2.1 + place.x * .01);
    context.save();
    context.translate(place.x, place.y);
    context.globalCompositeOperation = 'lighter';
    const radius = known ? 34 + pulse * 7 : 21 + pulse * 5;
    const glow = context.createRadialGradient(0, 0, 1, 0, 0, radius * 1.8);
    glow.addColorStop(0, known ? 'rgba(232,163,104,.26)' : 'rgba(221,133,76,.19)');
    glow.addColorStop(1, 'rgba(228,115,60,0)');
    context.fillStyle = glow; context.beginPath(); context.arc(0, 0, radius * 1.8, 0, Math.PI * 2); context.fill();
    context.globalCompositeOperation = 'source-over';
    context.strokeStyle = known ? `rgba(239,187,132,${.5 + pulse * .3})` : `rgba(213,139,89,${.35 + pulse * .23})`;
    context.lineWidth = known ? 1.7 : 1.25;
    context.beginPath(); context.arc(0, 0, radius * .55, 0, Math.PI * 2); context.stroke();
    context.beginPath(); context.moveTo(-radius * .32, 0); context.lineTo(radius * .32, 0); context.moveTo(0, -radius * .32); context.lineTo(0, radius * .32); context.stroke();
    context.fillStyle = known ? '#ffcb8f' : '#edaa70';
    context.beginPath(); context.arc(0, 0, 3.6, 0, Math.PI * 2); context.fill();
    if (known) {
      context.font = '600 11px Georgia'; context.textAlign = 'center'; context.textBaseline = 'bottom';
      context.fillStyle = 'rgba(244,221,192,.9)'; context.shadowColor = '#0c0a0a'; context.shadowBlur = 6;
      context.fillText(place.title.toLocaleUpperCase('it'), 0, -radius * .76);
    }
    context.restore();
  }

  function drawShard(context, shard, t) {
    const pulse = .6 + Math.sin(t * 4 + shard.x * .02) * .18;
    context.save();
    context.translate(shard.x, shard.y + Math.sin(t * 2.5 + shard.y) * 3);
    context.globalCompositeOperation = 'lighter';
    const glow = context.createRadialGradient(0, 0, 1, 0, 0, 54);
    glow.addColorStop(0, `rgba(255,168,90,${.4 * pulse})`);
    glow.addColorStop(.34, 'rgba(230,86,45,.18)');
    glow.addColorStop(1, 'rgba(220,90,40,0)');
    context.fillStyle = glow; context.beginPath(); context.arc(0, 0, 54, 0, Math.PI * 2); context.fill();
    context.globalCompositeOperation = 'source-over';
    context.rotate(Math.sin(t * .9) * .18);
    context.beginPath(); context.moveTo(0, -15); context.lineTo(8, -2); context.lineTo(4, 12); context.lineTo(-4, 12); context.lineTo(-8, -2); context.closePath();
    const crystal = context.createLinearGradient(-7, -13, 7, 12);
    crystal.addColorStop(0, '#ffe0a9'); crystal.addColorStop(.32, '#ed995d'); crystal.addColorStop(1, '#8d332c');
    context.fillStyle = crystal; context.strokeStyle = 'rgba(255,217,169,.88)'; context.lineWidth = 1.2; context.fill(); context.stroke();
    context.beginPath(); context.moveTo(0, -15); context.lineTo(0, 11); context.strokeStyle = 'rgba(255,234,193,.65)'; context.lineWidth = .8; context.stroke();
    context.restore();
  }

  function drawPlayer(context) {
    context.save();
    context.translate(player.x, player.y + (player.moving ? Math.sin(player.bob) * 1.5 : 0));
    // The warm pool keeps the tiny pilgrim legible after dark.
    const halo = context.createRadialGradient(0, 0, 2, 0, 0, 48);
    halo.addColorStop(0, 'rgba(244,142,80,.27)'); halo.addColorStop(1, 'rgba(244,142,80,0)');
    context.fillStyle = halo; context.beginPath(); context.arc(0, 0, 48, 0, Math.PI * 2); context.fill();
    context.fillStyle = 'rgba(0,0,0,.58)'; context.beginPath(); context.ellipse(1, 8, 14, 9, 0, 0, Math.PI * 2); context.fill();
    context.rotate(player.angle + Math.PI / 2);
    context.beginPath(); context.moveTo(0, -15); context.quadraticCurveTo(12, -10, 12, 3); context.lineTo(8, 13); context.lineTo(-8, 13); context.lineTo(-12, 3); context.quadraticCurveTo(-12, -10, 0, -15); context.closePath();
    const cloak = context.createLinearGradient(-9, -8, 10, 12);
    cloak.addColorStop(0, '#674338'); cloak.addColorStop(.42, '#34272a'); cloak.addColorStop(1, '#171619');
    context.fillStyle = cloak; context.strokeStyle = 'rgba(241,177,128,.62)'; context.lineWidth = 1.3; context.fill(); context.stroke();
    context.beginPath(); context.arc(0, -8, 5.1, 0, Math.PI * 2); context.fillStyle = '#181518'; context.fill();
    context.strokeStyle = '#c58c66'; context.lineWidth = 1.3;
    context.beginPath(); context.moveTo(11, 0); context.lineTo(17, 15); context.stroke();
    context.beginPath(); context.arc(0, -8, 2.2, 0, Math.PI * 2); context.fillStyle = '#f7bd79'; context.shadowColor = '#ff9c51'; context.shadowBlur = 8; context.fill();
    context.restore();
  }

  function drawTarget(context) {
    if (!targetPoint) return;
    const pulse = .5 + Math.sin(time * 4) * .5;
    context.save(); context.translate(targetPoint.x, targetPoint.y); context.globalCompositeOperation = 'lighter';
    context.strokeStyle = `rgba(255,190,122,${.55 + pulse * .35})`; context.lineWidth = 2;
    context.beginPath(); context.arc(0, 0, 14 + pulse * 7, 0, Math.PI * 2); context.stroke();
    context.beginPath(); context.moveTo(-24, 0); context.lineTo(-9, 0); context.moveTo(9, 0); context.lineTo(24, 0); context.moveTo(0, -24); context.lineTo(0, -9); context.moveTo(0, 9); context.lineTo(0, 24); context.stroke();
    context.fillStyle = '#ffc887'; context.beginPath(); context.arc(0, 0, 3, 0, Math.PI * 2); context.fill();
    context.restore();
  }

  function refreshFog() {
    revealAt(player.x, player.y, 210);
  }

  function resize() {
    const rect = stage.getBoundingClientRect();
    viewWidth = Math.max(1, rect.width);
    viewHeight = Math.max(1, rect.height);
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.round(viewWidth * dpr);
    const height = Math.round(viewHeight * dpr);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width; canvas.height = height;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    camera.x = clamp(camera.x, viewWidth / (2 * zoom), WORLD.width - viewWidth / (2 * zoom));
    camera.y = clamp(camera.y, viewHeight / (2 * zoom), WORLD.height - viewHeight / (2 * zoom));
    drawAllMapCanvases();
  }

  function drawMapView(targetCanvas, large = false) {
    const rect = targetCanvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ratio = Math.min(window.devicePixelRatio || 1, large ? 2 : 1.5);
    const width = Math.max(1, Math.round(rect.width * ratio));
    const height = Math.max(1, Math.round(rect.height * ratio));
    if (targetCanvas.width !== width || targetCanvas.height !== height) {
      targetCanvas.width = width; targetCanvas.height = height;
    }
    const context = targetCanvas.getContext('2d');
    context.setTransform(1, 0, 0, 1, 0, 0);
    context.clearRect(0, 0, width, height);
    context.drawImage(mapLayer, 0, 0, width, height);
    context.drawImage(fogLayer, 0, 0, width, height);
    const sx = width / WORLD.width;
    const sy = height / WORLD.height;
    drawMapMarkers(context, sx, sy);

    // Current position is always identifiable, even on a compact map.
    const px = player.x * sx;
    const py = player.y * sy;
    context.save();
    context.fillStyle = 'rgba(248,147,81,.23)'; context.beginPath(); context.arc(px, py, large ? 15 : 9, 0, Math.PI * 2); context.fill();
    context.fillStyle = '#ffbf7c'; context.strokeStyle = '#2c1711'; context.lineWidth = 1.5;
    context.beginPath(); context.arc(px, py, large ? 5 : 3.2, 0, Math.PI * 2); context.fill(); context.stroke();
    context.restore();

    if (targetPoint) {
      const tx = targetPoint.x * sx, ty = targetPoint.y * sy;
      context.save(); context.strokeStyle = '#ffbe7c'; context.lineWidth = large ? 2 : 1;
      context.beginPath(); context.arc(tx, ty, large ? 10 : 5, 0, Math.PI * 2); context.stroke(); context.restore();
    }
    if (large) {
      const w = viewWidth / zoom * sx;
      const h = viewHeight / zoom * sy;
      const x = (camera.x - viewWidth / (2 * zoom)) * sx;
      const y = (camera.y - viewHeight / (2 * zoom)) * sy;
      context.save(); context.strokeStyle = 'rgba(245,193,140,.78)'; context.lineWidth = 1.3;
      context.setLineDash([6, 5]); context.strokeRect(x, y, w, h); context.setLineDash([]); context.restore();
    }
  }

  function wasRevealedAt(x, y) {
    if (distance(x, y, player.x, player.y) < 215) return true;
    for (let i = Math.max(0, visited.length - 900); i < visited.length; i++) {
      if (distance(x, y, visited[i].x, visited[i].y) < 164) return true;
    }
    return false;
  }

  function drawMapMarkers(context, sx, sy) {
    const scale = Math.max(.75, Math.min(1.65, Math.sqrt(sx * sy) * 48));
    landmarks.forEach(place => {
      if (!wasRevealedAt(place.x, place.y)) return;
      const x = place.x * sx, y = place.y * sy;
      context.save();
      context.fillStyle = 'rgba(19,14,13,.81)'; context.strokeStyle = discovered.has(place.id) ? '#efb57b' : 'rgba(224,161,106,.8)';
      context.lineWidth = large ? 1.5 : 1;
      context.beginPath(); context.arc(x, y, (large ? 7.5 : 4.5) * scale, 0, Math.PI * 2); context.fill(); context.stroke();
      context.fillStyle = '#f0b77d'; context.beginPath(); context.arc(x, y, (large ? 2.5 : 1.5) * scale, 0, Math.PI * 2); context.fill();
      if (large) {
        context.font = '600 10px "DM Sans", sans-serif'; context.textAlign = 'left'; context.textBaseline = 'middle';
        context.fillStyle = 'rgba(238,222,201,.88)'; context.shadowColor = '#09090a'; context.shadowBlur = 4;
        context.fillText(place.title.toLocaleUpperCase('it'), x + 11, y - 1);
      }
      context.restore();
    });
    shards.forEach(shard => {
      if (collected.has(shard.id) || !wasRevealedAt(shard.x, shard.y)) return;
      const x = shard.x * sx, y = shard.y * sy;
      context.save(); context.fillStyle = '#ffbb78'; context.shadowColor = '#f47846'; context.shadowBlur = large ? 13 : 6;
      context.beginPath(); context.moveTo(x, y - (large ? 7 : 4)); context.lineTo(x + (large ? 4 : 2.2), y); context.lineTo(x, y + (large ? 7 : 4)); context.lineTo(x - (large ? 4 : 2.2), y); context.closePath(); context.fill(); context.restore();
    });
  }

  function drawAllMapCanvases() {
    drawMapView(miniMap, false);
    if (isMapOpen) drawMapView(fullMap, true);
  }

  function getRegion() {
    let nearest = regions[0];
    let best = Infinity;
    regions.forEach(region => {
      const d = distance(player.x, player.y, region.x, region.y);
      if (d < best) { nearest = region; best = d; }
    });
    return nearest.name;
  }

  function updateQuestUI() {
    const count = collected.size;
    document.getElementById('fragmentFraction').textContent = `${count}/3`;
    document.getElementById('chapterProgress').textContent = `${count} / 3 SIGILLI`;
    document.getElementById('chapterFill').style.width = `${(count / 3) * 100}%`;
    document.querySelectorAll('#fragmentTrack i').forEach((part, i) => part.classList.toggle('active', i < count));
    document.getElementById('fragmentCaption').textContent = count === 0 ? 'Un richiamo tra le rovine' : count === 3 ? 'Il sigillo è completo' : 'Il richiamo si fa più forte';
    document.getElementById('destinationName').textContent = completed ? 'La soglia è aperta' : 'La Porta dell’Inferno';
    const gate = landmarks.find(p => p.id === 'porta');
    const dest = targetPoint || gate;
    const meters = Math.round(distance(player.x, player.y, dest.x, dest.y) * .42);
    document.getElementById('destinationDistance').textContent = meters < 1000 ? `${meters} m` : `${(meters / 1000).toFixed(1)} km`;
    document.getElementById('regionName').textContent = getRegion();
    const minutes = String(Math.floor(time / 60)).padStart(2, '0');
    const seconds = String(Math.floor(time % 60)).padStart(2, '0');
    document.getElementById('coordinateText').textContent = `${getRegion().split(' ')[0]} · ${minutes}:${seconds}`;
  }

  function showToast(message, duration = 3000) {
    toastMessage = message;
    const toast = document.getElementById('toast');
    document.getElementById('toastText').textContent = message;
    toast.classList.add('show');
    window.clearTimeout(lastToastTimer);
    lastToastTimer = window.setTimeout(() => toast.classList.remove('show'), duration);
  }

  function openLore(item, ending = false) {
    const panel = document.getElementById('lorePanel');
    document.getElementById('loreKicker').textContent = ending ? 'IL VARCO È APERTO' : item.kicker;
    document.getElementById('loreTitle').textContent = ending ? 'Oltre la soglia' : item.title;
    document.getElementById('loreText').textContent = ending
      ? 'I tre frammenti si ricompongono. La pietra si apre e una luce antica ti invita a proseguire. Hai trovato la via: il viaggio, però, è appena cominciato.'
      : item.text;
    document.getElementById('loreLocation').textContent = ending ? 'INFERNO · IL VIAGGIO CONTINUA' : item.location;
    document.getElementById('loreArt').hidden = !(ending || item.art);
    document.getElementById('restartButton').hidden = !ending;
    document.getElementById('loreFoot').hidden = false;
    panel.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    document.getElementById('modalBackdrop').classList.add('visible');
    document.getElementById('closeLore').focus({ preventScroll: true });
  }

  function closeLore() {
    const panel = document.getElementById('lorePanel');
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    if (!isMapOpen) document.getElementById('modalBackdrop').classList.remove('visible');
  }

  function openMap() {
    isMapOpen = true;
    const modal = document.getElementById('mapModal');
    modal.classList.add('open'); modal.setAttribute('aria-hidden', 'false');
    document.getElementById('modalBackdrop').classList.add('visible');
    drawMapView(fullMap, true);
    document.getElementById('closeMap').focus({ preventScroll: true });
  }

  function closeMap() {
    isMapOpen = false;
    const modal = document.getElementById('mapModal');
    modal.classList.remove('open'); modal.setAttribute('aria-hidden', 'true');
    if (!document.getElementById('lorePanel').classList.contains('open')) document.getElementById('modalBackdrop').classList.remove('visible');
  }

  function setTargetFromMap(event) {
    const rect = fullMap.getBoundingClientRect();
    const x = clamp((event.clientX - rect.left) / rect.width, 0, 1) * WORLD.width;
    const y = clamp((event.clientY - rect.top) / rect.height, 0, 1) * WORLD.height;
    targetPoint = { x, y };
    showToast('Segnalino posizionato sulla carta. Segui la distanza per raggiungerlo.', 3000);
    updateQuestUI();
    closeMap();
    saveProgress();
  }

  function clearTarget() {
    targetPoint = null;
    showToast('Segnalino rimosso. La meta è di nuovo la Porta dell’Inferno.', 2400);
    updateQuestUI();
    drawAllMapCanvases();
  }

  function getNearbyAction() {
    let candidate = null;
    let closest = Infinity;
    shards.forEach(shard => {
      if (collected.has(shard.id)) return;
      const d = distance(player.x, player.y, shard.x, shard.y);
      if (d < 94 && d < closest) { candidate = { kind: 'shard', item: shard, distance: d }; closest = d; }
    });
    landmarks.forEach(place => {
      const d = distance(player.x, player.y, place.x, place.y);
      const range = place.id === 'porta' ? 162 : 112;
      if (d < range && d < closest) { candidate = { kind: 'landmark', item: place, distance: d }; closest = d; }
    });
    return candidate;
  }

  function updateNearby() {
    const action = getNearbyAction();
    const prompt = document.getElementById('actionPrompt');
    if (!action) {
      prompt.classList.remove('visible');
      lastProximity = '';
      return;
    }
    const key = `${action.kind}:${action.item.id}`;
    document.getElementById('actionText').textContent = action.kind === 'shard' ? `Raccogli ${action.item.name}` : `Esamina ${action.item.title}`;
    prompt.classList.add('visible');
    if (key !== lastProximity) lastProximity = key;
  }

  function interact() {
    if (isMapOpen || document.getElementById('lorePanel').classList.contains('open')) return;
    const action = getNearbyAction();
    if (!action) {
      showToast('Nessuna presenza abbastanza vicina. Segui la strada nella cenere.', 2200);
      return;
    }
    if (action.kind === 'shard') {
      collected.add(action.item.id);
      soundPickup();
      showToast(`${action.item.name}: un frammento del sigillo è tuo.`, 3400);
      if (collected.size === 3) {
        window.setTimeout(() => showToast('I tre sigilli sono riuniti. La Porta dell’Inferno può aprirsi.', 4200), 900);
      }
      updateQuestUI();
      saveProgress();
      return;
    }
    const place = action.item;
    discovered.add(place.id);
    saveProgress();
    if (place.id === 'porta') {
      if (collected.size === 3) {
        completed = true;
        saveProgress();
        document.getElementById('endFlash').classList.remove('play');
        void document.getElementById('endFlash').offsetWidth;
        document.getElementById('endFlash').classList.add('play');
        openLore(place, true);
      } else {
        const missing = 3 - collected.size;
        showToast(`La porta resta chiusa. ${missing} ${missing === 1 ? 'sigillo manca' : 'sigilli mancano'} ancora.`, 3600);
        openLore(place, false);
      }
    } else {
      openLore(place, false);
    }
    updateQuestUI();
  }

  function autoDiscover() {
    landmarks.forEach(place => {
      if (discovered.has(place.id)) return;
      const d = distance(player.x, player.y, place.x, place.y);
      if (d < place.radius) {
        discovered.add(place.id);
        saveProgress();
        showToast(`Luogo scoperto · ${place.title}`, 3200);
      }
    });
  }

  function canMoveTo(x, y) {
    const margin = 48;
    if (x < margin || x > WORLD.width - margin || y < margin || y > WORLD.height - margin) return false;
    if (obstacles.some(obstacle => distance(x, y, obstacle.x, obstacle.y) < obstacle.r + 11)) return false;
    const riverDistance = distanceToLine(RIVER_POINTS, x, y);
    if (riverDistance < 46 && distance(x, y, BRIDGE.x, BRIDGE.y) > 106) return false;
    return true;
  }

  function movePlayer(dt) {
    let dx = 0, dy = 0;
    if (keys.has('a') || keys.has('arrowleft')) dx -= 1;
    if (keys.has('d') || keys.has('arrowright')) dx += 1;
    if (keys.has('w') || keys.has('arrowup')) dy -= 1;
    if (keys.has('s') || keys.has('arrowdown')) dy += 1;
    const mag = Math.hypot(dx, dy);
    if (!mag) { player.moving = false; return; }
    dx /= mag; dy /= mag;
    player.moving = true;
    player.angle = Math.atan2(dy, dx);
    player.bob += dt * (keys.has('shift') ? 15 : 10);
    const speed = keys.has('shift') ? 330 : 225;
    const nextX = player.x + dx * speed * dt;
    const nextY = player.y + dy * speed * dt;
    // Axis-separated collision gives a gentle slide along stones and river banks.
    if (canMoveTo(nextX, player.y)) player.x = nextX;
    if (canMoveTo(player.x, nextY)) player.y = nextY;
    player.x = clamp(player.x, 48, WORLD.width - 48);
    player.y = clamp(player.y, 48, WORLD.height - 48);
    if (distance(lastVisited.x, lastVisited.y, player.x, player.y) > 54) {
      const point = { x: Math.round(player.x), y: Math.round(player.y) };
      visited.push(point);
      lastVisited = point;
      if (visited.length > 900) visited.splice(0, visited.length - 900);
      saveProgress();
    }
  }

  function update(dt) {
    const paused = isMapOpen || document.getElementById('lorePanel').classList.contains('open');
    if (paused) player.moving = false;
    else {
      movePlayer(dt);
      autoDiscover();
    }
    const follow = 1 - Math.pow(.001, dt);
    camera.x = lerp(camera.x, player.x, follow);
    camera.y = lerp(camera.y, player.y, follow);
    camera.x = clamp(camera.x, viewWidth / (2 * zoom), WORLD.width - viewWidth / (2 * zoom));
    camera.y = clamp(camera.y, viewHeight / (2 * zoom), WORLD.height - viewHeight / (2 * zoom));
    refreshFog();
    updateNearby();
    if (time - lastSave > 4) { saveProgress(); lastSave = time; }
    if (time - lastMapDraw > .11) { drawAllMapCanvases(); lastMapDraw = time; }
  }

  function render(now) {
    if (!lastFrame) lastFrame = now;
    const dt = Math.min(.05, Math.max(0, (now - lastFrame) / 1000));
    lastFrame = now;
    time += dt;
    update(dt);

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = '#0c0b0d';
    ctx.fillRect(0, 0, viewWidth, viewHeight);
    const left = viewWidth / 2 - camera.x * zoom;
    const top = viewHeight / 2 - camera.y * zoom;
    ctx.save();
    ctx.translate(left, top);
    ctx.scale(zoom, zoom);
    ctx.drawImage(mapLayer, 0, 0, WORLD.width, WORLD.height);
    drawDynamicWorld(ctx, dt);
    ctx.drawImage(fogLayer, 0, 0, WORLD.width, WORLD.height);
    drawTarget(ctx);
    drawPlayer(ctx);
    ctx.restore();

    if (now % 250 < 18) updateQuestUI();
    requestAnimationFrame(render);
  }

  function keyDown(event) {
    const key = event.key.toLowerCase();
    if (['arrowup', 'arrowdown', 'arrowleft', 'arrowright', ' '].includes(key)) event.preventDefault();
    if (key === 'escape') {
      if (isMapOpen) closeMap();
      else closeLore();
      return;
    }
    if (key === 'm' && !event.repeat) {
      isMapOpen ? closeMap() : openMap();
      return;
    }
    if (isMapOpen || document.getElementById('lorePanel').classList.contains('open')) return;
    if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright', 'shift'].includes(key)) keys.add(key);
    if (key === 'e' || key === ' ') { if (!event.repeat) interact(); }
    if (key === '+' || key === '=') setZoom(zoom + .1);
    if (key === '-' || key === '_') setZoom(zoom - .1);
  }

  function keyUp(event) { keys.delete(event.key.toLowerCase()); }
  function setZoom(next) { zoom = clamp(next, .72, 1.38); resize(); }

  function setupTouchControls() {
    document.querySelectorAll('.touch-key').forEach(button => {
      const dir = button.dataset.dir;
      const key = dir === 'up' ? 'w' : dir === 'down' ? 's' : dir === 'left' ? 'a' : 'd';
      const release = () => { keys.delete(key); button.classList.remove('pressed'); };
      button.addEventListener('pointerdown', event => {
        event.preventDefault(); keys.add(key); button.classList.add('pressed'); button.setPointerCapture(event.pointerId);
      });
      button.addEventListener('pointerup', release);
      button.addEventListener('pointercancel', release);
      button.addEventListener('lostpointercapture', release);
    });
    document.getElementById('touchInteract').addEventListener('pointerdown', event => { event.preventDefault(); interact(); });
  }

  function setupAudio() {
    const button = document.getElementById('soundButton');
    button.addEventListener('click', async () => {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) { showToast('Audio non supportato in questo browser.', 2300); return; }
      if (!soundContext) {
        soundContext = new AudioContext();
        masterGain = soundContext.createGain(); masterGain.gain.value = 0; masterGain.connect(soundContext.destination);
        const low = soundContext.createOscillator(); low.type = 'sine'; low.frequency.value = 54;
        const lowGain = soundContext.createGain(); lowGain.gain.value = .17; low.connect(lowGain); lowGain.connect(masterGain); low.start();
        const high = soundContext.createOscillator(); high.type = 'triangle'; high.frequency.value = 82;
        const highGain = soundContext.createGain(); highGain.gain.value = .035; high.connect(highGain); highGain.connect(masterGain); high.start();
        const lfo = soundContext.createOscillator(); lfo.frequency.value = .13;
        const lfoGain = soundContext.createGain(); lfoGain.gain.value = .035; lfo.connect(lfoGain); lfoGain.connect(masterGain.gain); lfo.start();
      }
      await soundContext.resume();
      isSoundOn = !isSoundOn;
      masterGain.gain.cancelScheduledValues(soundContext.currentTime);
      masterGain.gain.setTargetAtTime(isSoundOn ? .1 : 0, soundContext.currentTime, .25);
      button.setAttribute('aria-pressed', String(isSoundOn));
      button.title = isSoundOn ? 'Disattiva audio ambientale' : 'Attiva audio ambientale';
      button.setAttribute('aria-label', button.title);
      if (isSoundOn) showToast('Il respiro dell’Inferno ti accompagna.', 2200);
    });
  }

  function soundPickup() {
    if (!isSoundOn || !soundContext) return;
    const oscillator = soundContext.createOscillator();
    const gain = soundContext.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(580, soundContext.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(920, soundContext.currentTime + .18);
    gain.gain.setValueAtTime(.0001, soundContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(.16, soundContext.currentTime + .025);
    gain.gain.exponentialRampToValueAtTime(.0001, soundContext.currentTime + .42);
    oscillator.connect(gain); gain.connect(masterGain); oscillator.start(); oscillator.stop(soundContext.currentTime + .44);
  }

  function restartGame() {
    if (!window.confirm('Ricominciare il viaggio? I sigilli e la mappa esplorata verranno cancellati.')) return;
    try { localStorage.removeItem(SAVE_KEY); } catch (_error) { /* ignore */ }
    location.reload();
  }

  function setupUI() {
    document.getElementById('mapButton').addEventListener('click', () => isMapOpen ? closeMap() : openMap());
    document.getElementById('miniMapButton').addEventListener('click', openMap);
    document.getElementById('closeMap').addEventListener('click', closeMap);
    document.getElementById('closeLore').addEventListener('click', closeLore);
    document.getElementById('modalBackdrop').addEventListener('click', () => { closeMap(); closeLore(); });
    document.getElementById('fullMap').addEventListener('click', setTargetFromMap);
    document.getElementById('clearPin').addEventListener('click', clearTarget);
    document.getElementById('actionPrompt').addEventListener('click', interact);
    document.getElementById('actionPrompt').addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') interact(); });
    document.getElementById('restartButton').addEventListener('click', restartGame);
    document.getElementById('fullscreenButton').addEventListener('click', async () => {
      try {
        if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
        else await document.exitFullscreen();
      } catch (_error) { showToast('Schermo intero non disponibile.', 1800); }
    });
    stage.addEventListener('wheel', event => {
      if (isMapOpen) return;
      event.preventDefault();
      setZoom(zoom + (event.deltaY < 0 ? .06 : -.06));
    }, { passive: false });
    window.addEventListener('keydown', keyDown);
    window.addEventListener('keyup', keyUp);
    window.addEventListener('blur', () => keys.clear());
    window.addEventListener('resize', resize);
    document.addEventListener('fullscreenchange', resize);
    setupTouchControls();
    setupAudio();
  }

  // Build the illustrated world only once; movement and fog are live layers.
  drawWorldMap();
  initializeFog();
  setupUI();
  resize();
  updateQuestUI();
  if (!saved.position) {
    window.setTimeout(() => showToast('Esplora la selva. Le tue impronte sveleranno la carta.', 4400), 800);
  }
  requestAnimationFrame(render);
})();
