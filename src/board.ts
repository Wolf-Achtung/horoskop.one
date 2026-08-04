// Das Monatsbrett — Spiel-Frontend (Phase 1.2, docs/spielkonzept.md)
// Zustand liegt im LocalStorage; alles Orakelhafte kommt deterministisch vom
// Server. LLM-/Nutzertexte werden ausschließlich per textContent gerendert.
//
// v1.2: Wurf als Ritual (Stab-Animation nach Klick), Brett mit sichtbarem
// Serpentinen-Pfad, vergangene Tage getönt, Steindock statt Textlegende,
// Steinsymbole statt Buchstaben.

type Positions = Record<string, number>;
type Chapter = { day: number; stone: string; to: number; text: string;
                 chips: string[]; fieldName?: string };
type Profile = { birthDate: string; birthPlace?: string; birthTime?: string };
type Gespuer = { boardId: string; guessed: number; right: number };
type Resonanz = { date: string; partnerDate: string; text: string; chips: string[] };
type Person = { name: string; date: string; profil?: ProfilBlock[]; lastReading?: Resonanz };
type Wochenlesung = { week: string; text: string; chips: string[] };
type BoardState = {
  boardId: string; positions: Positions; lastPlayedDay: number;
  profile: Profile | null; chapters: Chapter[];
  album?: number[];      // je entdecktes Feld (1–30), überdauert Monatsbretter
  gespuer?: Gespuer;     // Vorahnungs-Zähler, resettet mit jedem neuen Brett
  resonanz?: Resonanz;   // Alt-Feld (v1) — wird zu people[0] migriert
  profil?: ProfilData;   // Profil-Karte, gecacht pro Geburtsdatum
  people?: Person[];     // „Deine Menschen": gespeicherte Resonanz-Personen
  wochenlesung?: Wochenlesung;  // Sonntagsbogen, gecacht pro Kalenderwoche
};
type ProfilBlock = { key: string; title: string; text: string };
type ProfilData = { birthDate: string; blocks: ProfilBlock[]; link?: string };
type FieldCard = { index: number; name: string; core: string };
type StarTwin = { name: string; year: number; known: string };
type BoardEvent = { key: string; symbol: string; name: string; text: string };
type ThrowData = {
  throw: number; legalMoves: Record<string, number>;
  event: BoardEvent | null;
  alt?: { throw: number; legalMoves: Record<string, number> };
};
type Explain = { key: string; title: string; heute: string; hintergrund: string; link: string };
type Today = {
  date: string; boardId: string; dayIndex: number;
  moon: { name: string; frac: number };
  hexagram: { index: number; name: string; core: string };
  ganzhi: { index: number; pinyin: string; label: string };
  field: { index: number; name: string; core: string };
  stones: Record<string, string>;
  explain?: Explain[];
};

const LS_KEY = 'brett_v2';
const STONE_META: Record<string, { glyph: string; color: string }> = {
  fokus: { glyph: '☉', color: '#b8860b' },
  werk:  { glyph: '⚒', color: '#3d6a8f' },
  liebe: { glyph: '♥', color: '#b05070' },
  kraft: { glyph: '⚡', color: '#4e7d3f' },
  geist: { glyph: '☽', color: '#7a5fa0' },
};
const SPECIAL_FIELDS: Record<number, string> = {
  15: '⟲', 26: '✶', 27: '≈', 28: '☰', 29: '☉', 30: '⌂',
};

const $ = (id: string) => document.getElementById(id)!;

function loadState(): BoardState {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return { boardId: '', positions: {}, lastPlayedDay: 0, profile: null, chapters: [] };
}
function saveState(s: BoardState) { try { localStorage.setItem(LS_KEY, JSON.stringify(s)); } catch {} }

async function api(path: string, body?: unknown) {
  const res = await fetch(path, body === undefined
    ? undefined
    : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data?.detail || ('HTTP ' + res.status)), { data });
  return data;
}

function moonEmoji(frac: number): string {
  const seq = ['🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘'];
  return seq[Math.round(frac * 8) % 8];
}

// --- Feld-Album ------------------------------------------------------------

let FIELD_CARDS: FieldCard[] = [];

function albumSet(state: BoardState): Set<number> {
  if (!state.album) {
    // Migration: Bestandsspielern die bereits erlebten Kapitel gutschreiben.
    state.album = [...new Set(state.chapters.map(c => c.to).filter(t => t >= 1 && t <= 30))];
  }
  return new Set(state.album);
}

function unlockFields(state: BoardState, ...fields: number[]) {
  const set = albumSet(state);
  for (const f of fields) if (f >= 1 && f <= 30) set.add(f);
  state.album = [...set].sort((a, b) => a - b);
}

function renderAlbum(state: BoardState) {
  const el = document.getElementById('album');
  if (!el || !FIELD_CARDS.length) return;
  const found = albumSet(state);
  const wasOpen = !!el.querySelector('details[open]');
  el.innerHTML = '';
  const det = document.createElement('details'); det.className = 'album';
  det.open = wasOpen;
  const sum = document.createElement('summary');
  sum.textContent = `Dein Feld-Album — ${found.size} von 30 Häusern entdeckt`;
  det.appendChild(sum);
  const hint = document.createElement('p'); hint.className = 'album-hint';
  hint.textContent = 'Jedes Haus, das einer deiner Steine je betreten hat, bleibt '
    + 'hier gesammelt — über alle Monatsbretter hinweg. Selten sind die '
    + 'Auszugshäuser 28–30 und das Haus des Wassers.';
  det.appendChild(hint);
  const grid = document.createElement('div'); grid.className = 'album-grid';
  for (const card of FIELD_CARDS) {
    const tile = document.createElement('div');
    const has = found.has(card.index);
    tile.className = 'album-tile' + (has ? ' found' : '');
    const num = document.createElement('span'); num.className = 'album-num';
    num.textContent = String(card.index) + (SPECIAL_FIELDS[card.index] ? ' ' + SPECIAL_FIELDS[card.index] : '');
    const name = document.createElement('span'); name.className = 'album-name';
    name.textContent = has ? card.name : '?';
    tile.append(num, name);
    if (has) tile.title = card.core;
    grid.appendChild(tile);
  }
  det.appendChild(grid);
  el.appendChild(det);
}

