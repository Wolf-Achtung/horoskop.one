/* enhancements.js — consolidated v14+v15+v16 layer + vanilla Kosmischer Mixer.
   Self-contained, no React, no Babel, no third-party CDN.
   Replaces enhancements-v14.js, enhancements-v15.js, enhancements-v16.js.

   Features:
   - Hero parallax (v14)
   - Star overlay canvas with intensity toggle (v15 + v16)
   - Zodiac glyph upgrade in chips (v14/v15)
   - Birth badges with zodiac, chinese, lifepath, celtic, i-ching (v15/v16)
   - Vanilla Kosmischer Mixer mounted into #mixer-root
*/
(function () {
  'use strict';

  // ----- Shared sprite loader -------------------------------------------------
  const _spriteCache = new Map();
  function loadSprite(url) {
    if (_spriteCache.has(url)) return _spriteCache.get(url);
    const p = fetch(url)
      .then(r => r.ok ? r.text() : '')
      .then(txt => {
        const map = {};
        if (!txt) return map;
        try {
          const doc = new DOMParser().parseFromString(txt, 'image/svg+xml');
          doc.querySelectorAll('symbol').forEach(sym => { map[sym.id] = sym.innerHTML; });
        } catch (e) { /* swallow */ }
        return map;
      })
      .catch(() => ({}));
    _spriteCache.set(url, p);
    return p;
  }
  const zMap = loadSprite('/assets/zodiac-glyphs.svg');
  const cMap = loadSprite('/assets/chinese-glyphs.svg');

  function inlineGlyph(mapPromise, id) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('width', '14');
    svg.setAttribute('height', '14');
    svg.style.opacity = '.9';
    svg.style.verticalAlign = '-2px';
    svg.style.marginRight = '6px';
    mapPromise.then(map => { svg.innerHTML = map[id] || ''; });
    return svg;
  }

  function tinyHex(n) {
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('width', '14');
    svg.setAttribute('height', '14');
    svg.classList.add('tiny-hex');
    const g = document.createElementNS(NS, 'g');
    svg.appendChild(g);
    for (let i = 0; i < 6; i++) {
      const y = 2 + i * 2;
      const yang = ((n >> i) & 1) === 1;
      if (yang) {
        const l = document.createElementNS(NS, 'line');
        l.setAttribute('x1', '1'); l.setAttribute('y1', y);
        l.setAttribute('x2', '13'); l.setAttribute('y2', y);
        g.appendChild(l);
      } else {
        const l1 = document.createElementNS(NS, 'line');
        l1.setAttribute('x1', '1'); l1.setAttribute('y1', y);
        l1.setAttribute('x2', '5'); l1.setAttribute('y2', y);
        g.appendChild(l1);
        const l2 = document.createElementNS(NS, 'line');
        l2.setAttribute('x1', '9'); l2.setAttribute('y1', y);
        l2.setAttribute('x2', '13'); l2.setAttribute('y2', y);
        g.appendChild(l2);
      }
    }
    svg.style.marginRight = '6px';
    svg.style.verticalAlign = '-2px';
    return svg;
  }

  // ----- Zodiac helpers -------------------------------------------------------
  const ZODIAC_IDS = [
    'aries','taurus','gemini','cancer','leo','virgo',
    'libra','scorpio','sagittarius','capricorn','aquarius','pisces'
  ];
  function glyphFor(text) {
    const t = (text || '').toLowerCase();
    if (t.includes('widder')) return 'aries';
    if (t.includes('stier')) return 'taurus';
    if (t.includes('zwilling')) return 'gemini';
    if (t.includes('krebs')) return 'cancer';
    if (t.includes('löwe') || t.includes('loewe')) return 'leo';
    if (t.includes('jungfrau')) return 'virgo';
    if (t.includes('waage')) return 'libra';
    if (t.includes('skorpion')) return 'scorpio';
    if (t.includes('schütze') || t.includes('schuetze')) return 'sagittarius';
    if (t.includes('steinbock')) return 'capricorn';
    if (t.includes('wassermann')) return 'aquarius';
    if (t.includes('fische')) return 'pisces';
    return null;
  }
  function shortLabel(text) {
    const m = (text || '').match(/(widder|stier|zwillinge?|krebs|l[öoe]+we|jungfrau|waage|skorpion|sch[üue]+tze|steinbock|wassermann|fische)/i);
    return m ? m[0].replace('oe', 'ö').replace('ue', 'ü') : text;
  }

  // ----- Chip upgrades --------------------------------------------------------
  function upgradeChips(root) {
    (root || document).querySelectorAll('.chip').forEach(ch => {
      if (ch.dataset.glyphdone) return;
      const id = glyphFor(ch.textContent || '');
      if (!id) return;
      const lab = shortLabel(ch.textContent || '');
      const svg = inlineGlyph(zMap, 'glyph-' + id);
      ch.textContent = '';
      ch.appendChild(svg);
      ch.appendChild(document.createTextNode(lab));
      ch.dataset.glyphdone = '1';
    });
  }

  // ----- Birth-date helpers ---------------------------------------------------
  function parseBirthDate(str) {
    if (!str) return null;
    let m = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);     // ISO from <input type=date>
    if (m) { const d = new Date(+m[1], +m[2] - 1, +m[3]); return isNaN(d) ? null : d; }
    m = str.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);        // German DD.MM.YYYY
    if (m) { const d = new Date(+m[3], +m[2] - 1, +m[1]); return isNaN(d) ? null : d; }
    return null;
  }
  function zodiacFromDate(d) {
    const m = d.getMonth() + 1, day = d.getDate();
    const edges = [
      ['capricorn', 1, 19], ['aquarius', 2, 18], ['pisces', 3, 20],
      ['aries', 4, 19], ['taurus', 5, 20], ['gemini', 6, 20],
      ['cancer', 7, 22], ['leo', 8, 22], ['virgo', 9, 22],
      ['libra', 10, 22], ['scorpio', 11, 21], ['sagittarius', 12, 21],
      ['capricorn', 12, 31]
    ];
    let id = 'capricorn';
    for (const [n, mm, dd] of edges) {
      if ((m < mm) || (m === mm && day <= dd)) { id = n; break; }
    }
    const labels = { aries: 'Widder', taurus: 'Stier', gemini: 'Zwillinge', cancer: 'Krebs', leo: 'Löwe', virgo: 'Jungfrau', libra: 'Waage', scorpio: 'Skorpion', sagittarius: 'Schütze', capricorn: 'Steinbock', aquarius: 'Wassermann', pisces: 'Fische' };
    const desc = { aries: 'Pioniergeist und Aufbruch.', taurus: 'Beständigkeit und Genuss.', gemini: 'Neugier und Austausch.', cancer: 'Zuwendung und Schutz.', leo: 'Ausstrahlung und Herz.', virgo: 'Präzision und Dienst.', libra: 'Harmonie und Maß.', scorpio: 'Tiefe und Wandlung.', sagittarius: 'Weite und Sinn.', capricorn: 'Disziplin und Ziel.', aquarius: 'Freiheit und Ideen.', pisces: 'Einfühlung und Träume.' };
    return { kind: 'zodiac', id, label: labels[id], desc: desc[id] };
  }
  function chineseFromYear(y) {
    const animals = ['Ratte','Büffel','Tiger','Hase','Drache','Schlange','Pferd','Ziege','Affe','Hahn','Hund','Schwein'];
    const ids = ['ratte','bueffel','tiger','hase','drache','schlange','pferd','ziege','affe','hahn','hund','schwein'];
    const idx = ((y - 1900) % 12 + 12) % 12;
    const desc = { Ratte: 'gewandt, wachsam', Büffel: 'ruhig, verlässlich', Tiger: 'mutig, impulsiv', Hase: 'feinfühlig, verbindend', Drache: 'kraftvoll, visionär', Schlange: 'intuitiv, still', Pferd: 'lebendig, unabhängig', Ziege: 'sanft, ästhetisch', Affe: 'pfiffig, erfinderisch', Hahn: 'klar, direkt', Hund: 'loyal, schützend', Schwein: 'offen, großzügig' };
    return { kind: 'cn', id: ids[idx], label: animals[idx], desc: desc[animals[idx]] };
  }
  function lifePathFromDate(d) {
    const s = '' + d.getFullYear() + String(d.getMonth() + 1).padStart(2, '0') + String(d.getDate()).padStart(2, '0');
    let sum = s.split('').reduce((a, b) => a + +b, 0);
    const master = [11, 22, 33];
    while (sum > 9 && !master.includes(sum)) {
      sum = String(sum).split('').reduce((a, b) => a + +b, 0);
    }
    const desc = { 1: 'Initiative', 2: 'Team & Takt', 3: 'Ausdruck', 4: 'Struktur', 5: 'Wandel', 6: 'Fürsorge', 7: 'Tiefe', 8: 'Wirksamkeit', 9: 'Weite', 11: 'Inspiration', 22: 'Baukunst', 33: 'Herzführung' };
    return { kind: 'num', id: 'num' + sum, label: 'Lebenszahl ' + sum, desc: desc[sum] || '' };
  }
  function celticTree(d) {
    const ranges = [
      ['Birke', 12, 24, 1, 20], ['Eberesche', 1, 21, 2, 17], ['Esche', 2, 18, 3, 17],
      ['Erle', 3, 18, 4, 14], ['Weide', 4, 15, 5, 12], ['Weißdorn', 5, 13, 6, 9],
      ['Eiche', 6, 10, 7, 7], ['Stechpalme', 7, 8, 8, 4], ['Hasel', 8, 5, 9, 1],
      ['Weinrebe', 9, 2, 9, 29], ['Efeu', 9, 30, 10, 27], ['Schilfrohr', 10, 28, 11, 24],
      ['Holunder', 11, 25, 12, 23]
    ];
    const y = d.getFullYear();
    const md = (m, dd) => new Date(y, m - 1, dd);
    let name = 'Birke';
    for (const [n, m1, d1, m2, d2] of ranges) {
      const s = md(m1, d1), e = md(m2, d2);
      const inside = s <= e ? (d >= s && d <= e) : (d >= s || d <= e);
      if (inside) { name = n; break; }
    }
    const desc = { Birke: 'Neuanfang', Eberesche: 'Inspiration', Esche: 'Wandlung', Erle: 'Mut', Weide: 'Gefühl', Weißdorn: 'Grenze', Eiche: 'Kraft', Stechpalme: 'Würde', Hasel: 'Weisheit', Weinrebe: 'Reife', Efeu: 'Beständigkeit', Schilfrohr: 'Wort & Wind', Holunder: 'Wandeln' };
    return { kind: 'tree', id: 'tree', label: name, desc: desc[name] || '' };
  }
  function ichingFromDate(d) {
    const start = new Date(d.getFullYear(), 0, 0);
    const day = Math.floor((d - start) / 86400000);
    const idx = (day + d.getFullYear()) % 64 || 1;
    const names = { 1: 'Das Schöpferische', 2: 'Das Empfangende', 3: 'Anfangsschwierigkeit', 4: 'Jugendtorheit', 11: 'Frieden', 12: 'Stockung', 24: 'Wiederkehr', 61: 'Innere Wahrheit' };
    return { kind: 'hex', id: idx, label: 'I Ging ' + idx, desc: names[idx] || 'Bewegung im Wandel' };
  }

  // ----- Birth badges renderer -----------------------------------------------
  function ensureBadgeRow() {
    let row = document.getElementById('birthBadges');
    if (!row) {
      row = document.createElement('div');
      row.id = 'birthBadges';
      row.className = 'badge-row';
      row.style.display = 'none';
      const hero = document.querySelector('.hero');
      if (hero && hero.parentNode) hero.parentNode.insertBefore(row, hero);
      else document.body.insertBefore(row, document.body.firstChild);
    }
    return row;
  }
  function renderBirthBadges(dateStr) {
    const d = parseBirthDate(dateStr);
    const row = ensureBadgeRow();
    if (!d) { row.style.display = 'none'; row.innerHTML = ''; return; }
    row.style.display = 'flex';
    row.innerHTML = '';
    const items = [
      zodiacFromDate(d),
      chineseFromYear(d.getFullYear()),
      lifePathFromDate(d),
      celticTree(d),
      ichingFromDate(d)
    ];
    items.forEach(it => {
      const el = document.createElement('span');
      el.className = 'badge';
      if (it.kind === 'zodiac') el.appendChild(inlineGlyph(zMap, 'glyph-' + it.id));
      else if (it.kind === 'cn') el.appendChild(inlineGlyph(cMap, 'cn-' + it.id));
      else if (it.kind === 'hex') el.appendChild(tinyHex(Number(it.id) || 1));
      else {
        const dot = document.createElement('span');
        dot.textContent = '•';
        dot.style.marginRight = '6px';
        dot.style.opacity = '.7';
        el.appendChild(dot);
      }
      el.appendChild(document.createTextNode(it.label));
      const desc = document.createElement('span');
      desc.className = 'desc';
      desc.textContent = ' – ' + it.desc;
      el.appendChild(desc);
      row.appendChild(el);
    });
  }

  // ----- Star overlay (v15) + intensity toggle (v16) -------------------------
  function startStarOverlay() {
    const cvs = document.createElement('canvas');
    cvs.id = 'starOverlay';
    Object.assign(cvs.style, { position: 'fixed', inset: '0', zIndex: '0', pointerEvents: 'none' });
    document.body.appendChild(cvs);
    const ctx = cvs.getContext('2d');
    const DPR = Math.min(2, window.devicePixelRatio || 1);
    let W = 0, H = 0, scrollY = 0, mouseX = 0, mouseY = 0;
    function resize() {
      W = cvs.width = innerWidth * DPR;
      H = cvs.height = innerHeight * DPR;
      cvs.style.transform = `scale(${1 / DPR})`;
      cvs.style.transformOrigin = '0 0';
    }
    addEventListener('resize', resize, { passive: true });
    resize();
    addEventListener('scroll', () => { scrollY = window.scrollY || 0; }, { passive: true });
    addEventListener('mousemove', (e) => {
      mouseX = (e.clientX / innerWidth - 0.5);
      mouseY = (e.clientY / innerHeight - 0.5);
    }, { passive: true });
    const stars = Array.from({ length: 200 }, () => ({
      x: Math.random(), y: Math.random(),
      r: 0.8 + Math.random() * 1.6,
      p: Math.random() * 6.28,
      d: 1 + Math.random()
    }));
    if (typeof window.INTENS !== 'number') window.INTENS = 1.0;
    (function draw(t) {
      ctx.clearRect(0, 0, W, H);
      ctx.globalCompositeOperation = 'lighter';
      const intens = window.INTENS;
      const parY = (scrollY * 0.12) * DPR;
      const parX = (scrollY * 0.05) * DPR;
      const tiltX = mouseX * 10 * DPR;
      const tiltY = mouseY * 8 * DPR;
      for (const s of stars) {
        const tw = (Math.sin(t * 0.002 + s.p) * 0.5 + 0.5) * 1.3 + 0.4;
        const driftX = Math.sin(t * 0.0001 + s.p) * s.d * 16;
        const driftY = Math.cos(t * 0.00009 + s.p) * s.d * 12;
        const x = s.x * W + driftX + parX * (0.3 + s.d * 0.2) + tiltX;
        const y = s.y * H + driftY + parY * (0.35 + s.d * 0.25) + tiltY;
        const rad = s.r * DPR * (1.0 + tw) * intens;
        const g = ctx.createRadialGradient(x, y, 0, x, y, rad);
        g.addColorStop(0, `rgba(250,255,255,${intens})`);
        g.addColorStop(0.5, `rgba(190,220,255,${0.6 * intens})`);
        g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(x, y, rad, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalCompositeOperation = 'source-over';
      requestAnimationFrame(draw);
    })(performance.now());
  }

  function ensureSkyToggle() {
    if (document.getElementById('skyToggleVisible')) return;
    const btn = document.createElement('button');
    btn.id = 'skyToggleVisible';
    btn.type = 'button';
    btn.className = 'btn small ghost';
    btn.style.cssText = 'position:absolute;right:10px;top:6px;z-index:5;opacity:.85;font-size:12px;padding:4px 10px';
    btn.textContent = 'Himmel: kräftig';
    const container = document.querySelector('.hero') || document.body;
    if (container !== document.body) container.style.position = 'relative';
    container.appendChild(btn);
    let strong = true;
    btn.addEventListener('click', () => {
      strong = !strong;
      window.INTENS = strong ? 1.0 : 0.5;
      btn.textContent = strong ? 'Himmel: kräftig' : 'Himmel: dezent';
    });
  }

  // ----- Hero parallax (v14) --------------------------------------------------
  function ensureHeroParallax() {
    const hero = document.querySelector('.hero');
    if (!hero) return;
    const img = hero.querySelector('img');
    if (!img) return;
    if (hero.querySelector('#heroWrap')) return;
    const wrap = document.createElement('div');
    wrap.id = 'heroWrap';
    wrap.className = 'hero-wrap';
    img.replaceWith(wrap);
    wrap.appendChild(img);
    const max = 3;
    function onScroll() {
      const y = Math.max(0, window.scrollY || 0);
      wrap.style.transform = `translateY(${Math.min(max, y * 0.03)}px)`;
    }
    addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // ----- Kosmischer Mixer (vanilla) ------------------------------------------
  const METHODS = [
    { key: 'astro',  label: 'Astrologie / Transite', color: '#9bb4ff' },
    { key: 'num',    label: 'Numerologie',           color: '#61dafb' },
    { key: 'tarot',  label: 'Tarot',                 color: '#ffd48a' },
    { key: 'iching', label: 'I-Ging',                color: '#8ef3ff' },
    { key: 'cn',     label: 'Chinesisch',            color: '#a5f59b' },
    { key: 'tree',   label: 'Baumkreis',             color: '#b3e1ff' }
  ];
  const PRESETS = {
    Balance:  { astro: 34, num: 13, tarot: 17, iching: 14, cn: 11, tree: 11 },
    Rational: { astro: 55, num: 20, tarot:  8, iching:  7, cn:  5, tree:  5 },
    Mystisch: { astro: 35, num: 10, tarot: 25, iching: 15, cn:  8, tree:  7 }
  };
  const MODES = [
    { key: 'mystic_coach', label: 'Mystic Coach' },
    { key: 'mystic',       label: 'Mystisch' },
    { key: 'coach',        label: 'Coach' },
    { key: 'skeptic',      label: 'Skeptisch' }
  ];
  const TIMEFRAMES = [
    { key: 'day',   label: 'Heute' },
    { key: 'week',  label: 'Woche' },
    { key: 'month', label: 'Monat' }
  ];
  const clamp = (n, lo = 0, hi = 100) => Math.max(lo, Math.min(hi, n));
  const round2 = (n) => Math.round(n * 100) / 100;
  const sumValues = (o) => Object.values(o).reduce((a, b) => a + b, 0);

  function rebalance(prev, key, val) {
    const next = { ...prev, [key]: clamp(val) };
    const others = Object.keys(next).filter(k => k !== key);
    const rest = 100 - next[key];
    const sumOthers = others.reduce((a, k) => a + (prev[k] || 0), 0);
    if (sumOthers <= 0) {
      const even = rest / others.length;
      others.forEach(k => { next[k] = even; });
      return next;
    }
    others.forEach(k => { next[k] = rest * (prev[k] / sumOthers); });
    return next;
  }
  function toGradient(weights) {
    let acc = 0;
    const stops = [];
    METHODS.forEach(({ key, color }) => {
      const pct = clamp(weights[key] || 0);
      if (pct <= 0) return;
      stops.push(`${color} ${acc}% ${acc + pct}%`);
      acc += pct;
    });
    if (!stops.length) stops.push('#e5e7eb 0% 100%');
    return `conic-gradient(${stops.join(', ')})`;
  }

  function mountMixer(root) {
    if (!root) return;
    if (root.dataset.mounted) return;
    root.dataset.mounted = '1';

    const state = {
      mode: 'mystic_coach',
      timeframe: 'week',
      weights: { ...PRESETS.Balance }
    };
    // Sync external pre-existing state if present
    const ext = window.__mixerState;
    if (ext && typeof ext === 'object') {
      if (ext.mode) state.mode = ext.mode;
      if (ext.timeframe) state.timeframe = ext.timeframe;
      if (ext.weights) state.weights = { ...state.weights, ...ext.weights };
    }

    const card = document.createElement('div');
    card.className = 'mixer-card';

    const head = document.createElement('div');
    head.className = 'mixer-head';
    head.innerHTML = '<h3>Kosmischer Mixer<sup>™</sup></h3>';
    const presets = document.createElement('div');
    presets.className = 'mixer-presets';
    Object.keys(PRESETS).forEach(name => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = name;
      b.addEventListener('click', () => setPreset(name));
      presets.appendChild(b);
    });
    const reset = document.createElement('button');
    reset.type = 'button';
    reset.textContent = 'Zurücksetzen';
    reset.addEventListener('click', () => setPreset('Balance'));
    presets.appendChild(reset);
    head.appendChild(presets);
    card.appendChild(head);

    const segs = document.createElement('div');
    segs.className = 'mixer-segs';
    segs.appendChild(buildSegmented('Ton', MODES, () => state.mode, (v) => { state.mode = v; render(); emit(); }));
    segs.appendChild(buildSegmented('Zeitraum', TIMEFRAMES, () => state.timeframe, (v) => { state.timeframe = v; render(); emit(); }));
    card.appendChild(segs);

    const body = document.createElement('div');
    body.className = 'mixer-body';
    const donut = document.createElement('div');
    donut.className = 'mixer-donut';
    body.appendChild(donut);
    const list = document.createElement('div');
    list.className = 'mixer-list';
    body.appendChild(list);
    card.appendChild(body);

    const foot = document.createElement('div');
    foot.className = 'mixer-foot';
    card.appendChild(foot);

    root.appendChild(card);

    function buildSegmented(label, options, getter, setter) {
      const wrap = document.createElement('div');
      const lab = document.createElement('div');
      lab.className = 'mixer-seg-label';
      lab.textContent = label;
      wrap.appendChild(lab);
      const seg = document.createElement('div');
      seg.className = 'mixer-seg';
      options.forEach(o => {
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = o.label;
        b.dataset.key = o.key;
        b.addEventListener('click', () => setter(o.key));
        seg.appendChild(b);
      });
      wrap.appendChild(seg);
      wrap._refresh = () => {
        seg.querySelectorAll('button').forEach(b => {
          b.setAttribute('aria-pressed', String(b.dataset.key === getter()));
        });
      };
      wrap._refresh();
      return wrap;
    }

    function setPreset(name) {
      const preset = PRESETS[name];
      if (!preset) return;
      const next = { ...preset };
      const s = sumValues(next);
      const factor = s > 0 ? 100 / s : 0;
      Object.keys(next).forEach(k => { next[k] = round2(next[k] * factor); });
      state.weights = next;
      render(); emit();
    }

    function onSlider(key, val) {
      state.weights = rebalance(state.weights, key, +val);
      render(); emit();
    }

    function render() {
      donut.style.background = toGradient(state.weights);
      list.innerHTML = '';
      METHODS.forEach(m => {
        const row = document.createElement('div');
        row.className = 'mixer-row';
        const sw = document.createElement('span');
        sw.className = 'swatch';
        sw.style.background = m.color;
        const lab = document.createElement('span');
        lab.className = 'label';
        lab.textContent = m.label;
        const slider = document.createElement('input');
        slider.type = 'range';
        slider.min = '0';
        slider.max = '100';
        slider.step = '1';
        slider.value = String(Math.round(state.weights[m.key] || 0));
        slider.addEventListener('input', (e) => onSlider(m.key, e.target.value));
        const pct = document.createElement('span');
        pct.className = 'pct';
        pct.textContent = round2(state.weights[m.key] || 0).toFixed(2) + '%';
        row.appendChild(sw);
        row.appendChild(lab);
        row.appendChild(slider);
        row.appendChild(pct);
        list.appendChild(row);
      });
      const total = round2(sumValues(state.weights));
      foot.innerHTML = `Summe: <b>${total.toFixed(2)}%</b> · bleibt automatisch bei 100%`;
      segs.querySelectorAll('div').forEach(el => { if (el._refresh) el._refresh(); });
    }

    function emit() {
      const detail = {
        mode: state.mode,
        timeframe: state.timeframe,
        weights: Object.fromEntries(METHODS.map(m => [m.key, round2(state.weights[m.key])]))
      };
      window.__mixerState = detail;
      window.dispatchEvent(new CustomEvent('horoskop:mixer', { detail }));
    }

    window.addEventListener('horoskop:set', (e) => {
      const d = e.detail || {};
      if (d.mode) state.mode = d.mode;
      if (d.timeframe) state.timeframe = d.timeframe;
      if (d.weights) state.weights = { ...state.weights, ...d.weights };
      render(); emit();
    });

    render();
    emit();
  }

  // ----- Init -----------------------------------------------------------------
  function init() {
    // Ensure global mixer state container exists
    if (!window.__mixerState) {
      window.__mixerState = {
        mode: 'mystic_coach',
        timeframe: 'week',
        weights: { ...PRESETS.Balance }
      };
    }

    upgradeChips(document.body);
    const mo = new MutationObserver(muts => muts.forEach(m => upgradeChips(m.target)));
    mo.observe(document.documentElement, { subtree: true, childList: true });

    ensureHeroParallax();
    startStarOverlay();
    ensureSkyToggle();

    const bd = document.getElementById('birthDate');
    if (bd) {
      bd.addEventListener('input', (e) => renderBirthBadges(e.target.value));
      if (bd.value) renderBirthBadges(bd.value);
    }

    mountMixer(document.getElementById('mixer-root'));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
