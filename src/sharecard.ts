function wrapText(ctx,text,x,y,maxWidth,lineHeight){ const words=text.split(' '); let line=''; for(let n=0;n<words.length;n++){ const testLine=line+words[n]+' '; const w=ctx.measureText(testLine).width; if(w>maxWidth && n>0){ ctx.fillText(line.trim(),x,y); line=words[n]+' '; y+=lineHeight; } else { line=testLine; } } ctx.fillText(line.trim(),x,y); return y; }
export async function renderShareCardPNG(canvas,opts){
  const ctx=canvas.getContext('2d'); const W=canvas.width, H=canvas.height;
  const g=ctx.createLinearGradient(0,0,0,H); g.addColorStop(0,'#0f1930'); g.addColorStop(1,'#0a0f1c'); ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
  ctx.globalAlpha=.5; for(let i=0;i<120;i++){ const x=Math.random()*W, y=Math.random()*H, r=Math.random()*1.2; ctx.fillStyle='white'; ctx.beginPath(); ctx.arc(x,y,r,0,Math.PI*2); ctx.fill(); } ctx.globalAlpha=1;
  const cx=W*.18, cy=H*.52, R=Math.min(W,H)*.28; ctx.strokeStyle='rgba(255,255,255,.2)'; ctx.lineWidth=2; ctx.beginPath(); ctx.arc(cx,cy,R,0,Math.PI*2); ctx.stroke(); ctx.beginPath(); ctx.arc(cx,cy,R*.66,0,Math.PI*2); ctx.stroke();
  for(let i=0;i<12;i++){ const a=i/12*Math.PI*2-Math.PI/2; const x1=cx+Math.cos(a)*R, y1=cy+Math.sin(a)*R, x2=cx+Math.cos(a)*(R-16), y2=cy+Math.sin(a)*(R-16); ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke(); }
  ctx.fillStyle='#e6ebff'; ctx.font='700 54px system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial'; ctx.fillText(opts.title, W*.38, H*.28);
  if(opts.subtitle){ ctx.globalAlpha=.86; ctx.font='400 22px system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial'; ctx.fillText(opts.subtitle, W*.38, H*.36); ctx.globalAlpha=1; }
  const maxWidth=W*.52; let y=H*.42;
  if(opts.bullets?.length){ ctx.font='500 28px system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial'; for(const b of opts.bullets.slice(0,3)){ ctx.fillStyle='#e1c07a'; ctx.beginPath(); ctx.arc(W*.38-18,y-8,5,0,Math.PI*2); ctx.fill(); ctx.fillStyle='#e6ebff'; y=wrapText(ctx,b,W*.38,y,maxWidth,34)+34; } }
  else{ ctx.font='400 26px system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial'; ctx.fillStyle='#e6ebffcc'; y=wrapText(ctx,'Heute ist ein guter Tag für einen kleinen, mutigen Schritt.', W*.38, y, maxWidth, 34); }
  return canvas.toDataURL('image/png');
}