// --- Sternzwillinge --------------------------------------------------------

async function renderStarTwins(profile: Profile) {
  const el = document.getElementById('startwins');
  if (!el) return;
  const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(profile.birthDate || '');
  if (!m) return;
  const [, dd, mm, yyyy] = m;
  let twins: StarTwin[];
  try {
    const res = await fetch('/assets/sternzwillinge.json');
    if (!res.ok) return;
    const data = await res.json();
    twins = data[`${mm}-${dd}`] || [];
  } catch { return; }
  if (!twins.length) return;
  el.innerHTML = '';
  const line = document.createElement('p'); line.className = 'startwins-line';
  const star = document.createElement('b'); star.textContent = '✦ Deine Sternzwillinge: ';
  line.appendChild(star);
  const names = twins.map(t => `${t.name} (${t.known}, *${t.year})`).join(' · ');
  line.appendChild(document.createTextNode(names
    + (twins.length === 1 ? ' hat' : ' haben') + ' am selben Tag Geburtstag wie du.'));
  const same = twins.find(t => String(t.year) === yyyy);
  if (same) {
    const jw = document.createElement('b');
    jw.textContent = ` ${same.name} sogar im selben Jahr — dein Jahrgangszwilling!`;
    line.appendChild(jw);
  }
  el.appendChild(line);
}

// --- Profil-Karte ----------------------------------------------------------

async function renderProfil(state: BoardState) {
  const el = document.getElementById('profil');
  if (!el || !state.profile) return;
  if (!state.profil || state.profil.birthDate !== state.profile.birthDate) {
    try {
      const data = await api('/profil?birthDate=' + encodeURIComponent(state.profile.birthDate));
      state.profil = { birthDate: state.profile.birthDate, blocks: data.blocks, link: data.link };
      saveState(state);
    } catch { return; }
  }
  el.hidden = false;
  el.innerHTML = '';
  const det = document.createElement('details');
  const sum = document.createElement('summary'); sum.className = 'resonanz-summary';
  sum.textContent = '✦ Dein Profil — was deine Zeichen über dich erzählen';
  det.appendChild(sum);
  for (const b of state.profil.blocks) {
    const block = document.createElement('div'); block.className = 'explain-block';
    const t = document.createElement('h3'); t.textContent = b.title;
    const p = document.createElement('p'); p.textContent = b.text;
    block.append(t, p);
    det.appendChild(block);
  }
  if (state.profil.link) {
    const a = document.createElement('a'); a.href = state.profil.link;
    a.className = 'explain-link';
    a.textContent = 'Woher das kommt: das Methoden-Lexikon →';
    det.appendChild(a);
  }
  el.appendChild(det);
}

// --- „Deine Menschen" (Resonanz & Kompatibilität) --------------------------

function peopleOf(state: BoardState): Person[] {
  if (!state.people) {
    state.people = [];
    // Migration v1 → v2: das einzelne Resonanz-Datum wird zur ersten Person.
    if (state.resonanz?.partnerDate) {
      state.people.push({ name: '', date: state.resonanz.partnerDate,
                          lastReading: state.resonanz });
    }
  }
  return state.people;
}

function renderChipsAndText(out: HTMLElement, chips: string[], text: string) {
  const row = document.createElement('div'); row.className = 'reading-chips';
  for (const c of chips) {
    const s = document.createElement('span'); s.className = 'reading-chip'; s.textContent = c;
    row.appendChild(s);
  }
  const txt = document.createElement('p'); txt.className = 'resonanz-text';
  txt.textContent = text;
  out.append(row, txt);
}

