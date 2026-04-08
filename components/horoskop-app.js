// horoskop-app.js — root index.html runtime: button handlers, /reading
// fetch, render, share-card. Externalized from inline <script> so the
// strict CSP (`script-src 'self' https://unpkg.com`, no 'unsafe-inline')
// can serve it.
(function () {
  'use strict';

  const RAILWAY_BASE = "https://horoskopone-production-4739.up.railway.app";

  // Default mixer state — overridden by enhancements.js once the mixer mounts
  if (!window.__mixerState) {
    window.__mixerState = {
      mode: 'mystic_coach',
      timeframe: 'week',
      weights: { astro: 34, num: 13, tarot: 17, iching: 14, cn: 11, tree: 11 }
    };
  }

  function $(id) { return document.getElementById(id); }

  function bindClick(id, handler) {
    const el = $(id);
    if (el) el.addEventListener('click', handler);
  }

  // ----- Dialog "Geburtszeit finden?" ----------------------------------------
  bindClick('btn-timehelp', () => {
    const d = $('dlg-time');
    if (!d) return;
    d.showModal();
    // Focus the "Okay" button so Enter closes the dialog immediately.
    const okay = $('btn-dlg-okay');
    if (okay) okay.focus();
  });
  // The dialog's "Okay" button used to use inline onclick — bind it here so
  // CSP without 'unsafe-inline' can still close it. <dialog>'s native Escape
  // handling closes it too, so no extra key handler is needed.
  bindClick('btn-dlg-okay', () => { const d = $('dlg-time'); if (d) d.close(); });
  // Click on the backdrop closes the dialog.
  (function bindBackdropClose(){
    const d = $('dlg-time');
    if (!d) return;
    d.addEventListener('click', (e) => {
      if (e.target === d) d.close();
    });
  })();

  // ----- Heliocentric hero wheel ---------------------------------------------
  // Each <g class="planet-orbit orbit-X"> has its dot drawn at angle -90°
  // (12 o'clock). We compute the mean ecliptic longitude for every planet
  // from a simplified Kepler mean-motion model (J2000.0 epoch) and apply
  // it as a direct rotate() transform on the group. By default the wheel
  // shows TODAY's real sky and stays still. A small date input beneath the
  // hero lets the user pick any other day — e.g. their birthday — and the
  // planets smoothly glide to that configuration (CSS handles the tween).
  (function skyWheel() {
    // Simplified mean longitudes L0 (deg, J2000.0) and mean motions n (deg/day).
    // Values are standard osculating elements rounded for visual fidelity;
    // accurate to a few degrees, which is all the 380px hero needs.
    const PLANETS = [
      { name: 'mercury', L0: 252.25, n: 4.09233445, el: null },
      { name: 'venus',   L0: 181.98, n: 1.60213034, el: null },
      { name: 'earth',   L0: 100.46, n: 0.98560028, el: null },
      { name: 'mars',    L0: 355.43, n: 0.52402068, el: null },
      { name: 'jupiter', L0:  34.35, n: 0.08308529, el: null },
      { name: 'saturn',  L0:  50.08, n: 0.03344414, el: null },
      { name: 'uranus',  L0: 314.06, n: 0.01172834, el: null },
      { name: 'neptune', L0: 304.35, n: 0.00598103, el: null }
    ];
    for (const p of PLANETS) p.el = document.querySelector('.orbit-' + p.name);
    if (!PLANETS.some(p => p.el)) return; // no hero SVG on this page

    // Days since J2000.0 (2000-01-01 12:00 TT, close enough to UTC here).
    const J2000_MS = Date.UTC(2000, 0, 1, 12, 0, 0);

    function render(dateMs) {
      const daysSinceJ2000 = (dateMs - J2000_MS) / 86400000;
      for (const p of PLANETS) {
        if (!p.el) continue;
        const lon = (((p.L0 + p.n * daysSinceJ2000) % 360) + 360) % 360;
        // Dot sits at -90° (top). Ecliptic longitude 0° = 3 o'clock, so the
        // rotation that takes the dot from the top to longitude λ is λ+90°.
        const rot = (lon + 90) % 360;
        p.el.style.transform = 'rotate(' + rot.toFixed(2) + 'deg)';
      }
      const cap = document.getElementById('sky-date');
      if (cap) {
        const d = new Date(dateMs);
        cap.textContent = 'Himmel am ' + d.toLocaleDateString('de-DE', {
          day: '2-digit', month: 'long', year: 'numeric'
        });
      }
    }

    // Format a Date as YYYY-MM-DD in the LOCAL timezone (so "today" matches
    // the user's wall-clock day, not UTC).
    function toYmd(d) {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      return y + '-' + m + '-' + dd;
    }
    // Parse a YYYY-MM-DD string as noon UTC — noon avoids any timezone edge
    // where a local-midnight date would flip to the previous/next day and
    // makes the Kepler longitude deterministic for a whole calendar day.
    function parseYmd(s) {
      const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || '');
      if (!m) return null;
      return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12, 0, 0);
    }

    const input = $('sky-date-input');
    const btnToday = $('btn-sky-today');

    function currentSkyMs() {
      const parsed = input && input.value ? parseYmd(input.value) : null;
      if (parsed != null) return parsed;
      // Fallback: today at local noon → noon UTC of today's local date.
      return parseYmd(toYmd(new Date()));
    }

    if (input) {
      input.value = toYmd(new Date());
      input.addEventListener('input', () => render(currentSkyMs()));
      input.addEventListener('change', () => render(currentSkyMs()));
    }
    if (btnToday) {
      btnToday.addEventListener('click', () => {
        if (input) input.value = toYmd(new Date());
        render(currentSkyMs());
      });
    }

    render(currentSkyMs());
  })();

  // ----- Birthplace autocomplete (Nominatim) ---------------------------------
  // Live-search against OpenStreetMap Nominatim so users see whether their
  // place resolved BEFORE hitting "Sterne fragen", and we can stash the
  // lat/lon + canonical label straight into the request payload. Two-pass
  // strategy: DACH-countries first (typical for a German-language app),
  // then worldwide fallback if nothing comes back.
  (function birthplaceAutocomplete() {
    const input = $('birthPlace');
    const list  = $('place-suggest');
    const status = $('place-status');
    const latH = $('birthLat');
    const lonH = $('birthLon');
    if (!input || !list) return;

    const NOMINATIM = 'https://nominatim.openstreetmap.org/search';
    let debounceTimer = null;
    let lastQuery = '';
    let activeIdx = -1;
    let items = [];

    function setStatus(kind, text) {
      if (!status) return;
      status.className = 'place-status' + (kind ? ' ' + kind : '');
      status.textContent = text || '';
    }

    function closeList() {
      list.classList.remove('open');
      list.innerHTML = '';
      activeIdx = -1;
    }

    function renderList() {
      list.innerHTML = '';
      items.forEach((it, i) => {
        const row = document.createElement('div');
        row.className = 'ps-item' + (i === activeIdx ? ' active' : '');
        row.setAttribute('role', 'option');
        const main = document.createElement('span');
        main.textContent = it.display;
        row.appendChild(main);
        if (it.country) {
          const cc = document.createElement('span');
          cc.className = 'ps-country';
          cc.textContent = it.country;
          row.appendChild(cc);
        }
        row.addEventListener('mousedown', (e) => {
          e.preventDefault();
          choose(it);
        });
        list.appendChild(row);
      });
      list.classList.toggle('open', items.length > 0);
    }

    function choose(it) {
      input.value = it.display;
      if (latH) latH.value = String(it.lat);
      if (lonH) lonH.value = String(it.lon);
      setStatus('ok', '✓ Erkannt: ' + it.display + (it.country ? ' (' + it.country + ')' : ''));
      closeList();
    }

    async function queryNominatim(q, countryCodes) {
      const params = new URLSearchParams({
        format: 'jsonv2',
        limit: '6',
        addressdetails: '1',
        q: q
      });
      if (countryCodes) params.set('countrycodes', countryCodes);
      const url = NOMINATIM + '?' + params.toString();
      try {
        const r = await fetch(url, {
          headers: { 'Accept': 'application/json', 'Accept-Language': 'de,en' }
        });
        if (!r.ok) return [];
        const data = await r.json();
        return (data || []).map(row => ({
          display: row.display_name || row.name || q,
          lat: parseFloat(row.lat),
          lon: parseFloat(row.lon),
          country: ((row.address && row.address.country_code) || '').toUpperCase()
        })).filter(x => !isNaN(x.lat) && !isNaN(x.lon));
      } catch (e) {
        return [];
      }
    }

    async function search(q) {
      lastQuery = q;
      setStatus('', 'Suche …');
      let hits = await queryNominatim(q, 'de,at,ch');
      if (!hits.length) hits = await queryNominatim(q, '');
      if (q !== lastQuery) return; // stale response
      items = hits.slice(0, 6);
      if (!items.length) {
        setStatus('warn', 'Kein Treffer. Tipp: Land oder PLZ ergänzen, z. B. „Neustadt, Weinstraße" oder „10405 Berlin".');
        closeList();
        return;
      }
      setStatus('', items.length + ' Vorschläge');
      renderList();
    }

    input.addEventListener('input', () => {
      if (latH) latH.value = '';
      if (lonH) lonH.value = '';
      const q = input.value.trim();
      clearTimeout(debounceTimer);
      if (q.length < 3) { closeList(); setStatus('', ''); return; }
      debounceTimer = setTimeout(() => search(q), 280);
    });
    input.addEventListener('keydown', (e) => {
      if (!list.classList.contains('open')) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); activeIdx = Math.min(items.length - 1, activeIdx + 1); renderList(); }
      else if (e.key === 'ArrowUp')   { e.preventDefault(); activeIdx = Math.max(0, activeIdx - 1); renderList(); }
      else if (e.key === 'Enter' && activeIdx >= 0) { e.preventDefault(); choose(items[activeIdx]); }
      else if (e.key === 'Escape') { closeList(); }
    });
    input.addEventListener('blur', () => { setTimeout(closeList, 120); });
  })();

  // ----- "Heute" shortcut ----------------------------------------------------
  bindClick('btn-heute', () => {
    window.__mixerState.timeframe = 'day';
    const tf = $('timeFrame'); if (tf) tf.value = 'day';
    callReading();
    window.dispatchEvent(new CustomEvent('horoskop:set', { detail: { timeframe: 'day' } }));
  });

  // ----- Helpers --------------------------------------------------------------
  function chipTip(text) {
    const LEX = {
      "Sternzeichen": "Tierkreis aus Geburtsdatum – Grundstimmung.",
      "Lebenszahl": "Numerologie (Quersumme) – Lernfelder.",
      "Persönliches Jahr": "Rollierender 1–9-Zyklus aus Geburtsmonat + -tag + aktuellem Jahr.",
      "Zeitfenster": "Uhrzeit/Zeit-Bucket – prägt Tagesenergie.",
      "Ort": "Geburtsort → Zeitzone, Hemisphäre, Licht.",
      "Tag/Nacht": "Aus Sunrise/Sunset am Ort.",
      "Saison": "Meteorologische Jahreszeit der Hemisphäre.",
      "Mondphase": "Mondzyklus am Datum.",
      "I-Ging": "Hexagramm aus Datum – Grundlage der Deutung.",
      "Tarot": "Große Arkana, deterministisch aus Datum + Zeitraum gezogen.",
      "Chinesisch": "Chinesisches Tierkreiszeichen aus Geburtsjahr.",
      "Baumkreis": "Keltischer Baumkreis-Zyklus aus Datum.",
      "Sunrise/Sunset": "Auf-/Untergangszeiten vor Ort."
    };
    for (const k in LEX) { if (text.includes(k)) return LEX[k]; }
    return "Begründung";
  }

  function setEphemeris(meta) {
    const bar = $('ephemeris');
    if (!bar) return;
    bar.innerHTML = '';
    if (!meta) return;
    const mini = meta.mini || {};
    const geo = meta.geo || {};
    const chips = [];
    if (meta.birthPlace) chips.push([meta.birthPlace, 'Ort']);
    if (geo.tz) chips.push([geo.tz, 'Zeitzone']);
    if (meta.season) chips.push([meta.season + (meta.hemisphere ? ' (' + meta.hemisphere + ')' : ''), 'Saison']);
    if (mini.moonPhase) chips.push([mini.moonPhase, 'Mondphase']);
    if (mini.sunSignApprox) chips.push([mini.sunSignApprox, 'Sternzeichen']);
    if (mini.lifePath != null) chips.push(['Lebenszahl ' + mini.lifePath, 'Lebenszahl']);
    if (mini.personalYear != null) chips.push(['P-Jahr ' + mini.personalYear, 'Persönliches Jahr']);
    if (mini.iChingName) chips.push(['I-Ging: ' + mini.iChingName, 'I-Ging']);
    if (mini.tarot && mini.tarot.name) chips.push(['Tarot: ' + mini.tarot.name, 'Tarot']);
    if (mini.chinese) chips.push([mini.chinese, 'Chinesisch']);
    if (mini.tree) chips.push([mini.tree, 'Baumkreis']);
    chips.forEach(([t, label]) => {
      const el = document.createElement('span');
      el.className = 'chip';
      el.title = chipTip(label);
      el.textContent = t;
      bar.appendChild(el);
    });
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  // ----- Reveal-on-scroll (used by renderReadingUI) --------------------------
  const _obs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('show');
        _obs.unobserve(e.target);
      }
    });
  }, { threshold: 0.12 });
  function _reveal(el) { if (!el) return; el.classList.add('reveal'); _obs.observe(el); }

  // ----- Constellation separator ---------------------------------------------
  function makeSep(seed) {
    seed = String(seed || '').split('').reduce((a, c) => a + c.charCodeAt(0), 0)
      || Math.floor(Math.random() * 9999);
    function rand() { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; }
    const pts = [];
    const n = 6 + Math.floor(rand() * 3);
    for (let i = 0; i < n; i++) {
      const x = 40 + i * (520 / (n - 1)) + (rand() - 0.5) * 18;
      const y = 12 + rand() * 10;
      pts.push([Math.max(10, Math.min(590, x)), Math.max(6, Math.min(28, y))]);
    }
    const path = 'M ' + pts.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L ');
    const stars = pts.map(p =>
      `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${(1.3 + rand() * 1.7).toFixed(1)}" fill="url(#sg)"/>`
    ).join('');
    return `<div class="constellation" aria-hidden="true"><svg viewBox="0 0 600 34" preserveAspectRatio="none">
      <defs>
        <radialGradient id="sg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#e7ecff" stop-opacity="1"/>
          <stop offset="60%" stop-color="#bcd0ff" stop-opacity=".45"/>
          <stop offset="100%" stop-color="#000" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <path d="${path}" stroke="#2a3f79" stroke-opacity=".55" stroke-dasharray="2 5" fill="none" />
      ${stars}
    </svg></div>`;
  }

  // ----- Render reading -------------------------------------------------------
  function renderReadingUI(data) {
    const box = $('result');
    box.innerHTML = "";
    setEphemeris(data?.meta);

    if (data?.meta?.error) {
      const err = document.createElement('div');
      err.className = 'card';
      err.style.borderColor = '#6b2a2a';
      err.innerHTML = `<b>Es gab ein Problem bei der Berechnung:</b><div class="small">${escapeHtml(data.meta.error)}</div>`;
      box.appendChild(err);
    }

    const toneLabel = data?.meta?.toneLabel || data?.meta?.tone || '-';
    const period = data?.meta?.period || '-';
    const label = data?.meta?.readingLabel || data?.meta?.readingType || 'Reading';
    const seedKey = (data?.meta?.birthDate || '') + '|' + (data?.meta?.birthPlace || '') + '|' + period;
    const periodLabel = period === 'day' ? 'Heute' : period === 'week' ? 'Woche' : period === 'month' ? 'Monat' : period;
    const head = document.createElement('div');
    head.className = 'card';
    _reveal(head);
    // Show the mixer top-3 so the user sees the traditions that actually
    // shaped the reading.
    const mx = data?.meta?.activeMixer || {};
    const mxLabels = data?.meta?.mixerLabels || {};
    const mxEntries = Object.entries(mx)
      .filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([k, v]) => `${escapeHtml(mxLabels[k] || k)} ${v}%`);
    const mxLine = mxEntries.length
      ? `<div class="small" style="margin-top:4px">Mixer: ${mxEntries.join(' · ')}</div>`
      : '';
    head.innerHTML =
      `<div class="small">${escapeHtml(label)} · Ton: <b>${escapeHtml(toneLabel)}</b> · Zeitraum: <b>${escapeHtml(periodLabel)}</b></div>`
      + mxLine;
    box.appendChild(head);
    box.insertAdjacentHTML('beforeend', makeSep(seedKey));

    const sections = Array.isArray(data?.sections) ? data.sections : [];
    if (!sections.length) {
      const empty = document.createElement('div');
      empty.className = 'card';
      empty.textContent = 'Keine Sektionen erhalten.';
      box.appendChild(empty);
    }
    sections.forEach((s, i) => {
      const area = s?.title || (["Fokus", "Beruf", "Liebe", "Energie", "Soziales"][i % 5]);
      const det = document.createElement('details');
      det.open = true;
      _reveal(det);
      const summary = document.createElement('summary');
      summary.textContent = area;
      det.appendChild(summary);
      const inner = document.createElement('div');
      inner.style.padding = '0 14px 12px 14px';
      inner.innerHTML = `<div style='margin-bottom:6px'>${escapeHtml(s?.text || '')}</div>`;
      det.appendChild(inner);
      const why = document.createElement('div');
      why.className = 'row';
      (Array.isArray(s?.chips) ? s.chips : []).forEach(w => {
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.textContent = w;
        chip.title = chipTip(w);
        why.appendChild(chip);
      });
      det.appendChild(why);
      box.appendChild(det);
      box.insertAdjacentHTML('beforeend', makeSep(seedKey + ':' + i));
    });

    if (data?.disclaimer) {
      const dc = document.createElement('div');
      dc.className = 'disclaimer';
      dc.textContent = data.disclaimer;
      box.appendChild(dc);
    }
  }

  // ----- /reading call --------------------------------------------------------
  async function callReading() {
    const d = $('birthDate').value;
    const p = $('birthPlace').value.trim();
    const t = $('birthTime').value;
    const a = $('timeApprox').value || "";
    const tf = $('timeFrame').value;
    if (!d || !p) {
      $('result').textContent = 'Bitte Datum und Ort angeben.';
      return;
    }
    const mapDaypart = { morning: "morgens", noon: "mittags", evening: "abends", night: "nachts", "": "unbekannt" };
    const approx = mapDaypart[a] ?? "unbekannt";

    const m = window.__mixerState || {};
    const mixer = m.weights || null;
    const rtEl = $('readingType');
    const readingType = (rtEl && rtEl.value) ? rtEl.value : 'classic';

    // If the autocomplete resolved the birthplace, pass the coords straight
    // through so the backend skips its own Nominatim call.
    const latH = $('birthLat'), lonH = $('birthLon');
    const latV = latH && latH.value ? parseFloat(latH.value) : NaN;
    const lonV = lonH && lonH.value ? parseFloat(lonH.value) : NaN;
    const coords = (!isNaN(latV) && !isNaN(lonV)) ? { lat: latV, lon: lonV } : null;

    const payload = {
      birthDate: d,
      birthPlace: p,
      period: tf,
      approxDaypart: approx,
      readingType,
      ...(t && /^\d{1,2}:\d{2}$/.test(t) ? { birthTime: t } : {}),
      ...(mixer ? { mixer } : {}),
      ...(coords ? { coords } : {}),
      tone: (m && m.mode) ? m.mode : 'mystic_coach',
      ...(m && typeof m.seed !== 'undefined' ? { seed: m.seed } : {})
    };

    $('result').innerHTML = '<div class="card">Berechnung läuft – bitte warten (kann bis zu 60 s dauern) …</div>';

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 90000);
    try {
      const res = await fetch(RAILWAY_BASE.replace(/\/$/, '') + '/reading', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: ctrl.signal
      });
      if (!res.ok) {
        let errText = 'HTTP ' + res.status;
        try {
          const ej = await res.json();
          if (Array.isArray(ej?.detail)) {
            errText += ' – ' + ej.detail.map(d => (d.loc || []).join('.') + ': ' + d.msg).join(' | ');
          }
        } catch { /* ignore */ }
        throw new Error(errText);
      }
      const data = await res.json();
      renderReadingUI(data);
    } catch (e) {
      const msg = (e && e.name === 'AbortError')
        ? 'Zeitüberschreitung – bitte erneut versuchen.'
        : (e?.message || String(e));
      $('result').innerHTML = '<div class="card">Fehler: ' + escapeHtml(msg) + '</div>';
    } finally {
      clearTimeout(timer);
    }
  }

  bindClick('btn-gold', () => { callReading(); });

  // Stardust hover (updates CSS vars on brand buttons)
  document.addEventListener('mousemove', (e) => {
    document.querySelectorAll('.btn.brand').forEach(btn => {
      const rect = btn.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      btn.style.setProperty('--x', x + '%');
      btn.style.setProperty('--y', y + '%');
    });
  }, { passive: true });
})();
