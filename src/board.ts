// Das Monatsbrett — Spiel-Frontend (Phase 1.1, docs/spielkonzept.md)
// Zustand liegt im LocalStorage; alles Orakelhafte kommt deterministisch vom
// Server. LLM-/Nutzertexte werden ausschließlich per textContent gerendert.
//
// v2-Fixes gegenüber v1: Neueinsteiger starten bei ihrem heutigen Bretttag
// (kein rückwirkendes Orakel-Nachholen einer nie gespielten Historie), das
// Orakel wählt beim Nachholen abwechselnd statt stur den ersten Stein, und
// die Oberfläche führt in klaren Schritten durch den Tag.

type Positions = Record<string, number>;
type Chapter = { day: number; stone: string; to: number; text: string;
                 chips: string[]; fieldName?: string };
type Profile = { birthDate: string; birthPlace?: string; birthTime?: string };
type BoardState = {
  boardId: string; positions: Positions; lastPlayedDay: number;
  profile: Profile | null; chapters: Chapter[];
};
type Today = {
  date: string; boardId: string; dayIndex: number;
  moon: { name: string; frac: number };
  hexagram: { index: number; name: string; core: string };
  ganzhi: { index: number; pinyin: string; label: string };
  field: { index: number; name: string; core: string };
  stones: Record<string, string>;
};

const LS_KEY = 'brett_v2'; // v1 hatte den Einstiegs-Bug — bewusst frischer Schnitt
const STONE_META: Record<string, { letter: string; color: string }> = {
  fokus: { letter: 'F', color: '#b8860b' },
  werk:  { letter: 'W', color: '#3d6a8f' },
  liebe: { letter: 'L', color: '#b05070' },
  kraft: { letter: 'K', color: '#4e7d3f' },
  geist: { letter: 'G', color: '#7a5fa0' },
};
const SPECIAL_GLYPHS: Record<number, string> = { 15: '⟲', 26: '✶', 27: '≈', 28: '☰', 29: '☉', 30: '⌂' };

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

// --- Brett-Rendering (SVG, 3×10 Boustrophedon) -----------------------------

function fieldXY(n: number, cw: number, ch: number): [number, number] {
  const row = Math.floor((n - 1) / 10);
  const c0 = (n - 1) % 10;
  const col = row === 1 ? 9 - c0 : c0;
  return [col * cw, row * ch];
}