function renderMenschen(state: BoardState, today: Today, selected = -1) {
  const el = document.getElementById('resonanz');
  if (!el || !state.profile) return;
  const people = peopleOf(state);
  if (selected < 0 && people.length) selected = 0;
  const wasOpen = !!el.querySelector('details[open]');
  el.hidden = false;
  el.innerHTML = '';
  const det = document.createElement('details');
  det.open = wasOpen || false;
  const sum = document.createElement('summary'); sum.className = 'resonanz-summary';
  sum.textContent = '♡ Deine Menschen — Resonanz & Kompatibilität';
  det.appendChild(sum);
  const hint = document.createElement('p'); hint.className = 'onboard-hint';
  hint.textContent = 'Speichere die Geburtstage deiner Menschen — Partner, Freundin, '
    + 'Kollege — und schau, wie eure Zeichen zusammenspielen: als dauerhaftes '
    + 'Kompatibilitätsprofil und als Tages-Resonanz. Alles bleibt in deinem Browser.';
  det.appendChild(hint);

  const rerender = (idx: number) => {
    const open = det.open;
    renderMenschen(state, today, idx);
    const d2 = document.querySelector('#resonanz details') as HTMLDetailsElement | null;
    if (d2) d2.open = open;
  };

  // Personen-Chips
  if (people.length) {
    const chips = document.createElement('div'); chips.className = 'people-row';
    people.forEach((p, i) => {
      const chip = document.createElement('button');
      chip.className = 'dock-chip person-chip' + (i === selected ? ' active' : '');
      chip.textContent = (p.name || p.date) + ' ';
      const x = document.createElement('span'); x.className = 'person-remove'; x.textContent = '×';
      x.title = 'Entfernen';
      x.addEventListener('click', (ev) => {
        ev.stopPropagation();
        people.splice(i, 1); saveState(state);
        rerender(-1);
      });
      chip.appendChild(x);
      chip.addEventListener('click', () => rerender(i));
      chips.appendChild(chip);
    });
    det.appendChild(chips);
  }

  // Hinzufügen-Formular
  const row = document.createElement('div'); row.className = 'resonanz-row';
  const nameIn = document.createElement('input'); nameIn.type = 'text';
  nameIn.placeholder = 'Name (optional)'; nameIn.maxLength = 40;
  const dateIn = document.createElement('input'); dateIn.type = 'date';
  const addBtn = document.createElement('button'); addBtn.className = 'btn-ghost';
  addBtn.textContent = '+ Hinzufügen';
  addBtn.addEventListener('click', () => {
    if (!dateIn.value) { dateIn.focus(); return; }
    const [y, m, d] = dateIn.value.split('-');
    people.push({ name: nameIn.value.trim(), date: `${d}.${m}.${y}` });
    saveState(state);
    rerender(people.length - 1);
  });
  row.append(nameIn, dateIn, addBtn);
  det.appendChild(row);

  // Ausgewählte Person: Kompatibilitätsprofil + Tages-Resonanz
  const person = people[selected];
  if (person) {
    const out = document.createElement('div'); out.className = 'resonanz-out';
    det.appendChild(out);
    const h = document.createElement('h3'); h.className = 'person-heading';
    h.textContent = `Du & ${person.name || person.date}`;
    out.appendChild(h);

    const blocksWrap = document.createElement('div');
    out.appendChild(blocksWrap);
    const renderBlocks = (blocks: ProfilBlock[]) => {
      blocksWrap.innerHTML = '';
      for (const b of blocks) {
        const block = document.createElement('div'); block.className = 'explain-block';
        const t = document.createElement('h3'); t.textContent = b.title;
        const p = document.createElement('p'); p.textContent = b.text;
        block.append(t, p);
        blocksWrap.appendChild(block);
      }
    };
    if (person.profil) renderBlocks(person.profil);
    else {
      api(`/resonanz/profil?birthDate=${encodeURIComponent(state.profile!.birthDate)}`
          + `&partnerDate=${encodeURIComponent(person.date)}`)
        .then(data => { person.profil = data.blocks; saveState(state); renderBlocks(data.blocks); })
        .catch(() => {});
    }

    const daily = document.createElement('div');
    out.appendChild(daily);
    if (person.lastReading && person.lastReading.date === today.date) {
      renderChipsAndText(daily, person.lastReading.chips, person.lastReading.text);
    } else {
      const btn = document.createElement('button'); btn.className = 'btn-primary resonanz-btn';
      btn.textContent = 'Eure Tages-Resonanz lesen';
      btn.addEventListener('click', async () => {
        btn.disabled = true; btn.textContent = 'Das Orakel liest …';
        try {
          const data = await api('/resonanz', {
            birthDate: state.profile!.birthDate, partnerDate: person.date });
          person.lastReading = { date: data.date, partnerDate: person.date,
                                text: data.text, chips: data.chips };
          saveState(state);
          daily.innerHTML = '';
          renderChipsAndText(daily, data.chips, data.text);
        } catch (e: any) {
          btn.disabled = false; btn.textContent = 'Eure Tages-Resonanz lesen';
          alert('Fehler: ' + (e?.message || e));
        }
      });
      daily.appendChild(btn);
    }
  }
  el.appendChild(det);
}

// --- Wochenlesung (Sonntagsbogen) ------------------------------------------

function isoWeekKey(d: Date): string {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const y = t.getUTCFullYear();
  const week = Math.ceil(((t.getTime() - Date.UTC(y, 0, 1)) / 86400000 + 1) / 7);
  return `${y}-W${String(week).padStart(2, '0')}`;
}

function renderWochenlesung(state: BoardState, today: Today) {
  const el = document.getElementById('wochen');
  if (!el || !state.profile) return;
  const week = isoWeekKey(new Date());
  const cached = state.wochenlesung && state.wochenlesung.week === week
    ? state.wochenlesung : null;
  // Die Karte erscheint sonntags — und bleibt sichtbar, solange die
  // aktuelle Wochenlesung schon gelesen wurde.
  if (new Date().getDay() !== 0 && !cached) { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = '';
  const step = document.createElement('h2'); step.className = 'card-step';
  step.textContent = '🌙 Wochenlesung';
  const sub = document.createElement('span'); sub.className = 'step-sub';
  sub.textContent = 'Der Sonntagsbogen: Was diese Woche erzählt hat — und was sich für die nächste andeutet.';
  step.appendChild(sub);
  el.appendChild(step);
  const out = document.createElement('div');
  el.appendChild(out);
  if (cached) {
    renderChipsAndText(out, cached.chips, cached.text);
    return;
  }
  const btn = document.createElement('button'); btn.className = 'btn-primary';
  btn.textContent = 'Wochenlesung lesen';
  btn.addEventListener('click', async () => {
    btn.disabled = true; btn.textContent = 'Das Orakel liest …';
    try {
      const moves = state.chapters.slice(-7).map(c => ({
        day: c.day, stone: c.stone, field: c.fieldName || undefined }));
      const data = await api('/wochenlesung', {
        birthDate: state.profile!.birthDate, moves });
      state.wochenlesung = { week: data.week, text: data.text, chips: data.chips };
      saveState(state);
      out.innerHTML = '';
      renderChipsAndText(out, data.chips, data.text);
    } catch (e: any) {
      btn.disabled = false; btn.textContent = 'Wochenlesung lesen';
      alert('Fehler: ' + (e?.message || e));
    }
  });
  out.appendChild(btn);
}

// --- Web-Push (Morgen-Ritual) ----------------------------------------------

let PUSH_CONFIG: { enabled: boolean; publicKey: string | null } | null | 'unavailable' = null;

function urlBase64ToUint8Array(s: string): Uint8Array {
  const pad = '='.repeat((4 - (s.length % 4)) % 4);
  const raw = atob((s + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(Array.from(raw, c => c.charCodeAt(0)));
}

async function appendPushButton(container: HTMLElement) {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return;
  if (PUSH_CONFIG === null) {
    try { PUSH_CONFIG = await api('/push/config'); } catch { PUSH_CONFIG = 'unavailable'; }
  }
  if (PUSH_CONFIG === 'unavailable' || !PUSH_CONFIG?.enabled || !PUSH_CONFIG.publicKey) return;
  const key = PUSH_CONFIG.publicKey;
  let reg: ServiceWorkerRegistration;
  try { reg = await navigator.serviceWorker.ready; } catch { return; }
  let sub = await reg.pushManager.getSubscription();
  const btn = document.createElement('button'); btn.className = 'btn-ghost';
  const setLabel = () => {
    btn.textContent = sub ? '🔕 Morgen-Ritual abbestellen' : '🔔 Morgen-Ritual aktivieren';
  };
  setLabel();
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    try {
      if (sub) {
        const endpoint = sub.endpoint;
        await sub.unsubscribe();
        await api('/push/unsubscribe', { endpoint }).catch(() => {});
        sub = null;
      } else {
        const perm = await Notification.requestPermission();
        if (perm !== 'granted') { btn.disabled = false; return; }
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(key),
        });
        const j = sub.toJSON();
        await api('/push/subscribe', { endpoint: j.endpoint, keys: j.keys });
      }
    } catch {}
    setLabel();
    btn.disabled = false;
  });
  container.appendChild(btn);
}

