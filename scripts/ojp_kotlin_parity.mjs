/*
 * Parity oracle for the Kotlin OJP client (TECH-12).
 *
 * Runs the prototype's own adapter (assets/ojp.js) and writes what it produces, so the Kotlin tests in
 * android/core can check that they build the same XML and read the same values from every recorded answer:
 *
 *   tests/fixtures/ojp-kotlin/requests/<case>.params   parameters of a request (key=value per line)
 *   tests/fixtures/ojp-kotlin/requests/<case>.xml      the XML that assets/ojp.js builds for them
 *   tests/fixtures/ojp-kotlin/answers/<fixture>.txt    what assets/ojp.js reads from a recorded answer, one line per item
 *
 * The recorded requests of the app (tests/fixtures/ojp/app_*.request.xml) are rebuilt first and must match byte for byte.
 * Needs jsdom for the browser DOMParser the adapter uses:
 *
 *   npm install --prefix /tmp/jsenv jsdom
 *   NODE_PATH=/tmp/jsenv/node_modules node scripts/ojp_kotlin_parity.mjs
 */
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, readdirSync, writeFileSync, rmSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { JSDOM } = require('jsdom');
globalThis.DOMParser = new JSDOM('').window.DOMParser;
const OJP = require('../assets/ojp.js');

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const FIX = join(ROOT, 'tests/fixtures');
const OUT = join(FIX, 'ojp-kotlin');
rmSync(OUT, { recursive: true, force: true });
mkdirSync(join(OUT, 'requests'), { recursive: true });
mkdirSync(join(OUT, 'answers'), { recursive: true });

