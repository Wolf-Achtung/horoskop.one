
export async function fetchReading(payload: any) {
  const body = { ...payload };
  if (body.mode && !body.tone) body.tone = body.mode; // compatibility
  const endpoint = 'https://horoskopone-production.up.railway.app/reading';
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const res2 = await fetch('https://horoskopone-production.up.railway.app/readings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });
    if (!res2.ok) {
      let msg = 'HTTP ' + res.status;
      try { const ej = await res.json(); if (ej?.detail) msg += ' ' + JSON.stringify(ej.detail); } catch {}
      throw new Error(msg);
    }
    return await res2.json();
  }
  return await res.json();
}
