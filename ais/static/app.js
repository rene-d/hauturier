/* Carte AIS — rendu des cibles sur un canvas superposé à Leaflet.
 *
 * Un canvas plutôt que des marqueurs : le flux peut dépasser le millier de
 * cibles, et il faut pouvoir orienter chaque coque selon son cap, la mettre à
 * l'échelle réelle du navire au-delà d'un certain zoom, et tracer les vecteurs
 * vitesse. Le canvas est posé hors des panneaux transformés de Leaflet et
 * travaille donc en coordonnées conteneur, stables pendant le déplacement.
 */

if (!window.L) {
  document.body.innerHTML =
    '<p style="padding:2em;font:14px sans-serif">Leaflet n\'a pas pu être chargé.' +
    ' Lancer l\'application une fois avec un accès réseau pour le mettre en cache' +
    ' (~/.cache/aismap/vendor).</p>';
  throw new Error('leaflet manquant');
}

// --- constantes ------------------------------------------------------------

const COLORS = {
  cargo: '#2e9e63', tanker: '#d8443c', passenger: '#2f7fd8', hsc: '#e5b73b',
  fishing: '#b07a3e', tug: '#22b0b0', special: '#22b0b0', military: '#77808a',
  sailing: '#a568e0', pleasure: '#a568e0', sar: '#e8722c', other: '#9aa3ad',
  unknown: '#9aa3ad', aton: '#efc93f', coast: '#8fa3b8', sar_aircraft: '#e8722c',
  auxiliary: '#22b0b0', sart: '#ff3b30', mob: '#ff3b30', epirb: '#ff3b30',
  group: '#9aa3ad',
};

const LEGEND = [
  ['cargo', 'cargo'], ['tanker', 'pétrolier'], ['passenger', 'passagers'],
  ['hsc', 'grande vitesse'], ['fishing', 'pêche'], ['tug', 'servitude'],
  ['sailing', 'voile / plaisance'], ['military', 'militaire'],
  ['sar', 'SAR'], ['aton', 'aide à la navigation'], ['coast', 'station côtière'],
  ['unknown', 'inconnu'],
];

const FIELDS = {
  msg_type: 'type de message', repeat: 'répétitions', mmsi: 'MMSI',
  status: 'statut de navigation', turn: 'taux de giration (°/min)',
  speed: 'vitesse fond (nds)', accuracy: 'précision GNSS (< 10 m)',
  lon: 'longitude', lat: 'latitude', course: 'route fond (°)',
  heading: 'cap compas (°)', second: 'seconde UTC', maneuver: 'manœuvre',
  raim: 'RAIM', radio: 'état du canal radio', ais_version: 'version AIS',
  imo: 'numéro OMI', callsign: 'indicatif', shipname: 'nom du navire',
  ship_type: 'type de navire (code)', to_bow: 'antenne → étrave (m)',
  to_stern: 'antenne → tableau (m)', to_port: 'antenne → bâbord (m)',
  to_starboard: 'antenne → tribord (m)', epfd: 'système de positionnement',
  month: 'ETA — mois', day: 'ETA — jour', hour: 'ETA — heure',
  minute: 'ETA — minute', draught: 'tirant d\'eau (m)', destination: 'destination',
  dte: 'terminal de données', cs: 'unité classe B « CS »', display: 'écran intégré',
  dsc: 'ASN (DSC)', band: 'bande étendue', msg22: 'gestion par message 22',
  assigned: 'mode assigné', aid_type: 'type d\'aide à la navigation',
  name: 'nom', off_position: 'hors position', virtual_aid: 'aide virtuelle',
  name_ext: 'nom (suite)', vendorid: 'fabricant', model: 'modèle',
  serial: 'numéro de série', year: 'année (UTC)', reserved_1: 'réservé',
  reserved_2: 'réservé', regional: 'usage régional', altitude: 'altitude (m)',
  dac: 'DAC', fid: 'FID',
};