// --- Gespür (Orakelfrage) --------------------------------------------------

function gespuerFor(state: BoardState, boardId: string): Gespuer {
  if (!state.gespuer || state.gespuer.boardId !== boardId) {
    state.gespuer = { boardId, guessed: 0, right: 0 };
  }
  return state.gespuer;
}

// --- Brett-Rendering (SVG, 3×10 Boustrophedon mit sichtbarem Pfad) ---------

const CW = 100, CH = 106;

function fieldXY(n: number): [number, number] {
  const row = Math.floor((n - 1) / 10);
  const c0 = (n - 1) % 10;
  const col = row === 1 ? 9 - c0 : c0;
  return [col * CW, row * CH];
}
const fieldCenter = (n: number): [number, number] => {
  const [x, y] = fieldXY(n); return [x + CW / 2, y + CH / 2];
};

function renderBoard(positions: Positions, today: Today, legal: Record<string, number> | null,
                     onPick: ((stone: string) => void) | null) {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${CW * 10} ${CH * 3}`);

  for (let n = 1; n <= 30; n++) {
    const [x, y] = fieldXY(n);
    const rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', String(x + 2)); rect.setAttribute('y', String(y + 2));
    rect.setAttribute('width', String(CW - 4)); rect.setAttribute('height', String(CH - 4));
    rect.setAttribute('rx', '9');
    const cls = n === today.dayIndex ? 'cell cell-today'
      : n < today.dayIndex ? 'cell cell-past' : 'cell';
    rect.setAttribute('class', cls);
    const tip = document.createElementNS(NS, 'title');
    tip.textContent = `Feld ${n}`;
    rect.appendChild(tip);
    svg.appendChild(rect);
    const num = document.createElementNS(NS, 'text');
    num.setAttribute('x', String(x + 10)); num.setAttribute('y', String(y + 19));
    num.setAttribute('class', 'cell-num'); num.textContent = String(n);
    svg.appendChild(num);
    if (SPECIAL_FIELDS[n]) {
      const g = document.createElementNS(NS, 'text');
      g.setAttribute('x', String(x + CW - 26)); g.setAttribute('y', String(y + 24));
      g.setAttribute('class', 'cell-glyph'); g.textContent = SPECIAL_FIELDS[n];
      svg.appendChild(g);
    }
  }

  // Der Weg: eine gepunktete Serpentine durch alle 30 Feldmitten macht die
  // Laufrichtung sichtbar (1→10, 20←11, 21→30).
  const path = document.createElementNS(NS, 'polyline');
  path.setAttribute('points',
    Array.from({ length: 30 }, (_, i) => fieldCenter(i + 1).join(',')).join(' '));
  path.setAttribute('class', 'board-path');
  svg.appendChild(path);

  const byField: Record<number, string[]> = {};
  for (const s of Object.keys(STONE_META)) {
    const p = positions[s] ?? 0;
    (byField[p] = byField[p] || []).push(s);
  }
  for (const [fieldStr, stones] of Object.entries(byField)) {
    const f = Number(fieldStr);
    if (f < 1 || f > 30) continue; // Start/Binsengefilde stehen im Dock
    stones.forEach((stone, i) => {
      const [cx0, cy0] = fieldCenter(f);
      const cx = cx0 + (i - (stones.length - 1) / 2) * 20;
      const cy = cy0 + 12;
      const meta = STONE_META[stone];
      const cls = ['stone'];
      if (legal && legal[stone] !== undefined) cls.push('stone-legal');
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', String(cx)); c.setAttribute('cy', String(cy)); c.setAttribute('r', '17');
      c.setAttribute('fill', meta.color); c.setAttribute('class', cls.join(' '));
      if (legal && legal[stone] !== undefined && onPick) c.addEventListener('click', () => onPick(stone));
      svg.appendChild(c);
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', String(cx)); t.setAttribute('y', String(cy + 5));
      t.setAttribute('text-anchor', 'middle'); t.setAttribute('class', 'stone-label');
      t.textContent = meta.glyph;
      svg.appendChild(t);
    });
  }
  const wrap = $('board-wrap'); wrap.innerHTML = ''; wrap.appendChild(svg);
  renderDock(positions, today, legal, onPick);
}

function dockChip(stone: string, label: string, suffix: string,
                  clickable: boolean, onPick: ((stone: string) => void) | null): HTMLElement {
  const chip = document.createElement('span');
  chip.className = 'dock-chip' + (clickable ? ' legal' : '');
  const orb = document.createElement('span'); orb.className = 'orb';
  orb.style.background = STONE_META[stone]?.color || '#ccc';
  orb.textContent = STONE_META[stone]?.glyph || '?';
  chip.appendChild(orb);
  chip.appendChild(document.createTextNode(label + suffix));
  if (clickable && onPick) chip.addEventListener('click', () => onPick(stone));
  return chip;
}

function renderDock(positions: Positions, today: Today,
                    legal: Record<string, number> | null,
                    onPick: ((stone: string) => void) | null) {
  const dock = $('stone-dock'); dock.innerHTML = '';
  const groups: Array<[string, (p: number) => boolean, (s: string, p: number) => string]> = [
    ['Vor dem Brett', p => p === 0, () => ''],
    ['Unterwegs', p => p >= 1 && p <= 30, (_s, p) => ` · Feld ${p}`],
    ['Binsengefilde', p => p === 31, () => ' ✓'],
  ];
  for (const [title, match, suffix] of groups) {
    const stones = Object.keys(STONE_META).filter(s => match(positions[s] ?? 0));
    if (!stones.length) continue;
    const row = document.createElement('div'); row.className = 'dock-row';
    const t = document.createElement('span'); t.className = 'dock-title'; t.textContent = title;
    row.appendChild(t);
    for (const s of stones) {
      const clickable = !!(legal && legal[s] !== undefined);
      row.appendChild(dockChip(s, today.stones[s] || s, suffix(s, positions[s] ?? 0), clickable, onPick));
    }
    dock.appendChild(row);
  }
}

// --- Tageslage -------------------------------------------------------------

function renderTageslage(today: Today) {
  const el = $('tageslage'); el.innerHTML = '';
  const step = document.createElement('h2'); step.className = 'card-step';
  step.textContent = '1 · Die Tageslage';
  const head = document.createElement('div'); head.className = 'tageslage-head';
  const h2 = document.createElement('h2');
  h2.textContent = `Tag ${today.dayIndex} von 30 ${moonEmoji(today.moon.frac)}`;
  const sub = document.createElement('span'); sub.className = 'tageslage-sub';
  sub.textContent = `${today.moon.name} · I-Ging ${today.hexagram.index} „${today.hexagram.name}“ · Tageszeichen ${today.ganzhi.label}`;
  head.append(h2, sub);
  const fld = document.createElement('div'); fld.className = 'tageslage-field';
  const b = document.createElement('b'); b.textContent = `Heutiges Feld ${today.field.index} — ${today.field.name}: `;
  fld.appendChild(b); fld.appendChild(document.createTextNode(today.field.core));
  el.append(step, head, fld);

  // „Was bedeutet das?" — die ausführlichen Erklärungen stehen als eigene
  // Karte am Seitenende (hier wurden sie nur überscrollt); in der Tageslage
  // bleibt ein Sprunglink als Wegweiser.
  if (today.explain?.length) {
    const jump = document.createElement('p'); jump.className = 'explain-jump';
    const a = document.createElement('a'); a.href = '#erklaerungen';
    a.textContent = 'Was bedeutet das alles? ↓ Erklärungen am Seitenende';
    jump.appendChild(a);
    el.appendChild(jump);
    renderExplainCard(today);
  }
}

function renderExplainCard(today: Today) {
  const el = document.getElementById('explaincard');
  if (!el || !today.explain?.length) return;
  el.innerHTML = '';
  (el as HTMLElement).hidden = false;
  const step = document.createElement('h2'); step.className = 'card-step';
  step.textContent = 'Zum Nachlesen';
  const h = document.createElement('h3'); h.className = 'explain-heading';
  h.textContent = 'Was bedeutet das alles?';
  const intro = document.createElement('p'); intro.className = 'explain-intro';
  intro.textContent = 'Die vier Elemente der heutigen Tageslage — woher sie kommen, '
    + 'wer sie nutzt und was sie heute sagen.';
  el.append(step, h, intro);
  for (const ex of today.explain) {
    const block = document.createElement('div'); block.className = 'explain-block';
    const t = document.createElement('h3'); t.textContent = ex.title;
    const heute = document.createElement('p');
    const hb = document.createElement('b'); hb.textContent = 'Heute: ';
    heute.appendChild(hb); heute.appendChild(document.createTextNode(ex.heute));
    const hg = document.createElement('p'); hg.className = 'explain-bg';
    hg.textContent = ex.hintergrund;
    block.append(t, heute, hg);
    if (ex.link) {
      const a = document.createElement('a'); a.href = ex.link; a.className = 'explain-link';
      a.textContent = 'Mehr im Methoden-Lexikon →';
      block.appendChild(a);
    }
    el.appendChild(block);
  }
}

// --- Kapitel & Share -------------------------------------------------------

// Die Prompts bitten das Orakel, mit dem „Satz für heute" zu schließen —
// einem kleinen, konkreten Impuls. Wir heben den letzten Satz visuell heraus;
// klappt die Satztrennung nicht, bleibt der Text einfach ungeteilt.
function splitImpuls(text: string): { body: string; impuls: string | null } {
  const parts = text.match(/[^.!?]+[.!?]+["“”»']*\s*/g);
  if (!parts || parts.length < 2) return { body: text, impuls: null };
  const impuls = parts[parts.length - 1].trim();
  if (impuls.length < 8 || impuls.length > 160) return { body: text, impuls: null };
  return { body: parts.slice(0, -1).join('').trim(), impuls };
}

function todaysImpuls(state: BoardState, today: Today): string | null {
  const ch = [...state.chapters].reverse().find(c => c.day === today.dayIndex);
  return ch ? splitImpuls(ch.text).impuls : null;
}

function renderChapters(state: BoardState, today: Today) {
  const el = $('chapters'); el.innerHTML = '';
  if (!state.chapters.length) return;
  const h = document.createElement('h2'); h.className = 'chapters-heading';
  h.textContent = 'Deine Monatsgeschichte';
  el.appendChild(h);
  for (const ch of [...state.chapters].reverse().slice(0, 10)) {
    const card = document.createElement('section'); card.className = 'card chapter';
    const day = document.createElement('div'); day.className = 'chapter-day';
    day.textContent = `Tag ${ch.day}`;
    const title = document.createElement('div'); title.className = 'chapter-title';
    const orb = document.createElement('span'); orb.className = 'orb';
    orb.style.background = STONE_META[ch.stone]?.color || '#ccc';
    orb.textContent = STONE_META[ch.stone]?.glyph || '?';
    const label = today.stones[ch.stone] || ch.stone;
    const where = ch.to === 31 ? 'zieht aus ins Binsengefilde'
      : `zieht auf Feld ${ch.to}${ch.fieldName ? ' · ' + ch.fieldName : ''}`;
    const strong = document.createElement('strong'); strong.textContent = `${label} ${where}`;
    title.append(orb, strong);
    const { body, impuls } = splitImpuls(ch.text);
    const txt = document.createElement('div'); txt.className = 'chapter-text';
    txt.textContent = body;
    card.append(day, title, txt);
    if (impuls) {
      const imp = document.createElement('div'); imp.className = 'impuls';
      imp.textContent = impuls;
      card.appendChild(imp);
    }
    if (ch.chips?.length) {
      const chips = document.createElement('div'); chips.className = 'reading-chips';
      for (const c of ch.chips) {
        const s = document.createElement('span'); s.className = 'reading-chip'; s.textContent = c;
        chips.appendChild(s);
      }
      card.appendChild(chips);
    }
    el.appendChild(card);
  }
}

function shareText(state: BoardState, today: Today): string {
  const rows = Object.keys(STONE_META).map(s => {
    const p = state.positions[s] ?? 0;
    const filled = Math.round(Math.min(p, 30) / 30 * 5);
    return STONE_META[s].glyph + ' ' + '▓'.repeat(filled) + '░'.repeat(5 - filled) + (p === 31 ? ' ✓' : '');
  });
  const impuls = todaysImpuls(state, today);
  return `Das Monatsbrett · Tag ${today.dayIndex} ${moonEmoji(today.moon.frac)}\n${rows.join('\n')}`
    + (impuls ? `\n„${impuls}“` : '')
    + `\nhttps://www.horoskop.one/play`;
}

