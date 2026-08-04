# Main Service

**Ziel:** API-Service (Python 3.11, siehe `Dockerfile`) mit gebündeltem
`pyswisseph` — Aszendent/Häuser werden direkt in `main.py` berechnet
(`swe_compute()`), es ist **kein** separater Aufruf nötig.

## Deployment & DNS — aktueller Stand

> **Achtung:** Die Domain ist derzeit auf zwei Plattformen aufgeteilt.
> Eine frühere Version dieser README behauptete, Railway sei die einzige
> Produktionsplattform und Netlify nur Preview. **Das war falsch.**

Tatsächlicher DNS-Stand:

| Hostname | Ziel | Plattform |
|---|---|---|
| `horoskop.one` (Apex) | A → `75.2.60.5` | Netlify (Apex-Load-Balancer) |
| `www.horoskop.one` | CNAME → `horoskopone-production-4739.up.railway.app` | Railway |

Daraus folgen zwei bekannte Fehlerbilder:

- **Apex liefert Netlifys 404.** Netlify publiziert aus dem **Repo-Root**
  (deshalb war auch `_headers` dort wirksam). Seit die alten Root-HTML-
  Dateien entfernt wurden, gibt es dort kein `index.html` mehr.
- **www hat ein nicht passendes Zertifikat**
  (`ERR_CERT_COMMON_NAME_INVALID`): `www.horoskop.one` zeigt per CNAME auf
  Railway, ist dort aber nicht als Custom Domain registriert — Railway
  liefert daher sein `*.up.railway.app`-Zertifikat aus.

**Zielzustand: alles über Railway.** Der Code ist genau dafür gebaut —
`src/readingApi.ts` nutzt `API_BASE = ''` (relative Aufrufe) und `main.py`
mountet das gebaute Frontend (`dist/`) unter `/`. Frontend und API müssen
deshalb dieselbe Origin haben; eine Aufteilung Frontend/API auf zwei Hosts
funktioniert ohne zusätzlichen Proxy nicht.

Migrationsschritte (manuell, außerhalb des Repos):

1. In Railway → Settings → Networking **beide** Domains als Custom Domain
   anlegen: `horoskop.one` und `www.horoskop.one`. Railway stellt dann
   passende Zertifikate aus.
2. Beim Registrar den Apex-A-Record `75.2.60.5` (Netlify) durch das von
   Railway genannte Ziel ersetzen.
3. Netlify-Integration entfernen. Danach ist `_headers` endgültig
   wirkungslos — die Security-Header setzt die Middleware in `main.py`.

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