function renderBoard(positions: Positions, today: Today, legal: Record<string, number> | null,
                     onPick: ((stone: string) => void) | null) {
  const NS = 'http://www.w3.org/2000/svg';
  const cw = 100, ch = 106;
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${cw * 10} ${ch * 3}`);
  for (let n = 1; n <= 30; n++) {
    const [x, y] = fieldXY(n, cw, ch);
    const rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', String(x + 2)); rect.setAttribute('y', String(y + 2));
    rect.setAttribute('width', String(cw - 4)); rect.setAttribute('height', String(ch - 4));
    rect.setAttribute('rx', '8');
    rect.setAttribute('class', n === today.dayIndex ? 'cell cell-today' : 'cell');
    svg.appendChild(rect);
    const num = document.createElementNS(NS, 'text');
    num.setAttribute('x', String(x + 10)); num.setAttribute('y', String(y + 18));
    num.setAttribute('class', 'cell-num'); num.textContent = String(n);
    svg.appendChild(num);
    if (SPECIAL_GLYPHS[n]) {
      const g = document.createElementNS(NS, 'text');
      g.setAttribute('x', String(x + cw - 22)); g.setAttribute('y', String(y + 20));
      g.setAttribute('class', 'cell-glyph'); g.textContent = SPECIAL_GLYPHS[n];
      svg.appendChild(g);
    }
  }
  const byField: Record<number, string[]> = {};
  for (const s of Object.keys(STONE_META)) {
    const p = positions[s] ?? 0;
    (byField[p] = byField[p] || []).push(s);
  }
  for (const [fieldStr, stones] of Object.entries(byField)) {
    const f = Number(fieldStr);
    if (f < 1 || f > 30) continue; // Start/Binsengefilde stehen in der Legende
    stones.forEach((stone, i) => {
      const [x, y] = fieldXY(f, cw, ch);
      const cx = x + cw / 2 + (i - (stones.length - 1) / 2) * 18;
      const cy = y + ch / 2 + 8;
      const meta = STONE_META[stone];
      const cls = ['stone'];
      if (legal && legal[stone] !== undefined) cls.push('stone-legal');
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', String(cx)); c.setAttribute('cy', String(cy)); c.setAttribute('r', '15');
      c.setAttribute('fill', meta.color); c.setAttribute('class', cls.join(' '));
      if (legal && legal[stone] !== undefined && onPick) c.addEventListener('click', () => onPick(stone));
      svg.appendChild(c);
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', String(cx)); t.setAttribute('y', String(cy + 4));
      t.setAttribute('text-anchor', 'middle'); t.setAttribute('class', 'stone-label');
      t.textContent = meta.letter;
      svg.appendChild(t);
    });
  }
  const wrap = $('board-wrap'); wrap.innerHTML = ''; wrap.appendChild(svg);

  const legend = $('board-legend'); legend.innerHTML = '';
  for (const [stone, label] of Object.entries(today.stones)) {
    const span = document.createElement('span');
    const dot = document.createElement('span');
    dot.className = 'dot'; dot.style.background = STONE_META[stone]?.color || '#ccc';
    span.appendChild(dot);
    const p = positions[stone] ?? 0;
    span.appendChild(document.createTextNode(
      `${label}: ${p === 0 ? 'vor dem Brett' : p === 31 ? 'Binsengefilde ✓' : 'Feld ' + p}`));
    legend.appendChild(span);
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
}

// --- Kapitel & Share -------------------------------------------------------

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
    const dot = document.createElement('span'); dot.className = 'dot';
    dot.style.background = STONE_META[ch.stone]?.color || '#ccc';
    const label = today.stones[ch.stone] || ch.stone;
    const where = ch.to === 31 ? 'zieht aus ins Binsengefilde'
      : `zieht auf Feld ${ch.to}${ch.fieldName ? ' · ' + ch.fieldName : ''}`;
    const strong = document.createElement('strong'); strong.textContent = `${label} ${where}`;
    title.append(dot, strong);
    const txt = document.createElement('div'); txt.className = 'chapter-text';
    txt.textContent = ch.text;
    card.append(day, title, txt);
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
    return STONE_META[s].letter + ' ' + '▓'.repeat(filled) + '░'.repeat(5 - filled) + (p === 31 ? ' ✓' : '');
  });
  return `Das Monatsbrett · Tag ${today.dayIndex} ${moonEmoji(today.moon.frac)}\n${rows.join('\n')}\nhttps://www.horoskop.one/play`;
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

function renderThrow(today: Today, throwVal: number,
                     legal: Record<string, number>, onMove: (stone: string) => void) {
  const el = $('action'); el.innerHTML = '';
  actionStep(el, 'Das Orakel hat für dich geworfen. Du triffst genau eine Entscheidung pro Tag: Welcher Lebensbereich geht diesen Weg?');
  const row = document.createElement('div'); row.className = 'throw-row';
  const sticks = document.createElement('span'); sticks.className = 'throw-sticks';
  sticks.textContent = '▮'.repeat(throwVal) + '▯'.repeat(Math.max(0, 5 - throwVal));
  const label = document.createElement('span'); label.className = 'throw-label';
  label.textContent = `Der Wurf: ${throwVal} ${throwVal === 1 ? 'Feld' : 'Felder'} weit.`;
  row.append(sticks, label); el.appendChild(row);
  const choices = document.createElement('div'); choices.className = 'stone-choices';
  for (const [stone, name] of Object.entries(today.stones)) {
    const btn = document.createElement('button'); btn.className = 'stone-btn';
    btn.style.borderColor = STONE_META[stone]?.color || '';
    btn.textContent = name;
    const target = legal[stone];
    const tspan = document.createElement('span'); tspan.className = 'target';
    if (target === undefined) { btn.disabled = true; tspan.textContent = 'kein Zug möglich'; }
    else tspan.textContent = target === 31 ? '→ Auszug ins Binsengefilde' : `→ Feld ${target}`;
    btn.appendChild(tspan);
    if (target !== undefined) btn.addEventListener('click', () => onMove(stone));
    choices.appendChild(btn);
  }
  el.appendChild(choices);
  const hint = document.createElement('p'); hint.className = 'action-hint';
  hint.textContent = 'Tipp: Wähle den Bereich, der heute deine Aufmerksamkeit verdient — die Deutung entsteht aus Zug, Zielfeld und deinem Profil.';
  el.appendChild(hint);
}

function renderPlayed(state: BoardState, today: Today) {
  const el = $('action'); el.innerHTML = '';
  actionStep(el);
  const p = document.createElement('p');
  p.textContent = '✓ Dein Zug für heute ist gemacht — die Deutung steht unten in deiner Monatsgeschichte.';
  const nxt = document.createElement('p'); nxt.className = 'action-hint';
  nxt.textContent = 'Morgen wirft das Orakel neu. Schau einfach wieder vorbei.';
  el.append(p, nxt);
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
}

// --- Hauptablauf -----------------------------------------------------------

async function playDay(state: BoardState, day: number, stone: string, silent: boolean) {
  const data = await api('/board/move', {
    birthDate: state.profile!.birthDate, birthPlace: state.profile!.birthPlace,
    positions: state.positions, stone, dayIndex: day,
  });
  state.positions = data.positions;
  state.chapters.push({ day, stone, to: data.moved.to, text: data.reading.text,
                        chips: silent ? [] : data.reading.chips,
                        fieldName: data.moved.field });
  state.lastPlayedDay = day;
  saveState(state);
}

async function catchUp(state: BoardState, today: Today) {
  // Verpasste Tage seit dem letzten eigenen Zug: das Orakel zieht behutsam
  // weiter — abwechselnd statt stur denselben Stein (docs/spielkonzept.md §5).
  for (let day = state.lastPlayedDay + 1; day < today.dayIndex; day++) {
    try {
      const t = await api('/board/throw', {
        birthDate: state.profile!.birthDate, positions: state.positions, dayIndex: day });
      const stones = Object.keys(t.legalMoves);
      if (!stones.length) { state.lastPlayedDay = day; saveState(state); continue; }
      await playDay(state, day, stones[day % stones.length], true);
    } catch { break; } // z. B. Rate-Limit: morgen geht es weiter
  }
}

async function startDay(state: BoardState, today: Today) {
  renderTageslage(today);
  if (state.boardId && state.boardId !== today.boardId) {
    // Neumond → neues Brett: alle beginnen wieder bei Tag 1 des neuen Zyklus.
    state.boardId = today.boardId; state.positions = {}; state.chapters = [];
    state.lastPlayedDay = today.dayIndex - 1; // Geschichte beginnt heute
    saveState(state);
  }
  await catchUp(state, today);
  renderChapters(state, today);

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
    renderBoard(state.positions, today, t.legalMoves, pick);
    renderThrow(today, t.throw, t.legalMoves, pick);
    async function pick(stone: string) {
      setActionMessage('Der Zug wird gedeutet …');
      try {
        await playDay(state, today.dayIndex, stone, false);
        renderBoard(state.positions, today, null, null);
        renderChapters(state, today);
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
  let today: Today;
  try { today = await api('/board/today'); }
  catch { setActionMessage('Die Tageslage konnte nicht geladen werden.', 'Bitte lade die Seite neu.'); return; }
  const state = loadState();
  renderTageslage(today);
  renderBoard(state.positions, today, null, null);
  if (!state.profile) {
    // Erstbesuch: Hilfe aufklappen und Einstieg erklären.
    const help = document.getElementById('help') as HTMLDetailsElement | null;
    if (help) help.open = true;
    renderOnboarding(today, (profile) => {
      state.profile = profile;
      state.boardId = today.boardId;
      // Kern-Fix: Die Geschichte beginnt HEUTE — kein rückwirkendes
      // Nachspielen von Tagen vor dem Einstieg.
      state.lastPlayedDay = today.dayIndex - 1;
      saveState(state);
      if (help) help.open = false;
      startDay(state, today);
    });
  } else {
    startDay(state, today);
  }
}

document.addEventListener('DOMContentLoaded', init);