// --- Aktionsbereich --------------------------------------------------------

function actionStep(el: HTMLElement, sub?: string) {
  const step = document.createElement('h2'); step.className = 'card-step';
  step.textContent = '2 · Dein Zug';
  if (sub) {
    const s = document.createElement('span'); s.className = 'step-sub'; s.textContent = sub;
    step.appendChild(s);
  }
  el.appendChild(step);
}

function renderOnboarding(today: Today, onDone: (p: Profile) => void) {
  const el = $('action'); el.innerHTML = '';
  const step = document.createElement('h2'); step.className = 'card-step';
  step.textContent = 'Bevor es losgeht';
  const h = document.createElement('h3');
  h.textContent = 'Dein Brett beginnt mit deinem Geburtstag';
  const intro = document.createElement('p'); intro.className = 'onboard-hint';
  intro.textContent = `Aus deinem Geburtsdatum berechnet das Orakel deinen täglichen Wurf. `
    + `Du steigst heute an Tag ${today.dayIndex} dieses Mondmonats ein — deine Geschichte beginnt mit deinem ersten Zug. `
    + `Zum nächsten Neumond startet für alle ein frisches Brett.`;
  const grid = document.createElement('div'); grid.className = 'onboard-grid';
  const mk = (label: string, type: string, id: string, required: boolean, full = false) => {
    const lab = document.createElement('label'); if (full) lab.className = 'full';
    lab.textContent = label;
    const inp = document.createElement('input'); inp.type = type; inp.id = id; inp.required = required;
    lab.appendChild(inp); grid.appendChild(lab); return inp;
  };
  const d = mk('Geburtsdatum *', 'date', 'ob-date', true, true);
  const p = mk('Geburtsort (optional)', 'text', 'ob-place', false);
  const t = mk('Geburtszeit (optional — die wenigsten kennen sie)', 'time', 'ob-time', false);
  const hint = document.createElement('p'); hint.className = 'onboard-hint';
  hint.textContent = 'Alles bleibt in deinem Browser (Local Storage). Kein Konto, keine Cookies. '
    + 'Das Orakel braucht nur das Datum — Ort und Zeit verfeinern später die Deutung.';
  const btn = document.createElement('button'); btn.className = 'btn-primary'; btn.textContent = 'Das Brett betreten';
  btn.addEventListener('click', () => {
    if (!d.value) { d.focus(); return; }
    const [y, m, dd] = d.value.split('-');
    onDone({ birthDate: `${dd}.${m}.${y}`, birthPlace: p.value.trim() || undefined, birthTime: t.value || undefined });
  });
  el.append(step, h, intro, grid, hint, btn);
}

