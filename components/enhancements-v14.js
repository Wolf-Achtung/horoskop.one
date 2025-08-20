// enhancements-v14: zodiac glyph chips + hero parallax
(function(){
  function glyphFor(text){
    const t = (text||'').toLowerCase();
    if(t.includes('widder')) return 'aries';
    if(t.includes('stier')) return 'taurus';
    if(t.includes('zwilling')) return 'gemini';
    if(t.includes('krebs')) return 'cancer';
    if(t.includes('löwe') || t.includes('loewe')) return 'leo';
    if(t.includes('jungfrau')) return 'virgo';
    if(t.includes('waage')) return 'libra';
    if(t.includes('skorpion')) return 'scorpio';
    if(t.includes('schütze') || t.includes('schuetze')) return 'sagittarius';
    if(t.includes('steinbock')) return 'capricorn';
    if(t.includes('wassermann')) return 'aquarius';
    if(t.includes('fische')) return 'pisces';
    return null;
  }
  function shortLabel(text){
    const m = (text||'').match(/(widder|stier|zwillinge?|krebs|l[ö|oe]we|jungfrau|waage|skorpion|sch[ü|ue]tze|steinbock|wassermann|fische)/i);
    return m ? (m[0].replace('oe','ö').replace('ue','ü')) : text;
  }
  function upgradeChips(root){
    (root||document).querySelectorAll('.chip').forEach(ch=>{
      if(ch.dataset.upgraded) return;
      const w = ch.textContent.trim();
      const id = glyphFor(w);
      if(id){
        const label = shortLabel(w);
        ch.innerHTML = `<svg aria-hidden="true" style="width:14px;height:14px;opacity:.9;margin-right:6px;vertical-align:-2px"><use href="assets/zodiac-glyphs.svg#glyph-${id}"></use></svg><span>${label}</span>`;
        ch.dataset.upgraded = "1";
      }
    });
  }

  // Initial & dynamic upgrades
  const mo = new MutationObserver(muts => muts.forEach(m=> upgradeChips(m.target)));
  mo.observe(document.documentElement, {subtree:true, childList:true});

  if(document.readyState !== 'loading') upgradeChips(document.body);
  else document.addEventListener('DOMContentLoaded', ()=>upgradeChips(document.body));

  // Hero parallax wrapper (2–3px)
  function ensureHeroWrap(){
    const hero = document.querySelector('.hero');
    if(!hero) return;
    if(hero.querySelector('#heroWrap')) return;
    const img = hero.querySelector('img');
    if(!img) return;
    const wrap = document.createElement('div');
    wrap.id='heroWrap';
    wrap.className='hero-wrap';
    img.replaceWith(wrap);
    wrap.appendChild(img);
  }
  ensureHeroWrap();

  const style = document.createElement('style');
  style.textContent = `.hero-wrap{display:inline-block;will-change:transform}`;
  document.head.appendChild(style);

  const max = 3;
  function onScroll(){
    const wrap = document.getElementById('heroWrap');
    if(!wrap) return;
    const y = Math.max(0, window.scrollY || 0);
    const shift = Math.min(max, y*0.03);
    wrap.style.transform = `translateY(${shift}px)`;
  }
  window.addEventListener('scroll', onScroll, {passive:true});
  onScroll();
})();