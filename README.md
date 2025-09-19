# Main Service (Option C)

**Ziel:** Moderner API-Service (Python 3.12) ohne lokale Swiss-Ephemeris-Dependency.
Optional ruft er einen separaten SWE-Worker (Python 3.11) auf.

## Deploy (Railway/Nixpacks)

1. Dieses Verzeichnis als neues Railway-Projekt deployen.
2. `requirements.txt` enthält **kein** pyswisseph – Build läuft mit Python 3.12.
3. Env-Variablen setzen (Project → Variables):
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL` (optional, Default gpt-4o-mini)
   - `CORS_ALLOW_ORIGINS` (optional)
   - `SWE_URL` (optional; erst setzen, wenn der Worker live ist)
   - `HOUSE_SYSTEM` (optional, Default P)
4. Start-Command: `uvicorn main:app --host 0.0.0.0 --port $PORT` (über `Procfile` gesetzt)

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