const METEO = {
  wspeed: ['vent moyen', 'nds'], wgust: ['rafales', 'nds'],
  wdir: ['direction du vent', '°'], wgustdir: ['direction des rafales', '°'],
  airtemp: ['température de l\'air', '°C'], humidity: ['humidité', '%'],
  dewpoint: ['point de rosée', '°C'], pressure: ['pression', 'hPa'],
  pressuretend: ['tendance', ''], visibility: ['visibilité', 'NM'],
  waterlevel: ['niveau d\'eau', 'm'], leveltrend: ['tendance du niveau', ''],
  cspeed: ['courant de surface', 'nds'], cdir: ['direction du courant', '°'],
  cspeed2: ['courant (2)', 'nds'], cdir2: ['direction courant (2)', '°'],
  cdepth2: ['profondeur mesure (2)', 'm'], cspeed3: ['courant (3)', 'nds'],
  cdir3: ['direction courant (3)', '°'], cdepth3: ['profondeur mesure (3)', 'm'],
  waveheight: ['hauteur des vagues', 'm'], waveperiod: ['période des vagues', 's'],
  wavedir: ['direction des vagues', '°'], swellheight: ['houle', 'm'],
  swellperiod: ['période de houle', 's'], swelldir: ['direction de la houle', '°'],
  seastate: ['état de la mer (Beaufort)', ''], watertemp: ['température de l\'eau', '°C'],
  preciptype: ['précipitations', ''], salinity: ['salinité', '‰'], ice: ['glace', ''],
};

const MMSI_KIND = {
  vessel: 'navire', coast: 'station côtière', aton: 'aide à la navigation',
  auxiliary: 'embarcation annexe', sart: 'AIS-SART (détresse)',
  mob: 'homme à la mer', epirb: 'balise EPIRB-AIS',
  sar_aircraft: 'aéronef SAR', group: 'appel de groupe',
};

const NM = 1852;

// --- état ------------------------------------------------------------------

const state = {
  ships: new Map(),
  details: new Map(),
  tracks: new Map(),
  seq: 0,
  cfg: { ref: [48.7, -4.0], radius: 50, max_age: 3600 },
  selected: null,
  hover: null,
  pinned: false,
  cursor: { x: 0, y: 0 },
  hits: [],
  filter: '',
  opts: { labels: true, tracks: false, moving: false, all: false, vector: 6 },
};

// --- formatage -------------------------------------------------------------

const pad = (n, w = 2) => String(n).padStart(w, '0');

function fmtLat(v) {
  const d = Math.floor(Math.abs(v)), m = (Math.abs(v) - d) * 60;
  return `${pad(d)}°${m.toFixed(3).padStart(6, '0')}′${v < 0 ? 'S' : 'N'}`;
}

function fmtLon(v) {
  const d = Math.floor(Math.abs(v)), m = (Math.abs(v) - d) * 60;
  return `${pad(d, 3)}°${m.toFixed(3).padStart(6, '0')}′${v < 0 ? 'W' : 'E'}`;
}

function fmtAge(s) {
  if (s === null || s === undefined) return '—';
  if (s < 60) return `${Math.round(s)} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ${pad(Math.floor(s % 3600 / 60))}`;
  return `${Math.floor(s / 86400)} j`;
}

function fmtClock(t) {
  const d = new Date(t * 1000);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

const num = (v, digits = 1) => (v === null || v === undefined ? '—' : v.toFixed(digits).replace('.', ','));
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function shipLabel(s) { return s.name || `MMSI ${s.mmsi}`; }
function colorOf(s) { return COLORS[s.group] || COLORS[s.kind] || COLORS.unknown; }

function hasAngle(s) {
  if (s.hdg !== undefined && s.hdg >= 0 && s.hdg < 360) return s.hdg;
  if (s.cog !== undefined && s.cog >= 0 && s.cog < 360 && (s.sog || 0) > 0.3) return s.cog;
  return null;
}

// --- carte -----------------------------------------------------------------

const map = L.map('map', { zoomControl: true, preferCanvas: true, attributionControl: true })
  .setView(state.cfg.ref, 10);

const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '© OpenStreetMap',
}).addTo(map);

const charts = L.tileLayer('/tiles/{z}/{x}/{y}.png', {
  maxZoom: 19, maxNativeZoom: 15, attribution: 'cartes hors ligne',
}).addTo(map);

L.control.layers(
  { 'OpenStreetMap': osm },
  { 'cartes locales (mbtiles)': charts },
  { position: 'topleft', collapsed: true },
).addTo(map);

L.control.scale({ imperial: false, metric: true, position: 'bottomleft' }).addTo(map);

// Point de référence : celui envoyé au serveur AIS, avec le cercle du rayon.
const refMarker = L.circleMarker(state.cfg.ref, {
  radius: 5, color: '#fff', weight: 2, fillColor: '#4aa8ff', fillOpacity: 1,
}).addTo(map).bindTooltip('point de référence');
const refCircle = L.circle(state.cfg.ref, {
  radius: state.cfg.radius * NM, color: '#4aa8ff', weight: 1,
  opacity: .45, fill: false, dashArray: '5 6',
}).addTo(map);

