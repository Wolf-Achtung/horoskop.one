// enhancements-v15: stronger star overlay + zodiac chips + birth badges + hero inline switch
(function(){
  // 0) Switch hero to inline wheel if present
  const heroImg = document.querySelector('.hero img');
  if(heroImg){ heroImg.src = 'assets/hero-wheel-inline.svg'; }

  // 1) Stronger star overlay (second canvas) + more parallax
  const holder = document.body;
  const cvs = document.createElement('canvas'); cvs.id='starOverlay';
  Object.assign(cvs.style, {position:'fixed', inset:'0', zIndex:'0', pointerEvents:'none'});
  holder.appendChild(cvs);
  const ctx = cvs.getContext('2d');
  const DPR = Math.min(2, window.devicePixelRatio||1);
  let W=0,H=0, scrollY=0, mouseX=0, mouseY=0;
  function resize(){ W=cvs.width=innerWidth*DPR; H=cvs.height=innerHeight*DPR; cvs.style.transform=`scale(${1/DPR})`; cvs.style.transformOrigin='0 0';}
  addEventListener('resize', resize, {passive:true}); resize();
  addEventListener('scroll', ()=>{scrollY=window.scrollY||0;}, {passive:true});
  addEventListener('mousemove', (e)=>{ mouseX=(e.clientX/innerWidth-0.5); mouseY=(e.clientY/innerHeight-0.5); }, {passive:true});
  const stars = Array.from({length:200},()=>({x:Math.random(),y:Math.random(),r:0.8+Math.random()*1.6,p:Math.random()*6.28,d:1+Math.random()}));
  (function draw(t){
    ctx.clearRect(0,0,W,H);
    ctx.globalCompositeOperation='lighter';
    const parY = (scrollY*0.12) * DPR;
    const parX = (scrollY*0.05) * DPR;
    const tiltX = mouseX*10*DPR, tiltY = mouseY*8*DPR;
    for(const s of stars){
      const tw = (Math.sin(t*0.002+s.p)*0.5+0.5)*1.3+0.4;
      const driftX = Math.sin(t*0.0001+s.p)*s.d*16;
      const driftY = Math.cos(t*0.00009+s.p)*s.d*12;
      const x=s.x*W + driftX + parX*(0.3+s.d*0.2)+tiltX;
      const y=s.y*H + driftY + parY*(0.35+s.d*0.25)+tiltY;
      const rad=s.r*DPR*(1.0+tw);
      const g=ctx.createRadialGradient(x,y,0,x,y,rad);
      g.addColorStop(0,'rgba(250,255,255,1)'); g.addColorStop(.5,'rgba(190,220,255,.6)'); g.addColorStop(1,'rgba(0,0,0,0)');
      ctx.fillStyle=g; ctx.beginPath(); ctx.arc(x,y,rad,0,Math.PI*2); ctx.fill();
    }
    ctx.globalCompositeOperation='source-over';
    requestAnimationFrame(draw);
  })(performance.now());

  // 2) Load zodiac sprite and inline into chips
  let _map = null;
  async function loadSprite(){
    if(_map) return _map;
    const txt = await fetch('assets/zodiac-glyphs.svg').then(r=>r.text()).catch(()=>null);
    if(!txt){ _map={}; return _map; }
    const doc = new DOMParser().parseFromString(txt,'image/svg+xml');
    _map={};
    doc.querySelectorAll('symbol[id^="glyph-"]').forEach(sym=>{ _map[sym.id.replace('glyph-','')] = sym.innerHTML; });
    return _map;
  }
  function glyphFor(text){
    const t=(text||'').toLowerCase();
    if(t.includes('widder')) return 'aries';
    if(t.includes('stier')) return 'taurus';
    if(t.includes('zwilling')) return 'gemini';
    if(t.includes('krebs')) return 'cancer';
    if(t.includes('löwe')||t.includes('loewe')) return 'leo';
    if(t.includes('jungfrau')) return 'virgo';
    if(t.includes('waage')) return 'libra';
    if(t.includes('skorpion')) return 'scorpio';
    if(t.includes('schütze')||t.includes('schuetze')) return 'sagittarius';
    if(t.includes('steinbock')) return 'capricorn';
    if(t.includes('wassermann')) return 'aquarius';
    if(t.includes('fische')) return 'pisces';
    return null;
  }
  function shortLabel(text){
    const m=(text||'').match(/(widder|stier|zwillinge?|krebs|l[ö|oe]we|jungfrau|waage|skorpion|sch[ü|ue]tze|steinbock|wassermann|fische)/i);
    return m? m[0].replace('oe','ö').replace('ue','ü') : text;
  }
  function upgradeChips(root){
    (root||document).querySelectorAll('.chip').forEach(ch=>{
      if(ch.dataset.glyphdone) return;
      const id = glyphFor(ch.textContent||'');
      if(id){
        const lab = shortLabel(ch.textContent||'');
        const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
        svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('width','14'); svg.setAttribute('height','14');
        svg.style.opacity='.9'; svg.style.marginRight='6px'; svg.style.verticalAlign='-2px';
        loadSprite().then(map=>{ svg.innerHTML = map[id]||''; });
        ch.textContent=''; ch.appendChild(svg); ch.appendChild(document.createTextNode(lab));
        ch.dataset.glyphdone="1";
      }
    });
  }
  const mo=new MutationObserver(muts=>muts.forEach(m=>upgradeChips(m.target)));
  mo.observe(document.documentElement,{subtree:true,childList:true});
  if(document.readyState!=='loading') upgradeChips(document.body);
  else document.addEventListener('DOMContentLoaded', ()=>upgradeChips(document.body));

  // 3) Birth badges under hero when date is entered
  function parseBirthDate(str){ const m=(str||'').match(/(\d{1,2})\.(\d{1,2})\.(\d{4})/); if(!m) return null; const d=new Date(+m[3],+m[2]-1,+m[1]); return isNaN(d)?null:d; }
  function zodiacFromDate(d){
    const m=d.getMonth()+1, day=d.getDate();
    const edges=[['capricorn',1,19],['aquarius',2,18],['pisces',3,20],['aries',4,19],['taurus',5,20],['gemini',6,20],['cancer',7,22],['leo',8,22],['virgo',9,22],['libra',10,22],['scorpio',11,21],['sagittarius',12,21],['capricorn',12,31]];
    let name='capricorn'; for(const [n,mm,dd] of edges){ if((m<mm)||(m===mm&&day<=dd)){ name=n; break; } }
    const labels={aries:'Widder',taurus:'Stier',gemini:'Zwillinge',cancer:'Krebs',leo:'Löwe',virgo:'Jungfrau',libra:'Waage',scorpio:'Skorpion',sagittarius:'Schütze',capricorn:'Steinbock',aquarius:'Wassermann',pisces:'Fische'};
    const texts={aries:'Pioniergeist und Aufbruch.', taurus:'Beständigkeit und Genuss.', gemini:'Neugier und Austausch.', cancer:'Zuwendung und Schutz.', leo:'Ausstrahlung und Herz.', virgo:'Präzision und Dienst.', libra:'Harmonie und Maß.', scorpio:'Tiefe und Wandlung.', sagittarius:'Weite und Sinn.', capricorn:'Disziplin und Ziel.', aquarius:'Freiheit und Ideen.', pisces:'Einfühlung und Träume.'};
    return {id:name,label:labels[name],desc:texts[name]};
  }
  function chineseFromYear(y){
    const animals=['Ratte','Büffel','Tiger','Hase','Drache','Schlange','Pferd','Ziege','Affe','Hahn','Hund','Schwein'];
    const base=1900; const idx=((y-base)%12+12)%12;
    const texts={'Ratte':'gewandt, wachsam','Büffel':'ruhig, verlässlich','Tiger':'mutig, impulsiv','Hase':'feinfühlig, verbindend','Drache':'kraftvoll, visionär','Schlange':'intuitiv, still','Pferd':'lebendig, unabhängig','Ziege':'sanft, ästhetisch','Affe':'pfiffig, erfinderisch','Hahn':'klar, direkt','Hund':'loyal, schützend','Schwein':'offen, großzügig'};
    return {id:'cn', label:animals[idx], desc:texts[animals[idx]]};
  }
  function lifePathFromDate(d){
    const s=''+d.getFullYear()+String(d.getMonth()+1).padStart(2,'0')+String(d.getDate()).padStart(2,'0');
    let sum=s.split('').reduce((a,b)=>a+ +b,0), master=[11,22,33];
    while(sum>9 && !master.includes(sum)){ sum=String(sum).split('').reduce((a,b)=>a+ +b,0); }
    const desc={1:'Initiative',2:'Team & Takt',3:'Ausdruck',4:'Struktur',5:'Wandel',6:'Fürsorge',7:'Tiefe',8:'Wirksamkeit',9:'Weite',11:'Inspiration',22:'Baukunst',33:'Herzführung'};
    return {id:'num', label:'Lebenszahl '+sum, desc:desc[sum]||''};
  }
  function celticTree(d){
    const ranges=[['Birke',12,24,1,20],['Eberesche',1,21,2,17],['Esche',2,18,3,17],['Erle',3,18,4,14],['Weide',4,15,5,12],['Weißdorn',5,13,6,9],['Eiche',6,10,7,7],['Stechpalme',7,8,8,4],['Hasel',8,5,9,1],['Weinrebe',9,2,9,29],['Efeu',9,30,10,27],['Schilfrohr',10,28,11,24],['Holunder',11,25,12,23]];
    const y=d.getFullYear(); const md=(m,dd)=>new Date(y,m-1,dd); let name='Birke';
    for(const [n,m1,d1,m2,d2] of ranges){ const s=md(m1,d1), e=md(m2,d2); const inside=s<=e ? (d>=s&&d<=e) : (d>=s||d<=e); if(inside){ name=n; break; } }
    const desc={'Birke':'Neuanfang','Eberesche':'Inspiration','Esche':'Wandlung','Erle':'Mut','Weide':'Gefühl','Weißdorn':'Grenze','Eiche':'Kraft','Stechpalme':'Würde','Hasel':'Weisheit','Weinrebe':'Reife','Efeu':'Beständigkeit','Schilfrohr':'Wort & Wind','Holunder':'Wandeln'};
    return {id:'tree', label:name, desc:desc[name]||''};
  }
  function ichingFromDate(d){
    const start=new Date(d.getFullYear(),0,0); const day=Math.floor((d-start)/86400000); const idx=(day+d.getFullYear())%64||1;
    const names={1:'Das Schöpferische',2:'Das Empfangende',3:'Anfangsschwierigkeit',4:'Jugendtorheit',11:'Frieden',12:'Stockung',24:'Wiederkehr',61:'Innere Wahrheit'};
    return {id:'hex', label:'I Ging '+idx, desc:names[idx]||'Bewegung im Wandel'};
  }
  function inlineZodiac(id){
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'); svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('width','14'); svg.setAttribute('height','14');
    svg.style.opacity='.9'; svg.style.verticalAlign='-2px'; svg.style.marginRight='6px';
    loadSprite().then(map=>{ svg.innerHTML = map[id]||''; });
    return svg;
  }
  function ensureBadgeRow(){
    let row=document.getElementById('birthBadges'); 
    if(!row){ row=document.createElement('div'); row.id='birthBadges'; row.className='badge-row'; row.style.display='none'; const hero=document.querySelector('.hero'); hero && hero.parentNode.insertBefore(row, hero); }
    return row;
  }
  function renderBirthBadges(dateStr){
    const d=(function(str){ const m=(str||'').match(/(\d{1,2})\.(\d{1,2})\.(\d{4})/); if(!m) return null; const dt=new Date(+m[3],+m[2]-1,+m[1]); return isNaN(dt)?null:dt; })(dateStr);
    const row=ensureBadgeRow();
    if(!d){ row.style.display='none'; row.innerHTML=''; return; }
    row.style.display='flex'; row.innerHTML='';
    const items=[zodiacFromDate(d), chineseFromYear(d.getFullYear()), lifePathFromDate(d), celticTree(d), ichingFromDate(d)];
    items.forEach(it=>{
      const el=document.createElement('span'); el.className='badge';
      if(['aries','taurus','gemini','cancer','leo','virgo','libra','scorpio','sagittarius','capricorn','aquarius','pisces'].includes(it.id)){
        el.appendChild(inlineZodiac(it.id));
      } else {
        const dot=document.createElement('span'); dot.textContent='•'; dot.style.marginRight='6px'; dot.style.opacity='.7'; el.appendChild(dot);
      }
      el.appendChild(document.createTextNode(it.label));
      const desc=document.createElement('span'); desc.className='desc'; desc.textContent=' – '+it.desc; el.appendChild(desc);
      row.appendChild(el);
    });
  }
  // attach to input if present
  const bd=document.getElementById('birthDate');
  if(bd){ bd.addEventListener('input', e=>renderBirthBadges(e.target.value)); }
})();