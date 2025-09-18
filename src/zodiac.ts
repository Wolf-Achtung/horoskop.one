
export function drawZodiacWheel(canvas: HTMLCanvasElement) {
  const ctx = canvas.getContext('2d')!;
  const W = canvas.width, H = canvas.height;
  const cx = W/2, cy = H/2;
  const R = Math.min(W,H)/2 - 14;

  // bg
  const g = ctx.createRadialGradient(cx, cy, R*0.1, cx, cy, R);
  g.addColorStop(0, '#0f1930');
  g.addColorStop(1, '#0a0f1c');
  ctx.fillStyle = g; ctx.fillRect(0,0,W,H);

  // outer ring
  ctx.strokeStyle = 'rgba(255,255,255,0.28)';
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI*2); ctx.stroke();
  ctx.beginPath(); ctx.arc(cx, cy, R*0.68, 0, Math.PI*2); ctx.stroke();

  // ticks
  for (let i=0;i<360;i+=30){
    const a = (i-90) * Math.PI/180;
    const x1 = cx + Math.cos(a)*R;
    const y1 = cy + Math.sin(a)*R;
    const x2 = cx + Math.cos(a)*(R-16);
    const y2 = cy + Math.sin(a)*(R-16);
    ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke();
  }

  // gentle dot stars
  ctx.globalAlpha = 0.5;
  for (let i=0;i<80;i++){ const x=Math.random()*W, y=Math.random()*H, r=Math.random()*1.4; ctx.fillStyle='#fff'; ctx.beginPath(); ctx.arc(x,y,r,0,Math.PI*2); ctx.fill(); }
  ctx.globalAlpha = 1;

  // center
  ctx.fillStyle = '#e1c07a'; ctx.beginPath(); ctx.arc(cx, cy, 2.4, 0, Math.PI*2); ctx.fill();
}