function setActionMessage(msg: string, sub?: string) {
  const el = $('action'); el.innerHTML = '';
  actionStep(el);
  const p = document.createElement('p'); p.textContent = msg; el.appendChild(p);
  if (sub) { const s = document.createElement('p'); s.className = 'action-hint'; s.textContent = sub; el.appendChild(s); }
}

function sticksRow(throwVal: number | null, tossing: boolean): HTMLElement {
  // Senet-Wurfstäbe: 1–4 = so viele helle (flache) Seiten oben, 5 = alle dunkel.
  const row = document.createElement('div');
  row.className = 'sticks-row' + (tossing ? ' tossing' : '');
  for (let i = 0; i < 4; i++) {
    const stick = document.createElement('div');
    stick.className = 'stick' + (throwVal !== null && throwVal <= 4 && i < throwVal ? ' light' : '');
    row.appendChild(stick);
  }
  if (throwVal !== null) {
    const res = document.createElement('span'); res.className = 'throw-result';
    res.textContent = String(throwVal);
    row.appendChild(res);
  }
  return row;
}

type Guess = 'kurz' | 'weit' | null;

function eventBanner(event: BoardEvent): HTMLElement {
  const b = document.createElement('div'); b.className = 'event-banner';
  const t = document.createElement('b'); t.textContent = `${event.symbol} ${event.name}! `;
  b.appendChild(t);
  b.appendChild(document.createTextNode(event.text));
  return b;
}

