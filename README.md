# Main Service

**Ziel:** API-Service (Python 3.11, siehe `Dockerfile`) mit gebündeltem
`pyswisseph` — Aszendent/Häuser werden direkt in `main.py` berechnet
(`swe_compute()`), es ist **kein** separater Aufruf nötig.

**Produktionsplattform:** Railway (Docker-Build via `Dockerfile`). Dieses
Repo ist zusätzlich an eine Netlify-Integration angebunden, die
PR-Deploy-Previews erzeugt — das ist ein reines Vorschau-Feature ohne
Bezug zur Produktion (kein `netlify.toml`/`_redirects` vorhanden) und kann
in den Netlify-Projekteinstellungen entfernt werden, falls nicht mehr
gebraucht.

`swe_worker/` ist ein historischer, separat deploybarer Ephemeris-Worker
(Python 3.11 + pyswisseph), den `main.py` aktuell **nicht** aufruft (keine
`SWE_URL`-Nutzung im Code). Falls davon noch eine zweite Railway-Instanz
läuft, kann sie ohne Auswirkung auf den Hauptservice gestoppt werden.

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
