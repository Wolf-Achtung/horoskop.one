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
  bindClick('btn-timehelp', () => { const d = $('dlg-time'); if (d) d.showModal(); });
  // The dialog's "Okay" button used to use inline onclick — bind it here so
  // CSP without 'unsafe-inline' can still close it.
  document.querySelectorAll('#dlg-time button').forEach(b => {
    if (/okay/i.test(b.textContent || '')) {
      b.addEventListener('click', () => { const d = $('dlg-time'); if (d) d.close(); });
    }
  });

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

  let __lastData = null;
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
    __lastData = data;
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

    const sr = $('shareRow'); if (sr) sr.style.display = 'flex';
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

    const payload = {
      birthDate: d,
      birthPlace: p,
      period: tf,
      approxDaypart: approx,
      readingType,
      ...(t && /^\d{1,2}:\d{2}$/.test(t) ? { birthTime: t } : {}),
      ...(mixer ? { mixer } : {}),
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

  // ----- Share-Card -----------------------------------------------------------
  function drawWrappedText(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
    const words = (text || '').split(' ');
    let line = '';
    const lines = [];
    for (let n = 0; n < words.length; n++) {
      const test = line + words[n] + ' ';
      const w = ctx.measureText(test).width;
      if (w > maxWidth && n > 0) {
        lines.push(line.trim());
        line = words[n] + ' ';
        if (lines.length >= maxLines) break;
      } else {
        line = test;
      }
    }
    if (lines.length < maxLines) lines.push(line.trim());
    lines.forEach((ln, i) => ctx.fillText(ln, x, y + i * lineHeight));
  }

  async function makeShareCard(data) {
    const tf = (data?.meta?.timeframe || '').toString();
    const moon = (data?.meta?.ephemeris?.moon_phase_name || '').toString();
    const place = (data?.meta?.profile?.place || '').toString();
    const c = document.createElement('canvas');
    c.width = 1200; c.height = 630;
    const ctx = c.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, 1200, 630);
    g.addColorStop(0, '#0b1020'); g.addColorStop(1, '#0f1630');
    ctx.fillStyle = g; ctx.fillRect(0, 0, 1200, 630);
    ctx.globalAlpha = 0.08; ctx.beginPath();
    for (let i = 0; i < 12; i++) {
      ctx.save();
      ctx.translate(600, 315);
      ctx.rotate((i / 12) * Math.PI * 2);
      ctx.arc(0, 0, 180, 0, Math.PI * 2);
      ctx.restore();
    }
    ctx.globalAlpha = 1.0;
    ctx.fillStyle = 'rgba(255,255,255,.25)';
    for (let i = 0; i < 180; i++) {
      const x = Math.random() * 1200, y = Math.random() * 630;
      ctx.fillRect(x, y, 1, 1);
    }
    ctx.fillStyle = '#e7ecff';
    ctx.font = '700 44px system-ui, Arial';
    ctx.fillText('horoskop.one', 56, 86);
    ctx.font = '16px system-ui, Arial';
    ctx.fillStyle = '#9fb2d9';
    ctx.fillText('Sternenkarte – achtsam, mystisch, erklärbar', 56, 110);
    ctx.font = '18px system-ui, Arial';
    ctx.fillStyle = '#a9c4ff';
    let cx = 56, cy = 140;
    function chip(txt) {
      const pad = 10;
      const w = ctx.measureText(txt).width + pad * 2;
      const h = 28;
      ctx.fillStyle = '#0d203f';
      ctx.strokeStyle = '#2a3f79';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(cx, cy, w, h, 14);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = '#bdd0ff';
      ctx.fillText(txt, cx + pad, cy + 20);
      cx += w + 10;
    }
    if (place) chip(place);
    if (tf) chip(tf === 'day' ? 'Heute' : tf === 'week' ? 'Woche' : 'Monat');
    if (moon) chip(moon);
    const hl = (data.highlights || []).slice(0, 3);
    ctx.fillStyle = '#e7ecff';
    ctx.font = '600 26px system-ui, Arial';
    ctx.fillText('Deine 3 Highlights', 56, 190);
    ctx.font = '20px system-ui, Arial';
    let y = 220;
    hl.forEach((h, i) => {
      ctx.fillStyle = '#a6b9e6';
      ctx.fillText(String(i + 1) + '.', 56, y);
      ctx.fillStyle = '#e7ecff';
      drawWrappedText(ctx, (h.title || '').toString(), 90, y, 1000, 26, 2);
      y += 56;
      ctx.fillStyle = '#9fb2d9';
      drawWrappedText(ctx, (h.action || '').toString(), 90, y - 6, 1000, 24, 1);
      y += 34;
    });
    ctx.fillStyle = '#7e96c9';
    ctx.font = '14px system-ui, Arial';
    ctx.fillText('Zeitraum: ' + (data?.meta?.timeframe || '-') + '  ·  Modus: ' + (data?.meta?.mode || '-'), 56, 600);
    return c;
  }

  bindClick('btn-share', async () => {
    if (!__lastData) { alert('Bitte zuerst ein Reading erzeugen.'); return; }
    const canvas = await makeShareCard(__lastData);
    canvas.toBlob((b) => {
      const url = URL.createObjectURL(b);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'horoskop-one-card.png';
      a.click();
      URL.revokeObjectURL(url);
    });
  });
})();
