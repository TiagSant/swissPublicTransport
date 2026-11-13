/*
 * OJP 2.0 adapter (TECH-05): official Swiss open data from api.opentransportdata.swiss.
 *
 * - Builds the XML requests (same structure as the official ojp-sdk, checked against real answers by the probe).
 * - Turns the XML answers into the JSON shape the prototype already uses (transport.opendata.ch v1:
 *   /locations, /stationboard, /connections), so the rest of the app does not depend on the data source.
 *
 * Builders are plain strings and also run in Node (scripts/ojp_probe.mjs). Parsers need DOMParser (browser).
 * Validated against tests/fixtures/ojp (real answers for Geneva, Nov 2026).
 */
(function (root) {
  'use strict';

  const ENDPOINT = 'https://api.opentransportdata.swiss/ojp20';
  const REQUESTOR = 'swissPublicTransport_prototype';

  // ---------- Requests ----------
  const xesc = s => String(s).replace(/[<>&'"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', "'": '&apos;', '"': '&quot;' }[c]));
  const iso = d => new Date(d).toISOString();

  function envelope(inner, lang, now) {
    const ts = iso(now || Date.now());
    return '<?xml version="1.0" encoding="utf-8"?>\n' +
      '<OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0">' +
      '<OJPRequest><siri:ServiceRequest>' +
      `<siri:ServiceRequestContext><siri:Language>${xesc(lang || 'fr')}</siri:Language></siri:ServiceRequestContext>` +
      `<siri:RequestTimestamp>${ts}</siri:RequestTimestamp><siri:RequestorRef>${REQUESTOR}</siri:RequestorRef>` +
      inner.replace('{TS}', ts) +
      '</siri:ServiceRequest></OJPRequest></OJP>';
  }

  // zone: { latMin, latMax, lonMin, lonMax }
  const rectangle = z =>
    '<GeoRestriction><Rectangle>' +
    `<UpperLeft><siri:Longitude>${z.lonMin}</siri:Longitude><siri:Latitude>${z.latMax}</siri:Latitude></UpperLeft>` +
    `<LowerRight><siri:Longitude>${z.lonMax}</siri:Longitude><siri:Latitude>${z.latMin}</siri:Latitude></LowerRight>` +
    '</Rectangle></GeoRestriction>';

  // types: 'stop' (default), 'address', 'poi' — several allowed
  const lirRestrictions = (limit, types) =>
    `<Restrictions>${(types || ['stop']).map(x => `<Type>${x}</Type>`).join('')}<NumberOfResults>${limit}</NumberOfResults><IncludePtModes>true</IncludePtModes></Restrictions>`;

  // Stop search by name, optionally limited to an area
  function locationsByName(name, o = {}) {
    return envelope('<OJPLocationInformationRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>' +
      `<InitialInput><Name>${xesc(name)}</Name>${o.zone ? rectangle(o.zone) : ''}</InitialInput>` +
      lirRestrictions(o.limit || 20, o.types) + '</OJPLocationInformationRequest>', o.lang, o.now);
  }

  // Stops inside an area (used for "stops near me" and around a map point)
  function locationsInZone(zone, o = {}) {
    return envelope('<OJPLocationInformationRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>' +
      `<InitialInput>${rectangle(zone)}</InitialInput>` +
      lirRestrictions(o.limit || 20) + '</OJPLocationInformationRequest>', o.lang, o.now);
  }

  // Departures. `onward: false` leaves out the next stops of each run: about 5× lighter, used for refreshes.
  function stopEvents(stopId, o = {}) {
    return envelope('<OJPStopEventRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>' +
      `<Location><PlaceRef><siri:StopPointRef>${xesc(stopId)}</siri:StopPointRef><Name><Text>n/a</Text></Name></PlaceRef>` +
      `<DepArrTime>${iso(o.from || Date.now())}</DepArrTime></Location>` +
      '<Params><IncludeAllRestrictedLines>true</IncludeAllRestrictedLines>' +
      `<NumberOfResults>${o.limit || 40}</NumberOfResults><StopEventType>departure</StopEventType>` +
      `<IncludePreviousCalls>false</IncludePreviousCalls><IncludeOnwardCalls>${o.onward === false ? 'false' : 'true'}</IncludeOnwardCalls>` +
      '<UseRealtimeData>explanatory</UseRealtimeData></Params></OJPStopEventRequest>', o.lang, o.now);
  }

  // Journeys between two stops, leaving at `at` or arriving by `at` (o.arrive)
  function trip(fromId, toId, o = {}) {
    const t = `<DepArrTime>${iso(o.at || Date.now())}</DepArrTime>`;
    const place = id => `<PlaceRef><StopPlaceRef>${xesc(id)}</StopPlaceRef><Name><Text>n/a</Text></Name></PlaceRef>`;
    return envelope('<OJPTripRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>' +
      `<Origin>${place(fromId)}${o.arrive ? '' : t}</Origin>` +
      `<Destination>${place(toId)}${o.arrive ? t : ''}</Destination>` +
      `<Params><NumberOfResults>${o.limit || 4}</NumberOfResults><UseRealtimeData>explanatory</UseRealtimeData>` +
      '<IncludeAllRestrictedLines>true</IncludeAllRestrictedLines><IncludeTrackSections>false</IncludeTrackSections>' +
      '<IncludeLegProjection>false</IncludeLegProjection><IncludeIntermediateStops>true</IncludeIntermediateStops></Params>' +
      '</OJPTripRequest>', o.lang, o.now);
  }

  // ---------- Identifiers and codes ----------
  // OJP uses Swiss location ids (SLOID): "ch:1:sloid:87387" or, for a platform, "ch:1:sloid:87387:0:128561".
  // The app (and the user's saved stops) use 7-digit UIC-style ids: 85 + number on 5 digits → "8587387".
  function stopId7(ref) {
    const s = String(ref || '');
    let m = s.match(/^ch:1:sloid:(\d+)/);
    if (m) return m[1].length <= 5 ? '85' + m[1].padStart(5, '0') : m[1];
    m = s.match(/^\d{7}$/);
    return m ? s : null;
  }

  // Operators seen in Geneva answers (siri:OperatorRef "ojp:<number>")
  const OPERATORS = { 881: 'TPG', 11: 'SBB', 199: 'Mouettes genevoises', 1185: 'SNCF' };
  // OJP mode → category code understood by the app (same codes as transport.opendata.ch)
  const MODE_CATEGORY = { tram: 'T', bus: 'B', trolleyBus: 'B', coach: 'B', water: 'BAT', ferry: 'BAT',
                          funicular: 'FUN', telecabin: 'GB', cableway: 'PB', metro: 'M' };
  const MODE_ICON = { rail: 'train', tram: 'tram', bus: 'bus', trolleyBus: 'bus', coach: 'bus', water: 'ship',
                      ferry: 'ship', funicular: 'funicular', telecabin: 'cableway', cableway: 'cableway', metro: 'metro' };

  // "IR57" → IR / 57, "RL4" (Léman Express) → R / L4, "RE33" → RE / 33, "TGV" → TGV
  function splitTrainName(name) {
    const m = String(name || '').replace(/\s+/g, '').match(/^([A-Z]+?)(L\d+|\d+)$/);
    return m ? { category: m[1], number: m[2] } : { category: name || '', number: '' };
  }

  // ---------- XML helpers (namespace-agnostic) ----------
  const kids = (node, name) => node ? Array.from(node.children).filter(c => c.localName === name) : [];
  function el(node, path) {
    for (const name of path.split('/')) { node = kids(node, name)[0]; if (!node) return null; }
    return node;
  }
  function txt(node, path) {
    const e = path ? el(node, path) : node;
    if (!e) return '';
    const t = kids(e, 'Text')[0];
    return (t || e).textContent.trim();
  }
  const all = (doc, name) => Array.from(doc.getElementsByTagNameNS('*', name));
  function parse(xml) {
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    if (doc.getElementsByTagName('parsererror').length) throw new Error('OJP: unreadable XML answer');
    return doc;
  }
  // "No results" and similar conditions come back as 200 with an error condition: treated as an empty answer
  function errorCondition(doc) {
    const e = all(doc, 'ErrorCondition')[0];
    return e ? (txt(e, 'Description') || e.textContent.trim()).slice(0, 200) : null;
  }
  const geo = node => {
    const g = el(node, 'GeoPosition');
    if (!g) return null;
    const lat = parseFloat(txt(g, 'Latitude')), lon = parseFloat(txt(g, 'Longitude'));
    return isNaN(lat) || isNaN(lon) ? null : { x: lat, y: lon };   // v1 convention: x = latitude, y = longitude
  };

  // Places of the response context: stop points and stop places by their reference
  function contextPlaces(doc) {
    const map = new Map();
    for (const p of all(doc, 'Place')) {
      const sp = el(p, 'StopPoint'), spl = el(p, 'StopPlace');
      const ref = sp ? txt(sp, 'StopPointRef') : spl ? txt(spl, 'StopPlaceRef') : '';
      if (!ref) continue;
      map.set(ref, { name: sp ? txt(sp, 'StopPointName') : txt(spl, 'StopPlaceName'), coordinate: geo(p) });
    }
    return map;
  }
  function station(ref, name, places) {
    const id = stopId7(ref);
    const p = places && (places.get(ref) || places.get(String(ref).replace(/^(ch:1:sloid:\d+).*/, '$1')));
    return { id, name: name || (p && p.name) || '', coordinate: (p && p.coordinate) || null };
  }

  // ---------- Answers → transport.opendata.ch shapes ----------
  // /locations
  function toLocations(xml) {
    const doc = parse(xml);
    const stations = [];
    for (const r of all(doc, 'PlaceResult')) {
      const place = el(r, 'Place'), sp = el(place, 'StopPlace');
      if (!sp) continue;                                  // addresses, POIs
      const id = stopId7(txt(sp, 'StopPlaceRef'));
      if (!id) continue;
      const mode = txt(place, 'Mode/PtMode');
      stations.push({ id, name: txt(sp, 'StopPlaceName') || txt(place, 'Name'), coordinate: geo(place),
                      icon: MODE_ICON[mode] || null });
    }
    return { stations, error: errorCondition(doc) };
  }

  // Stop search mixing stops, addresses and places of interest (US-23)
  function toPlaces(xml) {
    const doc = parse(xml);
    const out = [];
    for (const r of all(doc, 'PlaceResult')) {
      const place = el(r, 'Place'), coordinate = geo(place);
      const sp = el(place, 'StopPlace'), ad = el(place, 'Address'), poi = el(place, 'PointOfInterest');
      if (sp) {
        const id = stopId7(txt(sp, 'StopPlaceRef'));
        if (id) out.push({ type: 'stop', id, name: txt(sp, 'StopPlaceName') || txt(place, 'Name'), coordinate, icon: MODE_ICON[txt(place, 'Mode/PtMode')] || null });
      } else if (ad && coordinate) {
        out.push({ type: 'address', id: null, name: txt(ad, 'Name') || txt(place, 'Name'), coordinate,
                   street: txt(ad, 'Street'), number: txt(ad, 'HouseNumber'), town: txt(ad, 'TopographicPlaceName') });
      } else if (poi && coordinate) {
        out.push({ type: 'poi', id: null, name: txt(poi, 'PointOfInterestName') || txt(place, 'Name'), coordinate });
      }
    }
    // Building entrances ("60.1", "60.2"…) come with the main number: keep the main one
    const mains = new Set(out.filter(x => x.type === 'address' && x.number && !x.number.includes('.')).map(x => x.street + '|' + x.number + '|' + x.town));
    return { places: out.filter(x => !(x.type === 'address' && /\./.test(x.number || '') && mains.has(x.street + '|' + x.number.split('.')[0] + '|' + x.town))),
             error: errorCondition(doc) };
  }

  function serviceInfo(service) {
    const mode = txt(service, 'Mode/PtMode');
    const name = txt(service, 'PublishedServiceName') || txt(service, 'PublicCode');
    const split = mode === 'rail' ? splitTrainName(name)
      : { category: MODE_CATEGORY[mode] || txt(service, 'ProductCategory/ShortName') || txt(service, 'Mode/ShortName'), number: name };
    const op = (txt(service, 'OperatorRef').match(/(\d+)$/) || [])[1];
    return {
      category: split.category, number: split.number, name,
      operator: (op && OPERATORS[op]) || '', operatorRef: op || null,   // company number, e.g. 881 = TPG
      to: txt(service, 'DestinationText'),
      // a run pattern: same line, direction and terminus stop (whatever its platform) → same next stops
      pattern: [txt(service, 'LineRef'), txt(service, 'DirectionRef'), stopId7(txt(service, 'DestinationStopPointRef'))].join('|')
    };
  }
  const callTimes = (call, kind) => {
    const s = el(call, kind);
    return s ? { planned: txt(s, 'TimetabledTime') || null, estimated: txt(s, 'EstimatedTime') || null } : { planned: null, estimated: null };
  };
  const minutesBetween = (a, b) => (new Date(b) - new Date(a)) / 60000;

  /*
   * /stationboard. `patterns` (a Map kept by the caller) remembers, for each run pattern, its next stops and how
   * many minutes after this stop each is reached. A full answer (with onward calls) fills it; a light refresh
   * (without onward calls) uses it to rebuild the next stops, so the direction of each departure stays known.
   */
  function toStationboard(xml, stopId, patterns) {
    const doc = parse(xml);
    const places = contextPlaces(doc);
    const board = [];
    let unknown = 0;
    for (const ev of all(doc, 'StopEvent')) {
      const call = el(ev, 'ThisCall/CallAtStop'), service = el(ev, 'Service');
      if (!call || !service) continue;
      if (txt(call, 'NotServicedStop') === 'true' || txt(service, 'Cancelled') === 'true') continue;
      const info = serviceInfo(service);
      const dep = callTimes(call, 'ServiceDeparture');
      if (!dep.planned) continue;
      const here = station(txt(call, 'StopPointRef'), txt(call, 'StopPointName'), places);
      const hereId = stopId7(txt(call, 'StopPointRef')) || stopId;
      const onward = kids(ev, 'OnwardCall').map(o => el(o, 'CallAtStop')).filter(Boolean);
      let passList;
      if (onward.length) {
        passList = onward.map(c => {
          const a = callTimes(c, 'ServiceArrival'), d = callTimes(c, 'ServiceDeparture');
          return { station: station(txt(c, 'StopPointRef'), txt(c, 'StopPointName'), places),
                   arrival: a.estimated || a.planned, departure: d.estimated || d.planned, _planned: a.planned || d.planned,
                   platform: txt(c, 'EstimatedQuay') || txt(c, 'PlannedQuay') || null };
        });
        // remembered with each stop's position: a light refresh can then still say where the next stops are (US-50)
        if (patterns) patterns.set(info.pattern, passList.filter(p => p.station.id !== hereId).slice(0, 8)
          .map(p => ({ id: p.station.id, name: p.station.name, offMin: p._planned ? minutesBetween(dep.planned, p._planned) : null,
                       c: p.station.coordinate && p.station.coordinate.x != null ? [p.station.coordinate.x, p.station.coordinate.y] : null,
                       q: p.platform || null })));
      } else {
        const known = patterns && patterns.get(info.pattern);
        if (!known) unknown++;
        const base = new Date(dep.estimated || dep.planned).getTime();
        passList = (known || []).map(p => ({ station: { id: p.id, name: p.name, coordinate: p.c ? { type: 'WGS84', x: p.c[0], y: p.c[1] } : null },
          arrival: p.offMin == null ? null : new Date(base + p.offMin * 60000).toISOString(), platform: p.q || null }));
      }
      board.push({
        category: info.category, number: info.number, name: info.name, operator: info.operator, operatorRef: info.operatorRef, to: info.to,
        stop: { station: { id: hereId, name: here.name }, departure: dep.planned,
                prognosis: { departure: dep.estimated, platform: txt(call, 'EstimatedQuay') || null },
                platform: txt(call, 'PlannedQuay') || null, delay: null },
        passList: [{ station: { id: hereId, name: here.name } }, ...passList]
      });
    }
    const st = places.get('ch:1:sloid:' + String(stopId).replace(/^85/, '').replace(/^0+/, '')) || {};
    return { station: { id: stopId, name: st.name || (board[0] && board[0].stop.station.name) || '', coordinate: st.coordinate || null },
             stationboard: board, unknownPatterns: unknown, error: errorCondition(doc) };
  }

  // ISO 8601 duration "PT1H2M30S" → "01:02:30"
  function durationHMS(d) {
    const m = String(d || '').match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?/);
    if (!m) return null;
    const p = n => String(Math.round(+n || 0)).padStart(2, '0');
    return `${p(m[1])}:${p(m[2])}:${p(m[3])}`;
  }

  // /connections
  function toConnections(xml) {
    const doc = parse(xml);
    const places = contextPlaces(doc);
    const connections = [];
    for (const tripEl of all(doc, 'Trip')) {
      const sections = [];
      for (const leg of kids(tripEl, 'Leg')) {
        const timed = el(leg, 'TimedLeg');
        if (timed) {
          const board = el(timed, 'LegBoard'), alight = el(timed, 'LegAlight'), service = el(timed, 'Service');
          const info = serviceInfo(service);
          const d = callTimes(board, 'ServiceDeparture'), a = callTimes(alight, 'ServiceArrival');
          const st = c => station(txt(c, 'StopPointRef'), txt(c, 'StopPointName'), places);
          const inter = kids(timed, 'LegIntermediate');
          sections.push({
            journey: { category: info.category, number: info.number, name: info.name, operator: info.operator, operatorRef: info.operatorRef, to: info.to,
                       // every stop of the ride with its times (planned, and live in prognosis), as in transport.opendata.ch
                       passList: [board, ...inter, alight].map(c => {
                         const ca = callTimes(c, 'ServiceArrival'), cd = callTimes(c, 'ServiceDeparture');
                         return { station: st(c), arrival: ca.planned, departure: cd.planned,
                                  prognosis: { arrival: ca.estimated, departure: cd.estimated } };
                       }) },
            departure: { station: st(board), departure: d.planned, prognosis: { departure: d.estimated, platform: txt(board, 'EstimatedQuay') || null },
                         platform: txt(board, 'PlannedQuay') || null, delay: null },
            arrival: { station: st(alight), arrival: a.planned, prognosis: { arrival: a.estimated, platform: txt(alight, 'EstimatedQuay') || null },
                       platform: txt(alight, 'PlannedQuay') || null }
          });
        } else {
          // TransferLeg (change on foot) or ContinuousLeg (walk to/from a place)
          const w = el(leg, 'TransferLeg') || el(leg, 'ContinuousLeg');
          if (!w) continue;
          const end = el(w, 'LegEnd'), start = el(w, 'LegStart');
          const ref = n => n ? (txt(n, 'StopPointRef') || txt(n, 'StopPlaceRef')) : '';
          sections.push({ journey: null, walk: { duration: durationHMS(txt(w, 'Duration') || txt(leg, 'Duration')) },
            departure: { station: station(ref(start), txt(start, 'Name'), places) },
            arrival: { station: station(ref(end), txt(end, 'Name'), places) } });
        }
      }
      if (sections.length) connections.push({ duration: txt(tripEl, 'Duration'), transfers: +txt(tripEl, 'Transfers') || 0, sections });
    }
    return { connections, error: errorCondition(doc) };
  }

  const api = { ENDPOINT, REQUESTOR, locationsByName, locationsInZone, stopEvents, trip,
                stopId7, splitTrainName, toLocations, toPlaces, toStationboard, toConnections, durationHMS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.OJP_ADAPTER = api;
})(typeof window !== 'undefined' ? window : globalThis);
