/*
 * OJP 2.0 probe (TECH-05, TECH-07): sends real requests for Geneva to api.opentransportdata.swiss and saves the
 * raw XML answers as test fixtures, plus a report (status, timing, size, quota and CORS headers).
 *
 * Requests are built with the official SDK (ojp-sdk, MIT, openTdataCH) so their format is the reference one.
 * The token comes from the OJP_TOKEN environment variable (a GitHub Actions secret) and is never written anywhere.
 *
 *   OJP_TOKEN=… node scripts/ojp_probe.mjs tests/fixtures/ojp
 */
import * as OJP from 'ojp-sdk';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';
const APP = createRequire(import.meta.url)('../assets/ojp.js');   // the app's own request builders

const OUT = process.argv[2] || 'tests/fixtures/ojp';
const URL_OJP = 'https://api.opentransportdata.swiss/ojp20';
const ORIGIN = 'https://tiagsant.github.io';
const TOKEN = process.env.OJP_TOKEN;
if (!TOKEN) { console.error('OJP_TOKEN is not set (add it as a repository secret).'); process.exit(1); }

const sdk = OJP.SDK.create('swissPublicTransport_prototype', { url: URL_OJP, authToken: null }, 'fr');
const xml = req => req.buildRequestXML('fr', sdk.requestorRef, OJP.DefaultXML_Config);
const R = sdk.requests;
mkdirSync(OUT, { recursive: true });

const KEEP_HEADERS = /^(x-)?rate|^retry-after|^access-control|^content-(type|encoding|length)|^x-request-id|^date$/i;
const report = { probedAt: new Date().toISOString(), endpoint: URL_OJP, sdk: OJP.SDK_VERSION, requests: {}, cors: {} };

const sleep = ms => new Promise(res => setTimeout(res, ms));
const SPACING_MS = 1500;   // free tier: 50 requests per minute → stay well below

async function post(name, body, extraHeaders = {}) {
  await sleep(SPACING_MS);
  let r, text, t0, lastError;
  for (let attempt = 1; attempt <= 3 && !r; attempt++) {   // the server sometimes closes the socket: retry
    t0 = Date.now();
    try {
      r = await fetch(URL_OJP, { method: 'POST', body,
        headers: { 'Content-Type': 'application/xml', Authorization: `Bearer ${TOKEN}`, ...extraHeaders } });
      text = await r.text();
    } catch (e) { r = null; lastError = e; console.log(`${name.padEnd(22)} attempt ${attempt} failed: ${e.cause?.message || e.message}`); await sleep(3000 * attempt); }
  }
  if (!r) { report.requests[name] = { error: String(lastError?.cause?.message || lastError) }; return ''; }
  const headers = Object.fromEntries([...r.headers].filter(([k]) => KEEP_HEADERS.test(k)));
  report.requests[name] = { status: r.status, ms: Date.now() - t0, bytes: text.length, headers };
  writeFileSync(join(OUT, `${name}.request.xml`), body);
  writeFileSync(join(OUT, `${name}.xml`), text);
  console.log(`${name.padEnd(22)} ${r.status} ${String(Date.now() - t0).padStart(5)} ms ${String(text.length).padStart(8)} B`);
  return text;
}

// 1. Stop search by name, and stops around a point (Petit-Lancy, near Les Esserts)
await post('lir_name_belair', xml(R.LocationInformationRequest.initWithLocationName('Bel-Air', ['stop'], 10)));
await post('lir_name_esserts', xml(R.LocationInformationRequest.initWithLocationName('Esserts', ['stop'], 10)));
await post('lir_coords_point', xml(R.LocationInformationRequest.initWithPlaceRef('46.1890,6.1150', 10)));
await post('lir_bbox_point', xml(R.LocationInformationRequest.initWithBBOX([6.1100, 46.1860, 6.1200, 46.1920], ['stop'], 10)));

// 2. Departures: TPG tram/bus stop, main railway station, Mouettes pier, the PO's stop
const ser = {};
for (const [name, id] of [['ser_belair', '8587387'], ['ser_geneve_gare', '8501008'], ['ser_paquis_lac', '8501238'], ['ser_esserts', '8587418']]) {
  ser[name] = await post(name, xml(R.StopEventRequest.initWithPlaceRefAndDate(id, new Date())));
}