// --- canvas ----------------------------------------------------------------

const canvas = document.createElement('canvas');
canvas.id = 'ais-canvas';
map.getContainer().appendChild(canvas);
const ctx = canvas.getContext('2d');

function resize() {
  const size = map.getSize(), dpr = window.devicePixelRatio || 1;
  canvas.width = size.x * dpr;
  canvas.height = size.y * dpr;
  canvas.style.width = `${size.x}px`;
  canvas.style.height = `${size.y}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}

map.on('move zoom viewreset', draw);
map.on('resize', resize);
map.on('zoomstart', () => canvas.classList.add('hidden'));
map.on('zoomend', () => { canvas.classList.remove('hidden'); draw(); });

function metersPerPixel() {
  return 156543.03392 * Math.cos(map.getCenter().lat * Math.PI / 180) / Math.pow(2, map.getZoom());
}

function visibleShips() {
  const bounds = map.getBounds().pad(0.25);
  const now = Date.now() / 1000;
  const out = [];
  for (const s of state.ships.values()) {
    if (s.lat === null || s.lat === undefined) continue;
    if (state.opts.moving && (s.sog || 0) < 0.5) continue;
    if (state.filter && !matches(s, state.filter)) continue;
    if (!bounds.contains([s.lat, s.lon])) continue;
    s._age = now - (s.last_pos || s.last);
    out.push(s);
  }
  return out;
}

function draw() {
  if (!ctx) return;
  const size = map.getSize();
  ctx.clearRect(0, 0, size.x, size.y);
  const mpp = metersPerPixel();
  const zoom = map.getZoom();
  const ships = visibleShips();
  const hits = [];
  const boxes = [];

  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';

  if (state.opts.tracks) {
    ctx.lineWidth = 1;
    for (const [mmsi, pts] of state.tracks) {
      const s = state.ships.get(Number(mmsi));
      ctx.strokeStyle = s ? colorOf(s) + '80' : '#ffffff55';
      strokeTrack(pts);
    }
  }

  const selTrack = state.selected && state.details.get(state.selected);
  if (selTrack && selTrack.data && selTrack.data.track && selTrack.data.track.length > 1) {
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#ffffffcc';
    strokeTrack(selTrack.data.track.map((p) => [p[1], p[2]]));
  }

  for (const s of ships) {
    const pt = map.latLngToContainerPoint([s.lat, s.lon]);
    const stale = s._age > 600;
    const color = colorOf(s);
    const angle = hasAngle(s);
    ctx.globalAlpha = stale ? 0.45 : 1;

    if (state.opts.vector && (s.sog || 0) > 0.3 && s.cog !== undefined && s.cog < 360) {
      drawVector(pt, s, mpp, color);
    }

    let radius = 8;
    if (s.kind === 'aton') {
      drawAton(pt, s, color);
      radius = 9;
    } else if (s.kind === 'coast' || s.kind === 'group') {
      drawStation(pt, color);
    } else if (s.kind === 'sar_aircraft') {
      drawAircraft(pt, angle, color);
    } else {
      radius = drawVessel(pt, s, angle, color, mpp, zoom);
    }

    // Une coque à l'échelle peut occuper 200 px : le halo l'entoure, mais la
    // zone sensible et l'ancrage du nom restent de taille raisonnable.
    const halo = Math.min(radius + 5, 70);
    if (s.mmsi === state.selected) drawHalo(pt, halo, '#fff');
    else if (s.mmsi === state.hover) drawHalo(pt, halo, '#ffffff99');

    hits.push({ mmsi: s.mmsi, x: pt.x, y: pt.y, r: Math.min(Math.max(radius, 8), 26) });

    if (state.opts.labels && (zoom >= 9 || s.mmsi === state.selected)) {
      drawLabel(pt, s, Math.min(radius, 26), boxes, stale);
    }
  }

  ctx.globalAlpha = 1;
  state.hits = hits;
  if (state.pinned && state.selected) positionPinnedTip();
}

function strokeTrack(pts) {
  ctx.beginPath();
  for (let i = 0; i < pts.length; i++) {
    const p = map.latLngToContainerPoint(pts[i]);
    if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
  }
  ctx.stroke();
}

function drawVector(pt, s, mpp, color) {
  const meters = s.sog * NM * (state.opts.vector / 60);
  const len = Math.min(meters / mpp, 600);
  if (len < 4) return;
  const a = (s.cog - 90) * Math.PI / 180;
  const ex = pt.x + Math.cos(a) * len, ey = pt.y + Math.sin(a) * len;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.3;
  ctx.beginPath();
  ctx.moveTo(pt.x, pt.y);
  ctx.lineTo(ex, ey);
  ctx.stroke();
  // graduation à la minute, pour lire la distance parcourue d'un coup d'œil
  const step = len / state.opts.vector;
  if (step > 7) {
    ctx.lineWidth = 1;
    for (let i = 1; i < state.opts.vector; i++) {
      const x = pt.x + Math.cos(a) * step * i, y = pt.y + Math.sin(a) * step * i;
      ctx.beginPath();
      ctx.moveTo(x - Math.sin(a) * 2.5, y + Math.cos(a) * 2.5);
      ctx.lineTo(x + Math.sin(a) * 2.5, y - Math.cos(a) * 2.5);
      ctx.stroke();
    }
  }
}

/* Coque à l'échelle si les dimensions sont connues et le zoom suffisant,
   sinon triangle orienté, sinon cercle (cap inconnu). Renvoie le rayon de
   la zone sensible en pixels. */
function drawVessel(pt, s, angle, color, mpp, zoom) {
  ctx.save();
  ctx.translate(pt.x, pt.y);
  ctx.fillStyle = color;
  ctx.strokeStyle = '#00000099';
  ctx.lineWidth = 1;

  if (angle === null) {
    ctx.beginPath();
    ctx.arc(0, 0, 4.5, 0, 2 * Math.PI);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
    return 6;
  }

  ctx.rotate(angle * Math.PI / 180);
  const dim = s.dim;
  const lenPx = dim ? (dim[0] + dim[1]) / mpp : 0;

  if (dim && lenPx > 22) {
    const bow = dim[0] / mpp, stern = dim[1] / mpp;
    const port = Math.max(dim[2] / mpp, 1.5), star = Math.max(dim[3] / mpp, 1.5);
    ctx.beginPath();
    ctx.moveTo(-port, stern);
    ctx.lineTo(star, stern);
    ctx.lineTo(star, -bow * 0.55);
    ctx.lineTo((star - port) / 2, -bow);
    ctx.lineTo(-port, -bow * 0.55);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
    return Math.max(bow, stern, 8);
  }

  const k = zoom >= 12 ? 1.15 : 1;
  ctx.beginPath();
  ctx.moveTo(0, -8 * k);
  ctx.lineTo(5.5 * k, 6 * k);
  ctx.lineTo(0, 3 * k);
  ctx.lineTo(-5.5 * k, 6 * k);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  // trait de cap compas, distinct de la route fond
  if (s.hdg !== undefined && s.hdg < 360) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, -8 * k);
    ctx.lineTo(0, -15 * k);
    ctx.stroke();
  }
  ctx.restore();
  return 9;
}

function drawAton(pt, s, color) {
  ctx.save();
  ctx.translate(pt.x, pt.y);
  ctx.rotate(Math.PI / 4);
  ctx.lineWidth = 1.4;
  ctx.strokeStyle = s.off_position ? '#ff3b30' : '#00000099';
  if (s.virtual) {
    ctx.strokeStyle = color;
    ctx.setLineDash([2.5, 2]);
    ctx.strokeRect(-5, -5, 10, 10);
    ctx.setLineDash([]);
  } else {
    ctx.fillStyle = color;
    ctx.fillRect(-5, -5, 10, 10);
    ctx.strokeRect(-5, -5, 10, 10);
  }
  ctx.restore();
}

function drawStation(pt, color) {
  ctx.beginPath();
  ctx.arc(pt.x, pt.y, 5, 0, 2 * Math.PI);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.6;
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(pt.x, pt.y, 1.6, 0, 2 * Math.PI);
  ctx.fillStyle = color;
  ctx.fill();
}

function drawAircraft(pt, angle, color) {
  ctx.save();
  ctx.translate(pt.x, pt.y);
  ctx.rotate(((angle === null ? 0 : angle)) * Math.PI / 180);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, -9); ctx.lineTo(0, 7);
  ctx.moveTo(-8, 0); ctx.lineTo(8, 0);
  ctx.moveTo(-4, 7); ctx.lineTo(4, 7);
  ctx.stroke();
  ctx.restore();
}

function drawHalo(pt, r, color) {
  ctx.beginPath();
  ctx.arc(pt.x, pt.y, r, 0, 2 * Math.PI);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

function drawLabel(pt, s, radius, boxes, stale) {
  const text = shipLabel(s);
  ctx.font = '11px -apple-system, system-ui, sans-serif';
  const w = ctx.measureText(text).width;
  const x = pt.x + radius + 4, y = pt.y + 4;
  const box = [x - 2, y - 10, x + w + 2, y + 3];
  for (const b of boxes) {
    if (box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1]) return;
  }
  boxes.push(box);
  ctx.lineWidth = 3;
  ctx.strokeStyle = '#0b1219cc';
  ctx.strokeText(text, x, y);
  ctx.fillStyle = stale ? '#b9c4ce' : '#fff';
  ctx.fillText(text, x, y);

  if (map.getZoom() >= 12 && s.sog !== undefined && s.sog > 0.3) {
    const sub = `${num(s.sog)} nds  ${Math.round(s.cog ?? 0)}°`;
    ctx.strokeText(sub, x, y + 12);
    ctx.fillStyle = '#c8d3dd';
    ctx.fillText(sub, x, y + 12);
    boxes.push([x - 2, y + 2, x + ctx.measureText(sub).width + 2, y + 15]);
  }
}

// --- désignation d'une cible ----------------------------------------------

function hitTest(x, y) {
  let best = null, bestDist = 18 * 18;
  for (const h of state.hits) {
    const dx = x - h.x, dy = y - h.y;
    const d = dx * dx + dy * dy;
    const limit = Math.max(h.r + 6, 12) ** 2;
    if (d < limit && d < bestDist) { best = h.mmsi; bestDist = d; }
  }
  return best;
}

const container = map.getContainer();

container.addEventListener('mousemove', (e) => {
  const rect = container.getBoundingClientRect();
  state.cursor = { x: e.clientX - rect.left, y: e.clientY - rect.top };
  if (state.pinned) return;
  const hit = hitTest(state.cursor.x, state.cursor.y);
  if (hit !== state.hover) {
    state.hover = hit;
    container.style.cursor = hit ? 'pointer' : '';
    if (hit) showTip(hit); else hideTip();
    draw();
  } else if (hit) {
    placeTip(state.cursor.x, state.cursor.y);
  }
});

container.addEventListener('mouseleave', () => {
  if (state.pinned) return;
  state.hover = null;
  hideTip();
  draw();
});

map.on('click', (e) => {
  const hit = hitTest(e.containerPoint.x, e.containerPoint.y);
  if (hit) select(hit, true);
  else if (state.pinned) { state.pinned = false; state.selected = null; hideTip(); draw(); }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { state.pinned = false; state.selected = null; hideTip(); draw(); }
});

function select(mmsi, pin) {
  state.selected = mmsi;
  state.hover = mmsi;
  state.pinned = !!pin;
  showTip(mmsi);
  renderList();
  draw();
}

// --- infobulle -------------------------------------------------------------

const tip = document.getElementById('tip');

function hideTip() { tip.hidden = true; tip.classList.remove('pinned'); }

function showTip(mmsi) {
  const s = state.ships.get(mmsi);
  if (!s) return hideTip();
  const cached = state.details.get(mmsi);
  tip.hidden = false;
  tip.classList.toggle('pinned', state.pinned);
  tip.innerHTML = renderTip(s, cached && cached.data);
  if (state.pinned) positionPinnedTip();
  else placeTip(state.cursor.x, state.cursor.y);
  if (!cached || Date.now() - cached.t > 3000) fetchDetail(mmsi);
}

function placeTip(x, y) {
  const rect = tip.getBoundingClientRect();
  const box = container.getBoundingClientRect();
  let left = x + 18, top = y + 12;
  if (left + rect.width > box.width - 8) left = x - rect.width - 18;
  if (top + rect.height > box.height - 8) top = Math.max(8, box.height - rect.height - 8);
  tip.style.left = `${Math.max(8, left)}px`;
  tip.style.top = `${top}px`;
}

function positionPinnedTip() {
  const s = state.ships.get(state.selected);
  if (!s || s.lat === null || s.lat === undefined) return;
  const pt = map.latLngToContainerPoint([s.lat, s.lon]);
  placeTip(pt.x, pt.y);
}

async function fetchDetail(mmsi) {
  try {
    const r = await fetch(`/api/ship/${mmsi}`);
    if (!r.ok) return;
    const data = await r.json();
    state.details.set(mmsi, { t: Date.now(), data });
    if (state.hover === mmsi || state.selected === mmsi) {
      const s = state.ships.get(mmsi);
      if (s) {
        // Le détail rallonge l'infobulle : il faut la replacer, sinon elle
        // déborde sous le bas de la fenêtre.
        tip.innerHTML = renderTip(s, data);
        if (state.pinned) positionPinnedTip();
        else placeTip(state.cursor.x, state.cursor.y);
      }
      draw();
    }
  } catch (err) { /* le rafraîchissement suivant réessaiera */ }
}

function dl(rows) {
  const body = rows
    .filter((r) => r[1] !== undefined && r[1] !== null && r[1] !== '')
    .map((r) => `<dt>${esc(r[0])}</dt><dd${r[2] ? ` class="${r[2]}"` : ''}>${r[1]}</dd>`)
    .join('');
  return body ? `<dl>${body}</dl>` : '';
}

function section(title, rows) {
  const body = Array.isArray(rows) ? dl(rows) : rows;
  return body ? `<section><h3>${title}</h3>${body}</section>` : '';
}

function renderTip(s, d) {
  const now = Date.now() / 1000;
  const info = d || {};
  const out = [];

  const sub = [s.country, MMSI_KIND[info.mmsi_kind || s.kind] || ''].filter(Boolean).join(' · ');
  out.push(`<h2>${esc(shipLabel(s))} <span class="sub">${esc(sub)}</span></h2>`);
  const type = [s.type_label, s.type !== undefined && s.type !== null ? `code ${s.type}` : '']
    .filter(Boolean).join(' — ');
  if (type) out.push(`<div class="type">${esc(type)}</div>`);

  // position et mouvement
  const pos = [];
  if (s.lat !== null && s.lat !== undefined) {
    pos.push(['position', `<span class="mono">${fmtLat(s.lat)}<br>${fmtLon(s.lon)}</span>`]);
    if (s.dist !== undefined) pos.push(['du point de réf.', `${num(s.dist, 2)} NM au ${pad(s.brg, 3)}°`]);
  }
  if (s.sog !== undefined) pos.push(['vitesse fond', `${num(s.sog)} nds`]);
  if (s.cog !== undefined) pos.push(['route fond', `${num(s.cog)}°`]);
  if (s.hdg !== undefined && s.hdg < 360) pos.push(['cap compas', `${s.hdg}°`]);
  if (s.rot !== undefined && s.rot !== null) {
    pos.push(['giration', `${num(s.rot, 0)} °/min ${s.rot > 0 ? '(tribord)' : s.rot < 0 ? '(bâbord)' : ''}`]);
  }
  if (s.status_label) pos.push(['statut', esc(s.status_label)]);
  if (info.maneuver && info.maneuver !== 'non disponible') pos.push(['manœuvre', esc(info.maneuver)]);
  if (info.accuracy !== undefined) pos.push(['précision GNSS', info.accuracy ? '< 10 m (DGPS)' : '> 10 m']);
  if (info.epfd) pos.push(['positionnement', esc(info.epfd)]);
  if (info.raim !== undefined) pos.push(['RAIM', info.raim ? 'actif' : 'inactif']);
  out.push(section('Navigation', pos));

  // identité
  const id = [
    ['MMSI', `<span class="mono">${s.mmsi}</span>`],
    ['indicatif', s.callsign ? esc(s.callsign) : ''],
    ['OMI', info.imo ? String(info.imo) : ''],
    ['pavillon', s.country ? `${esc(s.country)} (MID ${info.mid || ''})` : ''],
  ];
  if (s.dim) {
    const [b, st, p, sb] = s.dim;
    id.push(['dimensions', `${b + st} × ${p + sb} m`]);
    // Sur un navire les quatre distances sont mesurées depuis l'antenne GNSS ;
    // sur une aide à la navigation elles ne décrivent que son encombrement.
    if (s.kind === 'vessel') id.push(['antenne', `${b} m de l'étrave, ${p} m du bord bâbord`]);
  }
  if (s.draught) id.push(['tirant d\'eau', `${num(s.draught)} m`]);
  if (info.raw && info.raw.vendorid) {
    id.push(['transpondeur', esc([info.raw.vendorid, info.raw.model, info.raw.serial].filter(Boolean).join(' '))]);
  }
  out.push(section('Identité', id));

  // voyage
  const voyage = [
    ['destination', s.dest ? esc(s.dest) : ''],
    ['ETA', info.eta || ''],
  ];
  out.push(section('Voyage', voyage));

  // aide à la navigation
  if (s.kind === 'aton') {
    out.push(section('Aide à la navigation', [
      ['type', info.aton_label ? esc(info.aton_label) : ''],
      ['nature', s.virtual ? '<span class="flag">virtuelle</span>' : 'physique'],
      ['position', s.off_position ? '<span class="flag">hors position</span>' : 'en place'],
    ]));
  }

  // météo (message 8 DAC=1 FID=31)
  if (info.meteo_clean && Object.keys(info.meteo_clean).length) {
    const rows = Object.entries(info.meteo_clean).map(([k, v]) => {
      const [label, unit] = METEO[k] || [k, ''];
      const value = typeof v === 'number' ? `${num(v, Number.isInteger(v) ? 0 : 1)}${unit ? ' ' + unit : ''}` : esc(v);
      return [label, value];
    });
    out.push(section('Météo / hydro transmises', rows));
  }

  // réception
  const types = info.msg_types
    ? Object.entries(info.msg_types).map(([k, v]) => `n°${k} ×${v}`).join(', ')
    : '';
  out.push(section('Réception', [
    ['dernier message', `il y a ${fmtAge(now - s.last)}`],
    ['dernière position', s.last_pos ? `il y a ${fmtAge(now - s.last_pos)} (${fmtClock(s.last_pos)})` : '—'],
    ['première vue', info.first ? fmtClock(info.first) : ''],
    ['messages', `${s.msgs}`],
    ['messages par type', types],
    ['points de trace', info.track ? String(info.track.length) : ''],
  ]));

  // tout le reste, brut
  if (info.raw) {
    const rows = Object.entries(info.raw).map(([k, v]) => [FIELDS[k] || k, `<span class="mono">${esc(v)}</span>`]);
    const meteoRows = info.meteo_raw && Object.keys(info.meteo_raw).length
      ? Object.entries(info.meteo_raw).map(([k, v]) => [(METEO[k] && METEO[k][0]) || FIELDS[k] || k, `<span class="mono">${esc(v)}</span>`])
      : [];
    out.push(`<details><summary>champs bruts décodés (${rows.length + meteoRows.length})</summary>${dl(rows)}`
      + (meteoRows.length ? `<h3 style="margin-top:6px">message 8 (météo), brut</h3>${dl(meteoRows)}` : '')
      + '</details>');
  } else {
    out.push('<div class="hint">chargement du détail…</div>');
  }

  out.push(`<div class="hint">${state.pinned ? 'Échap ou clic sur la carte pour refermer' : 'clic pour épingler'}</div>`);
  return out.join('');
}

