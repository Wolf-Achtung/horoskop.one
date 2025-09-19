let nextAllowed=0; let inflight=null; const sleep=(ms)=>new Promise(r=>setTimeout(r,ms));
export function attachAutocomplete({input,menu,onPick}){
  let debounceTimer=null; let lastQuery='';
  const close=()=>{menu.classList.remove('open'); menu.innerHTML='';};
  const open=()=>menu.classList.add('open');
  async function query(q){
    const now=Date.now(); if(now<nextAllowed) await sleep(nextAllowed-now); nextAllowed=Date.now()+1100;
    if(inflight) inflight.abort(); inflight=new AbortController();
    const url=new URL('https://nominatim.openstreetmap.org/search');
    url.searchParams.set('format','jsonv2'); url.searchParams.set('q',q); url.searchParams.set('addressdetails','1'); url.searchParams.set('limit','5');
    const res=await fetch(url.toString(),{headers:{'Accept-Language':navigator.language||'de'}, signal: inflight.signal});
    if(!res.ok) throw new Error('Geocoding HTTP '+res.status);
    const data=await res.json();
    return (data||[]).map(d=>({label:d.display_name,lat:Number(d.lat),lon:Number(d.lon)}));
  }
  function render(items){
    menu.innerHTML=''; if(!items.length){close(); return;} open();
    for(const it of items){ const div=document.createElement('div'); div.className='autocomplete-item'; div.setAttribute('role','option'); div.textContent=it.label; div.addEventListener('click',()=>{onPick(it); close();}); menu.appendChild(div); }
    const foot=document.createElement('div'); foot.className='autocomplete-item autocomplete-muted'; foot.textContent='Quelle: OpenStreetMap/Nominatim – 1 req/s'; menu.appendChild(foot);
  }
  input.addEventListener('input', ()=>{
    const q=input.value.trim(); if(q===lastQuery) return; lastQuery=q;
    if(debounceTimer) clearTimeout(debounceTimer); if(!q){close(); return;}
    debounceTimer=setTimeout(async()=>{ try{ render(await query(q)); } catch(e){ console.warn(e); } }, 400);
  });
  input.addEventListener('blur', ()=>setTimeout(close,200));
}