// 3. Journeys: stop to stop, and map point to map point (no nearest-stop workaround needed with OJP)
await post('tr_stops', xml(R.TripRequest.initWithPlaceRefsOrCoords('8587418', '8587057')));
await post('tr_coords', xml(R.TripRequest.initWithPlaceRefsOrCoords('46.1890,6.1150', '46.2100,6.1425')));

// 4. Details of one vehicle run taken from the Bel-Air departures (next stops)
const m = ser.ser_belair.match(/<JourneyRef>([^<]+)<\/JourneyRef>[\s\S]*?<OperatingDayRef>([^<]+)<\/OperatingDayRef>/);
if (m) await post('tir_from_belair', xml(R.TripInfoRequest.initWithJourneyRef(m[1], new Date(m[2] + 'T12:00:00'))));
else console.log('tir_from_belair        skipped (no JourneyRef found)');

// 5. Requests exactly as the prototype sends them (assets/ojp.js), to check them against the live service
const ZONE = { latMin: 45.85, latMax: 46.50, lonMin: 5.80, lonMax: 6.65 };   // Unireso area, as in the app
const ago = min => new Date(Date.now() - min * 60000);
await post('app_lir_name_zone_belair', APP.locationsByName('Bel-Air', { zone: ZONE, limit: 20 }));
await post('app_lir_name_zone_gare', APP.locationsByName('Gare', { zone: ZONE, limit: 20 }));
await post('app_lir_zone_esserts', APP.locationsInZone({ latMin: 46.1836, latMax: 46.1926, lonMin: 6.1066, lonMax: 6.1196 }, { limit: 20 }));
await post('app_ser_esserts_full', APP.stopEvents('8587418', { from: ago(30), limit: 150 }));
await post('app_ser_esserts_light', APP.stopEvents('8587418', { from: ago(30), limit: 150, onward: false }));
await post('app_ser_belair_light', APP.stopEvents('8587387', { from: ago(30), limit: 150, onward: false }));
await post('app_lir_address_rhone', APP.locationsByName('Rue du Rhône 10 Genève', { types: ['stop', 'address', 'poi'], limit: 10 }));
await post('app_lir_poi_palexpo', APP.locationsByName('Palexpo', { types: ['stop', 'address', 'poi'], limit: 10 }));
await post('app_lir_address_lancy', APP.locationsByName('Avenue des Communes-Réunies 60 Lancy', { types: ['address'], limit: 5 }));
await post('app_tr_depart', APP.trip('8587418', '8587057', { at: new Date() }));
await post('app_tr_arrive', APP.trip('8587418', '8587057', { at: new Date(Date.now() + 3600000), arrive: true }));

// 6. Can a browser page on GitHub Pages call the API directly? (CORS preflight + a real POST with an Origin)
const pre = await fetch(URL_OJP, { method: 'OPTIONS', headers: { Origin: ORIGIN, 'Access-Control-Request-Method': 'POST',
  'Access-Control-Request-Headers': 'authorization,content-type' } });
report.cors.preflight = { status: pre.status, headers: Object.fromEntries([...pre.headers].filter(([k]) => /^access-control/i.test(k))) };
await post('cors_post_with_origin', xml(R.LocationInformationRequest.initWithLocationName('Cornavin', ['stop'], 1)), { Origin: ORIGIN });
report.cors.post = report.requests.cors_post_with_origin.headers;
report.cors.browserCanCall = pre.ok && /tiagsant\.github\.io|\*/.test(report.cors.preflight.headers['access-control-allow-origin'] || '')
  && /authorization/i.test(report.cors.preflight.headers['access-control-allow-headers'] || '');

writeFileSync(join(OUT, 'probe-report.json'), JSON.stringify(report, null, 2) + '\n');
console.log('CORS preflight:', JSON.stringify(report.cors.preflight));
console.log('Browser can call OJP directly:', report.cors.browserCanCall);
const failed = Object.entries(report.requests).filter(([, v]) => v.status !== 200);
if (failed.length) { console.error('Non-200 answers:', failed.map(([k, v]) => `${k}=${v.status}`).join(', ')); process.exit(2); }
