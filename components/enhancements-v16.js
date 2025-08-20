// enhancements-v16: gold hero, transparent form, remove buttons, rename AI, intensity toggle visible,
// chinese glyphs + i-ching micro symbol in birth badges; glyphs in header chips stay from v15.
(function(){
  // --- 0) Swap hero to gold & gentle rotation/glow pulse
  const heroImg = document.querySelector('.hero img');
  if(heroImg){ heroImg.src = 'assets/hero-wheel-gold.svg'; }
  const style = document.createElement('style');
  style.textContent = `
    .hero img{ animation: spin-slow 140s linear infinite; filter: drop-shadow(0 0 10px rgba(250,230,180,.05)); }
    @keyframes spin-slow{ from{ transform: rotate(0deg)} to{ transform: rotate(360deg)} }
    .card{ background: rgba(12, 22, 44, .35) !important; backdrop-filter: blur(8px); border-color: rgba(90,110,170,.45) !important; }
    .btn{ backdrop-filter: blur(2px) }
    .badge-row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 4px}
    .badge{display:inline-flex;align-items:center;background:#0d203fcc;border:1px solid #2a3f79;border-radius:16px;padding:6px 10px;font-size:13px;color:#bdd0ff}
    .badge .desc{opacity:.85;margin-left:6px}
    .chip svg{width:14px;height:14px;opacity:.9;margin-right:6px;vertical-align:-2px}
    .tiny-hex line{stroke:#bdd0ff;stroke-width:1.6;stroke-linecap:round}
  `;
  document.head.appendChild(style);

  // --- 1) Remove "Heute" + "Sofort-Analyse (offline)" buttons; rename AI button
  function textOf(el){ return (el.textContent||'').trim().toLowerCase(); }
  document.querySelectorAll('button, .btn').forEach(b=>{
    const t = textOf(b);
    if(t === 'heute' || t === 'sofort-analyse (offline)'){ b.remove(); }
    if(t === 'gold-reading (ai)'){ b.textContent = 'Sterne fragen'; }
  });

  // --- 2) Visible intensity toggle (dezent/kräftig) for star overlay (v15 adds overlay)
  function ensureSkyToggle(){
    if(document.getElementById('skyToggleVisible')) return;
    const btn = document.createElement('button');
    btn.id='skyToggleVisible'; btn.className='btn small';
    btn.style.cssText='position:absolute; right:10px; top:6px; z-index:5; opacity:.9';
    btn.textContent='Himmel: kräftig';
    const container = document.querySelector('.hero') || document.body;
    container.style.position='relative';
    container.appendChild(btn);
    let strong = true;
    btn.addEventListener('click', ()=>{
      strong = !strong;
      window.INTENS = strong ? 1.0 : 0.5; // used by v15 overlay if present
      btn.textContent = strong ? 'Himmel: kräftig' : 'Himmel: dezent';
    });
    window.INTENS = 1.0;
  }
  ensureSkyToggle();

  // --- 3) Birth badges: include Chinese glyphs + tiny I-Ching hex
  async function loadSprite(url){
    const txt = await fetch(url).then(r=>r.text()).catch(()=>null);
    if(!txt) return {};
    const doc = new DOMParser().parseFromString(txt,'image/svg+xml');
    const map={}; doc.querySelectorAll('symbol').forEach(sym=> map[sym.id] = sym.innerHTML );
    return map;
  }
  // zodiac sprite (from v15 already present), but we reload for safety
  let zmapPromise = loadSprite('assets/zodiac-glyphs.svg');
  let cmapPromise = loadSprite('assets/chinese-glyphs.svg');

  function inlineGlyph(mapPromise, id){
    const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('width','14'); svg.setAttribute('height','14');
    svg.style.opacity='.9'; svg.style.verticalAlign='-2px'; svg.style.marginRight='6px';
    mapPromise.then(map=>{ svg.innerHTML = map[id]||''; });
    return svg;
  }
  function tinyHex(n){
    // Draws 6 lines; solid=yang, broken=yin (approx); here: use parity from n for variation
    const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('width','14'); svg.setAttribute('height','14'); svg.classList.add('tiny-hex');
    const g=document.createElementNS(svg.namespaceURI,'g'); svg.appendChild(g);
    for(let i=0;i<6;i++){
      const y=2+i*2; const yang = ((n>>i)&1)===1;
      if(yang){
        const l=document.createElementNS(svg.namespaceURI,'line'); l.setAttribute('x1','1'); l.setAttribute('y1',y); l.setAttribute('x2','13'); l.setAttribute('y2',y); g.appendChild(l);
      }else{
        const l1=document.createElementNS(svg.namespaceURI,'line'); l1.setAttribute('x1','1'); l1.setAttribute('y1',y); l1.setAttribute('x2','5'); l1.setAttribute('y2',y); g.appendChild(l1);
        const l2=document.createElementNS(svg.namespaceURI,'line'); l2.setAttribute('x1','9'); l2.setAttribute('y1',y); l2.setAttribute('x2','13'); l2.setAttribute('y2',y); g.appendChild(l2);
      }
    }
    svg.style.marginRight='6px'; svg.style.verticalAlign='-2px';
    return svg;
  }

  function parseBirthDate(str){ const m=(str||'').match(/(\d{1,2})\.(\d{1,2})\.(\d{4})/); if(!m) return null; const d=new Date(+m[3],+m[2]-1,+m[1]); return isNaN(d)?null:d;}
  function zodiacFromDate(d){
    const m=d.getMonth()+1, day=d.getDate();
    const edges=[['capricorn',1,19],['aquarius',2,18],['pisces',3,20],['aries',4,19],['taurus',5,20],['gemini',6,20],['cancer',7,22],['leo',8,22],['virgo',9,22],['libra',10,22],['scorpio',11,21],['sagittarius',12,21],['capricorn',12,31]];
    let name='capricorn'; for(const [n,mm,dd] of edges){ if((m<mm)||(m===mm&&day<=dd)){ name=n; break; } }
    const labels={aries:'Widder',taurus:'Stier',gemini:'Zwillinge',cancer:'Krebs',leo:'Löwe',virgo:'Jungfrau',libra:'Waage',scorpio:'Skorpion',sagittarius:'Schütze',capricorn:'Steinbock',aquarius:'Wassermann',pisces:'Fische'};
    const texts={aries:'Pioniergeist und Aufbruch.', taurus:'Beständigkeit und Genuss.', gemini:'Neugier und Austausch.', cancer:'Zuwendung und Schutz.', leo:'Ausstrahlung und Herz.', virgo:'Präzision und Dienst.', libra:'Harmonie und Maß.', scorpio:'Tiefe und Wandlung.', sagittarius:'Weite und Sinn.', capricorn:'Disziplin und Ziel.', aquarius:'Freiheit und Ideen.', pisces:'Einfühlung und Träume.'};
    return {kind:'zodiac', id:name, label:labels[name], desc:texts[name]};
  }
  function chineseFromYear(y){
    const animals=['Ratte','Büffel','Tiger','Hase','Drache','Schlange','Pferd','Ziege','Affe','Hahn','Hund','Schwein'];
    const base=1900; const idx=((y-base)%12+12)%12;
    const texts={'Ratte':'gewandt, wachsam','Büffel':'ruhig, verlässlich','Tiger':'mutig, impulsiv','Hase':'feinfühlig, verbindend','Drache':'kraftvoll, visionär','Schlange':'intuitiv, still','Pferd':'lebendig, unabhängig','Ziege':'sanft, ästhetisch','Affe':'pfiffig, erfinderisch','Hahn':'klar, direkt','Hund':'loyal, schützend','Schwein':'offen, großzügig'};
    const ids=['ratte','bueffel','tiger','hase','drache','schlange','pferd','ziege','affe','hahn','hund','schwein'];
    return {kind:'cn', id:ids[idx], label:animals[idx], desc:texts[animals[idx]]};
  }
  function lifePathFromDate(d){
    const s=''+d.getFullYear()+String(d.getMonth()+1).padStart(2,'0')+String(d.getDate()).padStart(2,'0');
    let sum=s.split('').reduce((a,b)=>a+ +b,0), master=[11,22,33];
    while(sum>9 && !master.includes(sum)){ sum=String(sum).split('').reduce((a,b)=>a+ +b,0); }
    const desc={1:'Initiative',2:'Team & Takt',3:'Ausdruck',4:'Struktur',5:'Wandel',6:'Fürsorge',7:'Tiefe',8:'Wirksamkeit',9:'Weite',11:'Inspiration',22:'Baukunst',33:'Herzführung'};
    return {kind:'num', id:'num'+sum, label:'Lebenszahl '+sum, desc:desc[sum]||''};
  }
  function celticTree(d){
    const ranges=[['Birke',12,24,1,20],['Eberesche',1,21,2,17],['Esche',2,18,3,17],['Erle',3,18,4,14],['Weide',4,15,5,12],['Weißdorn',5,13,6,9],['Eiche',6,10,7,7],['Stechpalme',7,8,8,4],['Hasel',8,5,9,1],['Weinrebe',9,2,9,29],['Efeu',9,30,10,27],['Schilfrohr',10,28,11,24],['Holunder',11,25,12,23]];
    const y=d.getFullYear(); const md=(m,dd)=>new Date(y,m-1,dd); let name='Birke';
    for(const [n,m1,d1,m2,d2] of ranges){ const s=md(m1,d1), e=md(m2,d2); const inside=s<=e ? (d>=s&&d<=e) : (d>=s||d<=e); if(inside){ name=n; break; } }
    const desc={'Birke':'Neuanfang','Eberesche':'Inspiration','Esche':'Wandlung','Erle':'Mut','Weide':'Gefühl','Weißdorn':'Grenze','Eiche':'Kraft','Stechpalme':'Würde','Hasel':'Weisheit','Weinrebe':'Reife','Efeu':'Beständigkeit','Schilfrohr':'Wort & Wind','Holunder':'Wandeln'};
    return {kind:'tree', id:'tree', label:name, desc:desc[name]||''};
  }
  function ichingFromDate(d){
    const start=new Date(d.getFullYear(),0,0); const day=Math.floor((d-start)/86400000); const idx=(day+d.getFullYear())%64||1;
    const names={1:'Das Schöpferische',2:'Das Empfangende',3:'Anfangsschwierigkeit',4:'Jugendtorheit',11:'Frieden',12:'Stockung',24:'Wiederkehr',61:'Innere Wahrheit'};
    return {kind:'hex', id:idx, label:'I Ging '+idx, desc:names[idx]||'Bewegung im Wandel'};
  }

  function ensureBadgeRow(){
    let row=document.getElementById('birthBadges');
    if(!row){
      row=document.createElement('div'); row.id='birthBadges'; row.className='badge-row'; row.style.display='none';
      const hero=document.querySelector('.hero'); hero && hero.parentNode.insertBefore(row, hero);
    }
    return row;
  }
  function renderBirthBadges(dateStr){
    const d=parseBirthDate(dateStr); const row=ensureBadgeRow();
    if(!d){ row.style.display='none'; row.innerHTML=''; return; }
    row.style.display='flex'; row.innerHTML='';
    const items=[zodiacFromDate(d), chineseFromYear(d.getFullYear()), lifePathFromDate(d), celticTree(d), ichingFromDate(d)];
    items.forEach(it=>{
      const el=document.createElement('span'); el.className='badge';
      if(it.kind==='zodiac'){
        el.appendChild(inlineGlyph(zmapPromise,'glyph-'+it.id));
      } else if(it.kind==='cn'){
        el.appendChild(inlineGlyph(cmapPromise,'cn-'+it.id));
      } else if(it.kind==='hex'){
        el.appendChild(tinyHex(Number(it.id)||1));
      } else {
        const dot=document.createElement('span'); dot.textContent='•'; dot.style.marginRight='6px'; dot.style.opacity='.7'; el.appendChild(dot);
      }
      el.appendChild(document.createTextNode(it.label));
      const desc=document.createElement('span'); desc.className='desc'; desc.textContent=' – '+it.desc; el.appendChild(desc);
      row.appendChild(el);
    });
  }
  const bd=document.getElementById('birthDate'); if(bd){ bd.addEventListener('input', e=>renderBirthBadges(e.target.value)); }

})();