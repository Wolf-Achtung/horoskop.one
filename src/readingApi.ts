const API_BASE='https://horoskopone-production.up.railway.app';

export async function fetchReading(payload){
  const body={...payload}; if(body.mode && !body.tone) body.tone=body.mode;
  const res=await fetch(API_BASE+'/reading',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!res.ok){
    const res2=await fetch(API_BASE+'/readings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!res2.ok){ let msg='HTTP '+res2.status; try{ const ej=await res2.json(); if(ej?.detail) msg+=' '+JSON.stringify(ej.detail);}catch{}; throw new Error(msg); }
    return await res2.json();
  }
  return await res.json();
}

export async function fetchReadingTypes(){
  const res=await fetch(API_BASE+'/reading-types');
  if(!res.ok) return [];
  return await res.json();
}