// --- liste latérale --------------------------------------------------------

const listBody = document.querySelector('#list tbody');

function matches(s, q) {
  return (s.name && s.name.toLowerCase().includes(q))
    || String(s.mmsi).includes(q)
    || (s.callsign && s.callsign.toLowerCase().includes(q))
    || (s.dest && s.dest.toLowerCase().includes(q))
    || (s.type_label && s.type_label.toLowerCase().includes(q))
    || (s.country && s.country.toLowerCase().includes(q));
}

function renderList() {
  const now = Date.now() / 1000;
  let ships = [...state.ships.values()];
  if (state.filter) ships = ships.filter((s) => matches(s, state.filter));
  if (state.opts.moving) ships = ships.filter((s) => (s.sog || 0) >= 0.5);
  ships.sort((a, b) => (a.dist ?? 9e9) - (b.dist ?? 9e9) || shipLabel(a).localeCompare(shipLabel(b)));

  document.getElementById('count').textContent = ships.length;

  const rows = ships.slice(0, 300).map((s) => {
    const age = now - (s.last_pos || s.last);
    const cls = [s.mmsi === state.selected ? 'sel' : '', age > 600 ? 'stale' : ''].join(' ').trim();
    const speed = s.sog !== undefined ? `${num(s.sog)}` : '';
    const cog = s.cog !== undefined && s.cog < 360 ? `${Math.round(s.cog)}°` : '';
    return `<tr data-mmsi="${s.mmsi}" class="${cls}">
      <td class="name" title="${esc(s.type_label || '')}">
        <i class="pip" style="background:${colorOf(s)}"></i>${esc(shipLabel(s))}
        <div class="mmsi">${s.mmsi}${s.country ? ' · ' + esc(s.country) : ''}</div>
      </td>
      <td class="num">${speed}<div class="mmsi">${cog}</div></td>
      <td class="num">${s.dist !== undefined ? num(s.dist, 1) : '—'}<div class="mmsi">${s.brg !== undefined ? pad(s.brg, 3) + '°' : ''}</div></td>
      <td class="num">${fmtAge(age)}</td>
    </tr>`;
  });
  listBody.innerHTML = rows.join('');
}

