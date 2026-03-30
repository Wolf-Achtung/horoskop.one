// Use relative URLs when served from the same origin (Railway serves both API + frontend)
const API_BASE = '';

export async function fetchReading(payload: Record<string, unknown>) {
  const body = { ...payload };
  if (body.mode && !body.tone) body.tone = body.mode;

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 90_000); // 90s timeout

  try {
    const res = await fetch(API_BASE + '/reading', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });

    if (!res.ok) {
      // Try legacy endpoint as fallback
      const res2 = await fetch(API_BASE + '/readings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      if (!res2.ok) {
        let msg = 'HTTP ' + res2.status;
        try {
          const ej = await res2.json();
          if (ej?.detail) msg += ' ' + JSON.stringify(ej.detail);
        } catch {}
        throw new Error(msg);
      }
      return await res2.json();
    }

    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchReadingTypes() {
  const res = await fetch(API_BASE + '/reading-types');
  if (!res.ok) return [];
  return await res.json();
}
