// starfield.js — animated background star canvas using assets/stars.json
// Externalized from inline <script> in index.html so the strict CSP
// (script-src 'self') can serve it without 'unsafe-inline'.
(async function () {
  const canvas = document.getElementById('starfield');
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext('2d');
  const DPR = Math.min(2, window.devicePixelRatio || 1);
  let W = canvas.width = innerWidth * DPR;
  let H = canvas.height = innerHeight * DPR;
  canvas.style.transform = `scale(${1 / DPR})`;
  canvas.style.transformOrigin = '0 0';

  const res = await fetch('assets/stars.json').then(r => r.json()).catch(() => null);
  let stars = (res?.stars || Array.from({ length: 380 }, () => ({
    x: Math.random(), y: Math.random(),
    r: 0.7 + Math.random() * 1.7,
    p: Math.random() * 6.28,
    d: 0.6 + Math.random()
  }))).map(s => ({
    x: s.x, y: s.y, r: s.r, p: s.p, d: s.d,
    tw: 0.6 + Math.random() * 1.2,
    burstAt: performance.now() + Math.random() * 8000 + 4000,
    burstDur: 400 + Math.random() * 800
  }));

  while (stars.length < 420) {
    stars.push({
      x: Math.random(), y: Math.random(),
      r: 0.7 + Math.random() * 1.6,
      p: Math.random() * 6.28,
      d: 0.6 + Math.random(),
      tw: 0.8,
      burstAt: performance.now() + Math.random() * 6000,
      burstDur: 300 + Math.random() * 900
    });
  }

  let scrollY = 0, mouseX = 0, mouseY = 0;
  addEventListener('scroll', () => { scrollY = window.scrollY || 0; }, { passive: true });
  addEventListener('mousemove', (e) => {
    mouseX = (e.clientX / innerWidth - 0.5);
    mouseY = (e.clientY / innerHeight - 0.5);
  }, { passive: true });

  // --- Global "Zucken" — the whole star field briefly flickers at irregular
  //     intervals, like a camera flash or distant lightning. Two- to three-pulse
  //     bursts mimic a real electrical flicker instead of a smooth pulse.
  let flickerStart = 0;
  let flickerDur = 0;
  let flickerAmp = 0;
  let nextFlickerAt = performance.now() + 2500 + Math.random() * 6000;

  function scheduleNextFlicker(now) {
    // 3–14 s between flickers, sometimes a cluster (two in quick succession).
    const cluster = Math.random() < 0.35;
    nextFlickerAt = now + (cluster ? 120 + Math.random() * 260 : 3000 + Math.random() * 11000);
  }

  function flickerMultiplier(now) {
    if (flickerStart === 0) {
      if (now >= nextFlickerAt) {
        flickerStart = now;
        flickerDur = 90 + Math.random() * 170;         // 90–260 ms
        flickerAmp = 0.55 + Math.random() * 0.45;      // 0.55–1.0 extra brightness
        scheduleNextFlicker(now);
      }
      return 0;
    }
    const phase = (now - flickerStart) / flickerDur;
    if (phase >= 1) { flickerStart = 0; return 0; }
    // Multi-peak envelope: sin^2 with a jittered secondary pulse near the end.
    const primary = Math.sin(phase * Math.PI);
    const jitter = phase > 0.55 ? Math.sin((phase - 0.55) * Math.PI * 3.2) * 0.35 : 0;
    return Math.max(0, (primary + jitter)) * flickerAmp;
  }

  function draw(t) {
    ctx.clearRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'lighter';
    const parY = (scrollY * 0.05) * DPR;
    const parX = (scrollY * 0.02) * DPR;
    const tiltX = mouseX * 6 * DPR;
    const tiltY = mouseY * 4 * DPR;
    const zucken = flickerMultiplier(performance.now());

    for (const s of stars) {
      const twinkle = (Math.sin(t * 0.001 + s.p) * 0.5 + 0.5) * s.tw + 0.2;
      let flare = 0;
      const now = performance.now();
      if (now > s.burstAt) {
        const phase = (now - s.burstAt) / s.burstDur;
        if (phase < 1) {
          flare = 0.8 * (1 - Math.abs(phase * 2 - 1));
        } else {
          s.burstAt = now + 6000 + Math.random() * 9000;
          s.burstDur = 400 + Math.random() * 1000;
        }
      }
      const driftX = Math.sin(t * 0.00006 + s.p) * s.d * 10;
      const driftY = Math.cos(t * 0.00005 + s.p) * s.d * 8;
      const x = s.x * W + driftX + parX * (0.2 + s.d * 0.15) + tiltX;
      const y = s.y * H + driftY + parY * (0.25 + s.d * 0.2) + tiltY;
      const rad = s.r * DPR * (0.8 + twinkle * 0.9 + flare + zucken * 0.9);
      const grd = ctx.createRadialGradient(x, y, 0, x, y, rad);
      const core = Math.min(1, 0.98 + zucken * 0.05);
      grd.addColorStop(0, `rgba(245,248,255,${core.toFixed(3)})`);
      grd.addColorStop(0.45, `rgba(190,210,255,${(0.55 + zucken * 0.3).toFixed(3)})`);
      grd.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = grd;
      ctx.beginPath();
      ctx.arc(x, y, rad, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalCompositeOperation = 'source-over';
    requestAnimationFrame(draw);
  }
  requestAnimationFrame(draw);

  addEventListener('resize', () => {
    W = canvas.width = innerWidth * DPR;
    H = canvas.height = innerHeight * DPR;
    canvas.style.transform = `scale(${1 / DPR})`;
  }, { passive: true });
})();
