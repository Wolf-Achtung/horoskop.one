
/**
 * HOROSKOP.ONE — Gold Standard Frontend
 * - esbuild bundled (no inline JS)
 * - CSP friendly
 * - Nominatim autocomplete with throttle
 * - Share-Card PNG (1200×630)
 * - Seeded permalinks, Skeptical/Poetic/Trailer modes
 */

import { attachAutocomplete } from './geocode';
import { fetchReading } from './readingApi';
import { renderShareCardPNG } from './sharecard';
import { drawZodiacWheel } from './zodiac';

const byId = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;

function isoToGerman(input: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(input)) return input;
  const [y,m,d] = input.split('-');
  return `${d}.${m}.${y}`;
}

function approxMap(v: string): string {
  const map: Record<string,string> = { morning:'morgens', noon:'mittags', evening:'abends', night:'nachts', '':'unbekannt' };
  return map[v] ?? 'unbekannt';
}

function setStatus(msg: string) {
  const el = byId('status');
  el.textContent = msg;
}

function setDebug(obj: unknown) {
  const box = byId<HTMLDetailsElement>('debug');
  const pre = byId<HTMLPreElement>('debugPre');
  box.hidden = false;
  pre.textContent = JSON.stringify(obj, null, 2);
}

function readForm() {
  const dRaw = (byId<HTMLInputElement>('birthDate').value || '').trim();
  const p = (byId<HTMLInputElement>('birthPlace').value || '').trim();
  const lat = (byId<HTMLInputElement>('birthLat').value || '').trim();
  const lon = (byId<HTMLInputElement>('birthLon').value || '').trim();
  const t = (byId<HTMLInputElement>('birthTime').value || '').trim();
  const a = (byId<HTMLSelectElement>('timeApprox').value || '').trim();
  const tf = (byId<HTMLSelectElement>('timeFrame').value || 'week').trim();
  const mode = (byId<HTMLSelectElement>('mode').value || 'balanced').trim();
  if (!dRaw || !p) throw new Error('Bitte Datum und Ort angeben.');
  const birthDate = /^\d{4}-\d{2}-\d{2}$/.test(dRaw) ? isoToGerman(dRaw) : dRaw;
  const payload: any = {
    birthDate, birthPlace: p, period: tf, approxDaypart: approxMap(a), mode
  };
  if (t && /^\d{1,2}:\d{2}$/.test(t)) payload.birthTime = t;
  if (lat && lon) payload.coords = { lat: Number(lat), lon: Number(lon) };
  // seed from URL or deterministic from date+place
  const url = new URL(location.href);
  const qsSeed = url.searchParams.get('seed');
  payload.seed = qsSeed ? Number(qsSeed) : stableSeed(birthDate + '|' + p);
  return payload;
}

function stableSeed(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i=0;i<s.length;i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

function permalinkFromForm() {
  const d = byId<HTMLInputElement>('birthDate').value;
  const p = byId<HTMLInputElement>('birthPlace').value;
  const t = byId<HTMLInputElement>('birthTime').value;
  const a = byId<HTMLSelectElement>('timeApprox').value;
  const tf = byId<HTMLSelectElement>('timeFrame').value;
  const lat = byId<HTMLInputElement>('birthLat').value;
  const lon = byId<HTMLInputElement>('birthLon').value;
  const mode = byId<HTMLSelectElement>('mode').value;
  const seed = stableSeed((d||'') + '|' + (p||''));
  const u = new URL(location.href);
  u.searchParams.set('d', d);
  u.searchParams.set('p', p);
  if (t) u.searchParams.set('t', t);
  if (a) u.searchParams.set('a', a);
  if (tf) u.searchParams.set('tf', tf);
  if (lat && lon) { u.searchParams.set('lat', lat); u.searchParams.set('lon', lon); }
  u.searchParams.set('mode', mode);
  u.searchParams.set('seed', String(seed));
  byId<HTMLAnchorElement>('permalink').href = u.toString();
}

async function onSubmit(ev: Event) {
  ev.preventDefault();
  try {
    setStatus('⏳ Berechnung läuft …');
    const payload = readForm();
    const data = await fetchReading(payload);
    setStatus('✓ Fertig');
    renderReading(data);
    byId('shareCardPreview').hidden = false;
    await drawShareCardFromReading(data);
    permalinkFromForm();
  } catch (e:any) {
    setStatus('Fehler: ' + (e?.message ?? String(e)));
    setDebug(e);
  }
}

function renderReading(data: any) {
  const out = byId('readingOut');
  out.innerHTML = '';
  const make = (title: string, text: string) => {
    const b = document.createElement('div');
    b.className = 'reading-block';
    b.innerHTML = `<strong>${title}</strong><div class="autocomplete-muted">${text}</div>`;
    out.appendChild(b);
  };
  // Try to unpack common fields, otherwise render JSON
  if (data?.summary) make('Zusammenfassung', data.summary);
  if (data?.highlights && Array.isArray(data.highlights)) {
    make('Highlights', data.highlights.map((s:string)=>'• '+s).join('<br>'));
  }
  if (data?.sections && Array.isArray(data.sections)) {
    for (const s of data.sections) make(s.title || 'Abschnitt', s.text || '');
  }
  if (!out.children.length) {
    make('Antwort', typeof data === 'string' ? data : JSON.stringify(data));
  }
}

async function drawShareCardFromReading(data: any) {
  const canvas = byId<HTMLCanvasElement>('shareCanvas');
  const d = byId<HTMLInputElement>('birthDate').value;
  const p = byId<HTMLInputElement>('birthPlace').value;
  const tf = byId<HTMLSelectElement>('timeFrame').value;
  const title = 'Dein Moment unter den Sternen';
  const highlights = (data?.highlights && Array.isArray(data.highlights))
    ? data.highlights.slice(0,3)
    : (data?.sections ? data.sections.slice(0,3).map((s:any)=>s.title || 'Impulse') : []);
  const png = await renderShareCardPNG(canvas, { title, subtitle: `${p} · ${d} · ${tf}`, bullets: highlights });
  const a = byId<HTMLAnchorElement>('btnDownload');
  a.href = png;
  a.hidden = false;
}

function attachEvents() {
  byId('astro-form').addEventListener('submit', onSubmit);
  byId('btnShare').addEventListener('click', async () => {
    byId('shareCardPreview').hidden = false;
    await drawShareCardFromReading({ highlights: ['Atem holen. Fokus finden.', 'Kleiner mutiger Schritt.', 'Heute freundlich zu dir sein.'] });
  });
}

function hydrateFromURL() {
  const url = new URL(location.href);
  const map: Record<string, string> = { d:'birthDate', p:'birthPlace', t:'birthTime', a:'timeApprox', tf:'timeFrame', mode:'mode', lat:'birthLat', lon:'birthLon' };
  for (const [q, id] of Object.entries(map)) {
    const v = url.searchParams.get(q);
    if (v) (byId(id) as HTMLInputElement|HTMLSelectElement).value = v;
  }
  permalinkFromForm();
}

function init() {
  drawZodiacWheel(byId('zodiac-canvas') as HTMLCanvasElement);
  attachAutocomplete({
    input: byId<HTMLInputElement>('birthPlace'),
    menu: byId('place-suggest'),
    onPick(place) {
      byId<HTMLInputElement>('birthPlace').value = place.label;
      byId<HTMLInputElement>('birthLat').value = String(place.lat ?? '');
      byId<HTMLInputElement>('birthLon').value = String(place.lon ?? '');
      permalinkFromForm();
    }
  });
  attachEvents();
  hydrateFromURL();
}

document.addEventListener('DOMContentLoaded', init);
