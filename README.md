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

**Apex-Lösung: Netlify als Redirect-Dienst.** united-domains erlaubt am
Apex weder CNAME noch ALIAS, und das Portal-Formular für neue Records wie
auch die Weiterleitungs-Funktion speichern derzeit fehlerhaft. Deshalb
übernimmt Netlify (das den Apex ohnehin per A-Record bedient) die
Umleitung: Die Datei `_redirects` im Repo-Root leitet alle Apex-Anfragen
per 301 auf `https://www.horoskop.one` weiter, Pfad inklusive.

**Wichtig deshalb: Die Netlify-GitHub-Integration muss verbunden
bleiben** — sie ist jetzt der Redirect-Dienst für den Apex. Erst bei
einem späteren DNS-Umzug (z. B. zu Cloudflare mit CNAME-Flattening, etwa
im Zuge einer neuen Produkt-Domain) kann Netlify entfallen. Bei einem
solchen Umzug den SPF-TXT-Record (`v=spf1 include:_smtp.udag.de ~all`)
mitnehmen, sonst bricht die E-Mail-Authentifizierung.

Die Security-Header setzt die Middleware in `main.py`.

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