function renderThrowIntro(gespuer: Gespuer | undefined, event: BoardEvent | null,
                          onThrow: (guess: Guess) => void) {
  const el = $('action'); el.innerHTML = '';
  actionStep(el, 'Vier Wurfstäbe entscheiden, wie weit du heute ziehst. Hast du eine Vorahnung, wie sie fallen?');
  const wrap = document.createElement('div'); wrap.className = 'throw-intro';
  if (event) wrap.appendChild(eventBanner(event));
  wrap.appendChild(sticksRow(null, false));
  const q = document.createElement('p'); q.className = 'throw-label';
  q.textContent = 'Deine Vorahnung — fällt der Wurf kurz oder weit?';
  wrap.appendChild(q);
  const row = document.createElement('div'); row.className = 'guess-row';
  const mkGuess = (label: string, sub: string, guess: Guess) => {
    const btn = document.createElement('button'); btn.className = 'stone-btn guess-btn';
    btn.appendChild(document.createTextNode(label));
    const t = document.createElement('span'); t.className = 'target'; t.textContent = sub;
    btn.appendChild(t);
    btn.addEventListener('click', () => onThrow(guess));
    row.appendChild(btn);
  };
  mkGuess('Kurz', '1–2 Felder', 'kurz');
  mkGuess('Weit', '3–5 Felder', 'weit');
  wrap.appendChild(row);
  const skip = document.createElement('button'); skip.className = 'btn-ghost';
  skip.textContent = 'Ohne Vorahnung werfen';
  skip.addEventListener('click', () => onThrow(null));
  wrap.appendChild(skip);
  if (gespuer && gespuer.guessed > 0) {
    const stat = document.createElement('p'); stat.className = 'action-hint';
    stat.textContent = `Dein Gespür auf diesem Brett: ${gespuer.right} von ${gespuer.guessed} Vorahnungen richtig.`;
    wrap.appendChild(stat);
  }
  el.appendChild(wrap);
}

function renderThrowChoices(today: Today, t: ThrowData, useAlt: boolean,
                            onMove: (stone: string) => void,
                            onSwitch: (useAlt: boolean) => void,
                            guess: Guess, gespuer: Gespuer | undefined) {
  const el = $('action'); el.innerHTML = '';
  actionStep(el, 'Die Stäbe sind gefallen. Du triffst genau eine Entscheidung pro Tag: Welcher Lebensbereich geht diesen Weg?');
  if (t.event) el.appendChild(eventBanner(t.event));
  const shownThrow = useAlt && t.alt ? t.alt.throw : t.throw;
  const legal = useAlt && t.alt ? t.alt.legalMoves : t.legalMoves;
  el.appendChild(sticksRow(shownThrow, false));
  const label = document.createElement('p'); label.className = 'throw-label';
  if (!useAlt && t.event?.key === 'rueckenwind') {
    label.textContent = `Der Wurf: ${t.throw} · 🌬 Rückenwind → ${t.throw + 1} Felder weit.`;
  } else {
    label.textContent = `Der Wurf: ${shownThrow} ${shownThrow === 1 ? 'Feld' : 'Felder'} weit.`;
  }
  el.appendChild(label);
  if (t.alt) {
    // Sternschnuppe: zwei Würfe liegen auf dem Tisch — einer gilt.
    const row = document.createElement('div'); row.className = 'guess-row';
    const mkSwitch = (alt: boolean, tv: number) => {
      const btn = document.createElement('button');
      btn.className = 'btn-ghost throw-switch' + ((alt === useAlt) ? ' active' : '');
      btn.textContent = `${alt === useAlt ? '● ' : ''}Wurf ${alt ? 2 : 1}: ${tv} ${tv === 1 ? 'Feld' : 'Felder'}`;
      btn.addEventListener('click', () => { if (alt !== useAlt) onSwitch(alt); });
      row.appendChild(btn);
    };
    mkSwitch(false, t.throw);
    mkSwitch(true, t.alt.throw);
    el.appendChild(row);
  }
  if (guess) {
    const correct = (t.throw <= 2) === (guess === 'kurz');
    const verdict = document.createElement('p');
    verdict.className = 'guess-verdict' + (correct ? ' hit' : '');
    verdict.textContent = correct
      ? `✨ Dein Gespür lag richtig — der Wurf fiel ${t.throw <= 2 ? 'kurz' : 'weit'}.`
      : `Der Wurf fiel ${t.throw <= 2 ? 'kurz' : 'weit'} — diesmal wollte das Orakel dich überraschen.`;
    if (gespuer && gespuer.guessed > 0) {
      verdict.textContent += ` (${gespuer.right} von ${gespuer.guessed} richtig)`;
    }
    el.appendChild(verdict);
  }
  const choices = document.createElement('div'); choices.className = 'stone-choices';
  for (const [stone, name] of Object.entries(today.stones)) {
    const btn = document.createElement('button'); btn.className = 'stone-btn';
    btn.style.borderColor = STONE_META[stone]?.color || '';
    const g = document.createElement('span'); g.className = 'glyph';
    g.textContent = STONE_META[stone]?.glyph || '';
    btn.append(g, document.createTextNode(name));
    const target = legal[stone];
    const tspan = document.createElement('span'); tspan.className = 'target';
    if (target === undefined) { btn.disabled = true; tspan.textContent = 'kein Zug möglich'; }
    else tspan.textContent = target === 31 ? '→ Auszug ins Binsengefilde' : `→ Feld ${target}`;
    btn.appendChild(tspan);
    if (target !== undefined) btn.addEventListener('click', () => onMove(stone));
    choices.appendChild(btn);
  }
  el.appendChild(choices);
}

function renderPlayed(state: BoardState, today: Today) {
  const el = $('action'); el.innerHTML = '';
  actionStep(el);
  const p = document.createElement('p');
  p.textContent = '✓ Dein Zug für heute ist gemacht — die Deutung steht unten in deiner Monatsgeschichte.';
  el.appendChild(p);
  const impuls = todaysImpuls(state, today);
  if (impuls) {
    const hero = document.createElement('div'); hero.className = 'impuls-hero';
    const lab = document.createElement('span'); lab.className = 'impuls-label';
    lab.textContent = 'Dein Satz für heute';
    const q = document.createElement('p'); q.textContent = impuls;
    hero.append(lab, q);
    el.appendChild(hero);
  }
  const nxt = document.createElement('p'); nxt.className = 'action-hint';
  nxt.textContent = 'Morgen wirft das Orakel neu. Schau einfach wieder vorbei.';
  el.appendChild(nxt);
  const row = document.createElement('div'); row.className = 'share-row';
  const share = document.createElement('button'); share.className = 'btn-ghost';
  share.textContent = 'Brettstand teilen';
  share.addEventListener('click', async () => {
    const text = shareText(state, today);
    try {
      if (navigator.share) await navigator.share({ text });
      else { await navigator.clipboard.writeText(text); share.textContent = 'Kopiert ✓'; }
    } catch {}
  });
  const reset = document.createElement('button'); reset.className = 'btn-ghost';
  reset.textContent = 'Profil zurücksetzen';
  reset.addEventListener('click', () => {
    if (confirm('Profil und Spielstand aus diesem Browser löschen?')) {
      localStorage.removeItem(LS_KEY); location.reload();
    }
  });
  row.append(share, reset); el.appendChild(row);
  appendPushButton(row);
}

