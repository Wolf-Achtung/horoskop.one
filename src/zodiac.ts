// zodiac.ts — animated hero wheel for public/index.html.
// Draws a white zodiac ring (no purple fill) and eight colour-coded
// planets that orbit the centre at different speeds. A legend below the
// canvas pairs each colour with its planet name so the viewer can tell
// which dot is which.

type Planet = {
  name: string;
  color: string;
  // radius of orbit (px in the 520x520 canvas)
  radius: number;
  // how long one full revolution takes (ms)
  period: number;
  // body radius (px)
  size: number;
  // starting angle offset (rad)
  phase: number;
  hasRing?: boolean;
  hasMoon?: boolean;
};

const PLANETS: Planet[] = [
  { name: 'Merkur',  color: '#a8b5c7', radius:  56, period: 22000, size: 3.6, phase: 0.3 },
  { name: 'Venus',   color: '#ffd48a', radius:  78, period: 38000, size: 4.4, phase: 1.1 },
  { name: 'Erde',    color: '#6bb7ff', radius: 102, period: 56000, size: 4.0, phase: 2.0, hasMoon: true },
  { name: 'Mars',    color: '#ff7a5a', radius: 126, period: 72000, size: 3.8, phase: 0.8 },
  { name: 'Jupiter', color: '#e7c48a', radius: 156, period: 96000, size: 6.4, phase: 2.9 },
  { name: 'Saturn',  color: '#f1c27d', radius: 184, period:124000, size: 5.6, phase: 1.6, hasRing: true },
  { name: 'Uranus',  color: '#8ef3ff', radius: 210, period:160000, size: 4.2, phase: 0.4 },
  { name: 'Neptun',  color: '#9bb4ff', radius: 232, period:200000, size: 4.2, phase: 3.7 }
];

const ZODIAC_GLYPHS = ['♑','♒','♓','♈','♉','♊','♋','♌','♍','♎','♏','♐'];

function ensurePlanetLegend(canvas: HTMLCanvasElement) {
  if (!canvas.parentElement) return;
  let list = canvas.parentElement.querySelector('.planet-legend') as HTMLUListElement | null;
  if (list) return;
  list = document.createElement('ul');
  list.className = 'planet-legend';
  list.setAttribute('aria-label', 'Legende der Planeten');
  const items: [string, string][] = [
    ['Sonne', '#f1c27d'],
    ...PLANETS.map(p => [p.name, p.color] as [string, string])
  ];
  for (const [name, color] of items) {
    const li = document.createElement('li');
    const swatch = document.createElement('i');
    swatch.style.color = color;
    swatch.style.background = color;
    const b = document.createElement('b');
    b.textContent = name;
    li.appendChild(swatch);
    li.appendChild(b);
    list.appendChild(li);
  }
  canvas.parentElement.appendChild(list);
}

export function drawZodiacWheel(canvas: HTMLCanvasElement) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const W = canvas.width;
  const H = canvas.height;
  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(W, H) / 2 - 14;

  ensurePlanetLegend(canvas);

  // Static background stars drawn once into an off-screen buffer so the
  // animation loop only composites the moving parts.
  const starCount = 90;
  const stars = Array.from({ length: starCount }, () => ({
    x: Math.random() * W,
    y: Math.random() * H,
    r: Math.random() * 1.4 + 0.2,
    tw: Math.random() * Math.PI * 2
  }));

  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  function drawFrame(now: number) {
    ctx.clearRect(0, 0, W, H);

    // Twinkling stars
    for (const s of stars) {
      const alpha = 0.4 + 0.4 * Math.sin(now * 0.0015 + s.tw);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Orbit guide rings
    ctx.strokeStyle = 'rgba(155, 180, 255, 0.14)';
    ctx.lineWidth = 1;
    for (const p of PLANETS) {
      ctx.beginPath();
      ctx.arc(cx, cy, p.radius, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Zodiac ring – thin white dashed circle + 12 glyphs
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
    ctx.setLineDash([4, 6]);
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = '#ffffff';
    ctx.font = '24px serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
      const gx = cx + Math.cos(a) * (R - 2);
      const gy = cy + Math.sin(a) * (R - 2);
      const twinkle = 0.7 + 0.3 * Math.sin(now * 0.0018 + i);
      ctx.globalAlpha = twinkle;
      ctx.fillText(ZODIAC_GLYPHS[i], gx, gy);
    }
    ctx.globalAlpha = 1;

    // Planets
    for (const p of PLANETS) {
      const t = reduce ? 0 : (now / p.period) * Math.PI * 2;
      const a = t + p.phase;
      const px = cx + Math.cos(a) * p.radius;
      const py = cy + Math.sin(a) * p.radius;
      const pulse = 1 + 0.15 * Math.sin(now * 0.004 + p.phase);

      // Halo
      const halo = ctx.createRadialGradient(px, py, 0, px, py, p.size * 4);
      halo.addColorStop(0, p.color + 'cc');
      halo.addColorStop(0.4, p.color + '44');
      halo.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = halo;
      ctx.beginPath();
      ctx.arc(px, py, p.size * 4, 0, Math.PI * 2);
      ctx.fill();

      // Body
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(px, py, p.size * pulse, 0, Math.PI * 2);
      ctx.fill();

      if (p.hasRing) {
        ctx.strokeStyle = p.color;
        ctx.globalAlpha = 0.75;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.ellipse(px, py, p.size * 2.2, p.size * 0.7, a, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
      if (p.hasMoon) {
        const moonA = now * 0.003;
        const mx = px + Math.cos(moonA) * (p.size * 2.4);
        const my = py + Math.sin(moonA) * (p.size * 2.4);
        ctx.fillStyle = '#e7ecff';
        ctx.beginPath();
        ctx.arc(mx, my, 1.6, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Sun at centre
    const sunGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 32);
    sunGlow.addColorStop(0, '#ffe6b3');
    sunGlow.addColorStop(0.6, '#f1c27d');
    sunGlow.addColorStop(1, 'rgba(241, 194, 125, 0)');
    ctx.fillStyle = sunGlow;
    ctx.beginPath();
    ctx.arc(cx, cy, 32, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#f1c27d';
    ctx.beginPath();
    ctx.arc(cx, cy, 9, 0, Math.PI * 2);
    ctx.fill();

    if (!reduce) requestAnimationFrame(drawFrame);
  }

  requestAnimationFrame(drawFrame);
}
