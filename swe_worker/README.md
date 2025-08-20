# SWE Worker (Option C)

Python 3.11 + pyswisseph. Liefert Asc/MC, Häuserspitzen, Sonnen-/Mondhaus.

## Deploy (Railway/Nixpacks)
1. Dieses Verzeichnis als **zweites** Railway-Projekt deployen.
2. `runtime.txt` (3.11) sorgt für kompatible Python-Version.
3. `requirements.txt` installiert `pyswisseph==2.10.3.2`.
4. Start-Command per `Procfile` gesetzt: `uvicorn swe_worker:app ...`
5. Optional: `CORS_ALLOW_ORIGINS` setzen.

**Healthcheck:** `GET /health`  
**Endpoint:** `POST /swe` – Beispiel:
```bash
curl -X POST "$SWE_URL"       -H "Content-Type: application/json"       -d '{
    "birthDate":"1980-08-12",
    "birthTime":"14:30",
    "lat":52.52,
    "lon":13.405,
    "tzname":"Europe/Berlin",
    "houseSystem":"P"
  }'
```
Response (gekürzt):
```json
{
  "houseSystem":"P",
  "ascendant":{"deg":123.4,"sign":"Löwe"},
  "mc":{"deg":210.1,"sign":"Skorpion"},
  "cusps":[... 12 Werte ...],
  "sunHouse":9,
  "moonHouse":3
}
```