// --- Hauptablauf -----------------------------------------------------------

async function playDay(state: BoardState, day: number, stone: string, silent: boolean,
                       useAlt = false) {
  const data = await api('/board/move', {
    birthDate: state.profile!.birthDate, birthPlace: state.profile!.birthPlace,
    positions: state.positions, stone, dayIndex: day, useAlt,
  });
  state.positions = data.positions;
  state.chapters.push({ day, stone, to: data.moved.to, text: data.reading.text,
                        chips: silent ? [] : data.reading.chips,
                        fieldName: data.moved.field });
  // Album: das erreichte Haus freischalten; das Haus des Wassers (27) ist nie
  // Landefeld, zählt aber als „berührt", wenn die Strömung uns getragen hat.
  unlockFields(state, data.moved.to);
  if (data.moved.water) unlockFields(state, 27);
  state.lastPlayedDay = day;
  saveState(state);
}

async function catchUp(state: BoardState, today: Today) {
  for (let day = state.lastPlayedDay + 1; day < today.dayIndex; day++) {
    try {
      const t = await api('/board/throw', {
        birthDate: state.profile!.birthDate, positions: state.positions, dayIndex: day });
      const stones = Object.keys(t.legalMoves);
      if (!stones.length) { state.lastPlayedDay = day; saveState(state); continue; }
      await playDay(state, day, stones[day % stones.length], true);
    } catch { break; }
  }
}

async function startDay(state: BoardState, today: Today) {
  renderTageslage(today);
  renderStarTwins(state.profile!);
  if (state.boardId && state.boardId !== today.boardId) {
    state.boardId = today.boardId; state.positions = {}; state.chapters = [];
    state.lastPlayedDay = today.dayIndex - 1; // Geschichte beginnt heute
    saveState(state); // Album & Gespür: Album überdauert, Gespür resettet beim ersten Tipp
  }
  await catchUp(state, today);
  renderChapters(state, today);
  renderAlbum(state);
  renderProfil(state);
  renderMenschen(state, today);
  renderWochenlesung(state, today);

  if (state.lastPlayedDay >= today.dayIndex) {
    renderBoard(state.positions, today, null, null);
    renderPlayed(state, today);
    return;
  }
  try {
    const t = await api('/board/throw', {
      birthDate: state.profile!.birthDate, positions: state.positions, dayIndex: today.dayIndex });
    if (!Object.keys(t.legalMoves).length) {
      state.lastPlayedDay = today.dayIndex; saveState(state);
      renderBoard(state.positions, today, null, null);
      setActionMessage('Stille: Heute ist kein Zug möglich.',
        'Das Brett ruht — manchmal ist Nicht-Handeln der Zug. Morgen wirft das Orakel neu.');
      return;
    }
    renderBoard(state.positions, today, null, null);
    // Das Ritual: erst die Vorahnung (Orakelfrage), dann fliegen die Stäbe —
    // der eine Klick wird zu Einsatz → Enthüllung → Wahl.
    renderThrowIntro(state.gespuer?.boardId === today.boardId ? state.gespuer : undefined,
      t.event || null,
      (guess) => {
        const g = gespuerFor(state, today.boardId);
        if (guess) {
          g.guessed += 1;
          if ((t.throw <= 2) === (guess === 'kurz')) g.right += 1;
          saveState(state);
        }
        const el = $('action'); el.innerHTML = '';
        actionStep(el);
        el.appendChild(sticksRow(t.throw, true));
        const show = (useAlt: boolean) => {
          const legal = useAlt && t.alt ? t.alt.legalMoves : t.legalMoves;
          renderBoard(state.positions, today, legal, s => pick(s, useAlt));
          renderThrowChoices(today, t, useAlt, s => pick(s, useAlt), show, guess, state.gespuer);
        };
        setTimeout(() => show(false), 1150);
      });
    async function pick(stone: string, useAlt: boolean) {
      setActionMessage('Der Zug wird gedeutet …');
      try {
        await playDay(state, today.dayIndex, stone, false, useAlt);
        renderBoard(state.positions, today, null, null);
        renderChapters(state, today);
        renderAlbum(state);
        renderPlayed(state, today);
      } catch (e: any) {
        setActionMessage('Fehler: ' + (e?.message || e), 'Bitte versuche es gleich noch einmal.');
      }
    }
  } catch (e: any) {
    setActionMessage('Fehler: ' + (e?.message || e), 'Bitte lade die Seite neu.');
  }
}

async function init() {
  // Service Worker (nur Push/Notification, kein Caching) früh registrieren.
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
  let today: Today;
  try { today = await api('/board/today'); }
  catch { setActionMessage('Die Tageslage konnte nicht geladen werden.', 'Bitte lade die Seite neu.'); return; }
  const state = loadState();
  // Feldkarten fürs Album im Hintergrund laden (statisch, cachebar).
  api('/board/fields')
    .then(d => { FIELD_CARDS = d.fields || []; renderAlbum(state); })
    .catch(() => {});
  renderTageslage(today);
  renderBoard(state.positions, today, null, null);
  if (!state.profile) {
    const help = document.getElementById('help') as HTMLDetailsElement | null;
    if (help) help.open = true;
    renderOnboarding(today, (profile) => {
      state.profile = profile;
      state.boardId = today.boardId;
      state.lastPlayedDay = today.dayIndex - 1; // Geschichte beginnt heute
      saveState(state);
      if (help) help.open = false;
      startDay(state, today);
    });
  } else {
    startDay(state, today);
  }
}

document.addEventListener('DOMContentLoaded', init);