// ---------- Requests ----------
const tag = (xml, name) => { const m = xml.match(new RegExp(`<${name}>([^<]*)</${name}>`)); return m ? m[1] : null; };
const unesc = s => s.replace(/&lt;|&gt;|&quot;|&apos;|&amp;/g, e => ({ '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'", '&amp;': '&' }[e]));

// Parameters of a recorded app request, read back from its XML
function paramsOf(xml) {
  const p = { lang: tag(xml, 'siri:Language'), now: tag(xml, 'siri:RequestTimestamp') };
  const zone = () => {
    const m = xml.match(/<UpperLeft><siri:Longitude>([^<]+)<\/siri:Longitude><siri:Latitude>([^<]+)<\/siri:Latitude><\/UpperLeft><LowerRight><siri:Longitude>([^<]+)<\/siri:Longitude><siri:Latitude>([^<]+)<\/siri:Latitude>/);
    return m ? { latMin: +m[4], latMax: +m[2], lonMin: +m[1], lonMax: +m[3] } : null;
  };
  if (xml.includes('<OJPLocationInformationRequest>')) {
    const types = [...xml.matchAll(/<Type>([^<]+)<\/Type>/g)].map(m => m[1]);
    const name = tag(xml, 'Name');
    Object.assign(p, { limit: +tag(xml, 'NumberOfResults'), types, zone: zone() });
    if (name != null) Object.assign(p, { kind: 'byName', name: unesc(name) }); else p.kind = 'inZone';
  } else if (xml.includes('<OJPStopEventRequest>')) {
    Object.assign(p, { kind: 'stopEvents', stopId: tag(xml, 'siri:StopPointRef'), from: tag(xml, 'DepArrTime'),
                       limit: +tag(xml, 'NumberOfResults'), onward: tag(xml, 'IncludeOnwardCalls') === 'true' });
  } else {
    const refs = [...xml.matchAll(/<StopPlaceRef>([^<]+)<\/StopPlaceRef>/g)].map(m => m[1]);
    Object.assign(p, { kind: 'trip', fromId: refs[0], toId: refs[1], at: tag(xml, 'DepArrTime'),
                       arrive: /<Destination>.*<DepArrTime>/.test(xml), limit: +tag(xml, 'NumberOfResults') });
  }
  return p;
}

function build(p) {
  switch (p.kind) {
    case 'byName': return OJP.locationsByName(p.name, { lang: p.lang, now: p.now, limit: p.limit, types: p.types, zone: p.zone || undefined });
    case 'inZone': return OJP.locationsInZone(p.zone, { lang: p.lang, now: p.now, limit: p.limit });
    case 'stopEvents': return OJP.stopEvents(p.stopId, { lang: p.lang, now: p.now, from: p.from, limit: p.limit, onward: p.onward });
    case 'trip': return OJP.trip(p.fromId, p.toId, { lang: p.lang, now: p.now, at: p.at, arrive: p.arrive, limit: p.limit });
  }
  throw new Error('unknown kind ' + p.kind);
}

function writeParams(name, p) {
  const lines = Object.entries(p).filter(([, v]) => v !== undefined && v !== null).map(([k, v]) =>
    k === 'zone' ? `zone=${v.latMin},${v.latMax},${v.lonMin},${v.lonMax}` :
    Array.isArray(v) ? `${k}=${v.join(',')}` : `${k}=${v}`);
  writeFileSync(join(OUT, 'requests', name + '.params'), lines.join('\n') + '\n');
  writeFileSync(join(OUT, 'requests', name + '.xml'), build(p));
}

let recorded = 0;
for (const f of readdirSync(join(FIX, 'ojp')).filter(f => /^app_.*\.request\.xml$/.test(f)).sort()) {
  const xml = readFileSync(join(FIX, 'ojp', f), 'utf8');
  const p = paramsOf(xml);
  if (build(p) !== xml) throw new Error(`${f}: assets/ojp.js does not rebuild the recorded request`);
  writeParams('recorded_' + f.replace('.request.xml', ''), p);
  recorded++;
}

// Edge cases: escaping, defaults, whole-number coordinates, several types, arriving by
const NOW = '2026-11-20T17:05:09.007Z';
const extra = {
  edge_name_escaped: { kind: 'byName', lang: 'de', now: NOW, name: `Zürich "HB" <Bahnhof> & 'Gleis'`, limit: 20, types: ['stop'] },
  edge_name_defaults: { kind: 'byName', lang: 'it', now: NOW, name: 'Lugano', limit: 20, types: ['stop'] },
  edge_name_all_types_zone: { kind: 'byName', lang: 'rm', now: NOW, name: 'Cuira', limit: 30, types: ['stop', 'address', 'poi'],
                              zone: { latMin: 46, latMax: 47.5, lonMin: 9, lonMax: 10.25 } },
  edge_zone_whole_numbers: { kind: 'inZone', lang: 'en', now: NOW, zone: { latMin: 46, latMax: 47, lonMin: 6, lonMax: 7 }, limit: 40 },
  edge_stop_events_full: { kind: 'stopEvents', lang: 'fr', now: NOW, stopId: '8501008', from: '2026-11-20T17:03:09.007Z', limit: 40, onward: true },
  edge_stop_events_escaped_id: { kind: 'stopEvents', lang: 'fr', now: NOW, stopId: 'ch:1:sloid:7000<&>', from: NOW, limit: 5, onward: false },
  edge_trip_arrive: { kind: 'trip', lang: 'en', now: NOW, fromId: '8592995', toId: '8501120', at: '2026-11-21T08:00:00.000Z', arrive: true, limit: 6 },
};
for (const [name, p] of Object.entries(extra)) writeParams(name, p);

// ---------- Answers ----------
const clean = v => v == null || v === '' ? '-' : String(v).replace(/\\/g, '\\\\').replace(/\|/g, '\\|').replace(/\r?\n/g, '\\n');
const line = (...xs) => xs.map(clean).join('|');
const time = s => { if (!s) return null; const d = new Date(s); return isNaN(d) ? 'bad:' + s : d.toISOString(); };
const coord = c => c ? `${c.x},${c.y}` : null;
// ISO 8601 duration → whole seconds ("PT1H23M" and "PT83M" are the same duration)
const secs = d => { const m = String(d || '').match(/^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$/); return m ? (+m[1] || 0) * 3600 + (+m[2] || 0) * 60 + Math.round(+m[3] || 0) : null; };
const st = s => s ? `${s.id || ''}~${s.name || ''}` : null;
const sitIds = list => (list || []).map(s => s.id).join(',');
function sitLines(all) {
  const seen = new Map();
  for (const s of all) if (!seen.has(s.id)) seen.set(s.id, s);
  return [...seen.values()].sort((a, b) => a.id < b.id ? -1 : 1).map(s => line('sit', s.id, s.severity, s.planned,
    s.periods.map(p => `${time(p[0]) || ''}/${time(p[1]) || ''}`).join(','), s.summary, s.description, s.consequence, s.recommendation, s.duration));
}

function locations(xml) {
  const r = OJP.toLocations(xml);
  return [...r.stations.map(s => line('stop', s.id, s.name, coord(s.coordinate), s.icon)), line('error', r.error)];
}
function places(xml) {
  const r = OJP.toPlaces(xml);
  return [...r.places.map(p => line(p.type, p.id, p.name, coord(p.coordinate), p.street, p.number, p.town)), line('error', r.error)];
}
function board(xml, stopId, patterns) {
  const r = OJP.toStationboard(xml, stopId, patterns, 'fr');
  const out = [line('station', r.station.id, r.station.name, coord(r.station.coordinate)), line('unknownPatterns', r.unknownPatterns)];
  for (const d of r.stationboard) {
    out.push(line('dep', d.category, d.number, d.name, d.operator, d.operatorRef, d.to, d.multiDest,
      time(d.stop.departure), time(d.stop.prognosis.departure), d.stop.platform, d.stop.prognosis.platform,
      st(d.stop.station), sitIds(d.situations),
      d.passList.slice(1).map(p => `${p.station.id}~${p.station.name}~${time(p.arrival) || ''}~${p.platform || ''}~${coord(p.station.coordinate) || ''}`).join(';')));
  }
  out.push(...sitLines(r.stationboard.flatMap(d => d.situations)));
  out.push(line('error', r.error));
  return out;
}
function connections(xml) {
  const r = OJP.toConnections(xml, 'fr');
  const out = [], sits = [];
  for (const c of r.connections) {
    out.push(line('trip', secs(c.duration), c.transfers));
    for (const s of c.sections) {
      if (s.journey) {
        const j = s.journey;
        sits.push(...j.situations);
        out.push(line('ride', j.category, j.number, j.name, j.operator, j.operatorRef, j.to, j.multiDest, j.cancelled,
          st(s.departure.station), time(s.departure.departure), time(s.departure.prognosis.departure), s.departure.platform, s.departure.prognosis.platform,
          st(s.arrival.station), time(s.arrival.arrival), time(s.arrival.prognosis.arrival), s.arrival.platform, s.arrival.prognosis.platform,
          sitIds(j.situations),
          j.passList.map(p => `${p.station.id}~${time(p.arrival) || ''}~${time(p.prognosis.arrival) || ''}~${time(p.departure) || ''}~${time(p.prognosis.departure) || ''}`).join(';')));
      } else {
        out.push(line('walk', s.walk.duration, st(s.departure.station), st(s.arrival.station)));
      }
    }
  }
  out.push(...sitLines(sits));
  out.push(line('error', r.error));
  return out;
}

const write = (name, lines) => writeFileSync(join(OUT, 'answers', name + '.txt'), lines.join('\n') + '\n');
const requestOf = (dir, f) => { const p = join(FIX, dir, f.replace(/\.xml$/, '.request.xml')); return existsSync(p) ? readFileSync(p, 'utf8') : ''; };
let answers = 0;
for (const dir of ['ojp', 'ojp-places', 'ojp-split']) {
  const files = readdirSync(join(FIX, dir)).filter(f => f.endsWith('.xml') && !f.endsWith('.request.xml')).sort();
  // a full board first, so the light refresh of the same stop can rebuild its next stops (as the prototype does)
  files.sort((a, b) => (a.includes('_light') - b.includes('_light')) || (a < b ? -1 : 1));
  const patterns = new Map();   // per stop id, shared by the answers of one folder
  for (const f of files) {
    const xml = readFileSync(join(FIX, dir, f), 'utf8');
    const name = dir + '__' + f.replace(/\.xml$/, '');
    if (xml.includes('<OJPLocationInformationDelivery')) {
      write(name + '.locations', locations(xml));
      write(name + '.places', places(xml));
    } else if (xml.includes('<OJPStopEventDelivery')) {
      const stopId = OJP.stopId7(tag(requestOf(dir, f), 'siri:StopPointRef') || tag(requestOf(dir, f), 'StopPointRef') || '') ||
                     OJP.stopId7((xml.match(/<siri:StopPointRef>([^<]+)</) || [])[1]);
      if (!patterns.has(stopId)) patterns.set(stopId, new Map());
      write(name + '.board', [line('stopId', stopId), ...board(xml, stopId, patterns.get(stopId))]);
    } else if (xml.includes('<OJPTripDelivery')) {
      write(name + '.trips', connections(xml));
    } else continue;   // TripInfo answers: not read by the prototype's adapter
    answers++;
  }
}
console.log(`ojp-kotlin: ${recorded} recorded requests rebuilt, ${Object.keys(extra).length} edge cases, ${answers} answers`);