listBody.addEventListener('click', (e) => {
  const tr = e.target.closest('tr');
  if (!tr) return;
  const mmsi = Number(tr.dataset.mmsi);
  const s = state.ships.get(mmsi);
  if (s && s.lat !== null && s.lat !== undefined) map.panTo([s.lat, s.lon]);
  select(mmsi, true);
});

// --- réglages --------------------------------------------------------------

document.getElementById('search').addEventListener('input', (e) => {
  state.filter = e.target.value.trim().toLowerCase();
  renderList();
  draw();
});

function bindCheck(id, key, after) {
  document.getElementById(id).addEventListener('change', (e) => {
    state.opts[key] = e.target.checked;
    if (after) after();
    renderList();
    draw();
  });
}

bindCheck('opt-labels', 'labels');
bindCheck('opt-moving', 'moving');
bindCheck('opt-tracks', 'tracks', () => { if (state.opts.tracks) pollTracks(); else state.tracks.clear(); });
bindCheck('opt-all', 'all', () => { state.seq = 0; state.ships.clear(); poll(); });

document.getElementById('opt-vector').addEventListener('change', (e) => {
  state.opts.vector = Number(e.target.value);
  draw();
});

document.getElementById('collapse').addEventListener('click', () => {
  document.getElementById('panel').classList.toggle('collapsed');
});

