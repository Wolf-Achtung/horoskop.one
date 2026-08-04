# Main Service

**Ziel:** API-Service (Python 3.11, siehe `Dockerfile`) mit gebündeltem
`pyswisseph` — Aszendent/Häuser werden direkt in `main.py` berechnet
(`swe_compute()`), es ist **kein** separater Aufruf nötig.

## Deployment & DNS

**Produktion läuft über Railway.** Der Code ist genau dafür gebaut —
`src/readingApi.ts` nutzt `API_BASE = ''` (relative Aufrufe) und `main.py`
mountet das gebaute Frontend (`dist/`) unter `/`. Frontend und API müssen
deshalb dieselbe Origin haben; eine Aufteilung Frontend/API auf zwei Hosts
funktioniert ohne zusätzlichen Proxy nicht.

DNS-Stand (Registrar/Zone: united-domains):

| Hostname | Ziel | Status |
|---|---|---|
| `www.horoskop.one` | CNAME → `6ko1my9t.up.railway.app` | ✅ live, Zertifikat von Railway |
| `horoskop.one` (Apex) | A → `75.2.60.5` (Netlify) | ❌ liefert 404, Migration offen |

**Offener Schritt — Apex reparieren.** united-domains erlaubt am Apex
weder CNAME noch ALIAS ("CNAME nur für Subdomains"), Railway vergibt aber
nur ein CNAME-Ziel und keine feste IP. Zwei gangbare Wege:

1. **united-domains-Weiterleitung** (einfachster Weg): im Portal eine
   Weiterleitung `horoskop.one` → `https://www.horoskop.one` (301)
   einrichten. Kein neuer DNS-Record nötig.
2. **DNS-Umzug zu Cloudflare** (nachhaltiger Weg): Nameserver wechseln,
   dann per CNAME-Flattening den Apex direkt auf Railway zeigen lassen.
   Domain bleibt bei united-domains registriert. SPF-TXT-Record
   (`v=spf1 include:_smtp.udag.de ~all`) mit umziehen, sonst bricht
   E-Mail-Authentifizierung.

Danach die Netlify-GitHub-Integration entfernen (Netlify hat dann keine
Funktion mehr). Die Security-Header setzt die Middleware in `main.py`.

Hinweis: Ein früherer separater Ephemeris-Worker (`swe_worker/`) wurde aus
dem Repo entfernt — `main.py` bündelt `pyswisseph` direkt und hat den
Worker nie aufgerufen. Falls in Railway noch eine zweite Instanz davon
läuft, kann sie ersatzlos gestoppt werden (im Dashboard prüfen).

## Deploy (Railway/Docker)

1. Dieses Verzeichnis als Railway-Projekt deployen (baut über `Dockerfile`).
2. Env-Variablen setzen (Project → Variables):
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL` (optional, Default `gpt-5-mini`)
   - `CORS_ALLOW_ORIGINS` (optional, komma-separierte feste Origin-Liste)
   - `HOUSE_SYSTEM` (optional, Default P)
3. Start-Command: `uvicorn main:app --host 0.0.0.0 --port $PORT` (über `Procfile` gesetzt)

**Healthcheck:** `GET /health`

**Haupt-Route:** `POST /reading` mit Body:
```json
{
  "birthDate": "12.08.1980",
  "birthPlace": "Berlin",
  "birthTime": "14:30",
  "approxDaypart": null,
  "period": "day",
  "tone": "mystic_deep",
  "seed": 42,
  "mixer": {"mut": 30, "kraft": 70}
}
```