document.getElementById('legend').innerHTML = LEGEND
  .map(([k, label]) => `<span><i style="background:${COLORS[k]}"></i>${label}</span>`).join('');

// --- flux de données -------------------------------------------------------

async function poll() {
  try {
    const q = `since=${state.seq}${state.opts.all ? '&all=1' : ''}`;
    const r = await fetch(`/api/ships?${q}`);
    const data = await r.json();
    if (data.full) state.ships.clear();
    for (const s of data.ships) state.ships.set(s.mmsi, s);
    state.seq = data.seq;
    prune(data.now);
    renderList();
    draw();
    if (state.pinned && state.selected) fetchDetail(state.selected);
  } catch (err) { /* serveur momentanément indisponible */ }
}

function prune(now) {
  const limit = now - state.cfg.max_age;
  for (const [mmsi, s] of state.ships) if (s.last < limit) state.ships.delete(mmsi);
}

async function pollTracks() {
  if (!state.opts.tracks) return;
  try {
    const r = await fetch(`/api/tracks?minutes=180${state.opts.all ? '&all=1' : ''}`);
    const data = await r.json();
    state.tracks = new Map(Object.entries(data));
    draw();
  } catch (err) { /* ignoré */ }
}

async function pollStatus() {
  try {
    const r = await fetch('/api/status');
    const st = await r.json();
    const first = !state.ready;
    state.cfg = { ref: st.ref, radius: st.radius, max_age: st.max_age };
    if (first) {
      state.ready = true;
      map.setView(st.ref, 10);
      refMarker.setLatLng(st.ref);
      refCircle.setLatLng(st.ref).setRadius(st.radius * NM);
      const maxNative = st.charts.length ? Math.max(...st.charts.map((c) => c.maxzoom)) : 15;
      charts.options.maxNativeZoom = maxNative;
      if (st.charts.length) {
        charts.getAttribution = () => st.charts.map((c) => c.name).join(', ');
        map.attributionControl.addAttribution(st.charts.map((c) => esc(c.description || c.name)).join(' · '));
      } else {
        map.removeLayer(charts);
      }
      resize();
    }
    document.getElementById('conn').className = `dot ${st.connected ? 'on' : 'off'}`;
    document.getElementById('status-text').innerHTML =
      `${st.connected ? esc(st.source) : 'déconnecté'} · ${st.rate} msg/s · `
      + `${st.positioned}/${st.ships} positions · rayon ${st.radius} NM`
      + (st.error && !st.connected ? `<br><span class="flag">${esc(st.error)}</span>` : '');
  } catch (err) {
    document.getElementById('conn').className = 'dot off';
    document.getElementById('status-text').textContent = 'serveur injoignable';
  }
}

pollStatus();
poll();
setInterval(poll, 2000);
setInterval(pollStatus, 5000);
setInterval(pollTracks, 20000);
setInterval(() => { renderList(); draw(); }, 10000);
resize();
